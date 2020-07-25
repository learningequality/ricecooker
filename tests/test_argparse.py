import pytest
import sys

from mock import patch

from ricecooker.exceptions import InvalidUsageException
from ricecooker.chefs import SushiChef


@pytest.fixture
def cli_args_and_expected():
    defaults = {
        'command': 'uploadchannel',
        'update': False,
        'verbose': True, 'debug': False, 'warn': False, 'quiet': False,
        'compress': False,
        'thumbnails': False,
        'download_attempts': 3,
        'resume': False, 'step': 'LAST', 'prompt': False, 'reset_deprecated': False,
        'stage': True, 'stage_deprecated': False,
        'publish': False,
        'sample': None,
    }
    return [
        {   # this used to be the old recommended CLI args to run chefs
            'cli_input': './sushichef.py -v --reset --token=letoken',
            'expected_args': dict(defaults, token='letoken', reset_deprecated=True),
            'expected_options': {},
        },
        {   # nowadays we've changed the CLI defaults so don't need to specify these
            'cli_input': './sushichef.py --token=letoken',
            'expected_args': dict(defaults, token='letoken'),
            'expected_options': {},
        },
        {
            'cli_input': './sushichef.py --token=letoken --resume --step=START_UPLOAD',
            'expected_args': dict(defaults, token='letoken', resume=True, step='START_UPLOAD'),
            'expected_options': {},
        },
        {
            'cli_input': './sushichef.py --token=letoken lang=fr',
            'expected_args': dict(defaults, token='letoken'),
            'expected_options': dict(lang='fr')
        },
        {
            'cli_input': './sushichef.py --token=letoken somethin=else extrakey=extraval',
            'expected_args': dict(defaults, token='letoken'),
            'expected_options': dict(somethin='else', extrakey='extraval')
        },
        {
            'cli_input': './sushichef.py -uv --warn --compress --download-attempts=4 --token=besttokenever --resume --step=PUBLISH_CHANNEL --prompt --deploy --publish',
            'expected_args': dict(defaults,
                                          update=True,
                                             warn=True, compress=True,
                                                               download_attempts=4,  token='besttokenever', resume=True, step='PUBLISH_CHANNEL',
                                                                                                                                            prompt=True, stage=False, publish=True),
            'expected_options': {}
        },
    ]


def chef_arg_parser(cli_input):
    """
    Takes a string `cli_input` and parses it using the SushiChef arg parser.
    Returns tuple of args and options.
    """
    test_argv = cli_input.split(' ')
    with patch.object(sys, 'argv', test_argv):
        chef = SushiChef()
        args, options = chef.parse_args_and_options()
    assert args is not None, 'argparse parsing failed'
    return args, options



""" *********** CLI ARGUMENTS TESTS *********** """

def test_basic_command_line_args_and_options(cli_args_and_expected):
    for case in cli_args_and_expected:
        cli_input = case['cli_input']
        expected_args = case['expected_args']
        expected_options = case['expected_options']

        args, options = chef_arg_parser(cli_input)

        # print('observed', args, options)
        # print('expected', expected_args, expected_options)

        for arg, val in expected_args.items():
            assert args[arg] == val
        for opt, val in expected_options.items():
            assert options[opt] == val


def test_cannot_publish_without_deploy():
    bad_cli_input = './sushichef.py --token=letoken --publish'
    with pytest.raises(InvalidUsageException):
        args, options = chef_arg_parser(bad_cli_input)

    good_cli_input = './sushichef.py --token=letoken --deploy --publish'
    args, options = chef_arg_parser(good_cli_input)
    assert args['stage'] == False
    assert args['publish'] == True

