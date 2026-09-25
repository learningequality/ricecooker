import subprocess
import sys
from pathlib import Path

import pytest
from test_remote_driver import attached_clients
from test_remote_driver import box_tools
from test_remote_driver import needs_sh
from test_remote_driver import needs_uv
from test_remote_driver import write_global_config
from test_remote_session import make_session
from test_remote_transport import write

from ricecooker.utils.remote.cli import DEPENDENCIES
from ricecooker.utils.remote.cli import run_remote_command
from ricecooker.utils.remote.transport import RunResult


def run_cli(laptop, root, *argv, **kwargs):
    config = write_global_config(laptop.parent / "remote.toml", root)
    return run_remote_command(list(argv), chef_dir=laptop, global_path=config, **kwargs)


@needs_sh
def test_cache_info_counts_entries_not_locks(box, laptop, capsys):
    entry_dir = box / ".ricecookerfilecache" / "a" / "b" / "c" / "d" / "e"
    for name in ("abcde1", "abcde1.lock", "abcde2"):
        write(entry_dir / name)
    assert run_cli(laptop, box, "cache", "info") == 0
    lines = capsys.readouterr().out.splitlines()
    assert f"path: {box}/.ricecookerfilecache" in lines
    assert "entries: 2" in lines


@needs_sh
@pytest.mark.parametrize("extra,selected", [([], "a"), (["--remote", "b"], "b")])
def test_cache_commands_use_selected_profile(box, laptop, capsys, extra, selected):
    config = laptop.parent / "remote.toml"
    config.write_text(
        'default = "a"\n\n'
        f'[a]\nssh = "box"\nremote_root = "{box}/a"\n\n'
        f'[b]\nssh = "box"\nremote_root = "{box}/b"\n'
    )
    argv = ["cache", "info", *extra]
    assert run_remote_command(argv, chef_dir=laptop, global_path=config) == 0
    out = capsys.readouterr().out.splitlines()
    assert f"path: {box}/{selected}/.ricecookerfilecache" in out


@needs_sh
@pytest.mark.usefixtures("tmux_server")
def test_cache_clear_empties_only_the_shared_cache(box, laptop, capsys):
    write(box / ".ricecookerfilecache" / "a" / "entry")
    keep = box / "my-chef" / "storage" / "keep"
    write(keep)
    assert run_cli(laptop, box, "cache", "clear") == 0
    assert run_cli(laptop, box, "cache", "info") == 0
    assert "entries: 0" in capsys.readouterr().out.splitlines()
    assert keep.exists()


@needs_sh
@pytest.mark.usefixtures("tmux_server")
@pytest.mark.parametrize("other_root,refused", [(False, True), (True, False)])
def test_cache_clear_refuses_while_any_chef_under_root_runs(
    box, laptop, capsys, other_root, refused
):
    entry = box / ".ricecookerfilecache" / "a" / "entry"
    write(entry)
    root = box / "other-root" if other_root else box
    root.mkdir(exist_ok=True)
    make_session(root, "other-chef").create(["sleep", "30"])
    assert run_cli(laptop, box, "cache", "clear") == (1 if refused else 0)
    assert entry.exists() == refused
    if refused:
        err = capsys.readouterr().err
        assert err.startswith("remote: other-chef running")


def test_unreachable_box_fails_with_ssh_stderr(laptop, capsys):
    ssh_error = "ssh: connect to host box port 22: Connection refused\n"

    def unreachable(argv, capture):
        return RunResult(255, stderr=ssh_error)

    assert run_cli(laptop, "/srv", "cache", "info", runner=unreachable) == 1
    err = capsys.readouterr().err
    assert err.startswith("remote:")
    assert ssh_error in err


@needs_sh
@needs_uv
@pytest.mark.usefixtures("gnu_rsync", "tmux_server")
def test_sync_uploads_chef_dir_to_fresh_box(box, laptop):
    write(laptop / "chef.py")
    assert run_cli(laptop, box / "fresh" / "root", "sync") == 0
    assert (box / "fresh" / "root" / "laptop" / "chef.py").exists()


@needs_sh
@needs_uv
@pytest.mark.usefixtures("gnu_rsync", "tmux_server")
def test_sync_refuses_while_chef_runs(box, laptop, capsys):
    write(laptop / "chef.py", "new")
    write(box / "laptop" / "chef.py", "old")
    make_session(box, "laptop").create(["sleep", "30"])
    assert run_cli(laptop, box, "sync") == 1
    assert capsys.readouterr().err.startswith("remote:")
    assert (box / "laptop" / "chef.py").read_text() == "old"


@pytest.mark.usefixtures("gnu_rsync")
@pytest.mark.parametrize("explicit_dest", [True, False])
def test_pull_fetches_path_relative_to_chef_dir(
    box, laptop, tmp_path, monkeypatch, explicit_dest
):
    write(box / "laptop" / "chefdata" / "trees" / "a.json", "tree")
    out = tmp_path / "out"
    out.mkdir()
    if explicit_dest:
        dest = [str(out)]
    else:
        monkeypatch.chdir(out)
        dest = []
    assert run_cli(laptop, box, "pull", "chefdata/trees", *dest) == 0
    assert (out / "trees" / "a.json").read_text() == "tree"


@pytest.mark.usefixtures("gnu_rsync")
def test_pull_with_trailing_slash_copies_contents(box, laptop, tmp_path):
    write(box / "laptop" / "storage" / "a.zip", "zip")
    out = tmp_path / "out"
    assert run_cli(laptop, box, "pull", "storage/", str(out)) == 0
    assert (out / "a.zip").read_text() == "zip"


@pytest.mark.usefixtures("gnu_rsync")
def test_pull_of_missing_path_fails_with_rsync_stderr(box, laptop, tmp_path, capsys):
    assert run_cli(laptop, box, "pull", "nope", str(tmp_path / "out")) == 1
    err = capsys.readouterr().err
    assert err.startswith("remote:")
    assert "rsync:" in err


@pytest.mark.usefixtures("gnu_rsync")
@pytest.mark.parametrize(
    "remote_path", ["{box}/secret", "..", "../secret", "a/../../secret"]
)
def test_pull_refuses_path_outside_chef_dir(box, laptop, tmp_path, capsys, remote_path):
    write(box / "secret", "secret")
    (box / "laptop").mkdir()
    out = tmp_path / "out"
    out.mkdir()
    assert run_cli(laptop, box, "pull", remote_path.format(box=box), str(out)) == 1
    assert capsys.readouterr().err.startswith("remote:")
    assert list(out.iterdir()) == []


CLI = """
import sys
from ricecooker.utils.remote.cli import run_remote_command
sys.exit(run_remote_command(sys.argv[2:], global_path=sys.argv[1]))
"""


def cli_argv(laptop, root, *argv):
    config = write_global_config(laptop.parent / "remote.toml", root)
    return [sys.executable, "-c", CLI, str(config), *argv]


@needs_sh
@pytest.mark.parametrize("name", ["laptop", "it's a chef"])
def test_shell_opens_in_remote_chef_dir(box, laptop, tmp_path, monkeypatch, name):
    if name != "laptop":
        (laptop / ".ricecooker-remote.toml").write_text(f'name = "{name}"\n')
    (box / name).mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("SHELL", "/bin/sh")
    monkeypatch.setenv("HOME", str(home))
    result = subprocess.run(
        cli_argv(laptop, box, "shell"),
        cwd=laptop,
        input="pwd > where\nexit 7\n",
        text=True,
        capture_output=True,
    )
    assert result.returncode == 7, result.stderr
    where = (box / name / "where").read_text().strip()
    assert Path(where).resolve() == (box / name).resolve()


@pytest.mark.usefixtures("tmux_server")
def test_attach_joins_live_session_and_exits_with_chef_code(
    box, laptop, spawn_in_pty, wait_until
):
    make_session(box, "laptop").create(
        ["sh", "-c", "until [ -e go ]; do sleep 0.1; done; exit 3"]
    )
    client = spawn_in_pty(cli_argv(laptop, box, "attach"), cwd=laptop)
    assert wait_until(lambda: attached_clients() > 0)
    (box / "laptop" / "go").touch()
    assert client.wait() == 3


@pytest.mark.usefixtures("tmux_server")
def test_attach_without_session_fails(box, laptop, capsys):
    assert run_cli(laptop, box, "attach") == 1
    assert capsys.readouterr().err.startswith("remote:")


def dependency_lines(out):
    return [line for line in out.splitlines() if line.endswith((": ok", ": missing"))]


@needs_sh
@pytest.mark.parametrize("name,binary", DEPENDENCIES.items())
def test_doctor_reports_each_missing_dependency(
    box, laptop, monkeypatch, capsys, name, binary
):
    box_tools(box, monkeypatch, set(DEPENDENCIES.values()) - {binary})
    assert run_cli(laptop, box, "doctor") == 1
    assert dependency_lines(capsys.readouterr().out) == [
        f"{n}: {'missing' if n == name else 'ok'}" for n in DEPENDENCIES
    ]


@needs_sh
def test_doctor_with_all_dependencies_installs_nothing(
    box, laptop, monkeypatch, capsys
):
    box_tools(box, monkeypatch, DEPENDENCIES.values())
    monkeypatch.setenv("HOME", str(box.parent / "home"))
    assert run_cli(laptop, box / "fresh", "doctor") == 0
    assert dependency_lines(capsys.readouterr().out) == [
        f"{name}: ok" for name in DEPENDENCIES
    ]
    assert not (box / "fresh").exists()


@needs_sh
@pytest.mark.parametrize("mode,refused", [(0o600, False), (0o644, True)])
def test_doctor_reports_box_env_open_to_other_users(
    box, laptop, tmp_path, monkeypatch, capsys, mode, refused
):
    box_tools(box, monkeypatch, DEPENDENCIES.values())
    monkeypatch.setenv("HOME", str(tmp_path))
    env_file = tmp_path / ".config" / "ricecooker" / "remote-env"
    write(env_file, "STUDIO_TOKEN=box-token\n")
    env_file.chmod(mode)
    assert run_cli(laptop, box, "doctor") == (1 if refused else 0)
    assert ("chmod 600" in capsys.readouterr().out) == refused


@needs_sh
@pytest.mark.parametrize(
    "manifest,source,shared",
    [
        (None, None, True),
        ("pyproject.toml", None, False),
        ("requirements.txt", None, False),
        (None, "local", False),
    ],
)
def test_doctor_reports_shared_default_venv(
    box, laptop, monkeypatch, capsys, manifest, source, shared
):
    box_tools(box, monkeypatch, DEPENDENCIES.values())
    if manifest:
        (laptop / manifest).write_text("")
    config = write_global_config(laptop.parent / "remote.toml", box)
    if source:
        config.write_text(config.read_text() + f'ricecooker_source = "{source}"\n')
    run_remote_command(["doctor"], chef_dir=laptop, global_path=config)
    assert (str(box / ".default-venv") in capsys.readouterr().out) == shared


CHEF = """\
from pathlib import Path
from ricecooker.chefs import SushiChef

class Chef(SushiChef):
    def __init__(self):
        super().__init__()
        self.arg_parser.add_argument("--lang", required=True)

    def run(self, args, options):
        Path("ran").touch()

Chef().main()
"""


@pytest.fixture
def chef_script(box, laptop, tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".config" / "ricecooker").mkdir(parents=True)
    write_global_config(home / ".config" / "ricecooker" / "remote.toml", box)
    monkeypatch.setenv("HOME", str(home))
    (laptop / "chef.py").write_text(CHEF)
    return laptop / "chef.py"


def run_chef(*argv, cwd):
    return subprocess.run(
        [sys.executable, *argv], cwd=cwd, capture_output=True, text=True
    )


@needs_sh
def test_chef_script_runs_remote_before_its_own_parser(box, laptop, chef_script):
    result = run_chef("chef.py", "remote", "cache", "info", cwd=laptop)
    assert result.returncode == 0, result.stderr
    assert f"path: {box}/.ricecookerfilecache" in result.stdout.splitlines()
    assert not (laptop / "ran").exists()


@needs_sh
def test_chef_script_outside_cwd_is_refused(box, tmp_path, chef_script):
    entry = box / ".ricecookerfilecache" / "x"
    write(entry)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    result = run_chef(str(chef_script), "remote", "cache", "clear", cwd=elsewhere)
    assert result.returncode == 1
    assert result.stderr.startswith("remote:")
    assert entry.exists()
