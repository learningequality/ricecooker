# Exceptions that might be raised during tree uploading process

class InvalidCommandException(Exception):
    """ InvalidCommandException: raised when unrecognized command is entered """
    def __init__(self,*args,**kwargs):
        Exception.__init__(self,*args,**kwargs)

class InvalidUsageException(Exception):
    """ InvalidUsageException: raised when command line syntax is invalid """
    def __init__(self,*args,**kwargs):
        Exception.__init__(self,*args,**kwargs)

class InvalidFormatException(Exception):
    """ InvalidFormatException: raised when file format is unrecognized """
    def __init__(self,*args,**kwargs):
        Exception.__init__(self,*args,**kwargs)

class FileNotFoundException(Exception):
    """ FileNotFoundException: raised when file path is not found """
    def __init__(self,*args,**kwargs):
        Exception.__init__(self,*args,**kwargs)

class UnknownContentKindError(Exception):
    """ UnknownContentKindError: raised when content kind is unrecognized """
    def __init__(self,*args,**kwargs):
        Exception.__init__(self,*args,**kwargs)

class UnknownQuestionTypeError(Exception):
    """ UnknownQuestionTypeError: raised when question type is unrecognized """
    def __init__(self,*args,**kwargs):
        Exception.__init__(self,*args,**kwargs)

class UnknownFileTypeError(Exception):
    """ UnknownFileTypeError: raised when file type is unrecognized """
    def __init__(self,*args,**kwargs):
        Exception.__init__(self,*args,**kwargs)

class UnknownLicenseError(Exception):
    """ UnknownLicenseError: raised when license is unrecognized """
    def __init__(self,*args,**kwargs):
        Exception.__init__(self,*args,**kwargs)

class InvalidNodeException(Exception):
    """ InvalidNodeException: raised when node is improperly formatted """
    def __init__(self,*args,**kwargs):
        Exception.__init__(self,*args,**kwargs)

class InvalidQuestionException(Exception):
    """ InvalidQuestionException: raised when question is improperly formatted """
    def __init__(self,*args,**kwargs):
        Exception.__init__(self,*args,**kwargs)

def raise_for_invalid_channel(channel):
	pass