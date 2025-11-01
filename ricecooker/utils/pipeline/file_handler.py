import os
import tempfile
import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import ClassVar, Dict, Optional, Type, Union, get_type_hints

from .context import ContextMetadata, FileMetadata
from .exceptions import ExpectedFileException, InvalidFileException
from ricecooker import config
from ricecooker.utils.caching import get_cache_data, set_cache_data
from ricecooker.utils.utils import copy_file_to_storage, extract_path_ext


class Handler(ABC):
    """Base class for handling file fetching and processing"""

    def __init__(self, **context):
        """
        Optionally initialize the handler with a fixed context.
        This allows the handler to store configuration data at creation time.
        """
        self._fixed_context = context or {}
        self.parent = None

    @abstractmethod
    def should_handle(self, path: str) -> bool:
        """Check if this handler should handle the given path"""
        pass

    @abstractmethod
    def execute(
        self, path: str, context: Optional[Dict] = None, skip_cache: Optional[bool] = False
    ) -> list[FileMetadata]:
        pass


class DualModeTemporaryFile:
    """Temporary file context manager for writing and reading"""

    def __init__(self, ext: str = ""):
        self._handle = None
        self._write_handle = None
        self.ext = ext
        self.name = None

    def __enter__(self):
        fd, self.name = tempfile.mkstemp(suffix=self.ext)
        os.close(fd)
        self._handle = open(self.name, "rb")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._write_handle:
            self._write_handle.close()
        self._handle.close()
        try:
            os.unlink(self.name)
        except OSError:
            pass

    def write(self, data):
        if not self._write_handle:
            self._write_handle = open(self.name, "wb")
        return self._write_handle.write(data)

    def file_not_empty(self):
        if self._write_handle:
            return self._write_handle.tell() > 0
        with open(self.name, "rb") as f:
            return len(f.read(1)) > 0


class FileHandler(Handler):
    """Base leaf class for handling file fetching and processing"""

    CONTEXT_CLASS: ClassVar[Optional[Type[ContextMetadata]]] = ContextMetadata
    HANDLED_EXCEPTIONS = []

    def __init__(self, **context):
        super().__init__(**context)
        self._thread_local = threading.local()

    @property
    def _output_path(self):
        return getattr(self._thread_local, "output_path", None)

    @_output_path.setter
    def _output_path(self, value):
        self._thread_local.output_path = value

    def _get_context(self, context: Optional[Dict] = None):
        if context is None:
            context = {}
        return {**self._fixed_context, **context}

    @contextmanager
    def write_file(self, extension: str):
        with DualModeTemporaryFile(ext=extension) as tempf:
            try:
                yield tempf
            finally:
                pass  # Handle post-write if needed

    def handle_file(self, path, **kwargs) -> Union[None, FileMetadata]:
        """
        Merge fixed context and per-call kwargs.
        Subclasses must implement actual file handling logic.
        """
        context = {**self._fixed_context, **kwargs}
        pass

    @property
    def STAGE(self):
        return self.parent and self.parent.STAGE

    def normalize_path(self, path):
        if path.startswith(os.path.abspath(config.STORAGE_DIRECTORY)):
            path = os.path.basename(path)
        return path

    def cached_file_outdated(self, filename):
        return False

    def get_file_kwargs(self, context: ContextMetadata) -> list[Dict]:
        return [context.to_dict()]

    def _get_cached_and_uncached_files(
        self, path: str, context: ContextMetadata, skip_cache: bool
    ) -> tuple[list[FileMetadata], list[Dict]]:
        kwargs_list = self.get_file_kwargs(context)
        cached_files = []
        uncached_files = []
        return cached_files, uncached_files


class CompositeHandler(Handler):
    """Base class for handlers that contain child handlers"""

    def __init__(self, **context):
        super().__init__(**context)
        self._children = []

    def add_child(self, child):
        self._children.append(child)
        child.parent = self


class FirstHandlerOnly(CompositeHandler):
    """Runs only the first handler that matches"""

    def execute(self, path: str, context: Optional[Dict] = None, skip_cache: Optional[bool] = False) -> list[FileMetadata]:
        for handler in self._children:
            if handler.should_handle(path):
                return handler.execute(path, context=context, skip_cache=skip_cache)
        return []


class StageHandler(FirstHandlerOnly):
    @property
    @abstractmethod
    def STAGE(self) -> str:
        pass

