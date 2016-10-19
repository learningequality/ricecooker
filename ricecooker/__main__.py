"""Usage: ricecooker uploadchannel [-hvqr] <file_path> [--debug] [[OPTIONS] ...]

Arguments:
  file_path        Path to file with channel data
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
    uploadchannel(arguments["<file_path>"], domain, verbose=arguments["-v"], **kwargs)