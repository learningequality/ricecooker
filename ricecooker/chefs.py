import argparse
import logging
import os
import sys
from datetime import datetime
from importlib.machinery import SourceFileLoader

from . import config
from .classes.nodes import ChannelNode
from .commands import authenticate_user
from .commands import uploadchannel
from .commands import uploadchannel_wrapper
from .exceptions import InvalidUsageException
from .exceptions import raise_for_invalid_channel
from .managers.progress import Status
from .sushi_bar_client import ControlWebSocket
from .sushi_bar_client import LocalControlSocket
from .sushi_bar_client import SushiBarClient
from .utils.jsontrees import build_tree_from_json
from .utils.jsontrees import get_channel_node_from_json
from .utils.jsontrees import read_tree_from_json
from .utils.linecook import build_ricecooker_json_tree
from .utils.linecook import FolderExistsAction
from .utils.metadata_provider import CsvMetadataProvider
from .utils.metadata_provider import DEFAULT_CHANNEL_INFO_FILENAME
from .utils.metadata_provider import DEFAULT_CONTENT_INFO_FILENAME
from .utils.metadata_provider import DEFAULT_EXERCISE_QUESTIONS_INFO_FILENAME
from .utils.metadata_provider import DEFAULT_EXERCISES_INFO_FILENAME
from .utils.tokens import get_content_curation_token
# for JsonTreeChef chef
# for LineCook chef


# SUSHI CHEF BASE CLASS (and backward compatibiliry)
################################################################################

class BaseChef(object):
    """
    The base class that parses command line arguments for sushichef scripts.
    Sushi chef sctipts call the `main` method as the entry point, which in turn
    calls the `run` method to performs all the work (see `uploadchannel`).

    This class also provides backward compaibility with old chef scripts.
    When invoking the a sushi chef script using the old API: \
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
        parser.add_argument('command', nargs='?', default='uploadchannel', help='Desired action: dryrun or uploadchannel')
        if self.compatibility_mode:
            parser.add_argument('chef_script', help='Path to chef script file')
        parser.add_argument('--token', default='#',                   help='Authorization token (can be token or path to file with token)')
        parser.add_argument('-u', '--update', action='store_true',    help='Force re-download of files (skip .ricecookerfilecache/ check)')
        parser.add_argument('-v', '--verbose', action='store_true', default=True, help='Verbose mode')
        parser.add_argument('--quiet', action='store_true',           help='Print only errors to stderr')
        parser.add_argument('--warn', action='store_true',            help='Print warnings to stderr')
        parser.add_argument('--debug', action='store_true',           help='Print debugging log info to stderr')
        parser.add_argument('--compress', action='store_true',        help='Compress high resolution videos to low resolution videos')
        parser.add_argument('--thumbnails', action='store_true',      help='Automatically generate thumbnails for topics')
        parser.add_argument('--download-attempts',type=int,default=3, help='Maximum number of times to retry downloading files')
        rrgroup = parser.add_mutually_exclusive_group()
        rrgroup.add_argument('--reset', action='store_true',          help='Restart session, overwriting previous session (cannot be used with --resume flag)')
        rrgroup.add_argument('--resume', action='store_true',         help='Resume from ricecooker step (cannot be used with --reset flag)')
        allsteps = [step.name.upper() for step in Status]
        parser.add_argument('--step',choices=allsteps,default='LAST', help='Step to resume progress from (must be used with --resume flag)')
        parser.add_argument('--prompt', action='store_true',          help='Prompt user to open the channel after creating it')
        parser.add_argument('--stage', dest='stage_deprecated', action='store_true',
                            help='(Deprecated.) Stage updated content for review. This flag is now the default and has been kept solely to maintain compatibility. Use --deploy to immediately push changes.')
        parser.add_argument('--deploy', dest='stage', action='store_false',
                            help='Immediately deploy changes to channel\'s main tree. This operation will delete the previous channel content once upload completes. Default (recommended) behavior is to post new tree for review.')
        parser.add_argument('--publish', action='store_true',         help='Publish newly uploaded version of the channel')
        parser.add_argument('--sample', type=int, metavar='SIZE',     help='Upload a sample of SIZE content nodes from the channel')
        # [OPTIONS] --- extra key=value options are supported, but do not appear in help
        self.arg_parser = parser


    def parse_args_and_options(self):
        """
        Parses all known command line args and also additional key=value options.
        NOTE: this should be the only place cli args are parsed in order to have
        a single consistent interface for all chef scripts.

        Args: None, but implicitly depends on `self.arg_parser` and `sys.argv`
        Returns:
          tuple (`args`, `options`)
            args (dict): chef command line arguments
            options (dict): extra key=value options given on command line
        """
        args_namespace, options_list = self.arg_parser.parse_known_args()
        args = args_namespace.__dict__

        # Handle case when command is not specified but key=value options are
        allcommands = [
            'uploadchannel',  # Whole pipeline: pre_run > run > [deploy,publish]
            'dryrun',         # Do pre_run and run but do not upload to Studio
        ]
        command_arg = args['command']
        if command_arg not in allcommands and '=' in command_arg:
            # a key=value options pair was incorrectly recognized as the command
            args['command'] = 'uploadchannel'
            options_list.append(command_arg)  # put command_arg where it belongs


        # Print CLI deprecation warnings info
        if args['stage_deprecated']:
            config.LOGGER.warning('DEPRECATION WARNING: --stage is now default, so the --stage flag has been deprecated and will be removed in ricecooker 1.0.')
        if args['publish'] and args['stage']:
            raise InvalidUsageException('The --publish argument must be used together with --deploy argument.')
        logging_args = [key for key in ['quiet', 'warn', 'debug'] if args[key]]
        if len(logging_args) > 1:
            raise InvalidUsageException('Agruments --quiet, --warn, and --debug cannot be used together.')

        if args['command'] == 'uploadchannel':
            # Make sure token is provided. There are four ways to specify:
            #  1. --token=path to token-containing file
            #  2. --token=140fefe...1f3
            # when --token is not given on the command line, it default to # and
            #  3. we look for environment variable STUDIO_TOKEN
            #  4. else prompt user
            # If ALL of these fail, this call will raise and chef run will stop.
            args['token'] = get_content_curation_token(args['token'])

        if args['command'] == 'dryrun':
            args['nomonitor'] = True    # no Sushibar logs and progress tracking
            if not args['resume']:
                args['reset'] = True    # set the --reset flag to avoid prompt

        # Parse additional keyword arguments from `options_list`
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

    def config_logger(self, args, options):
        """
        Set up stream (stderr), local file logging (logs/yyyy-mm-dd__HHMM.log),
        and remote logging to SushiBar server. This method is called as soon as
        we parse args so we can apply the user-preferred logging level settings.
        """

        # Set desired logging level based on command line arguments
        level = logging.INFO
        if args['debug']:
            level = logging.DEBUG
        elif args['warn']:
            level = logging.WARNING
        elif args['quiet']:
            level = logging.ERROR

        config.setup_logging(level=level)


        # 2. File handler (logs/yyyy-mm-dd__HHMM.log)
        try:
            # FIXME: This code assumes we run chefs from the chef's root directory.
            # We probably want to have chefs set a root directory for files like this.
            if not os.path.exists("logs"):
                os.makedirs("logs")
            logfile_name = datetime.now().strftime("%Y-%m-%d__%H%M") + ".log"
            logfile_path = os.path.join("logs", logfile_name)
            file_handler = logging.FileHandler(logfile_path)
            logfile_formatter = logging.Formatter("%(asctime)s - %(message)s", "%Y-%m-%d %H:%M:%S")
            file_handler.setFormatter(logfile_formatter)
            config.LOGGER.addHandler(file_handler)
        except Exception as e:
            config.LOGGER.warning('Unable to setup file logging due to %s' % e)

        # 3. Remote logging handler (sushibar logs via WebSockets)
        try:
            nomonitor = args.get('nomonitor', False)
            if not nomonitor:
                channel = self.get_channel(**options)
                username, token = authenticate_user(args['token'])
                config.SUSHI_BAR_CLIENT = SushiBarClient(channel, username, token, nomonitor=nomonitor)
        except Exception as e:
            config.LOGGER.warning('Unable to use remote logging due to: %s' % e)


    def pre_run(self, args, options):
        """
        This function is called before the Chef's `run` mehod is called.
        By default this function does nothing, but subclass can use this hook to
        run prerequisite tasks.
        Args:
            args (dict): chef command line arguments
            options (dict): extra key=value options given on command line
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
            options (dict): extra key=value options given on command line
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
                language=self.channel_info.get('CHANNEL_LANGUAGE'),
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
        self.config_logger(args, options)
        self.run(args, options)





# THE DEFAULT SUSHI CHEF
################################################################################

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
        subclasses = self.__class__.__mro__[:-3]     # all subclasses after this
        if any(['__init__' in c.__dict__.keys() for c in subclasses]):
            add_parser_help = False    # assume subclass' __init__ will add help
        else:
            add_parser_help = True

        self.arg_parser = argparse.ArgumentParser(
            description="Chef scripts upload content to the Kolibri Studio server.",
            add_help=add_parser_help,
            parents=[self.arg_parser]
        )
        self.arg_parser.add_argument('--daemon', action='store_true', help='Run chef in daemon mode')
        self.arg_parser.add_argument('--nomonitor', action='store_true', help='Disable SushiBar progress monitoring')
        self.arg_parser.add_argument('--cmdsock', help='Local command socket (for cronjobs)')
        # self.arg_parser.add_argument('--sushibar', help='Hostname of SushiBar server (e.g. "sushibar.learningequality.org")')
        # TODO: --bartoken


    def daemon_mode(self, args, options):
        """
        Open a ControlWebSocket to SushiBar server and listend for remote commands.
        Args:
            args (dict): chef command line arguments
            options (dict): additional key=value options given on command line
        """
        cws = ControlWebSocket(self, args, options)
        cws.start()
        if 'cmdsock' in args and args['cmdsock']:
            lcs = LocalControlSocket(self, args, options)
            lcs.start()
            lcs.join()
        cws.join()


    def run(self, args, options):
        """
        This function calls uploadchannel which performs all the run steps:
        Args:
            args (dict): chef command line arguments
            options (dict): additional key=value options given on command line
        """
        args_copy = args.copy()
        args_copy['token'] = args_copy['token'][0:6] + '...'
        config.LOGGER.info('In SushiChef.run method. args=' + str(args_copy) + ' options=' + str(options))
        self.pre_run(args, options)
        uploadchannel_wrapper(self, args, options)


    def main(self):
        args, options = self.parse_args_and_options()
        self.config_logger(args, options)
        if args['daemon']:
            self.daemon_mode(args, options)
        else:
            self.run(args, options)


# JSON TREE CHEF
################################################################################

class JsonTreeChef(SushiChef):
    """
    This sushi chef loads the data from a channel from a ricecooker json tree file
    which conatins the json representation of a full ricecooker node tree.
    For example the content hierarchy with two levels of subfolders and a PDF
    content node looks like this::

        {
          "title": "Open Stax",
          "source_domain": "openstax.org",
          "source_id": "open-stax",
          "language": "en",
          "children": [
            {
              "kind": "topic",
              "title": "Humanities",
              "children": [
                {
                  "kind": "topic",
                  "title": "U.S. History",
                  "children": [
                    {
                      "kind": "document",
                      "source_id": "Open Stax/Humanities/U.S. History/Student Handbook.pdf",
                      "title": "Student Handbook",
                      "author": "P. Scott Corbett, Volker Janssen, ..."",
                      "license": {
                        "license_id": "CC BY"
                      },
                      "files": [
                        {
                          "file_type": "document",
                          "path": "content/open_stax_zip/Open Stax/Humanities/U.S. History/Student Handbook.pdf"
                        }
                      ]
                    }]}]}]}

    Each object in the json tree correponds to a TopicNode, a ContentNode that
    contains a Files or an Exercise that contains Question.
    """
    DATA_DIR = 'chefdata'
    TREES_DATA_DIR = os.path.join(DATA_DIR, 'trees')
    RICECOOKER_JSON_TREE = 'ricecooker_json_tree.json'

    def pre_run(self, args, options):
        """
        This function is called before `run` to create the json tree file.
        """
        raise NotImplementedError('JsonTreeChef subclass must implement the `pre_run` method.')

    def get_json_tree_path(self, *args, **kwargs):
        """
        Return path to ricecooker json tree file. Override this method to use
        a custom filename, e.g., for channel with multiple languages.
        """
        json_tree_path = os.path.join(self.TREES_DATA_DIR, self.RICECOOKER_JSON_TREE)
        return json_tree_path

    def get_channel(self, **kwargs):
        # Load channel info from json_tree
        json_tree_path = self.get_json_tree_path(**kwargs)
        json_tree = read_tree_from_json(json_tree_path)
        channel = get_channel_node_from_json(json_tree)
        return channel

    def construct_channel(self, **kwargs):
        """
        Build the channel tree by adding TopicNodes and ContentNode children.
        """
        channel = self.get_channel(**kwargs)
        json_tree_path = self.get_json_tree_path(**kwargs)
        json_tree = read_tree_from_json(json_tree_path)
        build_tree_from_json(channel, json_tree['children'])
        raise_for_invalid_channel(channel)
        return channel




# SOUSCHEF LINECOOK
################################################################################

class LineCook(JsonTreeChef):
    """
    This sushi chef uses os.walk to import the content in `channeldir` folder
    `directory structure + CSV metadata files  -->  Kolibri channel`.
    Folders and CSV files can be creaed by hand or by a `souschef` script.
    """
    metadata_provider = None

    def __init__(self, *args, **kwargs):
        super(LineCook, self).__init__(*args, **kwargs)

        # We don't want to add argparse help if subclass has an __init__ method
        subclasses = self.__class__.__mro__[:-5]     # all subclasses after this
        if any(['__init__' in c.__dict__.keys() for c in subclasses]):
            add_parser_help = False    # assume subclass' __init__ will add help
        else:
            add_parser_help = True

        self.arg_parser = argparse.ArgumentParser(
            description="Upload the folder hierarchy to the content workshop.",
            add_help=add_parser_help,
            parents=[self.arg_parser]
        )
        self.arg_parser.add_argument('--channeldir', required=True,
            action=FolderExistsAction,
            help='The directory that corresponds to the root of the channel.')
        self.arg_parser.add_argument('--channelinfo',
            default=DEFAULT_CHANNEL_INFO_FILENAME,
            help='Filename for the channel metadata (assumed to be sibling of channeldir)')
        self.arg_parser.add_argument('--contentinfo',
            default=DEFAULT_CONTENT_INFO_FILENAME,
            help='Filename for content metadata (assumed to be sibling of channeldir)')
        self.arg_parser.add_argument('--exercisesinfo',
            default=DEFAULT_EXERCISES_INFO_FILENAME,
            help='Filename for execises metadata (assumed to be sibling of channeldir)')
        self.arg_parser.add_argument('--questionsinfo',
            default=DEFAULT_EXERCISE_QUESTIONS_INFO_FILENAME,
            help='Filename for execise questions metadata (assumed to be sibling of channeldir)')
        self.arg_parser.add_argument('--generate', action='store_true',
            help='Generate metadata files from directory stucture.')
        self.arg_parser.add_argument('--importstudioid',
            help='Generate CSV metadata from a specified studio_id (e.g. studio_id of main_tree for some channel)')


    def _init_metadata_provider(self, args, options):
        if args['contentinfo'].endswith('.csv'):
            metadata_provider = CsvMetadataProvider(args['channeldir'],
                                                    channelinfo=args['channelinfo'],
                                                    contentinfo=args['contentinfo'],
                                                    exercisesinfo=args['exercisesinfo'],
                                                    questionsinfo=args['questionsinfo'])
        else:
            raise ValueError('Uknown contentinfo file format ' + args['contentinfo'])
        self.metadata_provider = metadata_provider

    def pre_run(self, args, options):
        """
        This function is called before `run` in order to build the json tree.
        """
        if 'generate' in args and args['generate']:
            self.metadata_provider = CsvMetadataProvider(args['channeldir'],
                                                    channelinfo=args['channelinfo'],
                                                    contentinfo=args['contentinfo'],
                                                    exercisesinfo=args['exercisesinfo'],
                                                    questionsinfo=args['questionsinfo'],
                                                    validate_and_cache=False)
            self.metadata_provider.generate_templates(exercise_questions=True)
            self.metadata_provider.generate_contentinfo_from_channeldir(args, options)
            sys.exit(0)

        elif 'importstudioid' in args and args['importstudioid']:
            studio_id = args['importstudioid']
            config.LOGGER.info("Calling with importstudioid... " + studio_id)
            self.metadata_provider = CsvMetadataProvider(args['channeldir'],
                                                    channelinfo=args['channelinfo'],
                                                    contentinfo=args['contentinfo'],
                                                    exercisesinfo=args['exercisesinfo'],
                                                    questionsinfo=args['questionsinfo'],
                                                    validate_and_cache=False)
            self.metadata_provider.generate_templates(exercise_questions=True)
            self.metadata_provider.generate_exercises_from_importstudioid(args, options)
            sys.exit(0)

        if self.metadata_provider is None:
            self._init_metadata_provider(args, options)
        kwargs = {}   # combined dictionary of argparse args and extra options
        kwargs.update(args)
        kwargs.update(options)
        json_tree_path = self.get_json_tree_path(**kwargs)
        build_ricecooker_json_tree(args, options, self.metadata_provider, json_tree_path)

    # UNCOMMENT BELOW TO DISABLE CHANNEL UPLOAD
    # def run(self, args, options):
    #     self.pre_run(args, options)
