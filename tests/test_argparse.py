import sys

import pytest
from mock import patch

from ricecooker.chefs import SushiChef
from ricecooker.exceptions import InvalidUsageException


@pytest.fixture
def cli_args_and_expected():
    defaults = {
        "command": "uploadchannel",
        "update": False,
        "verbose": True,
        "debug": False,
        "warn": False,
        "quiet": False,
        "compress": False,
        "thumbnails": False,
        "download_attempts": 3,
        "prompt": False,
        "reset_deprecated": False,
        "stage": True,
        "stage_deprecated": False,
        "publish": False,
        "sample": None,
    }
    return [
        {  # this used to be the old recommended CLI args to run chefs
            "cli_input": "./sushichef.py -v --reset --token=letoken",
            "expected_args": dict(defaults, token="letoken", reset_deprecated=True),
            "expected_options": {},
        },
        {  # nowadays we've changed the CLI defaults so don't need to specify these
            "cli_input": "./sushichef.py --token=letoken",
            "expected_args": dict(defaults, token="letoken"),
            "expected_options": {},
        },
        {
            "cli_input": "./sushichef.py --token=letoken lang=fr",
            "expected_args": dict(defaults, token="letoken"),
            "expected_options": dict(lang="fr"),
        },
        {
            "cli_input": "./sushichef.py --token=letoken somethin=else extrakey=extraval",
            "expected_args": dict(defaults, token="letoken"),
            "expected_options": dict(somethin="else", extrakey="extraval"),
        },
        {
            "cli_input": (
                "./sushichef.py -uv --warn --compress --download-attempts=4 "
                "--token=besttokenever --prompt --deploy --publish"
            ),
            "expected_args": dict(
                defaults,
                update=True,
                warn=True,
                compress=True,
                download_attempts=4,
                token="besttokenever",
                prompt=True,
                stage=False,
                publish=True,
            ),
            "expected_options": {},
        },
    ]


def chef_arg_parser(cli_input):
    """
    Takes a string `cli_input` and parses it using the SushiChef arg parser.
    Returns tuple of args and options.
    """
    test_argv = cli_input.split(" ")
    with patch.object(sys, "argv", test_argv):
        chef = SushiChef()
        args, options = chef.parse_args_and_options()
    assert args is not None, "argparse parsing failed"
    return args, options


""" *********** CLI ARGUMENTS TESTS *********** """


def test_basic_command_line_args_and_options(cli_args_and_expected):
    for case in cli_args_and_expected:
        cli_input = case["cli_input"]
        expected_args = case["expected_args"]
        expected_options = case["expected_options"]

        args, options = chef_arg_parser(cli_input)

        # print('observed', args, options)
        # print('expected', expected_args, expected_options)

        for arg, val in expected_args.items():
            assert args[arg] == val
        for opt, val in expected_options.items():
            assert options[opt] == val


def test_cannot_publish_without_deploy():
    bad_cli_input = "./sushichef.py --token=letoken --publish"
    with pytest.raises(InvalidUsageException):
        args, options = chef_arg_parser(bad_cli_input)

    good_cli_input = "./sushichef.py --token=letoken --deploy --publish"
    args, options = chef_arg_parser(good_cli_input)
    assert not args["stage"]
    assert args["publish"]


""" *********** --remote HAND-OFF TESTS *********** """


@pytest.fixture
def studio_token(monkeypatch):
    # Keeps the local uploadchannel path from prompting for a token.
    monkeypatch.setenv("STUDIO_TOKEN", "env-tok")


@pytest.fixture
def handed_off(monkeypatch, studio_token):
    calls = []

    def record(argv, env, remote=None):
        calls.append((argv, env, remote))
        return 7

    def run(self, args, options):
        raise AssertionError("chef ran locally")

    monkeypatch.setattr("ricecooker.chefs.run_remotely", record)
    monkeypatch.setattr(SushiChef, "run", run)
    return calls


def run_main(cli_input):
    with patch.object(sys, "argv", cli_input.split(" ")):
        with pytest.raises(SystemExit) as exit_info:
            SushiChef().main()
    return exit_info.value.code


@pytest.mark.parametrize(
    "cli_input,remote,command",
    [
        ("./chef.py --remote uploadchannel", "", "uploadchannel"),
        ("./chef.py --remote=box dryrun", "box", "dryrun"),
        ("./chef.py --token=t", None, "uploadchannel"),
    ],
)
def test_remote_takes_a_name_only_after_equals(
    studio_token, cli_input, remote, command
):
    args, _ = chef_arg_parser(cli_input)
    assert (args["remote"], args["command"]) == (remote, command)


@pytest.mark.parametrize("flag", ["--env novalue", "--env 1A=x", "--env-pass A;B"])
def test_bad_env_values_are_rejected(studio_token, flag):
    with pytest.raises(SystemExit):
        chef_arg_parser(f"./chef.py --remote {flag}")


def test_env_flags_without_remote_are_usage_errors(studio_token):
    with pytest.raises(InvalidUsageException):
        chef_arg_parser("./chef.py --token=t --env A=1")


def test_main_hands_remote_run_off_without_running_chef(
    handed_off, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert run_main("./chef.py --remote dryrun") == 7
    assert len(handed_off) == 1
    assert not (tmp_path / "logs").exists()


def test_remote_hand_off_strips_client_flags_and_carries_env(handed_off, monkeypatch):
    monkeypatch.setenv("B", "from-laptop")
    run_main(
        "./chef.py --remote=box --token abc --env A=1 --env-pass=B -u dryrun lang=fr"
    )
    [(argv, env, remote)] = handed_off
    assert argv == ["./chef.py", "-u", "dryrun", "lang=fr"]
    assert env == {"STUDIO_TOKEN": "abc", "A": "1", "B": "from-laptop"}
    assert remote == "box"


def test_remote_hand_off_strips_abbreviated_client_flags(handed_off, monkeypatch):
    monkeypatch.setenv("B", "from-laptop")
    run_main("./chef.py --tok abc --env-p=B --remo dryrun")
    [(argv, env, remote)] = handed_off
    assert argv == ["./chef.py", "dryrun"]
    assert env == {"STUDIO_TOKEN": "abc", "B": "from-laptop"}
    assert remote is None


def test_remote_token_file_forwards_contents(handed_off, tmp_path):
    token_file = tmp_path / "token.txt"
    token_file.write_text("file-tok\n")
    run_main(f"./chef.py --remote --token={token_file}")
    [(argv, env, _)] = handed_off
    assert env["STUDIO_TOKEN"] == "file-tok"
    assert not any(str(token_file) in a for a in argv)


def test_remote_never_prompts_for_token(handed_off, monkeypatch):
    monkeypatch.delenv("STUDIO_TOKEN", raising=False)
    monkeypatch.delenv("CONTENT_CURATION_TOKEN", raising=False)

    def no_prompt(*args):
        raise AssertionError("prompted for token")

    monkeypatch.setattr("builtins.input", no_prompt)
    run_main("./chef.py --remote")
    [(_, env, _)] = handed_off
    assert "STUDIO_TOKEN" not in env


def test_env_pass_of_unset_variable_is_usage_error(handed_off, monkeypatch):
    monkeypatch.delenv("NOPE", raising=False)
    with pytest.raises(InvalidUsageException):
        run_main("./chef.py --remote --env-pass NOPE")
