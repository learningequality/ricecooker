import ast
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ricecooker.exceptions import RemoteTransportError
from ricecooker.utils.remote import transport
from ricecooker.utils.remote.config import RemoteProfile
from ricecooker.utils.remote.transport import RunResult
from ricecooker.utils.remote.transport import subprocess_runner
from ricecooker.utils.remote.transport import Transport


def _has_gnu_rsync():
    if not shutil.which("rsync"):
        return False
    out = subprocess.run(["rsync", "--version"], capture_output=True, text=True).stdout
    return out.startswith("rsync  version 3")


# openrsync (macOS) lacks per-directory merge filters; Windows has no rsync.
needs_rsync = pytest.mark.skipif(not _has_gnu_rsync(), reason="needs GNU rsync 3.x")
needs_sh = pytest.mark.skipif(os.name == "nt", reason="ssh shim needs sh")


SSH_SHIM = """#!/bin/sh
# Plays the box locally: drop ssh options and the host, run the command like sshd.
while [ "${1#-}" != "$1" ]; do shift; done
shift
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


def make_transport(box, chef_dir, protect=(), exclude=()):
    profile = RemoteProfile(
        ssh="box",
        remote_root=str(box),
        name="my-chef",
        protect=list(protect),
        exclude=list(exclude),
    )
    return Transport(profile, chef_dir=chef_dir)


def write(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def tree(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


@needs_rsync
def test_sync_mirrors_chef_dir_into_remote_chef_dir(box, laptop):
    write(laptop / "chef.py", "new!")
    write(laptop / "pkg" / "mod.py")
    write(box / "my-chef" / "chef.py", "old")
    write(box / "my-chef" / "stale.py")
    write(box / "my-chef" / "chefdata" / "tree.json")
    make_transport(box, laptop).sync()
    assert tree(box / "my-chef") == ["chef.py", "chefdata/tree.json", "pkg/mod.py"]
    assert (box / "my-chef" / "chef.py").read_text() == "new!"
    assert tree(laptop) == ["chef.py", "pkg/mod.py"]


@needs_rsync
def test_sync_neither_uploads_nor_deletes_box_managed_dirs(box, laptop):
    for managed in transport.BOX_MANAGED:
        write(laptop / managed / "laptop-only")
        write(box / "my-chef" / managed / "box-only")
    make_transport(box, laptop).sync()
    assert tree(box / "my-chef") == sorted(
        f"{m}box-only" for m in transport.BOX_MANAGED
    )


@needs_rsync
def test_sync_skips_gitignored_and_keeps_box_copy(box, laptop):
    write(laptop / ".gitignore", "*.log\n")
    write(laptop / "debug.log")
    write(box / "my-chef" / "run.log")
    make_transport(box, laptop).sync()
    assert tree(box / "my-chef") == [".gitignore", "run.log"]


@needs_rsync
def test_sync_newly_gitignored_box_dir_survives(box, laptop):
    write(laptop / ".gitignore", "")
    make_transport(box, laptop).sync()
    write(box / "my-chef" / "secrets" / "key")
    write(laptop / ".gitignore", "secrets/\n")
    make_transport(box, laptop).sync()
    assert (box / "my-chef" / "secrets" / "key").exists()


@needs_rsync
def test_sync_protect_keeps_box_copy_and_exclude_skips_upload(box, laptop):
    write(laptop / "credentials.json", "laptop")
    write(laptop / "scratch.tmp")
    write(box / "my-chef" / "credentials.json", "box")
    write(box / "my-chef" / "secrets" / "key")
    t = make_transport(
        box, laptop, protect=["credentials.json", "secrets/"], exclude=["*.tmp"]
    )
    t.sync()
    assert tree(box / "my-chef") == ["credentials.json", "secrets/key"]


@needs_rsync
def test_sync_default_chef_dir_is_cwd(box, laptop, monkeypatch):
    write(laptop / "chef.py")
    monkeypatch.chdir(laptop)
    make_transport(box, None).sync()
    assert tree(box) == ["my-chef/chef.py"]


@needs_rsync
def test_pull_fetches_path_relative_to_remote_chef_dir(box, laptop):
    write(box / "my-chef" / "chefdata" / "trees" / "a.json", "tree")
    make_transport(box, laptop).pull("chefdata/trees", laptop / "out")
    assert (laptop / "out" / "trees" / "a.json").read_text() == "tree"


@needs_rsync
def test_rsync_failure_raises_with_rsync_stderr(box, laptop):
    with pytest.raises(RemoteTransportError) as exc:
        make_transport(box, laptop).pull("nope", laptop / "out")
    assert str(exc.value).startswith("remote:")
    assert "rsync:" in str(exc.value)


@needs_sh
def test_ssh_args_reach_remote_shell_intact(box, laptop):
    result = make_transport(box, laptop).ssh(
        ["printf", "%s|", "a b", "it's", "$HOME", "x;y"]
    )
    assert result.stdout == "a b|it's|$HOME|x;y|"


@needs_sh
def test_ssh_tty_leaves_terminal_attached(box, laptop):
    assert make_transport(box, laptop).ssh(
        ["printf", "attached"], tty=True
    ) == RunResult(0)


@needs_sh
def test_ssh_nonzero_is_returned_not_raised(box, laptop):
    assert make_transport(box, laptop).ssh(["sh", "-c", "exit 1"]).returncode == 1


def test_subprocess_runner_captures_streams_and_exit_code():
    code = "import sys; sys.stdout.write('out'); sys.stderr.write('err'); sys.exit(3)"
    result = subprocess_runner([sys.executable, "-c", code], capture=True)
    assert result == RunResult(3, "out", "err")


def test_subprocess_runner_missing_binary_is_remote_error():
    with pytest.raises(RemoteTransportError) as exc:
        subprocess_runner(["ricecooker-no-such-binary-xyz"], capture=True)
    assert str(exc.value).startswith("remote:")
    assert "ricecooker-no-such-binary-xyz" in str(exc.value)


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
