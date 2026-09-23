import io
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
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


def _tmux_can_run():
    if os.name == "nt" or not shutil.which("tmux"):
        return False
    try:
        fds = os.openpty()
    except OSError:  # tmux panes need a pty; some sandboxes deny /dev/ptmx
        return False
    for fd in fds:
        os.close(fd)
    return True


needs_tmux = pytest.mark.skipif(not _tmux_can_run(), reason="needs tmux and a pty")
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


@pytest.fixture(autouse=True)
def isolated_tmux(monkeypatch):
    # Short path: the socket must fit in sun_path (104 bytes on macOS).
    tmpdir = tempfile.mkdtemp(prefix="rc-tmux-")
    monkeypatch.setenv("TMUX_TMPDIR", tmpdir)
    # Else tmux talks to the developer's server.
    monkeypatch.delenv("TMUX", raising=False)
    yield
    if shutil.which("tmux"):
        tmux("kill-server")
    shutil.rmtree(tmpdir, ignore_errors=True)


def make_session(box, name="my-chef"):
    (box / name).mkdir(exist_ok=True)
    profile = RemoteProfile(
        ssh="box", remote_root=str(box), name=name, protect=[], exclude=[]
    )
    return Session(Transport(profile))


def wait_until(predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            return False
        time.sleep(0.05)
    return True


def non_empty(path):
    return path.exists() and path.read_text() != ""


@needs_tmux
def test_status_without_session_is_none(box):
    assert make_session(box).status() == SessionStatus(NO_SESSION)


@needs_tmux
def test_create_runs_command_in_chef_dir_and_reports_live_since_start(box):
    s = make_session(box)
    before = datetime.now().replace(microsecond=0)
    s.create(["sh", "-c", "pwd > where; exec sleep 30"])
    status = s.status()
    assert status.state == LIVE
    assert before <= status.started <= datetime.now()
    where = box / "my-chef" / "where"
    assert wait_until(lambda: non_empty(where))
    assert Path(where.read_text().strip()).resolve() == (box / "my-chef").resolve()


@needs_tmux
def test_create_refuses_while_session_exists(box):
    s = make_session(box)
    s.create(["sleep", "30"])
    with pytest.raises(RemoteSessionError):
        s.create(["sleep", "30"])
    assert s.status().state == LIVE


@needs_tmux
def test_create_passes_args_ending_in_semicolon_verbatim(box):
    make_session(box).create(
        ["sh", "-c", 'printf "%s|" "$@" > args', "sh", "a\\;", "b;"]
    )
    args = box / "my-chef" / "args"
    assert wait_until(lambda: non_empty(args))
    assert args.read_text() == "a\\;|b;|"


@needs_tmux
def test_dotted_chef_name_is_found(box):
    s = make_session(box, "my.chef")
    s.create(["sleep", "30"])
    assert s.status().state == LIVE


@needs_tmux
def test_prefix_of_live_chef_name_sees_no_session(box):
    make_session(box, "foobar").create(["sleep", "30"])
    assert make_session(box, "foo").status().state == NO_SESSION


@needs_tmux
@pytest.mark.parametrize("code", [0, 3])
def test_finished_pane_lingers_with_exit_code_and_output(box, code):
    s = make_session(box)
    s.create(["sh", "-c", f"echo chef-output; exit {code}"])
    assert wait_until(lambda: s.status().state == FINISHED)
    assert s.status().exit_code == code
    assert (Path(s.bookkeeping_dir) / "exitcode").read_text().strip() == str(code)
    # -S -: the "Pane is dead" line scrolls the output into history.
    assert "chef-output" in tmux("capture-pane", "-p", "-S", "-", "-t", TARGET).stdout


@needs_tmux
def test_recorder_killed_after_leftover_code_finishes_without_code(box):
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


@needs_tmux
def test_ctrl_c_finishes_pane_with_sigint_code(box):
    s = make_session(box)
    s.create(["sh", "-c", "touch started; exec sleep 30"])
    assert wait_until((box / "my-chef" / "started").exists)
    tmux("send-keys", "-t", TARGET, "C-c")
    assert wait_until(lambda: s.status().state == FINISHED)
    assert s.status().exit_code == 130


@needs_tmux
@pytest.mark.parametrize(
    "command, state", [(["sleep", "30"], LIVE), (["sh", "-c", "exit 3"], FINISHED)]
)
def test_kill_tears_down_session(box, command, state):
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


def drain(fd):
    try:
        while os.read(fd, 1024):
            pass
    except OSError:
        pass


@needs_tmux
def test_attach_from_terminal_joins_session_until_detached(box):
    make_session(box).create(["sleep", "30"])
    parent_fd, child_fd = os.openpty()
    child = subprocess.Popen(
        [sys.executable, "-c", ATTACH, str(box)],
        stdin=child_fd,
        stdout=child_fd,
        stderr=child_fd,
        env={**os.environ, "TERM": "xterm"},
    )
    os.close(child_fd)
    # Unread output fills the pty buffer and blocks tmux.
    threading.Thread(target=drain, args=(parent_fd,), daemon=True).start()
    try:
        assert wait_until(lambda: tmux("list-clients", "-t", TARGET).stdout.strip())
        tmux("detach-client", "-s", TARGET)
        assert child.wait(timeout=10) == 0
    finally:
        child.kill()
        os.close(parent_fd)
