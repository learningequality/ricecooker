import base64
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from test_remote_session import make_session

import ricecooker
from ricecooker.exceptions import RemoteDriverError
from ricecooker.utils.remote import driver
from ricecooker.utils.remote.config import RemoteProfile
from ricecooker.utils.remote.config import resolve_profile
from ricecooker.utils.remote.driver import chef_command
from ricecooker.utils.remote.driver import plan_venv
from ricecooker.utils.remote.driver import preflight
from ricecooker.utils.remote.driver import REQUIRED_TOOLS
from ricecooker.utils.remote.driver import run_remotely
from ricecooker.utils.remote.driver import script_argv
from ricecooker.utils.remote.driver import sync_source
from ricecooker.utils.remote.session import LIVE
from ricecooker.utils.remote.session import NOT_A_TTY
from ricecooker.utils.remote.session import Session
from ricecooker.utils.remote.transport import RunResult
from ricecooker.utils.remote.transport import subprocess_runner
from ricecooker.utils.remote.transport import Transport

needs_sh = pytest.mark.skipif(os.name == "nt", reason="ssh shim needs sh")
needs_uv = pytest.mark.skipif(not shutil.which("uv"), reason="needs uv")

CHEF = """\
import hashlib, json, os, sys, time

seen = {k: os.environ.get(k) for k in ("BOX_ONLY", "ODD", "RICECOOKER_FILECACHE")}
seen["argv"] = sys.argv
seen["prefix"] = sys.prefix
token = os.environ.get("STUDIO_TOKEN")
seen["token_sha256"] = token and hashlib.sha256(token.encode()).hexdigest()
try:
    import fakerc
    seen["fakerc"] = fakerc.__file__
except ImportError:
    seen["fakerc"] = None
os.makedirs("chefdata", exist_ok=True)
with open("chefdata/seen.jsonl", "a") as f:
    f.write(json.dumps(seen) + "\\n")
print("chef-output", flush=True)
os.makedirs("logs", exist_ok=True)
open("logs/run.log", "w").close()
if "wait" in sys.argv[2:]:
    while not os.path.exists("go"):
        time.sleep(0.05)
sys.exit(int(sys.argv[1]) if len(sys.argv) > 1 else 0)
"""

PYPROJECT = (
    '[project]\nname = "chef"\nversion = "0"\n'
    'requires-python = ">=3.10"\ndependencies = []\n'
)


def write_global_config(path, box, ssh="box"):
    path.write_text(f'default = "box"\n\n[box]\nssh = "{ssh}"\nremote_root = "{box}"\n')
    return path


@pytest.fixture
def offline_uv(monkeypatch, tmp_path):
    monkeypatch.setenv("UV_OFFLINE", "1")
    monkeypatch.setenv("UV_PYTHON", sys.executable)
    monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path / "uv-cache"))
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


def make_profile(box, name="my-chef", **kwargs):
    return RemoteProfile(
        ssh="box", remote_root=str(box), name=name, protect=[], exclude=[], **kwargs
    )


def write_chef(laptop, manifest=None, text=""):
    (laptop / "chef.py").write_text(CHEF)
    if manifest:
        (laptop / manifest).write_text(text)


def fake_ricecooker(tmp_path) -> Path:
    """A stand-in for ricecooker that builds offline."""
    pkg = tmp_path / "fakerc"
    (pkg / "src" / "fakerc").mkdir(parents=True)
    (pkg / "src" / "fakerc" / "__init__.py").write_text("")
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "fakerc"\nversion = "0"\nrequires-python = ">=3.10"\n\n'
        '[build-system]\nrequires = ["uv_build"]\nbuild-backend = "uv_build"\n'
    )
    return pkg


def run_on_box(transport, venv, *args) -> RunResult:
    session = Session(transport)
    # In production tmux's -c sets the cwd.
    cd_and_run = 'cd "$1" && shift && exec "$@"'
    command = chef_command(session, venv, ["chef.py", *args])
    return transport.ssh(["sh", "-c", cd_and_run, "sh", session.chef_dir, *command])


def seen(chef_dir) -> list:
    path = Path(chef_dir) / "chefdata" / "seen.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()]


def seen_paths(chef_dir, key="prefix") -> list:
    return [Path(s[key]).resolve() for s in seen(chef_dir)]


def synced(box, laptop, name="my-chef", **kwargs):
    profile = make_profile(box, name, **kwargs)
    transport = Transport(profile, laptop)
    transport.sync()
    return profile, transport


def box_tools(box, monkeypatch, present):
    """Restrict the box's PATH to the ssh shim, sh, mkdir, ls and stubs for `present`."""
    tools = box.parent / "tools"
    tools.mkdir()
    for name in ("sh", "mkdir", "ls"):
        (tools / name).symlink_to(shutil.which(name))
    for name in present:
        stub = tools / name
        stub.write_text("#!/bin/sh\n")
        stub.chmod(0o755)
    shim_dir = os.environ["PATH"].split(os.pathsep)[0]
    monkeypatch.setenv("PATH", f"{shim_dir}{os.pathsep}{tools}")


def run_remotely_from(laptop, root, script=None, runner=subprocess_runner):
    config = write_global_config(laptop.parent / "remote.toml", root)
    argv = [str(script or laptop / "chef.py")]
    return run_remotely(argv, {}, chef_dir=laptop, runner=runner, global_path=config)


def test_unreachable_box_fails_with_ssh_stderr(laptop, capsys):
    ssh_error = "ssh: connect to host box port 22: Connection refused\n"

    def unreachable(argv, capture):
        return RunResult(255, stderr=ssh_error)

    assert run_remotely_from(laptop, "/srv", runner=unreachable) == 1
    err = capsys.readouterr().err
    assert err.startswith("remote:")
    assert ssh_error in err


@needs_sh
@pytest.mark.parametrize("missing", REQUIRED_TOOLS)
def test_missing_box_tool_fails_before_sync(box, laptop, monkeypatch, capsys, missing):
    box_tools(box, monkeypatch, set(REQUIRED_TOOLS) - {missing})
    assert run_remotely_from(laptop, box) == 1
    err = capsys.readouterr().err
    assert err.startswith("remote:")
    assert missing in err
    assert not (box / "laptop").exists()


@needs_sh
def test_preflight_creates_missing_remote_root(box, monkeypatch):
    box_tools(box, monkeypatch, REQUIRED_TOOLS)
    preflight(Transport(make_profile(box / "fresh" / "root")))
    assert (box / "fresh" / "root" / ".ricecookerfilecache").is_dir()


@needs_sh
@pytest.mark.parametrize("mode,refused", [(0o600, False), (0o640, True), (0o604, True)])
def test_preflight_refuses_box_env_file_open_to_others(
    box, monkeypatch, tmp_path, mode, refused
):
    box_tools(box, monkeypatch, REQUIRED_TOOLS)
    monkeypatch.setenv("HOME", str(tmp_path))
    env_file = tmp_path / ".config" / "ricecooker" / "remote-env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text("STUDIO_TOKEN=box-token\n")
    env_file.chmod(mode)
    if refused:
        with pytest.raises(RemoteDriverError, match="^remote: .*chmod 600"):
            preflight(Transport(make_profile(box)))
    else:
        preflight(Transport(make_profile(box)))


def test_script_outside_chef_dir_fails_before_contacting_box(tmp_path, laptop, capsys):
    calls = []

    def recorder(argv, capture):
        calls.append(argv)
        return RunResult(0)

    script = tmp_path / "elsewhere" / "chef.py"
    assert run_remotely_from(laptop, "/srv", script, runner=recorder) == 1
    assert capsys.readouterr().err.startswith("remote:")
    assert calls == []


def test_script_path_is_made_relative_to_chef_dir(laptop):
    argv = script_argv([str(laptop / "sub" / "chef.py"), "dryrun"], laptop)
    assert argv == ["sub/chef.py", "dryrun"]


def box_run(test):
    fixtures = pytest.mark.usefixtures("gnu_rsync", "offline_uv")
    return needs_sh(needs_uv(fixtures(test)))


@box_run
@pytest.mark.parametrize("name", ["my-chef", "it's a chef"])
def test_pyproject_chef_runs_in_uv_synced_venv(box, laptop, name):
    write_chef(laptop, "pyproject.toml", PYPROJECT)
    profile, transport = synced(box, laptop, name)
    assert run_on_box(transport, plan_venv(profile, laptop)).returncode == 0
    assert seen_paths(box / name) == [(box / name / ".venv").resolve()]


@box_run
def test_requirements_venv_rebuilt_only_when_manifest_changes(box, laptop):
    write_chef(laptop, "requirements.txt", "# none\n")
    profile, transport = synced(box, laptop)
    venv = plan_venv(profile, laptop)
    sentinel = box / "my-chef" / ".venv" / "sentinel"
    assert run_on_box(transport, venv).returncode == 0
    assert seen_paths(box / "my-chef") == [sentinel.parent.resolve()]
    sentinel.touch()
    # Left when another chef rebuilds a shared venv after this chef's build failed.
    stale_log = box / "my-chef" / ".ricecooker-remote" / "venv.log"
    stale_log.write_text("stale")
    assert run_on_box(transport, venv).returncode == 0
    assert sentinel.exists()
    assert not stale_log.exists()

    (laptop / "requirements.txt").write_text("# still none\n")
    transport.sync()
    assert run_on_box(transport, plan_venv(profile, laptop)).returncode == 0
    assert not sentinel.exists()
    assert len(seen(box / "my-chef")) == 3


@box_run
def test_chef_without_manifest_uses_shared_default_venv(
    box, laptop, tmp_path, monkeypatch
):
    monkeypatch.setattr(driver, "RELEASED_RICECOOKER", str(fake_ricecooker(tmp_path)))
    write_chef(laptop)
    profile, transport = synced(box, laptop)
    assert run_on_box(transport, plan_venv(profile, laptop)).returncode == 0
    default_venv = (box / ".default-venv").resolve()
    assert seen_paths(box / "my-chef") == [default_venv]
    [fakerc] = seen_paths(box / "my-chef", "fakerc")
    assert fakerc.is_relative_to(default_venv)


@box_run
def test_local_source_is_synced_and_installed_editable(box, laptop, tmp_path):
    pkg = fake_ricecooker(tmp_path)
    (pkg / ".git").write_text("gitdir: /nowhere\n")
    write_chef(laptop)
    profile, transport = synced(box, laptop, ricecooker_source="local")
    sync_source(transport, pkg)
    source = box / ".ricecooker-src"
    assert (source / "pyproject.toml").exists()
    assert not (source / ".git").exists()

    assert run_on_box(transport, plan_venv(profile, laptop, pkg)).returncode == 0
    [fakerc] = seen_paths(box / "my-chef", "fakerc")
    assert fakerc.is_relative_to(source.resolve())
    assert seen_paths(box / "my-chef") == [(box / "my-chef" / ".venv").resolve()]


def test_local_source_digest_tracks_pyproject_not_version(
    box, laptop, tmp_path, monkeypatch
):
    pkg = fake_ricecooker(tmp_path)
    profile = make_profile(box, ricecooker_source="local")
    monkeypatch.setattr(driver, "__version__", "1")
    digest = plan_venv(profile, laptop, pkg).digest
    monkeypatch.setattr(driver, "__version__", "2")
    assert plan_venv(profile, laptop, pkg).digest == digest
    with open(pkg / "pyproject.toml", "a") as f:
        f.write("# changed\n")
    assert plan_venv(profile, laptop, pkg).digest != digest


@box_run
def test_box_env_file_reaches_chef(box, laptop, offline_uv):
    env_file = offline_uv / ".config" / "ricecooker" / "remote-env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text("BOX_ONLY=from-box\n")
    write_chef(laptop, "pyproject.toml", PYPROJECT)
    profile, transport = synced(box, laptop)
    assert run_on_box(transport, plan_venv(profile, laptop)).returncode == 0
    assert [s["BOX_ONLY"] for s in seen(box / "my-chef")] == ["from-box"]


@box_run
def test_failed_venv_build_keeps_uv_output_and_skips_chef(box, laptop):
    write_chef(laptop, "requirements.txt", "no-such-package-xyz\n")
    profile, transport = synced(box, laptop)
    assert run_on_box(transport, plan_venv(profile, laptop)).returncode != 0
    assert seen(box / "my-chef") == []
    log = box / "my-chef" / ".ricecooker-remote" / "venv.log"
    assert "no-such-package-xyz" in log.read_text()


TARGET = "=ricecooker-laptop:"
CLIENT = """
import json, sys
from ricecooker.utils.remote.driver import run_remotely
sys.exit(run_remotely(sys.argv[3:], json.loads(sys.argv[2]), global_path=sys.argv[1]))
"""


def tmux(*args):
    return subprocess.run(["tmux", *args], capture_output=True, text=True)


def attached_clients() -> int:
    return len(tmux("list-clients", "-t", TARGET).stdout.splitlines())


def lifecycle(test):
    return box_run(pytest.mark.usefixtures("tmux_server")(test))


@pytest.fixture
def chef_dir(box):
    return box / "laptop"


@pytest.fixture
def remote(box, laptop, spawn_in_pty):
    """Starts run_remotely from a terminal on the no-dependency pyproject chef."""
    write_chef(laptop, "pyproject.toml", PYPROJECT)
    config = write_global_config(laptop.parent / "remote.toml", box)

    def start(*args, env=None):
        client = [sys.executable, "-c", CLIENT, str(config), json.dumps(env or {})]
        return spawn_in_pty(client + ["chef.py", *args], cwd=laptop)

    return start


@lifecycle
def test_fresh_run_exits_with_chef_code_and_prints_logs(
    box, chef_dir, remote, wait_until
):
    client = remote("3")
    assert client.wait() == 3
    assert str(chef_dir / "logs" / "run.log") in client.output
    session_log = chef_dir / ".ricecooker-remote" / "session.log"
    assert str(session_log) in client.output
    assert wait_until(lambda: "chef-output" in session_log.read_text())
    assert (box / ".ricecookerfilecache").is_dir()
    [run] = seen(chef_dir)
    assert run["RICECOOKER_FILECACHE"] == str(box / ".ricecookerfilecache")
    assert run["argv"] == ["chef.py", "3"]
    assert "venv build failed" not in client.output


@lifecycle
def test_finished_pane_is_reported_then_replaced(chef_dir, remote):
    assert remote("3").wait() == 3
    client = remote("0")
    assert client.wait() == 0
    assert "exited 3" in client.output
    assert len(seen(chef_dir)) == 2


@lifecycle
def test_live_session_is_attached_without_restart_or_sync(
    chef_dir, laptop, remote, wait_until
):
    first = remote("0", "wait")
    assert wait_until(lambda: attached_clients() == 1, timeout=30)
    with open(laptop / "chef.py", "a") as f:
        f.write("# edited\n")
    second = remote("0", "wait")
    assert wait_until(lambda: attached_clients() == 2)
    (chef_dir / "go").touch()
    assert first.wait() == 0
    assert second.wait() == 0
    assert "already running" in second.output
    assert len(seen(chef_dir)) == 1
    assert "# edited" not in (chef_dir / "chef.py").read_text()


@lifecycle
def test_detach_exits_zero_with_reattach_hint(box, remote, wait_until):
    client = remote("0", "wait")
    assert wait_until(lambda: attached_clients() == 1, timeout=30)
    tmux("detach-client", "-s", TARGET)
    assert client.wait() == 0
    assert "--remote" in client.output
    session = Session(Transport(make_profile(box, "laptop")))
    assert session.status().state == LIVE


@lifecycle
def test_ctrl_c_interrupts_chef_and_keeps_session(chef_dir, remote, wait_until):
    client = remote("0", "wait")
    assert wait_until(lambda: seen(chef_dir) and attached_clients(), timeout=30)
    os.write(client.fd, b"\x03")
    assert client.wait() == 130
    assert tmux("has-session", "-t", TARGET).returncode == 0


@lifecycle
def test_client_env_overrides_box_env_and_stays_off_disk(
    box, chef_dir, remote, offline_uv
):
    env_file = offline_uv / ".config" / "ricecooker" / "remote-env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text("STUDIO_TOKEN=box-token\nBOX_ONLY=from-box\nODD=box\n")
    env_file.chmod(0o600)
    odd = "x;y $HOME `id` 'q' \"d\" \\ #{a} end;\n"
    client = remote(env={"STUDIO_TOKEN": "s3cret-tok", "ODD": odd})
    assert client.wait() == 0
    [run] = seen(chef_dir)
    assert run["token_sha256"] == hashlib.sha256(b"s3cret-tok").hexdigest()
    assert run["ODD"] == odd
    assert run["BOX_ONLY"] == "from-box"
    on_disk = [p for p in box.rglob("*") if p.is_file() and not p.is_symlink()]
    forms = (b"s3cret-tok", base64.b64encode(b"s3cret-tok"))
    assert [p for p in on_disk if any(f in p.read_bytes() for f in forms)] == []


@lifecycle
def test_failed_venv_build_reports_uv_tail_and_keeps_session(box, laptop, remote):
    assert remote().wait() == 0
    (laptop / "pyproject.toml").unlink()
    (laptop / "requirements.txt").write_text("no-such-package-xyz\n")
    client = remote()
    assert client.wait() != 0
    assert "remote: venv build failed" in client.output
    assert "no-such-package-xyz" in client.output
    assert "chef log:" not in client.output
    assert tmux("has-session", "-t", TARGET).returncode == 0


@needs_sh
@needs_uv
@pytest.mark.usefixtures("gnu_rsync", "tmux_server")
def test_local_source_sync_refuses_while_another_chef_under_root_runs(
    box, laptop, capsys
):
    write_chef(laptop)
    config = write_global_config(laptop.parent / "remote.toml", box)
    with open(config, "a") as f:
        f.write('ricecooker_source = "local"\n')
    make_session(box, "other-chef").create(["sleep", "30"])
    argv = [str(laptop / "chef.py")]
    assert run_remotely(argv, {}, chef_dir=laptop, global_path=config) == 1
    assert capsys.readouterr().err.startswith("remote: other-chef running")
    assert not (box / ".ricecooker-src").exists()
    assert tmux("has-session", "-t", TARGET).returncode == 1


@needs_sh
@needs_uv
@pytest.mark.usefixtures("gnu_rsync", "tmux_server")
@pytest.mark.parametrize("same_digest", [True, False])
def test_default_venv_rebuild_refused_while_another_chef_under_root_runs(
    box, laptop, capsys, monkeypatch, same_digest
):
    # Not a terminal: a started run returns instead of attaching.
    monkeypatch.setattr(sys, "stdin", io.StringIO())
    write_chef(laptop)
    digest = plan_venv(make_profile(box, "laptop"), laptop).digest
    digest_file = box / ".default-venv" / ".ricecooker-digest"
    digest_file.parent.mkdir()
    digest_file.write_text(f"{digest if same_digest else 'old'}\n")
    make_session(box, "other-chef").create(["sleep", "30"])
    assert run_remotely_from(laptop, box) == (NOT_A_TTY if same_digest else 1)
    started = tmux("has-session", "-t", TARGET).returncode == 0
    assert started == same_digest
    if not same_digest:
        assert capsys.readouterr().err.startswith("remote: other-chef running")
        assert digest_file.read_text() == "old\n"


E2E_BOX = os.environ.get("RICECOOKER_REMOTE_E2E")
E2E_CHEF = """\
import json, os
import ricecooker
from ricecooker.chefs import SushiChef

class Chef(SushiChef):
    def run(self, args, options):
        print("e2e-ran", flush=True)
        os.makedirs("chefdata", exist_ok=True)
        with open("chefdata/e2e.json", "w") as f:
            json.dump({"file": ricecooker.__file__, "version": ricecooker.__version__}, f)

Chef().main()
"""


@pytest.mark.skipif(
    not E2E_BOX,
    reason="set RICECOOKER_REMOTE_E2E to an ssh destination with tmux, uv, network",
)
@pytest.mark.parametrize("source", [None, "local"])
def test_e2e_real_chef_on_localhost_box(tmp_path, laptop, spawn_in_pty, source):
    root = tmp_path / "e2e-box"
    config = write_global_config(tmp_path / "remote.toml", root, ssh=E2E_BOX)
    if source:
        with open(config, "a") as f:
            f.write(f'ricecooker_source = "{source}"\n')
    (laptop / "chef.py").write_text(E2E_CHEF)
    client = [sys.executable, "-c", CLIENT, str(config), "{}", "chef.py", "dryrun"]
    try:
        run = spawn_in_pty(client, cwd=laptop)
        assert run.wait(timeout=600) == 0
        assert "e2e-ran" in run.output
        if source:
            ran = json.loads((root / "laptop" / "chefdata" / "e2e.json").read_text())
            source_dir = (root / ".ricecooker-src").resolve()
            assert Path(ran["file"]).resolve().is_relative_to(source_dir)
            assert ran["version"] == ricecooker.__version__
        assert list((root / "laptop" / "logs").glob("*.log"))
    finally:
        profile = resolve_profile(chef_dir=laptop, global_path=config)
        Session(Transport(profile)).kill()
