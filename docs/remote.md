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
Each chef script gets its own box dir under `remote_root`, tmux session and venv, named
`<name>-<script path>` with `.py` dropped and `/` as `-`: from `library/`,
`scripts/a/chef.py` is `library-scripts-a-chef`.

An optional `.ricecooker-remote.toml` in the chef dir:

    name = "my-chef"            # first part of each script's name; defaults to the chef dir's name
    protect = ["/data/"]        # never deleted on the box; a laptop copy still overwrites it
    exclude = ["/scratch/"]     # never uploaded

Files matched by `.gitignore` are skipped. `.venv`, `.ricecooker-remote`, `storage`,
`restore`, `chefdata` and `logs` never sync; fetch all but `storage` with `remote pull`.


Running a chef
--------------
Run from the chef dir; the cwd is what syncs, and a chef script outside it is refused.

    python chef.py --remote[=NAME] [--detach] [--env KEY=VALUE] [--env-pass KEY] [chef args]

  - `--detach` starts the run and exits 0 without attaching, with or without a terminal.
    The chef's stdin is `/dev/null`, so a prompt (token, Studio version) fails the run; `--prompt` is refused.
    `getpass` reads the pane, not stdin, so it still blocks until you attach.
  - `--env KEY=VALUE` sets KEY; `--env-pass KEY` forwards KEY from your environment.
    Both override the box's `remote-env`.
  - `--token`, or else the laptop's `STUDIO_TOKEN`, is forwarded; with neither, the
    box's `STUDIO_TOKEN` applies. The client never prompts.
  - The venv comes from `pyproject.toml` (`uv sync`), else `requirements.txt`
    (`uv pip install -r`), else the shared `<remote_root>/.default-venv` with released
    ricecooker. It is rebuilt only when that manifest changes.
  - A start that would rebuild `.default-venv` or re-sync `.ricecooker-src` is refused
    while another chef under `remote_root` runs.
  - Each script has one run at a time: re-running while it is live attaches instead,
    or with `--detach` exits 0 and leaves the run untouched.
  - Detach with `Ctrl-b d`; `Ctrl-C` interrupts the chef.
  - A laptop `TERM` the box has no terminfo for (e.g. Ghostty's `xterm-ghostty`) attaches as `xterm-256color`.
  - The client prints the log paths and exits with the chef's exit code, or 0 on `Ctrl-b d`; after `--detach`, `remote status` prints them.
  - All chefs on a box share the file cache at `<remote_root>/.ricecookerfilecache` and downloads
    at `<remote_root>/.ricecooker-storage`, so a file one chef downloaded is reused by the others without a fetch.


`remote` subcommands
--------------------
Run as `python chef.py remote <command>`; `remote` must be the first argument.
Every command takes `--remote NAME`.

  - `attach`: attach to the script's session.
  - `status`: print the script's run state, Studio link and log paths; a chef run with
    `--warn` or `--quiet` logs no link. Exits `0` finished ok,
    `3` running, `4` finished failed (or without an exit code), `5` no run,
    `1` an error.
  - `sync`: sync the chef dir to the script's box dir; refused while a run is live.
  - `pull <remote-path> [dest]`: copy a path relative to the script's box dir to `dest` (default `.`).
  - `shell`: open a login shell in the script's box dir.
  - `cache info`: show the shared file cache's and storage's paths, entry counts and sizes.
  - `cache clear`: delete the shared file cache and storage; refused while any chef under `remote_root` runs.
  - `doctor`: report which box dependencies are missing, whether `remote-env` is readable by other users, whether the chef runs in the shared default venv, and whether runs would die at logout.
