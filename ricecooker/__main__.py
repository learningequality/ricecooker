"""Usage: ricecooker uploadchannel [-hvqr] <file_path> [--debug]

Arguments:
  file_path        Path to file with channel data

Options:
  -h --help
  -v       verbose mode
  -q       quiet mode
  -r       make report
"""

from ricecooker.commands import uploadchannel
from ricecooker import config
from docopt import docopt

commands = ["uploadchannel"]

if __name__ == '__main__':
    arguments = docopt(__doc__)
    domain = config.PRODUCTION_DOMAIN
    if arguments["--debug"]:
    	domain = config.DEBUG_DOMAIN
    uploadchannel(arguments["<file_path>"], domain, verbose=arguments["-v"])