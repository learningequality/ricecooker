# Exceptions that might be raised during tree uploading process


class InvalidCommandException(Exception):
    """InvalidCommandException: raised when unrecognized command is entered"""

    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)


class InvalidUsageException(Exception):
    """InvalidUsageException: raised when command line syntax is invalid"""

    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)


class InvalidFormatException(Exception):
    """InvalidFormatException: raised when file format is unrecognized"""

    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)


class FileNotFoundException(Exception):
    """FileNotFoundException: raised when file path is not found"""

    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)


class UnknownContentKindError(Exception):
    """UnknownContentKindError: raised when content kind is unrecognized"""

    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)


class UnknownQuestionTypeError(Exception):
    """UnknownQuestionTypeError: raised when question type is unrecognized"""

    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)


class UnknownFileTypeError(Exception):
    """UnknownFileTypeError: raised when file type is unrecognized"""

    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)


class UnknownLicenseError(Exception):
    """UnknownLicenseError: raised when license is unrecognized"""

    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)


class InvalidNodeException(Exception):
    """InvalidNodeException: raised when node is improperly formatted"""

    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)


class InvalidQuestionException(Exception):
    """InvalidQuestionException: raised when question is improperly formatted"""

    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)


class ChannelIncompleteError(Exception):
    """ChannelIncompleteError: raised when whole batches of nodes failed to
    upload, so committing would stage a channel with subtrees missing.

    Distinct from an individual node failing to build (a bad file, a node that
    did not validate): those are reported and the channel is still committed.
    This is raised only when an entire add_nodes request never landed, which
    takes every descendant of that request with it.
    """


class RemoteError(Exception):
    """RemoteError: base of every --remote failure; messages start with remote:"""


class RemoteConfigError(RemoteError):
    """RemoteConfigError: raised when --remote config cannot be resolved"""


class RemoteTransportError(RemoteError):
    """RemoteTransportError: raised when a local ssh/rsync invocation fails"""


class RemoteSessionError(RemoteError):
    """RemoteSessionError: raised when a tmux command on the box fails"""


class RemoteDriverError(RemoteError):
    """RemoteDriverError: raised when the box cannot run a --remote chef"""


class RemoteCliError(RemoteError):
    """RemoteCliError: raised when a `remote` subcommand cannot complete"""


def raise_for_invalid_channel(channel):
    pass
