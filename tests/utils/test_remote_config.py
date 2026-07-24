import pytest

from ricecooker.exceptions import RemoteConfigError
from ricecooker.utils.remote.config import CHEF_CONFIG_FILENAME
from ricecooker.utils.remote.config import ChefConfig
from ricecooker.utils.remote.config import GlobalConfig
from ricecooker.utils.remote.config import HostProfile
from ricecooker.utils.remote.config import load_chef_config
from ricecooker.utils.remote.config import load_global_config
from ricecooker.utils.remote.config import resolve_profile


def test_load_global_config_parses_profiles_and_default(tmp_path):
    p = tmp_path / "remote.toml"
    p.write_text(
        'default = "box1"\n'
        "\n"
        "[box1]\n"
        'ssh = "myalias"\n'
        'remote_root = "/home/me/chefs"\n'
        "\n"
        "[box2]\n"
        'ssh = "user@host2"\n'
        'remote_root = "/srv/chefs"\n'
    )
    gc = load_global_config(p)
    assert gc.default == "box1"
    assert gc.profiles["box1"] == HostProfile(
        ssh="myalias", remote_root="/home/me/chefs"
    )
    assert gc.profiles["box2"].ssh == "user@host2"


def test_load_global_config_missing_file_is_empty(tmp_path):
    gc = load_global_config(tmp_path / "nope.toml")
    assert gc == GlobalConfig(profiles={}, default=None)


def test_load_chef_config_parses_all_fields(tmp_path):
    d = tmp_path / "my-chef"
    d.mkdir()
    (d / CHEF_CONFIG_FILENAME).write_text(
        'name = "custom-name"\n'
        'protect = ["credentials.json"]\n'
        'exclude = ["*.tmp", "cache/"]\n'
    )
    cc = load_chef_config(d)
    assert cc == ChefConfig(
        name="custom-name", protect=["credentials.json"], exclude=["*.tmp", "cache/"]
    )


def test_load_chef_config_name_defaults_to_basename(tmp_path):
    d = tmp_path / "some-chef-dir"
    d.mkdir()
    cc = load_chef_config(d)
    assert cc.name == "some-chef-dir"
    assert cc.protect == []
    assert cc.exclude == []


def test_load_chef_config_name_default_when_key_omitted(tmp_path):
    d = tmp_path / "chef-x"
    d.mkdir()
    (d / CHEF_CONFIG_FILENAME).write_text('exclude = ["build/"]\n')
    cc = load_chef_config(d)
    assert cc.name == "chef-x"
    assert cc.exclude == ["build/"]


def test_remote_arg_beats_default(tmp_path):
    gp = tmp_path / "remote.toml"
    gp.write_text(
        'default = "box1"\n'
        '[box1]\nssh = "a"\nremote_root = "/one"\n'
        '[box2]\nssh = "b"\nremote_root = "/two"\n'
    )
    chef = tmp_path / "chef"
    chef.mkdir()
    prof = resolve_profile(remote="box2", chef_dir=chef, global_path=gp)
    assert (prof.ssh, prof.remote_root) == ("b", "/two")
    assert prof.name == "chef"


def test_falls_back_to_global_default(tmp_path):
    gp = tmp_path / "remote.toml"
    gp.write_text('default = "box1"\n[box1]\nssh = "a"\nremote_root = "/one"\n')
    chef = tmp_path / "chef"
    chef.mkdir()
    prof = resolve_profile(chef_dir=chef, global_path=gp)
    assert prof.ssh == "a"


def test_resolved_profile_carries_chef_settings(tmp_path):
    gp = tmp_path / "remote.toml"
    gp.write_text('default = "box1"\n[box1]\nssh = "a"\nremote_root = "/one"\n')
    chef = tmp_path / "chef"
    chef.mkdir()
    (chef / CHEF_CONFIG_FILENAME).write_text(
        'name = "cn"\nprotect = ["secret"]\nexclude = ["*.tmp"]\n'
    )
    prof = resolve_profile(chef_dir=chef, global_path=gp)
    assert prof.name == "cn"
    assert prof.protect == ["secret"]
    assert prof.exclude == ["*.tmp"]


def test_no_profile_configured_raises_with_example(tmp_path):
    gp = tmp_path / "remote.toml"
    gp.write_text("")  # no default, no profiles
    with pytest.raises(RemoteConfigError) as exc:
        resolve_profile(chef_dir=tmp_path, global_path=gp)
    msg = str(exc.value)
    assert msg.startswith("remote:")
    assert "remote_root" in msg and "ssh" in msg


def test_unknown_remote_names_missing_profile(tmp_path):
    gp = tmp_path / "remote.toml"
    gp.write_text('[box1]\nssh = "a"\nremote_root = "/one"\n')
    with pytest.raises(RemoteConfigError) as exc:
        resolve_profile(remote="ghost", chef_dir=tmp_path, global_path=gp)
    msg = str(exc.value)
    assert msg.startswith("remote:")
    assert "ghost" in msg


def test_profiles_defined_but_no_default_raises(tmp_path):
    # Profiles exist but nothing selects one → same "no host selected" branch.
    gp = tmp_path / "remote.toml"
    gp.write_text('[box1]\nssh = "a"\nremote_root = "/one"\n')
    with pytest.raises(RemoteConfigError) as exc:
        resolve_profile(chef_dir=tmp_path, global_path=gp)
    assert str(exc.value).startswith("remote:")
