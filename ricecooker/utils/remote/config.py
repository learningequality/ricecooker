from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ricecooker.exceptions import RemoteConfigError

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib


CHEF_CONFIG_FILENAME = ".ricecooker-remote.toml"
DEFAULT_GLOBAL_CONFIG_PATH = Path.home() / ".config" / "ricecooker" / "remote.toml"
RICECOOKER_SOURCES = (None, "local")


@dataclass
class HostProfile:
    ssh: str
    remote_root: str
    ricecooker_source: Optional[str] = None


@dataclass
class ChefConfig:
    name: str
    protect: list
    exclude: list


@dataclass
class GlobalConfig:
    profiles: dict[str, HostProfile]
    default: Optional[str]


@dataclass
class RemoteProfile:
    ssh: str
    remote_root: str
    name: str
    protect: list
    exclude: list
    ricecooker_source: Optional[str] = None


def _read_toml(path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def load_global_config(path) -> GlobalConfig:
    path = Path(path)
    if not path.exists():
        return GlobalConfig(profiles={}, default=None)
    data = _read_toml(path)
    default = data.pop("default", None)
    profiles = {}
    for name, table in data.items():
        if not isinstance(table, dict):
            continue
        source = table.get("ricecooker_source")
        if source not in RICECOOKER_SOURCES:
            raise RemoteConfigError(
                f'remote: profile "{name}" in {path} has ricecooker_source = '
                f'{source!r}; the only supported value is "local".'
            )
        profiles[name] = HostProfile(
            ssh=table["ssh"],
            remote_root=table["remote_root"],
            ricecooker_source=source,
        )
    return GlobalConfig(profiles=profiles, default=default)


def load_chef_config(chef_dir) -> ChefConfig:
    chef_dir = Path(chef_dir)
    basename = chef_dir.resolve().name
    path = chef_dir / CHEF_CONFIG_FILENAME
    if not path.exists():
        return ChefConfig(name=basename, protect=[], exclude=[])
    data = _read_toml(path)
    return ChefConfig(
        name=data.get("name") or basename,
        protect=data.get("protect", []),
        exclude=data.get("exclude", []),
    )


def relative_script(script, chef_dir) -> str:
    try:
        relative = Path(script).resolve().relative_to(Path(chef_dir).resolve())
    except ValueError:
        raise RemoteConfigError(
            f"remote: {script} is outside the chef dir {chef_dir}; "
            "only the chef dir is synced to the box."
        )
    return relative.as_posix()


def resolve_profile(
    script, remote=None, chef_dir=None, global_path=None
) -> RemoteProfile:
    chef_dir = Path.cwd() if chef_dir is None else Path(chef_dir)
    global_path = DEFAULT_GLOBAL_CONFIG_PATH if global_path is None else global_path

    gc = load_global_config(global_path)
    host_name = remote or gc.default

    if host_name is None:
        raise RemoteConfigError(
            "remote: no host selected. Pass --remote=<name> or add a top-level "
            f'"default" to {global_path}. Example config:\n\n'
            'default = "mybox"\n\n'
            "[mybox]\n"
            'ssh = "user@host"\n'
            'remote_root = "/home/user/chefs"\n'
        )

    if host_name not in gc.profiles:
        known = ", ".join(sorted(gc.profiles)) or "(none)"
        raise RemoteConfigError(
            f'remote: no profile named "{host_name}" in {global_path}. '
            f"Known profiles: {known}."
        )

    host = gc.profiles[host_name]
    chef = load_chef_config(chef_dir)
    script_name = (
        relative_script(script, chef_dir).removesuffix(".py").replace("/", "-")
    )
    return RemoteProfile(
        ssh=host.ssh,
        remote_root=host.remote_root,
        name=f"{chef.name}-{script_name}",
        protect=chef.protect,
        exclude=chef.exclude,
        ricecooker_source=host.ricecooker_source,
    )
