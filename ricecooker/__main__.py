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
from docopt import docopt

PRODUCTION_DOMAIN = "http://unicefcontentcuration.learningequality.org"
DEBUG_DOMAIN = "127.0.0.1:8000"

commands = ["uploadchannel"]

if __name__ == '__main__':
    arguments = docopt(__doc__)
    domain = PRODUCTION_DOMAIN
    if arguments["--debug"]:
    	domain = DEBUG_DOMAIN
    uploadchannel(arguments["<file_path>"], domain, verbose=arguments["-v"])