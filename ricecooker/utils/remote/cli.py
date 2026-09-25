import argparse
import posixpath
import sys
from pathlib import Path

from ricecooker.exceptions import RemoteCliError
from ricecooker.exceptions import RemoteError
from ricecooker.utils.remote.config import resolve_profile
from ricecooker.utils.remote.driver import BOX_ENV
from ricecooker.utils.remote.driver import CHECK_BOX_ENV
from ricecooker.utils.remote.driver import default_venv_dir
from ricecooker.utils.remote.driver import filecache_dir
from ricecooker.utils.remote.driver import finish
from ricecooker.utils.remote.driver import kills_on_logout
from ricecooker.utils.remote.driver import logind_state
from ricecooker.utils.remote.driver import LOOSE_BOX_ENV
from ricecooker.utils.remote.driver import MISSING_TOOLS
from ricecooker.utils.remote.driver import preflight
from ricecooker.utils.remote.driver import REQUIRED_TOOLS
from ricecooker.utils.remote.driver import script_argv
from ricecooker.utils.remote.driver import uses_default_venv
from ricecooker.utils.remote.session import LIVE
from ricecooker.utils.remote.session import live_chefs
from ricecooker.utils.remote.session import NO_SESSION
from ricecooker.utils.remote.session import Session
from ricecooker.utils.remote.transport import remote_chef_dir
from ricecooker.utils.remote.transport import subprocess_runner
from ricecooker.utils.remote.transport import Transport

# sh -c script; $1: shared file cache. Prints "<entries> <KiB>".
# filelock < 3.21 leaves a .lock beside every entry.
CACHE_INFO = (
    '[ -d "$1" ] || { echo 0 0; exit; }; '
    'echo "$(find "$1" -type f ! -name "*.lock" | wc -l) $(du -sk "$1" | cut -f1)"'
)

# sh -c script. Exits 0 only if polkit lets this user enable their own linger;
# pkcheck's 2 needs authentication, which a non-interactive ssh can't give.
CAN_SELF_LINGER = (
    "exec pkcheck --action-id org.freedesktop.login1.set-self-linger --process $$"
)

# Reported name -> binary on the box's PATH.
# rsync is not in REQUIRED_TOOLS: preflight skips it, but sync runs the box's rsync.
DEPENDENCIES = {
    "ffmpeg": "ffmpeg",
    "poppler-utils": "pdftoppm",
    "pandoc": "pandoc",
    "single-file-cli": "single-file",
    "rsync": "rsync",
    **{tool: tool for tool in REQUIRED_TOOLS},
}

# sh -c script; $1: remote chef dir. -l: the login shell a plain ssh gives.
SHELL_IN_CHEF_DIR = 'cd "$1" && exec "${SHELL:-sh}" -l'


def _ssh(transport, *argv, ok=(0,)):
    result = transport.ssh(list(argv))
    if result.returncode not in ok:
        raise RemoteCliError(
            f"remote: {argv[0]} exited {result.returncode}\n{result.stderr}"
        )
    return result


def cache_info(transport, args) -> int:
    path = filecache_dir(transport.profile)
    # wc -l pads its count on macOS.
    entries, size = _ssh(transport, "sh", "-c", CACHE_INFO, "sh", path).stdout.split()
    print(f"path: {path}\nentries: {entries}\nsize: {size} KiB")
    return 0


def cache_clear(transport, args) -> int:
    profile = transport.profile
    path = filecache_dir(profile)
    running = live_chefs(transport)
    if running:
        raise RemoteCliError(
            f"remote: {', '.join(running)} running on {profile.ssh} under "
            f"{profile.remote_root}; not clearing the cache they share."
        )
    _ssh(transport, "rm", "-rf", path)
    print(f"cleared {path}")
    return 0


def sync(transport, args) -> int:
    profile = transport.profile
    # Also creates a missing remote_root, which rsync would not.
    preflight(transport)
    if Session(transport).status().state == LIVE:
        raise RemoteCliError(
            f"remote: {profile.name} is running on {profile.ssh}; "
            "not syncing under a live run."
        )
    transport.sync()
    print(f"synced to {profile.ssh}:{remote_chef_dir(profile)}")
    return 0


def pull(transport, args) -> int:
    path = posixpath.normpath(args.remote_path)
    if posixpath.isabs(path) or path.split("/")[0] == "..":
        raise RemoteCliError(
            f"remote: {args.remote_path} is outside the chef dir; "
            "pull takes a path relative to it."
        )
    # As typed: rsync copies a trailing-/ source's contents, not the dir.
    transport.pull(args.remote_path, args.dest)
    return 0


def shell(transport, args) -> int:
    command = ["sh", "-c", SHELL_IN_CHEF_DIR, "sh", remote_chef_dir(transport.profile)]
    return transport.ssh(command, tty=True).returncode


def attach(transport, args) -> int:
    profile = transport.profile
    session = Session(transport)
    if session.status().state == NO_SESSION:
        raise RemoteCliError(
            f"remote: no session for {profile.name} on {profile.ssh}; "
            "start a run with --remote."
        )
    return finish(session, session.attach())


def _report_logout_kill(transport) -> bool:
    """Report logind's kill at logout, if it applies; True if runs would die of it."""
    state = logind_state(transport)
    if not kills_on_logout(state):
        return False
    user = state["User"]
    if state.get("Linger"):
        print(f"KillUserProcesses: {user} lingers, so runs outlive logout.")
        return False
    if transport.ssh(["sh", "-c", CAN_SELF_LINGER]).returncode == 0:
        print(
            f"KillUserProcesses: --remote enables linger for {user} on its first run."
        )
        return False
    print(
        "KillUserProcesses: runs would die at logout; "
        f"run `sudo loginctl enable-linger {user}` on the box."
    )
    return True


def doctor(transport, args) -> int:
    profile = transport.profile
    # Not preflight: doctor reports, it never creates remote_root.
    script = f"{MISSING_TOOLS}; {CHECK_BOX_ENV}"
    result = _ssh(transport, "sh", "-c", script, "sh", *DEPENDENCIES.values())
    missing = set(result.stdout.split())
    for name, binary in DEPENDENCIES.items():
        print(f"{name}: {'missing' if binary in missing else 'ok'}")
    if LOOSE_BOX_ENV in missing:
        print(f"{BOX_ENV}: accessible to other users; chmod 600 it.")
    if uses_default_venv(profile, transport.chef_dir):
        print(
            f"{profile.name} has no pyproject.toml or requirements.txt; it runs in "
            f"{default_venv_dir(profile)} with released ricecooker."
        )
    runs_die = _report_logout_kill(transport)
    return 1 if missing or runs_die else 0


def build_parser() -> argparse.ArgumentParser:
    profile = argparse.ArgumentParser(add_help=False)
    profile.add_argument("--remote", metavar="NAME")
    parser = argparse.ArgumentParser(prog=f"{Path(sys.argv[0]).name} remote")
    commands = parser.add_subparsers(required=True)
    commands.add_parser("attach", parents=[profile]).set_defaults(func=attach)
    commands.add_parser("sync", parents=[profile]).set_defaults(func=sync)
    pull_parser = commands.add_parser("pull", parents=[profile])
    pull_parser.add_argument("remote_path")
    pull_parser.add_argument("dest", nargs="?", default=".")
    pull_parser.set_defaults(func=pull)
    commands.add_parser("shell", parents=[profile]).set_defaults(func=shell)
    commands.add_parser("doctor", parents=[profile]).set_defaults(func=doctor)
    cache = commands.add_parser("cache").add_subparsers(required=True)
    cache.add_parser("info", parents=[profile]).set_defaults(func=cache_info)
    cache.add_parser("clear", parents=[profile]).set_defaults(func=cache_clear)
    return parser


def run_remote_command(
    argv, chef_dir=None, runner=subprocess_runner, global_path=None, script=None
) -> int:
    args = build_parser().parse_args(argv)
    chef_dir = Path.cwd() if chef_dir is None else Path(chef_dir)
    try:
        if script is not None:
            # Refuses a script outside the chef dir, as --remote does.
            script_argv([script], chef_dir)
        profile = resolve_profile(args.remote, chef_dir, global_path)
        transport = Transport(profile, chef_dir, runner)
        return args.func(transport, args)
    except RemoteError as e:
        print(e, file=sys.stderr)
        return 1
