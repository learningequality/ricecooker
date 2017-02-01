
"""Usage: ricecooker uploadchannel [-huv] <file_path> [--warn] [--compress] [--token=<t>] [--download-attempts=<n>] [--resume [--step=<step>] | --reset] [--prompt] [--publish] [[OPTIONS] ...]

Arguments:
  file_path        Path to file with channel data

Options:
  -h                          Help documentation
  -v                          Verbose mode
  -u                          Re-download files from file paths
  --warn                      Print out warnings to stderr
  --compress                  Compress high resolution videos to low resolution videos
  --token=<t>                 Authorization token (can be token or path to file with token) [default: #]
  --download-attempts=<n>     Maximum number of times to retry downloading files [default: 3]
  --resume                    Resume from ricecooker step (cannot be used with --reset flag)
  --step=<step>               Step to resume progress from (must be used with --resume flag) [default: last]
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

from .commands import uploadchannel
from . import config
from .exceptions import InvalidUsageException
from .managers.progress import Status
from docopt import docopt

commands = ["uploadchannel"]

if __name__ == '__main__':
    arguments = docopt(__doc__)

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

    # Make sure max-retries can be cast as an integer
    try:
      int(arguments['--download-attempts'])
    except ValueError:
      raise InvalidUsageException("Invalid argument: Download-attempts must be an integer.")


    uploadchannel(arguments["<file_path>"],
                  verbose=arguments["-v"],
                  update=arguments['-u'],
                  download_attempts=arguments['--download-attempts'],
                  resume=arguments['--resume'],
                  reset=arguments['--reset'],
                  token=arguments['--token'],
                  step=step,
                  prompt=arguments['--prompt'],
                  publish=arguments['--publish'],
                  warnings=arguments['--warn'],
                  compress=arguments['--compress'],
                  **kwargs)