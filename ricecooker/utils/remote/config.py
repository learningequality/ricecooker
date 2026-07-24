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


@dataclass
class HostProfile:
    ssh: str
    remote_root: str


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


def _read_toml(path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def load_global_config(path) -> GlobalConfig:
    path = Path(path)
    if not path.exists():
        return GlobalConfig(profiles={}, default=None)
    data = _read_toml(path)
    default = data.pop("default", None)
    profiles = {
        name: HostProfile(ssh=table["ssh"], remote_root=table["remote_root"])
        for name, table in data.items()
        if isinstance(table, dict)
    }
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


def resolve_profile(remote=None, chef_dir=None, global_path=None) -> RemoteProfile:
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
    return RemoteProfile(
        ssh=host.ssh,
        remote_root=host.remote_root,
        name=chef.name,
        protect=chef.protect,
        exclude=chef.exclude,
    )
