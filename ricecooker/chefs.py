import argparse
from importlib.machinery import SourceFileLoader

from . import config
from .classes.nodes import ChannelNode
from .commands import uploadchannel, uploadchannel_wrapper
from .exceptions import InvalidUsageException
from .managers.progress import Status
from .sushi_bar_client import ControlWebSocket
from .utils.tokens import get_content_curation_token




class BaseChef(object):
    """
    The base class that parses command line arguments for sushichef scripts.
    Sushi chef sctipts call the `main` method as the entry point, which in turn
    calls the `run` method to performs all the work (see `uploadchannel`).

    This class also provides backward compaibility with old chef scripts.
    When invoking the a sushi chef script using the old API
        python -m ricecooker uploadchannel chef_script.py --token=123 ...
    an instance of this class with `compatibility_mode = True` will be created.
    Calling `BaseChef.run` will call the function `construct_channel` in `chef_module`.
    """

    def __init__(self, *args, compatibility_mode=False, **kwargs):
        """
        Setup argparse arguments.
        """
        self.compatibility_mode = compatibility_mode

        # argparse setup
        parser = argparse.ArgumentParser(
            description="Ricecooker puts your content in the conten server.",
            add_help=(self.__class__ == BaseChef)  # only add help if not subclassed
        )
        if self.compatibility_mode:
            parser.add_argument('command', choices=['uploadchannel'], help='Main command for the chef script.')
            parser.add_argument('chef_script', help='Path to chef script file')
        #                    -h                                             Help documentation      # NO NEED BECAUSE AUTOMATIC
        parser.add_argument('-v', '--verbose', action='store_true',   help='Verbose mode')
        parser.add_argument('-u', '--update', action='store_true',    help='Re-download files from file paths')
        parser.add_argument('--warn', action='store_true',            help='Print out warnings to stderr')
        parser.add_argument('--stage', action='store_true',           help='Stage updates rather than deploying them for manual verification on Kolibri Studio')
        parser.add_argument('--compress', action='store_true',        help='Compress high resolution videos to low resolution videos')
        parser.add_argument('--thumbnails', action='store_true',      help='Automatically generate thumbnails for topics')
        parser.add_argument('--token', default='#',                   help='Authorization token (can be token or path to file with token)')
        parser.add_argument('--download-attempts',type=int,default=3, help='Maximum number of times to retry downloading files')
        rrgroup = parser.add_mutually_exclusive_group()
        rrgroup.add_argument('--reset', action='store_true',          help='Restart session, overwriting previous session (cannot be used with --resume flag)')
        rrgroup.add_argument('--resume', action='store_true',         help='Resume from ricecooker step (cannot be used with --reset flag)')
        allsteps = [step.name.upper() for step in Status]
        parser.add_argument('--step',choices=allsteps,default='LAST', help='Step to resume progress from (must be used with --resume flag)')
        parser.add_argument('--prompt', action='store_true',          help='Prompt user to open the channel after creating it')
        parser.add_argument('--publish', action='store_true',         help='Publish channel after creating it')
        # [OPTIONS] --- extra key=value options are supported, but do not appear in help
        self.arg_parser = parser


    def parse_args_and_options(self):
        """
        Parses all known command line args and also additional key=value options.
        NOTE: this should be the only place cli args are parsed in order to have
              a single consistent interface for all chef scripts.

        Args: None, but implicitly depends on `self.arg_parser` and `sys.argv
        Returns: tuple (args, options)
          args (dict): chef command line arguments
          options (dict): extra compatibility-mode options given on command line
        """
        args_namespace, options_list = self.arg_parser.parse_known_args()
        args = args_namespace.__dict__

        # Make sure token is provided. There are four possible ways to specify:
        #   --token=path to token-containing file
        #   --token=140fefe...1f3
        #   when --token is not specified on the command line, the default value is #
        #     - try environment variable CONTENT_CURATION_TOKEN
        #     - else prompt user
        # If ALL of these fail, this call will raise and chef run will stop
        args['token'] = get_content_curation_token(args['token'])

        # Parse additional compatibility mode keyword arguments from `options_list`
        options = {}
        for preoption in options_list:
            try:
                option_key, option_value = preoption.split('=')
                options.update({option_key.strip(): option_value.strip()})
            except IndexError:
                msg = "Invalid option '{0}': use [key]=[value] format (no whitespace)".format(preoption)
                raise InvalidUsageException(msg)

        # For compatibility mode, we check the chef script file exists and load it
        if self.compatibility_mode:
            try:
                # Try to load the chef_script as a module
                self.chef_module = SourceFileLoader("mod", args['chef_script']).load_module()
            except FileNotFoundError as e:
                raise InvalidUsageException('Error: must specify `chef_module` for compatibility_mode')

        return args, options


    def pre_run(self, args, options):
        """
        This function is called before the Chef's `run` mehod is called.
        By default this function does nothing, but subclass can use this hook to
        run prerequisite tasks.
        Args:
            args (dict): chef command line arguments
            options (dict): extra compatibility-mode options given on command line
        """
        pass


    def run(self, args, options):
        """
        This function calls uploadchannel which performs all the run steps:
          - Create ChannelNode
          - Pupulate Tree with TopicNodes, ContentNodes, and associated File objects
          - .
          - ..
          - ...

        Args:
            args (dict): ricecooker command line arguments
            options (dict): additional compatibility mode options given on command line
        """
        self.pre_run(args, options)
        args_and_options = args.copy()
        args_and_options.update(options)
        uploadchannel(self, **args_and_options)


    def get_channel(self, **kwargs):
        """
        Call chef script's get_channel method in compatibility mode
        ...or...
        Create a `ChannelNode` from the Chef's `channel_info` class attribute.

        Args:
            kwargs (dict): additional keyword arguments that `uploadchannel` received
        Returns: channel created from get_channel method or None
        """
        if self.compatibility_mode:
            # For pre-sushibar scritps that do not implement `get_channel`,
            # we must check it this function exists before calling it...
            if hasattr(self.chef_module, 'get_channel'):
                config.LOGGER.info("Calling get_channel... ")
                # Create channel (using the function in the chef script)
                channel = self.chef_module.get_channel(**kwargs)
            # For chefs with a `create_channel` method instead of `get_channel`
            if hasattr(self.chef_module, 'create_channel'):
                config.LOGGER.info("Calling create_channel... ")
                # Create channel (using the function in the chef script)
                channel = self.chef_module.create_channel(**kwargs)
            else:
                channel = None  # since no channel info, SushiBar functionality will be disabled...
            return channel

        elif hasattr(self, 'channel_info'):
            # If a sublass has an `channel_info` attribute (a dict) it doesn't need
            # to define a `get_channel` method and instead rely on this code:
            channel = ChannelNode(
                source_domain=self.channel_info['CHANNEL_SOURCE_DOMAIN'],
                source_id=self.channel_info['CHANNEL_SOURCE_ID'],
                title=self.channel_info['CHANNEL_TITLE'],
                thumbnail=self.channel_info.get('CHANNEL_THUMBNAIL'),
                description=self.channel_info.get('CHANNEL_DESCRIPTION'),
            )
            return channel

        else:
            raise NotImplementedError('BaseChef must overrride the get_channel method')


    def construct_channel(self, **kwargs):
        """
        Calls chef script's construct_channel method. Used only in compatibility mode.
        Args:
            kwargs (dict): additional keyword arguments that `uploadchannel` received
        Returns: channel populated from construct_channel method
        """
        if self.compatibility_mode:
            # Constuct channel (using function from imported chef script)
            config.LOGGER.info("Populating channel... ")
            channel = self.chef_module.construct_channel(**kwargs)
            return channel
        else:
            raise NotImplementedError('Your chef class must overrride the construct_channel method')


    def main(self):
        args, options = self.parse_args_and_options()
        print('In BaseChef.main method. args=', args, 'options=', options)
        self.run(args, options)







class SushiChef(BaseChef):
    """
    This is the main class that all suchi chefs should subclass. This class uses
    remote logging, remote stage and progress reporting, and remote commands.
    The `SushiChef` class a subclass of the `BaseChef` and supports the same
    command line arguments, additionally handles arguments for Sushi Bar server.
    Sushi chef scripts call the `main` method as the entry point, which in turn
    calls the `run` method to performs all the work (see `uploadchannel`).
    """

    def __init__(self, *args, **kwargs):
        """
        The SushiChef supports all the command line args of a BaseChef and more.
        Overrride this method in your sushi chef class to add custom arguments.
        """
        super(SushiChef, self).__init__(*args, **kwargs)

        # We don't want to add argparse help if subclass has an __init__ method
        if "__init__" in self.__class__.__dict__.keys():
            add_parser_help = False     # assume subclass __init__ will add help
        else:
            add_parser_help = True

        self.arg_parser = argparse.ArgumentParser(
            description="Ricecooker scripts put your content on the content server.",
            add_help=add_parser_help,
            parents=[self.arg_parser]
        )
        self.arg_parser.add_argument('--daemon', action='store_true', help='Runs in daemon mode')
        self.arg_parser.add_argument('--nomonitor', action='store_true', help='Disable SushiBar progress monitoring')
        # self.arg_parser.add_argument('--sushibar', help='Hostname of SushiBar server (e.g. "sushibar.learningequality.org")')
        # TODO: --bartoken


    def daemon_mode(self, args, options):
        """
        Open a ControlWebSocket to SushiBar server and listend for remote commands.
        Args:
            args (dict): chef command line arguments
            options (dict): additional compatibility mode options given on command line
        """
        cws = ControlWebSocket(self, args, options)
        cws.start()
        cws.join()


    def run(self, args, options):
        """
        This function calls uploadchannel which performs all the run steps:
        Args:
            args (dict): chef command line arguments
            options (dict): additional compatibility mode options given on command line
        """
        self.pre_run(args, options)
        uploadchannel_wrapper(self, args, options)


    def main(self):
        args, options = self.parse_args_and_options()
        print('In SushiChef.main method. args=', args, 'options=', options)

        if args['daemon']:
            self.daemon_mode(args, options)
        else:
            self.run(args, options)


