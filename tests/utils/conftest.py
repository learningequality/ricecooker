import functools
import os
import shutil
import subprocess
import tempfile
import threading
import time

import pytest

SSH_SHIM = """#!/bin/sh
# Plays the box locally: drop ssh options and the host, run the command like sshd.
tty=
while [ "${1#-}" != "$1" ]; do [ "$1" = -t ] && tty=1; shift; done
shift
# sshd runs this as sh -c's argv, which ps shows every user on the box.
printf '%s\n' "$*" >> "$RC_FAKE_SSH_LOG"
# Without -t, sshd gives the command no terminal.
if [ -z "$tty" ] && [ -t 0 ]; then sh -c "$*" </dev/null; else sh -c "$*"; fi
rc=$?
# Logout under KillUserProcesses=yes kills this session's tmux server; one started by
# systemd-run lives in user@.service, which outlives logout only while the user lingers.
s=$RC_FAKE_LOGIND kup=
[ -e "$s/settings" ] && read -r kup < "$s/settings"
case $kup in *true*)
    { [ -e "$s/linger" ] && tmux show-environment -g RC_FAKE_SCOPE; } >/dev/null 2>&1 ||
        tmux kill-server 2>/dev/null ;;
esac
exit $rc
"""

# Play logind from $RC_FAKE_LOGIND: settings holds busctl's lines for the kill settings
# (absent: no systemd), linger marks the user lingering, deny refuses enable-linger.
FAKE_LOGIND = {
    "busctl": """#!/bin/sh
s=$RC_FAKE_LOGIND
if [ ! -e "$s/settings" ]; then
    echo "Failed to connect to bus: No such file or directory" >&2
    exit 1
fi
case "$*" in
*KillUserProcesses*) while IFS= read -r l; do echo "$l"; done < "$s/settings" ;;
*) if [ -e "$s/linger" ]; then echo '{"type":"b","data":true}'
   else echo '{"type":"b","data":false}'; fi ;;
esac
""",
    "loginctl": """#!/bin/sh
if [ -e "$RC_FAKE_LOGIND/deny" ]; then
    echo "Could not enable linger: Access denied" >&2
    exit 1
fi
: > "$RC_FAKE_LOGIND/linger"
""",
    # RC_FAKE_SCOPE marks a tmux server started here; the ssh shim spares it at logout.
    "systemd-run": """#!/bin/sh
if [ -e "$RC_FAKE_LOGIND/no-user-manager" ]; then
    echo "Failed to connect to bus: No medium found" >&2
    exit 1
fi
while [ "${1#-}" != "$1" ]; do shift; done
RC_FAKE_SCOPE=1 exec "$@"
""",
    "pkcheck": '#!/bin/sh\n[ ! -e "$RC_FAKE_LOGIND/deny" ]\n',
}


@pytest.fixture
def box(tmp_path, monkeypatch, tmux_tmpdir):  # The shim runs tmux at logout.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, text in {"ssh": SSH_SHIM, **FAKE_LOGIND}.items():
        script = bin_dir / name
        script.write_text(text)
        script.chmod(0o755)
    (tmp_path / "logind").mkdir()
    # Else box tests read, and may enable linger on, the host's logind.
    monkeypatch.setenv("RC_FAKE_LOGIND", str(tmp_path / "logind"))
    monkeypatch.setenv("RC_FAKE_SSH_LOG", str(tmp_path / "ssh.log"))
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.delenv("RSYNC_RSH", raising=False)
    root = tmp_path / "box"
    root.mkdir()
    return root


@pytest.fixture
def logind(box):
    return box.parent / "logind"


@pytest.fixture
def ssh_log(box):
    return box.parent / "ssh.log"


@pytest.fixture
def laptop(tmp_path):
    d = tmp_path / "laptop"
    d.mkdir()
    return d


@functools.cache
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


@pytest.fixture
def tmux_tmpdir(monkeypatch):
    # Short path: the socket must fit in sun_path (104 bytes on macOS).
    tmpdir = tempfile.mkdtemp(prefix="rc-tmux-")
    monkeypatch.setenv("TMUX_TMPDIR", tmpdir)
    # Else tmux talks to the developer's server.
    monkeypatch.delenv("TMUX", raising=False)
    yield
    if shutil.which("tmux"):
        subprocess.run(["tmux", "kill-server"], capture_output=True)
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def tmux_server(tmux_tmpdir):
    if not _tmux_can_run():
        pytest.skip("needs tmux and a pty")


@functools.cache
def _has_gnu_rsync():
    if not shutil.which("rsync"):
        return False
    out = subprocess.run(["rsync", "--version"], capture_output=True, text=True).stdout
    return out.startswith("rsync  version 3")


@pytest.fixture
def gnu_rsync():
    # openrsync (macOS) lacks per-directory merge filters; Windows has no rsync.
    if not _has_gnu_rsync():
        pytest.skip("needs GNU rsync 3.x")


def _wait_until(predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            return False
        time.sleep(0.05)
    return True


@pytest.fixture
def wait_until():
    return _wait_until


class PtyProcess:
    """A child on a pty, as a terminal user runs it; its output is kept."""

    def __init__(self, argv, cwd=None):
        self.fd, child_fd = os.openpty()
        self.proc = subprocess.Popen(
            argv,
            stdin=child_fd,
            stdout=child_fd,
            stderr=child_fd,
            cwd=cwd,
            env={**os.environ, "TERM": "xterm"},
        )
        os.close(child_fd)
        self._chunks = []
        # Unread output fills the pty buffer and blocks tmux.
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()

    def _read(self):
        try:
            while chunk := os.read(self.fd, 1024):
                self._chunks.append(chunk)
        except OSError:  # EIO once the child side closes
            pass

    @property
    def output(self) -> str:
        return b"".join(self._chunks).decode(errors="replace")

    def wait(self, timeout=30) -> int:
        code = self.proc.wait(timeout=timeout)
        self._reader.join(timeout=5)
        return code

    def close(self):
        self.proc.kill()
        self.wait()
        os.close(self.fd)


@pytest.fixture
def spawn_in_pty():
    started = []

    def spawn(argv, cwd=None):
        started.append(PtyProcess(argv, cwd))
        return started[-1]

    yield spawn
    for child in started:
        child.close()
