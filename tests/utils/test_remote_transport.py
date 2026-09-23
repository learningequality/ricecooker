import ast
import sys
from pathlib import Path

import pytest

from ricecooker.exceptions import RemoteTransportError
from ricecooker.utils.remote import transport
from ricecooker.utils.remote.config import RemoteProfile
from ricecooker.utils.remote.transport import pull_argv
from ricecooker.utils.remote.transport import RunResult
from ricecooker.utils.remote.transport import ssh_argv
from ricecooker.utils.remote.transport import subprocess_runner
from ricecooker.utils.remote.transport import sync_argv
from ricecooker.utils.remote.transport import Transport

PROFILE = RemoteProfile(
    ssh="box",
    remote_root="/srv/chefs",
    name="my-chef",
    protect=["credentials.json", "secrets/"],
    exclude=["*.tmp"],
)


def test_sync_argv_exact(tmp_path):
    assert sync_argv(PROFILE, tmp_path) == [
        "rsync",
        "-a",
        "--delete",
        "--delete-after",
        "--filter=:- .gitignore",
        "--exclude=.venv/",
        "--exclude=.ricecooker-remote/",
        "--exclude=storage/",
        "--exclude=restore/",
        "--exclude=chefdata/",
        "--exclude=logs/",
        "--filter=P credentials.json",
        "--filter=P secrets/",
        "--exclude=*.tmp",
        f"{tmp_path}/",
        "box:/srv/chefs/my-chef/",
    ]


def test_pull_argv_exact():
    assert pull_argv(PROFILE, "chefdata/trees", "out") == [
        "rsync",
        "-a",
        "box:/srv/chefs/my-chef/chefdata/trees",
        "out",
    ]


def test_ssh_argv_quotes_command():
    assert ssh_argv(PROFILE, ["sh", "-c", "cd /srv/x && uv sync"]) == [
        "ssh",
        "box",
        "sh -c 'cd /srv/x && uv sync'",
    ]


def test_ssh_argv_tty_form():
    assert ssh_argv(
        PROFILE, ["tmux", "attach", "-t", "ricecooker-my-chef"], tty=True
    ) == ["ssh", "-t", "box", "tmux attach -t ricecooker-my-chef"]


class RecordingRunner:
    def __init__(self, result=RunResult(0)):
        self.result = result
        self.calls = []

    def __call__(self, argv, capture):
        self.calls.append((argv, capture))
        return self.result


EXIT_3_ARGV = [
    sys.executable,
    "-c",
    "import sys; sys.stdout.write('out'); sys.stderr.write('err'); sys.exit(3)",
]


def test_subprocess_runner_captures_streams_and_exit_code():
    assert subprocess_runner(EXIT_3_ARGV, capture=True) == RunResult(3, "out", "err")


def test_subprocess_runner_uncaptured_streams_are_empty_strings():
    assert subprocess_runner(EXIT_3_ARGV, capture=False) == RunResult(3, "", "")


def test_subprocess_runner_missing_binary_is_remote_error():
    with pytest.raises(RemoteTransportError) as exc:
        subprocess_runner(["ricecooker-no-such-binary-xyz"], capture=True)
    assert str(exc.value).startswith("remote:")
    assert "ricecooker-no-such-binary-xyz" in str(exc.value)


def test_transport_routes_every_operation_through_runner(tmp_path):
    fake = RecordingRunner()
    t = Transport(PROFILE, chef_dir=tmp_path, runner=fake)
    t.sync()
    t.pull("logs/", "out")
    t.ssh(["command", "-v", "uv"])
    t.ssh(["tmux", "attach"], tty=True)
    assert fake.calls == [
        (sync_argv(PROFILE, tmp_path), True),
        (pull_argv(PROFILE, "logs/", "out"), True),
        (ssh_argv(PROFILE, ["command", "-v", "uv"]), True),
        (ssh_argv(PROFILE, ["tmux", "attach"], tty=True), False),
    ]


def test_transport_default_chef_dir_is_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake = RecordingRunner()
    Transport(PROFILE, runner=fake).sync()
    assert fake.calls == [(sync_argv(PROFILE, Path.cwd()), True)]


@pytest.mark.parametrize(
    "operation", [lambda t: t.sync(), lambda t: t.pull("x", "y")], ids=["sync", "pull"]
)
def test_transport_rsync_failure_raises_with_stderr(operation):
    fake = RecordingRunner(RunResult(23, "", "rsync: link_stat failed"))
    with pytest.raises(RemoteTransportError) as exc:
        operation(Transport(PROFILE, runner=fake))
    assert str(exc.value).startswith("remote:")
    assert "rsync: link_stat failed" in str(exc.value)


def test_transport_ssh_nonzero_is_returned_not_raised():
    fake = RecordingRunner(RunResult(1))
    assert Transport(PROFILE, runner=fake).ssh(["tmux", "has-session"]) == RunResult(1)


def _violations(path):
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            modules = {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            modules = {node.module}
        else:
            modules = set()
        if "subprocess" in modules:
            yield "imports subprocess"
        if (
            isinstance(node, ast.List)
            and node.elts
            and isinstance(node.elts[0], ast.Constant)
            and node.elts[0].value in {"ssh", "rsync"}
        ):
            yield f"builds {node.elts[0].value} argv"


def test_only_transport_imports_subprocess_or_builds_ssh_rsync_argv():
    package = Path(transport.__file__).parent
    found = {
        path.name: list(_violations(path))
        for path in package.glob("*.py")
        if path.name != "transport.py"
    }
    assert {name: v for name, v in found.items() if v} == {}
