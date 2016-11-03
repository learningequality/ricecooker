"""Usage: ricecooker uploadchannel [-huv] <file_path> [--resume [--step=<step>] | --reset] [--token=<t>] [--debug] [[OPTIONS] ...]

Arguments:
  file_path        Path to file with channel data
  --debug          Run ricecooker against debug server (localhost:8000) rather than contentworkshop
  --token=<t>      Authorization token (can be token or path to file with token) [default: #]
  --resume         Resume from ricecooker step (cannot be used with --reset flag)
  --step=<step>    Step to resume progress from (must be used with --resume flag) [default: last]
  --reset          Restart session, overwriting previous session (cannot be used with --resume flag)
  [OPTIONS]        Extra arguments to add to command line (e.g. key='field')

Options:
  -h --help
  -v       verbose mode
  -u       check files for updates
"""

from ricecooker.commands import uploadchannel
from ricecooker import config
from ricecooker.exceptions import InvalidUsageException
from ricecooker.managers import Status
from docopt import docopt

commands = ["uploadchannel"]

if __name__ == '__main__':
    arguments = docopt(__doc__)
    kwargs = {}
    for arg in arguments['OPTIONS']:
      try:
        kwarg = arg.split('=')
        kwargs.update({kwarg[0].strip(): kwarg[1].strip()})
      except IndexError:
        raise InvalidUsageException("Invalid kwarg '{0}' found: Must format as [key]=[value] (no whitespace)".format(arg))

    step = arguments['--step']
    all_steps = [s.name for s in Status]
    if step.upper() not in all_steps:
      raise InvalidUsageException("Invalid step '{0}': Valid steps are {1}".format(step, all_steps))

    uploadchannel(arguments["<file_path>"],
                  arguments["--debug"],
                  verbose=arguments["-v"],
                  update=arguments['-u'],
                  resume=arguments['--resume'],
                  reset=arguments['--reset'],
                  token=arguments['--token'],
                  step=step,
                  **kwargs)