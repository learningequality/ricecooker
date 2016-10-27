"""Usage: ricecooker uploadchannel [-hvqru] <file_path> [--resume | --reset] [--token=<t>] [--debug] [[OPTIONS] ...]

Arguments:
  file_path        Path to file with channel data
  -u               Update all files (download all files again)
  --debug          Run ricecooker against debug server (localhost:8000) rather than contentworkshop
  --resume         Resume from where rice cooker left off (cannot be used with --reset flag)
  --reset          Restart session, overwriting previous session (cannot be used with --resume flag)
  --token=<t>      Authorization token (can be token or path to file with token) [default: 0]
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
from docopt import docopt

commands = ["uploadchannel"]

if __name__ == '__main__':
    arguments = docopt(__doc__)
    print(arguments)
    domain = config.PRODUCTION_DOMAIN
    kwargs = {}
    for arg in arguments['OPTIONS']:
      try:
        kwarg = arg.split('=')
        kwargs.update({kwarg[0].strip(): kwarg[1].strip()})
      except IndexError:
        raise InvalidUsageException("Invalid kwarg '{0}' found: Must format as [key]=[value] (no whitespace)".format(arg))
    if arguments["--debug"]:
    	domain = config.DEBUG_DOMAIN
    uploadchannel(arguments["<file_path>"],
                  domain,
                  verbose=arguments["-v"],
                  update=arguments["-u"],
                  resume=arguments['--resume'],
                  reset=arguments['--reset'],
                  token=arguments['--token'],
                  **kwargs)