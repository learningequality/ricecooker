import argparse
import base64
import dataclasses
import hashlib
import os
import posixpath
import re
import sys
from pathlib import Path
from shlex import quote

import ricecooker
from ricecooker import __version__
from ricecooker.exceptions import InvalidUsageException
from ricecooker.exceptions import RemoteDriverError
from ricecooker.exceptions import RemoteError
from ricecooker.utils.remote.config import resolve_profile
from ricecooker.utils.remote.session import FINISHED
from ricecooker.utils.remote.session import LIVE
from ricecooker.utils.remote.session import live_chefs
from ricecooker.utils.remote.session import NOT_A_TTY
from ricecooker.utils.remote.session import Session
from ricecooker.utils.remote.transport import remote_chef_dir
from ricecooker.utils.remote.transport import subprocess_runner
from ricecooker.utils.remote.transport import Transport
from ricecooker.utils.remote.transport import VENV_DIR

# The box word-splits the forwarded names, so this is a safety gate.
ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

FILECACHE_DIR = ".ricecookerfilecache"
DEFAULT_VENV = ".default-venv"
SOURCE_DIR = ".ricecooker-src"
RELEASED_RICECOOKER = "ricecooker"
BOX_ENV = "$HOME/.config/ricecooker/remote-env"
LOOSE_BOX_ENV = "remote-env"
REQUIRED_TOOLS = ("uv", "tmux", "base64")

# sh -c script; args: binaries. Prints each one not on the box's PATH.
MISSING_TOOLS = 'for t; do command -v "$t" >/dev/null || echo "$t"; done'

# Prints remote-env if group or others have any access to it.
CHECK_BOX_ENV = (
    f'f="{BOX_ENV}"; if [ -f "$f" ]; then '
    f'case $(ls -ln "$f") in ?[r-][w-][x-]------*) ;; *) echo {LOOSE_BOX_ENV};; esac; fi'
)

# sh -c script; args: <shared file cache> <tools...>. Prints each tool the box
# lacks, and remote-env if it is too open.
# The mkdir -p also creates a missing remote_root, which rsync would not.
PREFLIGHT = f'd=$1; shift; {MISSING_TOOLS}; mkdir -p "$d" || exit; {CHECK_BOX_ENV}'

# sh -c script; args: <bookkeeping dir> <venv> <digest> <build> <names> <chef argv...>.
# Box-owned env first, then the session env (client --env/--env-pass/token) over it.
# Session env values are base64: tmux 3.4 stores a `$` in a command argument as `\$`.
# The trailing x keeps a value's trailing newlines from $(...).
# venv.log survives only this run's failed build; the driver prints its tail.
# chef-started exists only once this run's chef starts.
# The { ...; echo $? > venv.rc; } | tee form: POSIX sh has no pipefail.
RUN_CHEF = (
    'd=$1 venv=$2 digest=$3 build=$4 names=$5; shift 5; mkdir -p "$d"; '
    'rm -f "$d/venv.log" "$d/chef-started"; '
    f'f="{BOX_ENV}"; set -a; [ -f "$f" ] && . "$f"; set +a; '
    'for k in $names; do v=$(tmux show-environment "$k") && '
    'v=$(printf %s "${v#*=}" | base64 -d && echo x) && export "$k=${v%x}"; done; '
    'if [ "$(cat "$venv/.ricecooker-digest" 2>/dev/null)" != "$digest" ]; then '
    '{ sh -c "$build" 2>&1; echo $? > "$d/venv.rc"; } | tee "$d/venv.log"; '
    'read rc < "$d/venv.rc"; [ "$rc" = 0 ] || exit "$rc"; '
    'echo "$digest" > "$venv/.ricecooker-digest"; rm -f "$d/venv.log" "$d/venv.rc"; fi; '
    'touch "$d/chef-started"; exec "$venv/bin/python" "$@"'
)

# sh -c script; $1: remote chef dir, $2: chef-started. Prints the newest log
# written since this run's chef started. `*.err.log` holds only the errors of a run.
LATEST_LOG = (
    'cd "$1" && [ -f "$2" ] && ls -t logs/*.log "$2" 2>/dev/null | '
    'grep -v "\\.err\\.log$" | head -n 1 | grep -vxF "$2"'
)

# Client-only flags that take a value; the box resolves none of them.
VALUE_FLAGS = ("--token", "--env", "--env-pass")


@dataclasses.dataclass(frozen=True)
class Venv:
    path: str
    digest: str
    build: str


def env_name(value: str) -> str:
    if not ENV_NAME.fullmatch(value):
        raise argparse.ArgumentTypeError(
            f"invalid environment variable name: {value!r}"
        )
    return value


def env_pair(value: str) -> tuple:
    key, sep, val = value.partition("=")
    if not sep:
        raise argparse.ArgumentTypeError(f"expected KEY=VALUE, got {value!r}")
    return (env_name(key), val)


def client_flag(name: str):
    """The client-only flag `name` spells, or None. argparse accepts unambiguous
    abbreviations (`--tok`), so those must be recognized too."""
    flags = ("--remote", *VALUE_FLAGS)
    if name in flags:
        return name
    matches = [f for f in flags if len(name) > 2 and f.startswith(name)]
    return matches[0] if len(matches) == 1 else None


def chef_argv(argv: list) -> list:
    kept = argv[:1]
    rest = iter(argv[1:])
    for arg in rest:
        name, eq, _ = arg.partition("=")
        flag = client_flag(name)
        if flag in VALUE_FLAGS and not eq:
            next(rest, None)
        elif flag is None:
            kept.append(arg)
    return kept


def forwarded_env(token, env, env_pass) -> dict:
    forwarded = {} if token is None else {"STUDIO_TOKEN": token}
    forwarded.update(env)
    for key in env_pass:
        if key not in os.environ:
            raise InvalidUsageException(f"--env-pass {key}: {key} is not set")
        forwarded[key] = os.environ[key]
    return forwarded


def filecache_dir(profile) -> str:
    return posixpath.join(profile.remote_root, FILECACHE_DIR)


def default_venv_dir(profile) -> str:
    return posixpath.join(profile.remote_root, DEFAULT_VENV)


def uses_default_venv(profile, chef_dir) -> bool:
    manifests = ("pyproject.toml", "requirements.txt")
    has_manifest = any((Path(chef_dir) / m).exists() for m in manifests)
    return not (has_manifest or profile.ricecooker_source)


def preflight(transport) -> None:
    result = transport.ssh(
        ["sh", "-c", PREFLIGHT, "sh", filecache_dir(transport.profile), *REQUIRED_TOOLS]
    )
    if result.returncode:
        raise RemoteDriverError(
            f"remote: ssh {transport.profile.ssh} exited {result.returncode}\n"
            f"{result.stderr}"
        )
    missing = result.stdout.split()
    if LOOSE_BOX_ENV in missing:
        raise RemoteDriverError(
            f"remote: {BOX_ENV} on {transport.profile.ssh} is accessible to "
            "other users; chmod 600 it."
        )
    if missing:
        raise RemoteDriverError(
            f"remote: {transport.profile.ssh} lacks {', '.join(missing)}; "
            "install it on the box."
        )


def script_argv(argv, chef_dir) -> list:
    script = Path(argv[0]).resolve()
    try:
        relative = script.relative_to(Path(chef_dir).resolve())
    except ValueError:
        raise RemoteDriverError(
            f"remote: {argv[0]} is outside the chef dir {chef_dir}; "
            "only the chef dir is synced to the box."
        )
    return [relative.as_posix(), *argv[1:]]


def plan_venv(profile, chef_dir, source_dir=None) -> Venv:
    pyproject = Path(chef_dir) / "pyproject.toml"
    requirements = Path(chef_dir) / "requirements.txt"
    shared = uses_default_venv(profile, chef_dir)
    if shared:
        path = default_venv_dir(profile)
    else:
        path = posixpath.join(remote_chef_dir(profile), VENV_DIR)
    venv = quote(path)
    install = f"uv pip install --python {venv}/bin/python"
    manifests = []
    if pyproject.exists():
        build = "uv sync"
        manifests = [pyproject, pyproject.with_name("uv.lock")]
    elif requirements.exists():
        build = f"uv venv {venv} && {install} -r requirements.txt"
        manifests = [requirements]
    elif shared:
        build = f"uv venv {venv} && {install} {quote(RELEASED_RICECOOKER)}"
    else:
        build = f"uv venv {venv}"
    build = digested = f"rm -rf {venv} && {build}"
    if source_dir is not None:
        source = quote(posixpath.join(profile.remote_root, SOURCE_DIR))
        editable = f"{install} -e {source}"
        digested = f"{build} && {editable}"
        # The synced copy has no git metadata for setuptools-scm to version from.
        pin = f"SETUPTOOLS_SCM_PRETEND_VERSION_FOR_RICECOOKER={quote(__version__)}"
        build = f"{build} && {pin} {editable}"
        manifests.append(Path(source_dir) / "pyproject.toml")
    # Version left out: a new local commit must not rebuild the venv.
    digest = hashlib.sha256(digested.encode())
    for manifest in manifests:
        if manifest.exists():
            digest.update(manifest.read_bytes())
    return Venv(path, digest.hexdigest(), build)


def chef_command(session, venv, argv, env_names=()) -> list:
    return [
        "sh",
        "-c",
        RUN_CHEF,
        "sh",
        session.bookkeeping_dir,
        venv.path,
        venv.digest,
        venv.build,
        " ".join(env_names),
        *argv,
    ]


def sync_source(transport, source_dir) -> None:
    profile = dataclasses.replace(
        transport.profile, name=SOURCE_DIR, protect=[], exclude=["/.git"]
    )
    Transport(profile, source_dir, transport.runner).sync()


def ricecooker_checkout() -> Path:
    checkout = Path(ricecooker.__file__).resolve().parent.parent
    if not (checkout / "pyproject.toml").exists():
        raise RemoteDriverError(
            f'remote: ricecooker_source = "local" needs a source checkout; '
            f"{checkout} has no pyproject.toml."
        )
    return checkout


def _say(message) -> None:
    print("remote: " + message, file=sys.stderr)


def _reattach_hint(session) -> str:
    profile = session.transport.profile
    return (
        f"{profile.name} keeps running on {profile.ssh}. "
        "Re-run with the same --remote to reattach."
    )


def _refuse_shared_rewrite(transport, venv, source) -> None:
    """Refuse to rewrite what other chefs under remote_root run from.
    Only called while this chef isn't live, so every live chef is another."""
    profile = transport.profile
    shared_venv = uses_default_venv(profile, transport.chef_dir)
    if source is None and not shared_venv:
        return
    running = live_chefs(transport)
    if not running:
        return
    if source is not None:
        rewritten = posixpath.join(profile.remote_root, SOURCE_DIR)
    else:
        digest_file = posixpath.join(venv.path, ".ricecooker-digest")
        # 1: no venv built yet.
        current = transport.ssh(["cat", digest_file])
        if current.returncode == 0 and current.stdout.strip() == venv.digest:
            return
        rewritten = venv.path
    raise RemoteDriverError(
        f"remote: {', '.join(running)} running on {profile.ssh} from "
        f"{rewritten}; not rewriting it under them."
    )


def _start(session, argv, env) -> None:
    transport = session.transport
    profile = transport.profile
    source = None
    if profile.ricecooker_source == "local":
        source = ricecooker_checkout()
    venv = plan_venv(profile, transport.chef_dir, source)
    _refuse_shared_rewrite(transport, venv, source)
    transport.sync()
    if source is not None:
        sync_source(transport, source)
    env = {"RICECOOKER_FILECACHE": filecache_dir(profile), **env}
    encoded = {k: base64.b64encode(v.encode()).decode() for k, v in env.items()}
    session.create(chef_command(session, venv, argv, env), encoded)


def finish(session, code) -> int:
    if code == NOT_A_TTY:
        _say(_reattach_hint(session))
        return code
    if code:
        raise RemoteDriverError(f"remote: attach exited {code}")
    exit_code = session.exit_code()
    transport = session.transport
    started = posixpath.join(session.bookkeeping_dir, "chef-started")
    latest = transport.ssh(["sh", "-c", LATEST_LOG, "sh", session.chef_dir, started])
    chef_log = latest.stdout.strip()
    if chef_log:
        _say(f"chef log: {posixpath.join(session.chef_dir, chef_log)}")
    _say(f"session log: {session.log_path}")
    if exit_code is None:
        _say(f"detached; {_reattach_hint(session)}")
        return 0
    if exit_code:
        venv_log = posixpath.join(session.bookkeeping_dir, "venv.log")
        tail = transport.ssh(["tail", "-n", "20", venv_log])
        if tail.returncode == 0:
            _say(
                f"venv build failed; {session.name} kept for inspection. "
                "Last uv output:"
            )
            print(tail.stdout, file=sys.stderr, end="")
    return exit_code


def run_remotely(
    argv, env, remote=None, chef_dir=None, runner=subprocess_runner, global_path=None
) -> int:
    chef_dir = Path.cwd() if chef_dir is None else Path(chef_dir)
    try:
        profile = resolve_profile(remote, chef_dir, global_path)
        argv = script_argv(argv, chef_dir)
        transport = Transport(profile, chef_dir, runner)
        preflight(transport)
        session = Session(transport)
        status = session.status()
        if status.state == LIVE:
            _say(
                f"{profile.name} is already running "
                f"(since {status.started:%Y-%m-%d %H:%M}); attaching"
            )
        else:
            if status.state == FINISHED:
                code = status.exit_code
                ended = (
                    "ended without an exit code" if code is None else f"exited {code}"
                )
                _say(f"previous run of {profile.name} {ended}")
                session.kill()
            # Only here: a live chef must not be synced under.
            _start(session, argv, env)
        return finish(session, session.attach())
    except RemoteError as e:
        print(e, file=sys.stderr)
        return 1
