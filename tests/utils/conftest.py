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
# Without -t, sshd gives the command no terminal.
[ -z "$tty" ] && [ -t 0 ] && exec sh -c "$*" </dev/null
exec sh -c "$*"
"""


@pytest.fixture
def box(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    shim = bin_dir / "ssh"
    shim.write_text(SSH_SHIM)
    shim.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.delenv("RSYNC_RSH", raising=False)
    root = tmp_path / "box"
    root.mkdir()
    return root


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
def tmux_server(monkeypatch):
    if not _tmux_can_run():
        pytest.skip("needs tmux and a pty")
    # Short path: the socket must fit in sun_path (104 bytes on macOS).
    tmpdir = tempfile.mkdtemp(prefix="rc-tmux-")
    monkeypatch.setenv("TMUX_TMPDIR", tmpdir)
    # Else tmux talks to the developer's server.
    monkeypatch.delenv("TMUX", raising=False)
    yield
    subprocess.run(["tmux", "kill-server"], capture_output=True)
    shutil.rmtree(tmpdir, ignore_errors=True)


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
