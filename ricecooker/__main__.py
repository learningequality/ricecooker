"""Usage: ricecooker uploadchannel [-hvqr] <file_path>

Arguments:
  file_path        Path to file with channel data

Options:
  -h --help
  -v       verbose mode
  -q       quiet mode
  -r       make report
"""

from fle_utils import constants
from ricecooker.commands import uploadchannel
from docopt import docopt

commands = ["uploadchannel"]

if __name__ == '__main__':
    arguments = docopt(__doc__)

    uploadchannel(arguments["<file_path>"], verbose=arguments["-v"])