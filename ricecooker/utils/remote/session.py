import posixpath
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from shlex import quote
from typing import Optional

from ricecooker.exceptions import RemoteSessionError
from ricecooker.utils.remote.transport import BOOKKEEPING_DIR
from ricecooker.utils.remote.transport import remote_chef_dir

NO_SESSION = "none"
LIVE = "live"
FINISHED = "finished"
SESSION_PREFIX = "ricecooker-"
NOT_A_TTY = 64  # sysexits EX_USAGE; distinct from tmux (1) and ssh (255) failures

# sh -c script; args: <bookkeeping dir> <tmux target> <command...>.
# Cleared here, not before new-session: a refused duplicate create must not
# erase a finished pane's code.
# `trap : INT` keeps this shell alive through Ctrl-C; the command still gets SIGINT.
# Write-then-rename so status() never reads a half-written file.
RECORD_EXIT = (
    'd=$1 t=$2; shift 2; mkdir -p "$d"; rm -f "$d/exitcode"; trap : INT; "$@"; '
    'rc=$?; echo $rc > "$d/exitcode.tmp"; mv "$d/exitcode.tmp" "$d/exitcode"; '
    # After the mv: a returning attach is the driver's cue to read exitcode.
    # Fails with no client attached; the pane must still exit with the code.
    'tmux detach-client -s "$t" 2>/dev/null; exit $rc'
)

# sh -c script; args: <command...>. ssh -t sends the laptop's TERM, and tmux
# won't attach under one the box has no terminfo for.
KNOWN_TERM = 'infocmp "$TERM" >/dev/null 2>&1 || export TERM=xterm-256color; exec "$@"'

# Tab-separated: a chef dir may contain spaces.
LIVE_PANES = "#{session_name}\t#{session_path}\t#{pane_dead}"


@dataclass(frozen=True)
class SessionStatus:
    state: str
    started: Optional[datetime] = None
    exit_code: Optional[int] = None


def tmux_quote(arg) -> str:
    # Nothing expands in tmux's '...', but a newline there drops the next line's
    # indent and can start a comment.
    return "'" + arg.replace("'", "'\"'\"'").replace("\n", "'\"\\n\"'") + "'"


def session_name(profile) -> str:
    # tmux 3.1+ rewrites "." and ":" in session names to "_"; 3.0 rejects them.
    return SESSION_PREFIX + re.sub(r"[.:]", "_", profile.name)


def live_chefs(transport) -> list:
    """Chefs with a live run under the profile's remote_root; all share its
    file cache, default venv and ricecooker source."""
    # 1: no tmux server.
    result = transport.ssh(["tmux", "list-panes", "-a", "-F", LIVE_PANES])
    if result.returncode not in (0, 1):
        raise RemoteSessionError(
            f"remote: tmux exited {result.returncode}\n{result.stderr}"
        )
    root = posixpath.normpath(transport.profile.remote_root)
    chefs = []
    for line in result.stdout.splitlines():
        name, path, dead = line.split("\t")
        path = posixpath.normpath(path)
        if (
            name.startswith(SESSION_PREFIX)
            and dead != "1"
            and posixpath.dirname(path) == root
        ):
            chefs.append(posixpath.basename(path))
    return sorted(set(chefs))


class Session:
    def __init__(self, transport):
        self.transport = transport
        self.name = session_name(transport.profile)
        self.chef_dir = remote_chef_dir(transport.profile)
        self.bookkeeping_dir = posixpath.join(self.chef_dir, BOOKKEEPING_DIR)
        self.log_path = posixpath.join(self.bookkeeping_dir, "session.log")
        # "=": exact match, or "ricecooker-foo" finds "ricecooker-foobar".
        self.target = f"={self.name}:"

    def create(self, command, env=None, launcher=()) -> None:
        bookkeeping, log = quote(self.bookkeeping_dir), quote(self.log_path)
        commands = [
            [
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
                self.target,
                *command,
            ],
            ["set-option", "-t", self.target, "remain-on-exit", "on"],
            *(
                ["set-environment", "-t", self.target, key, value]
                for key, value in (env or {}).items()
            ),
            # Run by /bin/sh; this mkdir races the pane's own.
            [
                "pipe-pane",
                "-t",
                self.target,
                f"mkdir -p {bookkeeping} && exec cat > {log}",
            ],
        ]
        # On stdin: the tmux server keeps the argv of the client that started it,
        # and ps shows that to every user on the box.
        # One line, run before tmux serves another client: the command can't read
        # show-environment before the env is set, or exit before remain-on-exit.
        # After a failed command (a duplicate session) tmux skips the rest of the
        # line, not the next line.
        script = " ; ".join(" ".join(map(tmux_quote, c)) for c in commands)
        self._ssh(
            *launcher, "tmux", "start-server", ";", "source-file", "-", input=script
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
        return SessionStatus(FINISHED, started=started, exit_code=self.exit_code())

    def exit_code(self) -> Optional[int]:
        # 1: still running, or the recorder died before writing a code.
        code = self._ssh(
            "cat", posixpath.join(self.bookkeeping_dir, "exitcode"), ok=(0, 1)
        )
        return None if code.returncode else int(code.stdout)

    def attach(self) -> int:
        if not sys.stdin.isatty():
            print(
                f"remote: stdin is not a terminal; not attaching to {self.name}",
                file=sys.stderr,
            )
            return NOT_A_TTY
        return self.transport.ssh(
            [
                "sh",
                "-c",
                KNOWN_TERM,
                "sh",
                "tmux",
                "attach-session",
                "-t",
                self.target,
                # A run that ended before this client arrived would hold it.
                ";",
                "if-shell",
                "-F",
                "#{pane_dead}",
                "detach-client",
            ],
            tty=True,
        ).returncode

    def kill(self) -> None:
        # 1: no such session, or no tmux server; already torn down.
        self._ssh("tmux", "kill-session", "-t", self.target, ok=(0, 1))

    def _ssh(self, *argv, ok=(0,), input=None):
        result = self.transport.ssh(list(argv), input=input)
        if result.returncode not in ok:
            raise RemoteSessionError(
                f"remote: {argv[0]} exited {result.returncode}\n{result.stderr}"
            )
        return result
