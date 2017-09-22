import argparse
import os
import pytest
import sys
import unittest

from docopt import docopt
from mock import patch

from ricecooker.exceptions import InvalidUsageException
from ricecooker.managers.progress import Status
from ricecooker.chefs import BaseChef

FAKE_CHEF_SCRIPT = 'chefs/fake_chef.py'


OLD_DOCOP_SPEC = """Usage: ricecooker uploadchannel [-huv] <file_path> [--warn] [--stage] [--compress] [--token=<t>] [--thumbnails] [--download-attempts=<n>] [--resume [--step=<step>] | --reset] [--prompt] [--publish] [[OPTIONS] ...]

Arguments:
  file_path        Path to file with channel data

Options:
  -h                          Help documentation
  -v                          Verbose mode
  -u                          Re-download files from file paths
  --warn                      Print out warnings to stderr
  --stage                     Stage updates rather than deploying them for manual verification on Kolibri Studio
  --compress                  Compress high resolution videos to low resolution videos
  --thumbnails                Automatically generate thumbnails for topics
  --token=<t>                 Authorization token (can be token or path to file with token) [default: #]
  --download-attempts=<n>     Maximum number of times to retry downloading files [default: 3]
  --resume                    Resume from ricecooker step (cannot be used with --reset flag)
  --step=<step>               Step to resume progress from (must be used with --resume flag) [default: LAST]
  --reset                     Restart session, overwriting previous session (cannot be used with --resume flag)
  --prompt                    Receive prompt to open the channel once it's uploaded
  --publish                   Automatically publish channel once it's been created
  [OPTIONS]                   Extra arguments to add to command line (e.g. key='field')

Steps (for restoring session):
  LAST (default):       Resume where the session left off
  INIT:                 Resume at beginning of session
  CONSTRUCT_CHANNEL:    Resume with call to construct channel
  CREATE_TREE:          Resume at set tree relationships
  DOWNLOAD_FILES:       Resume at beginning of download process
  GET_FILE_DIFF:        Resume at call to get file diff from Kolibri Studio
  START_UPLOAD:         Resume at beginning of uploading files to Kolibri Studio
  UPLOADING_FILES:      Resume at last upload request
  UPLOAD_CHANNEL:       Resume at beginning of uploading tree to Kolibri Studio
  PUBLISH_CHANNEL:      Resume at option to publish channel
  DONE:                 Resume at prompt to open channel

"""

@pytest.fixture
def fake_chef_path():
    testsdir = os.path.dirname(__file__)
    return os.path.join(testsdir, FAKE_CHEF_SCRIPT)

@pytest.fixture
def command_line_inputs(fake_chef_path):
    test_input_templates = [
      'ricecooker uploadchannel {} --token=letoken --resume --step=START_UPLOAD',
      'ricecooker uploadchannel {} --token=letoken --reset somethin=else extrakey=extraval',
      'ricecooker uploadchannel -uv {} --warn --compress --download-attempts=4 --token=besttokenever --resume --step=PUBLISH_CHANNEL --prompt --publish',
      'ricecooker uploadchannel {} -v --compress --token=katoken lang=en',
      'ricecooker uploadchannel {} -v --compress --token=katoken lang=en-us',
      'ricecooker uploadchannel {} -v --compress --token=katoken lang=fr-ca',
      'ricecooker uploadchannel {} -u --compress --token=katoken lang=en-us',
    ]
    test_inputs = [cmdt.format(fake_chef_path) for cmdt in test_input_templates]
    return test_inputs

def old_arguments_parser(cli_input):
    """
    Takes a string `cli_input` and parses it using the `docopt` module.
    Returns tuple of docopt arguments and extra kwargs (now called options).
    """
    test_argv = cli_input.split(' ')
    with patch.object(sys, 'argv', test_argv):
        arguments = docopt(OLD_DOCOP_SPEC)
    assert arguments is not None, 'doc opt parsing failed'

    # Parse OPTIONS for keyword arguments
    kwargs = {}
    for arg in arguments['OPTIONS']:
      try:
        kwarg = arg.split('=')
        kwargs.update({kwarg[0].strip(): kwarg[1].strip()})
      except IndexError:
        raise InvalidUsageException("Invalid kwarg '{0}' found: Must format as [key]=[value] (no whitespace)".format(arg))

    # Check if step is valid (if provided)
    step = arguments['--step']
    all_steps = [s.name for s in Status]
    if step.upper() not in all_steps:
      raise InvalidUsageException("Invalid step '{0}': Valid steps are {1}".format(step, all_steps))
    arguments['--step'] = step

    # Make sure max-retries can be cast as an integer
    try:
      int(arguments['--download-attempts'])
    except ValueError:
      raise InvalidUsageException("Invalid argument: Download-attempts must be an integer.")

    return arguments, kwargs


def arguments_to_args_renames(arguments):
    """
    The doc-opt parsed arguments include the - and -- and certain names are different.
    In order to have an apples-to-apples comparison with the new argparse approach,
    we must rename some of the keys.
    """
    args = {}
    for k, v in arguments.items():
        if k == '--download-attempts':
            args['download_attempts'] = int(v)
        elif k == '-u':
            args['update'] = v
        elif k == '-v':
            args['verbose'] = True # Should default to true
        elif k == '<file_path>':
            args['chef_script'] = v
        elif k == '-h':
            pass
        else:
            args[k.lstrip('-')] = v
    return args


def new_arg_parser(cli_input):
    """
    Takes a string `cli_input` and parses it using the BaseChef arg_parser.
    Returns tuple of args and options.
    """
    test_argv = cli_input.split(' ')
    with patch.object(sys, 'argv', test_argv):
        chef = BaseChef(compatibility_mode=True)
        args, options = chef.parse_args_and_options()
    assert args is not None, 'argparse parsing failed'
    return args, options

def dict_compare(d1, d2):
    """
    Compare two dicts. Usage: added, removed, modified, same = dict_compare(d1, d2)
    """
    d1_keys = set(d1.keys())
    d2_keys = set(d2.keys())
    intersect_keys = d1_keys.intersection(d2_keys)
    added = d1_keys - d2_keys
    removed = d2_keys - d1_keys
    modified = {o : (d1[o], d2[o]) for o in intersect_keys if d1[o] != d2[o]}
    same = set(o for o in intersect_keys if d1[o] == d2[o])
    return added, removed, modified, same




""" *********** CLI ARGUMENTS TESTS *********** """

def test_same_as_docopt(command_line_inputs):
    for line in command_line_inputs:
        arguments, kwargs = old_arguments_parser(line)
        orig_args = arguments_to_args_renames(arguments)
        del orig_args['uploadchannel']
        del orig_args['OPTIONS']

        args, options = new_arg_parser(line)
        del args['command']
        del args['quiet']  # new logging option was not present in docopt parser
        del args['debug']  # new logging option was not present in docopt parser

        added, removed, modified, same = dict_compare(orig_args, args)
        print('different', added, removed, modified)
        assert orig_args == args, 'docopt arguments differ from argparse args'
        assert kwargs == options, 'extra key=value options differ'
