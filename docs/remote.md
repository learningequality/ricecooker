Running chefs on a remote box
=============================
`python chef.py --remote …` syncs the chef dir to a box over `ssh`, runs the chef
there in `tmux`, and attaches your terminal to it.


Laptop setup
------------
The laptop needs `ssh` and GNU rsync 3.x. macOS ships openrsync, which lacks
per-directory filters, so run `brew install rsync`. Windows is unsupported.

Add a profile per box to `~/.config/ricecooker/remote.toml`:

    default = "mybox"

    [mybox]
    ssh = "user@host"             # or a ~/.ssh/config alias
    remote_root = "/home/user/chefs"
    # ricecooker_source = "local"   # run this laptop's ricecooker checkout, not the released one


Box setup
---------
The box needs `rsync`, `uv`, `tmux` 3.1+, `base64`, and the chef's own dependencies
(see [Installation](installation.md)).

Box secrets go in `~/.config/ricecooker/remote-env` on the box as `KEY=VALUE` lines,
sourced by `sh`. Runs are refused if group or others can access it:

    mkdir -p ~/.config/ricecooker
    echo 'STUDIO_TOKEN=...' > ~/.config/ricecooker/remote-env
    chmod 600 ~/.config/ricecooker/remote-env

On a box whose logind kills a user's processes at logout (`KillUserProcesses=yes`), a
run outlives its ssh connection only while the user lingers. `--remote` enables that
with `loginctl enable-linger` on its first run. Where the box's polkit forbids it, runs
are refused until an admin runs, once:

    sudo loginctl enable-linger <user>

*Checklist*: run `python chef.py remote doctor` from the chef dir.


Per-chef config
---------------
An optional `.ricecooker-remote.toml` in the chef dir:

    name = "my-chef"            # box dir under remote_root; defaults to the chef dir's name
    protect = ["/data/"]        # never deleted on the box; a laptop copy still overwrites it
    exclude = ["/scratch/"]     # never uploaded

Files matched by `.gitignore` are skipped. `.venv`, `.ricecooker-remote`, `storage`,
`restore`, `chefdata` and `logs` never sync; fetch them with `remote pull`.


Running a chef
--------------
Run from the chef dir; the cwd is what syncs, and a chef script outside it is refused.

    python chef.py --remote[=NAME] [--env KEY=VALUE] [--env-pass KEY] [chef args]

  - `--env KEY=VALUE` sets KEY; `--env-pass KEY` forwards KEY from your environment.
    Both override the box's `remote-env`.
  - `--token`, or else the laptop's `STUDIO_TOKEN`, is forwarded; with neither, the
    box's `STUDIO_TOKEN` applies. The client never prompts.
  - The venv comes from `pyproject.toml` (`uv sync`), else `requirements.txt`
    (`uv pip install -r`), else the shared `<remote_root>/.default-venv` with released
    ricecooker. It is rebuilt only when that manifest changes.
  - A start that would rebuild `.default-venv` or re-sync `.ricecooker-src` is refused
    while another chef under `remote_root` runs.
  - Each chef has one run at a time: re-running while it is live attaches instead.
  - Detach with `Ctrl-b d`; `Ctrl-C` interrupts the chef.
  - The client prints the log paths and exits with the chef's exit code, or 0 on detach.
  - All chefs on a box share the file cache at `<remote_root>/.ricecookerfilecache`.


`remote` subcommands
--------------------
Run as `python chef.py remote <command>`; `remote` must be the first argument.
Every command takes `--remote NAME`.

  - `attach`: attach to the chef's session.
  - `sync`: sync the chef dir; refused while a run is live.
  - `pull <remote-path> [dest]`: copy a path relative to the box's chef dir to `dest` (default `.`).
  - `shell`: open a login shell in the box's chef dir.
  - `cache info`: show the shared file cache's path, entry count and size.
  - `cache clear`: delete the shared file cache; refused while any chef under `remote_root` runs.
  - `doctor`: report which box dependencies are missing, whether `remote-env` is readable by other users, whether the chef runs in the shared default venv, and whether runs would die at logout.
