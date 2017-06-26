
import json
import os
try: # to support Python 2.x.
    input = raw_input
except NameError:
    pass

from requests.exceptions import HTTPError

from ricecooker import config


def get_env(envvar):
    """
    Reads an environment variable `envvar` if it is defined or returns None.
    """
    if envvar not in os.environ:
        return None
    else:
        return os.environ[envvar]

def get_content_curation_token(args_token):
    """
    Get the token through one of four possible ways. Input `args_token` can be
      1. path to a token-containing file (path)
      2. actual token (str) in which case there's nothing to get just pass along
      3. `#` (default value when no --token is given on command line)
        3a: if environment variable CONTENT_CURATION_TOKEN exists, we'll use that
        3b: else we prompt the user interactively
    """
    if args_token != "#":                               # retrieval methods 1, 2
        if os.path.isfile(args_token):
            with open(args_token, 'r') as fobj:
                return fobj.read().strip()
        else:
            return args_token
    else:                                               # retrieval strategies 3
        token = get_env('CONTENT_CURATION_TOKEN')
        if token is not None:
            return token                                # 3a
        else:
            return prompt_token(config.DOMAIN)          # 3b

def prompt_token(domain):
    """
    Prompt user to enter content curation server authentication token.
    Args: domain (str): domain to authenticate user
    Returns: token
    """
    token = input("\nEnter content curation server token ('q' to quit): ").lower()
    if token == 'q':
        sys.exit()
    else:
        return token.strip()

# SUSHI_BAR_TOKEN = get_env('SUSHI_BAR_TOKEN')  # TODO in near future