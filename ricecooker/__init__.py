# -*- coding: utf-8 -*-

import sys

__author__ = "Learning Equality"
__email__ = "info@learningequality.org"

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version

try:
    __version__ = version("ricecooker")
except PackageNotFoundError:
    __version__ = "0.0.0.dev0"

if sys.version_info < (3, 9, 0):
    raise RuntimeError("Ricecooker only supports Python 3.9+")
