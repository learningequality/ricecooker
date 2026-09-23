import os

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
