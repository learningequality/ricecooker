import posixpath
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ricecooker.exceptions import RemoteSessionError
from ricecooker.utils.remote.transport import BOOKKEEPING_DIR
from ricecooker.utils.remote.transport import remote_chef_dir

NO_SESSION = "none"
LIVE = "live"
FINISHED = "finished"
NOT_A_TTY = 64  # sysexits EX_USAGE; distinct from tmux (1) and ssh (255) failures

# sh -c script; args: <bookkeeping dir> <command...>.
# Cleared here, not before new-session: a refused duplicate create must not
# erase a finished pane's code.
# `trap : INT` keeps this shell alive through Ctrl-C; the command still gets SIGINT.
# Write-then-rename so status() never reads a half-written file.
RECORD_EXIT = (
    'd=$1; shift; mkdir -p "$d"; rm -f "$d/exitcode"; trap : INT; "$@"; '
    'echo $? > "$d/exitcode.tmp"; mv "$d/exitcode.tmp" "$d/exitcode"'
)


@dataclass(frozen=True)
class SessionStatus:
    state: str
    started: Optional[datetime] = None
    exit_code: Optional[int] = None


def session_name(profile) -> str:
    # tmux 3.1+ rewrites "." and ":" in session names to "_"; 3.0 rejects them.
    return "ricecooker-" + re.sub(r"[.:]", "_", profile.name)


class Session:
    def __init__(self, transport):
        self.transport = transport
        self.name = session_name(transport.profile)
        self.chef_dir = remote_chef_dir(transport.profile)
        self.bookkeeping_dir = posixpath.join(self.chef_dir, BOOKKEEPING_DIR)
        # "=": exact match, or "ricecooker-foo" finds "ricecooker-foobar".
        self.target = f"={self.name}:"

    def create(self, command) -> None:
        # tmux ends a command at any argument ending in ";"; "\;" keeps it literal.
        command = [a[:-1] + "\\;" if a.endswith(";") else a for a in command]
        self._ssh(
            "tmux",
            "new-session",
            "-d",
            "-s",
            self.name,
            "-c",
            self.chef_dir,
            "sh",
            "-c",
            RECORD_EXIT,
            "sh",
            self.bookkeeping_dir,
            *command,
            # Same invocation: a second round trip lets a fast command close the pane.
            ";",
            "set-option",
            "-t",
            self.target,
            "remain-on-exit",
            "on",
        )

    def status(self) -> SessionStatus:
        # 1: no such session, or no tmux server yet. Not display-message: it
        # exits 0 with empty output for a missing target on a running server.
        info = self._ssh(
            "tmux",
            "list-panes",
            "-t",
            self.target,
            "-F",
            "#{session_created} #{pane_dead}",
            ok=(0, 1),
        )
        if info.returncode:
            return SessionStatus(NO_SESSION)
        created, dead = info.stdout.split()[:2]
        started = datetime.fromtimestamp(int(created))
        if dead != "1":
            return SessionStatus(LIVE, started=started)
        # 1: the recorder died before writing a code.
        code = self._ssh(
            "cat", posixpath.join(self.bookkeeping_dir, "exitcode"), ok=(0, 1)
        )
        exit_code = None if code.returncode else int(code.stdout)
        return SessionStatus(FINISHED, started=started, exit_code=exit_code)

    def attach(self) -> int:
        if not sys.stdin.isatty():
            print(
                f"remote: stdin is not a terminal; not attaching to {self.name}",
                file=sys.stderr,
            )
            return NOT_A_TTY
        return self.transport.ssh(
            ["tmux", "attach-session", "-t", self.target], tty=True
        ).returncode

    def kill(self) -> None:
        # 1: no such session, or no tmux server; already torn down.
        self._ssh("tmux", "kill-session", "-t", self.target, ok=(0, 1))

    def _ssh(self, *argv, ok=(0,)):
        result = self.transport.ssh(list(argv))
        if result.returncode not in ok:
            raise RemoteSessionError(
                f"remote: {argv[0]} exited {result.returncode}\n{result.stderr}"
            )
        return result
