"""Usage: ricecooker uploadchannel [-hvqru] <file_path> [--resume [--step=<step>] | --reset] [--debug] [[OPTIONS] ...]

Arguments:
  file_path        Path to file with channel data
  -u               Update all files (download all files again)
  --debug          Run ricecooker against debug server (localhost:8000) rather than contentworkshop
  --resume         Resume from ricecooker step (cannot be used with --reset flag)
  --step=<step>    Step to resume progress from (must be used with --resume flag) [default: last]
  --reset          Restart session, overwriting previous session (cannot be used with --resume flag)
  [OPTIONS]        Extra arguments to add to command line (e.g. key='field')

Options:
  -h --help
  -v       verbose mode
  -q       quiet mode
  -r       make report
"""

from ricecooker.commands import uploadchannel
from ricecooker import config
from ricecooker.exceptions import InvalidUsageException
from ricecooker.managers import RESTORE_POINT_MAPPING
from docopt import docopt

commands = ["uploadchannel"]

if __name__ == '__main__':
    arguments = docopt(__doc__)
    domain = config.PRODUCTION_DOMAIN
    if arguments["--debug"]:
      domain = config.DEBUG_DOMAIN

    kwargs = {}
    for arg in arguments['OPTIONS']:
      try:
        kwarg = arg.split('=')
        kwargs.update({kwarg[0].strip(): kwarg[1].strip()})
      except IndexError:
        raise InvalidUsageException("Invalid kwarg '{0}' found: Must format as [key]=[value] (no whitespace)".format(arg))

    step = arguments['--step']
    all_steps = [key for key, value in RESTORE_POINT_MAPPING.items()]

    if step.upper() not in all_steps:
      raise InvalidUsageException("Invalid step '{0}': Must use one of these steps {1}".format(step, all_steps))

    uploadchannel(arguments["<file_path>"], domain, verbose=arguments["-v"], update=arguments["-u"], resume=arguments['--resume'], reset=arguments['--reset'], step=step, **kwargs)