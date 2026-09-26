import posixpath
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ricecooker.exceptions import RemoteTransportError

BOOKKEEPING_DIR = ".ricecooker-remote"
VENV_DIR = ".venv"

# --exclude, not --filter=P: P still uploads a local copy and deletes inside it.
# Anchored to the chef root: a nested pkg/storage/ is chef code.
BOX_MANAGED = (
    VENV_DIR,
    BOOKKEEPING_DIR,
    "storage",
    "restore",
    "chefdata",
    "logs",
)


def remote_chef_dir(profile) -> str:
    return posixpath.join(profile.remote_root, profile.name)


def sync_argv(profile, chef_dir) -> list:
    return (
        # --delete-after: the receiver applies its own .gitignore, stale under delete-during.
        ["rsync", "-a", "--delete", "--delete-after", "--filter=:- .gitignore"]
        + [f"--exclude=/{d}/" for d in BOX_MANAGED]
        # P <dir>/ guards only the entry: rsync deletes inside it once the laptop has the dir.
        + [
            f"--filter=P {q}"
            for p in profile.protect
            for q in (p, p.rstrip("/") + "/**")
        ]
        + [f"--exclude={p}" for p in profile.exclude]
        + [f"{chef_dir}/", f"{profile.ssh}:{remote_chef_dir(profile)}/"]
    )


def pull_argv(profile, remote_path, dest) -> list:
    source = posixpath.join(remote_chef_dir(profile), remote_path)
    return ["rsync", "-a", f"{profile.ssh}:{source}", str(dest)]


def ssh_argv(profile, command, tty=False) -> list:
    return ["ssh"] + (["-t"] if tty else []) + [profile.ssh, shlex.join(command)]


@dataclass(frozen=True)
class RunResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


def subprocess_runner(argv, capture, input=None) -> RunResult:
    try:
        proc = subprocess.run(argv, capture_output=capture, text=True, input=input)
    except FileNotFoundError:
        raise RemoteTransportError(
            f"remote: '{argv[0]}' is not installed on this machine"
        )
    return RunResult(proc.returncode, proc.stdout or "", proc.stderr or "")


class Transport:
    """runner: any callable (argv: list[str], capture: bool, input: str | None) -> RunResult."""

    def __init__(self, profile, chef_dir=None, runner=subprocess_runner):
        self.profile = profile
        self.chef_dir = Path.cwd() if chef_dir is None else Path(chef_dir)
        self.runner = runner

    def sync(self) -> RunResult:
        return self._rsync(sync_argv(self.profile, self.chef_dir))

    def pull(self, remote_path, dest=".") -> RunResult:
        return self._rsync(pull_argv(self.profile, remote_path, dest))

    def ssh(self, command, tty=False, input=None) -> RunResult:
        return self.runner(
            ssh_argv(self.profile, command, tty), capture=not tty, input=input
        )

    def _rsync(self, argv) -> RunResult:
        result = self.runner(argv, capture=True)
        if result.returncode:
            raise RemoteTransportError(
                f"remote: rsync exited {result.returncode}\n{result.stderr}"
            )
        return result
