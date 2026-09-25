import io
import os
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from ricecooker.exceptions import RemoteSessionError
from ricecooker.utils.remote.config import RemoteProfile
from ricecooker.utils.remote.session import FINISHED
from ricecooker.utils.remote.session import LIVE
from ricecooker.utils.remote.session import NO_SESSION
from ricecooker.utils.remote.session import NOT_A_TTY
from ricecooker.utils.remote.session import Session
from ricecooker.utils.remote.session import SessionStatus
from ricecooker.utils.remote.transport import RunResult
from ricecooker.utils.remote.transport import Transport

TARGET = "=ricecooker-my-chef:"
ATTACH = """
import sys
from ricecooker.utils.remote.config import RemoteProfile
from ricecooker.utils.remote.session import Session
from ricecooker.utils.remote.transport import Transport
profile = RemoteProfile(
    ssh="box", remote_root=sys.argv[1], name="my-chef", protect=[], exclude=[]
)
sys.exit(Session(Transport(profile)).attach())
"""


def tmux(*args):
    return subprocess.run(["tmux", *args], capture_output=True, text=True)


def make_session(box, name="my-chef"):
    (box / name).mkdir(exist_ok=True)
    profile = RemoteProfile(
        ssh="box", remote_root=str(box), name=name, protect=[], exclude=[]
    )
    return Session(Transport(profile))


def non_empty(path):
    return path.exists() and path.read_text() != ""


def test_status_without_session_is_none(box, tmux_server):
    assert make_session(box).status() == SessionStatus(NO_SESSION)


def test_create_runs_command_in_chef_dir_and_reports_live_since_start(
    box, tmux_server, wait_until
):
    s = make_session(box)
    before = datetime.now().replace(microsecond=0)
    s.create(["sh", "-c", "pwd > where; exec sleep 30"])
    status = s.status()
    assert status.state == LIVE
    assert before <= status.started <= datetime.now()
    where = box / "my-chef" / "where"
    assert wait_until(lambda: non_empty(where))
    assert Path(where.read_text().strip()).resolve() == (box / "my-chef").resolve()


def test_create_refuses_while_session_exists(box, tmux_server):
    s = make_session(box)
    s.create(["sleep", "30"])
    with pytest.raises(RemoteSessionError):
        s.create(["sleep", "30"])
    assert s.status().state == LIVE


def test_create_passes_args_ending_in_semicolon_verbatim(box, tmux_server, wait_until):
    make_session(box).create(
        ["sh", "-c", 'printf "%s|" "$@" > args', "sh", "a\\;", "b;"]
    )
    args = box / "my-chef" / "args"
    assert wait_until(lambda: non_empty(args))
    assert args.read_text() == "a\\;|b;|"


def test_create_sets_env_on_session_verbatim(box, tmux_server):
    make_session(box).create(["sleep", "30"], env={"RC_VALUE": "a b;"})
    # A trailing ";" unescaped is dropped by tmux.
    shown = tmux("show-environment", "-t", TARGET, "RC_VALUE").stdout
    assert shown == "RC_VALUE=a b;\n"


@pytest.mark.parametrize("name", ["my-chef", "it's a chef"])
def test_create_pipes_pane_output_to_log(box, name, tmux_server, wait_until):
    s = make_session(box, name)
    s.create(["sh", "-c", "echo piped-output"])
    log = Path(s.log_path)
    assert wait_until(lambda: log.exists() and "piped-output" in log.read_text())


def test_dotted_chef_name_is_found(box, tmux_server):
    s = make_session(box, "my.chef")
    s.create(["sleep", "30"])
    assert s.status().state == LIVE


def test_prefix_of_live_chef_name_sees_no_session(box, tmux_server):
    make_session(box, "foobar").create(["sleep", "30"])
    assert make_session(box, "foo").status().state == NO_SESSION


@pytest.mark.parametrize("code", [0, 3])
def test_finished_pane_lingers_with_exit_code_and_output(
    box, code, tmux_server, wait_until
):
    s = make_session(box)
    s.create(["sh", "-c", f"echo chef-output; exit {code}"])
    assert wait_until(lambda: s.status().state == FINISHED)
    assert s.status().exit_code == code
    assert (Path(s.bookkeeping_dir) / "exitcode").read_text().strip() == str(code)
    # -S -: the "Pane is dead" line scrolls the output into history.
    assert "chef-output" in tmux("capture-pane", "-p", "-S", "-", "-t", TARGET).stdout

    # No client attached: the recorder's detach must not replace the code.
    # tmux < 3.6 can drop the pane's SIGCHLD (tmux#4559), leaving
    # pane_dead_status empty. run-shell returns only after tmux's waitpid
    # loop reaps its job, which reaps the pane too.
    tmux("run-shell", "true")
    dead = tmux("display-message", "-p", "-t", TARGET, "#{pane_dead_status}")
    assert dead.stdout.strip() == str(code)
    log = Path(s.log_path)
    # pipe-pane creates the log asynchronously.
    assert wait_until(lambda: log.exists() and "chef-output" in log.read_text())
    assert "no current client" not in log.read_text()


def test_recorder_killed_after_leftover_code_finishes_without_code(
    box, tmux_server, wait_until
):
    s = make_session(box)
    bookkeeping = Path(s.bookkeeping_dir)
    bookkeeping.mkdir()
    (bookkeeping / "exitcode").write_text("3")
    s.create(["sh", "-c", "touch started; exec sleep 30"])
    assert wait_until((box / "my-chef" / "started").exists)
    pane_pid = tmux("display-message", "-p", "-t", TARGET, "#{pane_pid}").stdout
    os.killpg(int(pane_pid), signal.SIGKILL)
    assert wait_until(lambda: s.status().state == FINISHED)
    assert s.status().exit_code is None


def test_ctrl_c_finishes_pane_with_sigint_code(box, tmux_server, wait_until):
    s = make_session(box)
    s.create(["sh", "-c", "touch started; exec sleep 30"])
    assert wait_until((box / "my-chef" / "started").exists)
    tmux("send-keys", "-t", TARGET, "C-c")
    assert wait_until(lambda: s.status().state == FINISHED)
    assert s.status().exit_code == 130


@pytest.mark.parametrize(
    "command, state", [(["sleep", "30"], LIVE), (["sh", "-c", "exit 3"], FINISHED)]
)
def test_kill_tears_down_session(box, command, state, tmux_server, wait_until):
    s = make_session(box)
    s.create(command)
    assert wait_until(lambda: s.status().state == state)
    s.kill()
    assert s.status() == SessionStatus(NO_SESSION)
    s.kill()


def test_status_on_unreachable_box_raises_with_ssh_stderr():
    def unreachable(argv, capture):
        return RunResult(
            255, stderr="ssh: connect to host box port 22: Connection refused"
        )

    profile = RemoteProfile(
        ssh="box", remote_root="/srv", name="my-chef", protect=[], exclude=[]
    )
    with pytest.raises(RemoteSessionError) as exc:
        Session(Transport(profile, runner=unreachable)).status()
    assert str(exc.value).startswith("remote:")
    assert "Connection refused" in str(exc.value)


def test_attach_without_tty_refuses_with_distinct_code(box, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO())
    assert make_session(box).attach() == NOT_A_TTY
    assert capsys.readouterr().err.startswith("remote:")


@pytest.fixture
def attach_in_pty(box, spawn_in_pty):
    return lambda: spawn_in_pty([sys.executable, "-c", ATTACH, str(box)])


def has_client():
    return tmux("list-clients", "-t", TARGET).stdout.strip()


def test_attach_from_terminal_joins_session_until_detached(
    box, tmux_server, wait_until, attach_in_pty
):
    make_session(box).create(["sleep", "30"])
    child = attach_in_pty()
    assert wait_until(has_client)
    tmux("detach-client", "-s", TARGET)
    assert child.wait(timeout=10) == 0


def test_attached_client_returns_when_command_finishes(
    box, tmux_server, wait_until, attach_in_pty
):
    s = make_session(box)
    s.create(["sh", "-c", "until [ -e go ]; do sleep 0.1; done; exit 3"])
    child = attach_in_pty()
    assert wait_until(has_client)
    assert s.exit_code() is None
    (box / "my-chef" / "go").touch()
    assert child.wait(timeout=10) == 0
    assert s.exit_code() == 3


def test_attach_to_finished_pane_returns(box, tmux_server, wait_until, attach_in_pty):
    s = make_session(box)
    s.create(["sh", "-c", "exit 3"])
    assert wait_until(lambda: s.status().state == FINISHED)
    assert attach_in_pty().wait(timeout=10) == 0
