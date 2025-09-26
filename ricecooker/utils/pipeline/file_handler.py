"""
Utilities for handling file downloads from URLs
"""
import os
import tempfile
import threading
from abc import ABC
from abc import abstractmethod
from contextlib import contextmanager
from typing import ClassVar
from typing import Dict
from typing import get_type_hints
from typing import Optional
from typing import Type
from typing import Union

from .context import ContextMetadata
from .context import FileMetadata
from .exceptions import ExpectedFileException
from .exceptions import InvalidFileException
from ricecooker import config
from ricecooker.utils.caching import get_cache_data
from ricecooker.utils.caching import set_cache_data
from ricecooker.utils.utils import copy_file_to_storage
from ricecooker.utils.utils import extract_path_ext


class Handler(ABC):
    """Base class for handling file fetching and processing"""

    def __init__(self):
        self.parent = None

    @abstractmethod
    def should_handle(self, path: str) -> bool:
        """Check if this handler should handle the given path"""
        pass

    @abstractmethod
    def execute(
        self,
        path: str,
        context: Optional[Dict] = None,
        skip_cache: Optional[bool] = False,
    ) -> list[FileMetadata]:
        pass


class DualModeTemporaryFile:
    """
    A wrapper around NamedTemporaryFile that supports both writing to the filename and file handle writing.
    """

    def __init__(self, ext: Optional[str] = None):
        self._handle = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
        self._handle.close()
        self._write_handle = None

    @property
    def name(self):
        return self._handle.name

    def write(self, data):
        # Write to the file, reopening if needed
        if not self._write_handle:
            self._write_handle = open(self.name, "wb")
        return self._write_handle.write(data)

    def flush(self):
        if self._write_handle:
            self._write_handle.flush()

    def file_not_empty(self):
        if self._write_handle:
            return self._write_handle.tell() > 0
        with open(self.name, "rb") as f:
            # Read a byte from the file to assert we have written something
            return len(f.read(1)) > 0

    def close(self):
        if self._write_handle:
            self._write_handle.close()
            self._write_handle = None

        try:
            os.unlink(self.name)
        except OSError:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()


class FileHandler(Handler):
    """Base leaf class for handling file fetching and processing"""

    CONTEXT_CLASS: ClassVar[Optional[Type[ContextMetadata]]] = ContextMetadata

    # Subclasses can define this list to specify which exceptions should be caught and reported
    HANDLED_EXCEPTIONS = []

    def __init__(self):
        super().__init__()
        self._thread_local = threading.local()

    @property
    def _output_path(self):
        """Thread-safe output path property."""
        return getattr(self._thread_local, "output_path", None)

    @_output_path.setter
    def _output_path(self, value):
        """Thread-safe output path setter."""
        self._thread_local.output_path = value

    def _get_context(self, context: Optional[Dict] = None):
        fields = set(get_type_hints(self.CONTEXT_CLASS).keys())
        context = {k: v for k, v in (context or {}).items() if k in fields}
        try:
            context = self.CONTEXT_CLASS(**context)
        except TypeError:
            missing = fields - set(context)
            raise ValueError(
                f"Missing required context for {self.__class__.__name__}: {missing}"
            )
        return context

    @contextmanager
    def write_file(self, extension: str):
        """
        Context manager that provides a file handle to write to and handles copying to storage.
        """
        with DualModeTemporaryFile(ext=extension) as tempf:
            try:
                yield tempf
            finally:
                tempf.flush()
                if not tempf.file_not_empty():
                    raise InvalidFileException(
                        f"File with extension {extension} failed to write (corrupted)."
                    )
                filename = copy_file_to_storage(tempf.name, ext=extension)
                self._output_path = config.get_storage_path(filename)

    @abstractmethod
    def handle_file(self, path, **kwargs) -> Union[None, FileMetadata]:
        """
        Handle the file at path with the given kwargs.

        Subclasses should do all necessary downloading/processing here.
        Specifically, they may:
         - Read from disk or a remote source
         - Perform transformations or conversions
         - Write the resulting bytes to using the write_file helper contextmanager.

        Returns:
            - None

            - OR a FileMetadata object containing additional metadata about the processed
              file. For example:

                {
                  "file_extension": "mp4",
                  "original_filename": "video_source.mp4",
                  "duration": 120.0,
                  "language": "en",
                  ...
                }
        """
        pass

    @property
    def STAGE(self):
        return self.parent and self.parent.STAGE

    def normalize_path(self, path):
        # If this is a storage path, just use the hashed filename and extension
        if path.startswith(os.path.abspath(config.STORAGE_DIRECTORY)):
            path = os.path.basename(path)
        return path

    def get_cache_key(self, path, **kwargs) -> str:
        return f"{self.STAGE}:{self.normalize_path(path)}"

    def cached_file_outdated(self, filename):
        return False

    def get_file_kwargs(self, context: ContextMetadata) -> list[Dict]:
        """
        An overridable method to return a list of kwargs for the file handler.
        Defaults to [{}] which means that the file handler will be called once.
        This is particularly useful if a single path should be processed multiple times with different kwargs.
        """
        return [context.to_dict()]

    def _get_cached_and_uncached_files(
        self,
        path: str,
        context: ContextMetadata,
        skip_cache: bool,
    ) -> tuple[list[FileMetadata], list[Dict]]:
        kwargs_list = self.get_file_kwargs(context)

        cached_files = []
        uncached_files = []

        for kwargs in kwargs_list:
            cache_key = self.get_cache_key(path, **kwargs)
            file_metadata = get_cache_data(cache_key)
            if (
                file_metadata
                and not skip_cache
                and not self.cached_file_outdated(file_metadata["filename"])
            ):
                file_metadata["path"] = config.get_storage_path(
                    file_metadata["filename"]
                )
                cached_files.append(FileMetadata(**file_metadata))
            else:
                uncached_files.append(kwargs)

        return cached_files, uncached_files

    def execute(
        self,
        path: str,
        context: Optional[Dict] = None,
        skip_cache: Optional[bool] = False,
    ) -> list[FileMetadata]:
        context = self._get_context(context)
        file_metadata_list, uncached_kwargs = self._get_cached_and_uncached_files(
            path, context, skip_cache
        )

        for kwargs in uncached_kwargs:
            self._output_path = None
            if kwargs:
                config.LOGGER.info(
                    f"\tInitiating {self.STAGE} for {path} with kwargs {kwargs}"
                )
            else:
                config.LOGGER.info(f"\tInitiating {self.STAGE} for {path}")

            cache_key = self.get_cache_key(path, **kwargs)

            try:
                file_metadata = self.handle_file(path, **kwargs) or FileMetadata()
            except tuple(self.HANDLED_EXCEPTIONS) as e:
                config.LOGGER.error(
                    f"\tFailed {self.STAGE} for {path} with kwargs {kwargs}"
                )
                raise ExpectedFileException(e) from e

            original_path = path

            path = self._output_path or path

            file_metadata.filename = os.path.basename(path)

            set_cache_data(cache_key, file_metadata.to_dict())

            file_metadata.path = path

            self._output_path = None

            file_metadata_list.append(file_metadata)

            if kwargs:
                config.LOGGER.info(
                    f"\tCompleted {self.STAGE} for {original_path} with kwargs {kwargs} saved to {file_metadata.path}"
                )
            else:
                config.LOGGER.info(
                    f"\tCompleted {self.STAGE} for {original_path} saved to {file_metadata.path}"
                )

        return file_metadata_list


class ExtensionMatchingHandler(FileHandler):
    """Base class for handling files with specific extensions"""

    @property
    @abstractmethod
    def EXTENSIONS(self) -> set[str]:
        pass

    def should_handle(self, path: str) -> bool:
        try:
            ext = extract_path_ext(path)
        except ValueError:
            return False
        return ext in self.EXTENSIONS


class CompositeHandler(Handler):
    """Base composite class for handling file fetching and processing"""

    DEFAULT_CHILDREN: ClassVar[list[Type[FileHandler]]] = []

    def __init__(self, children: Optional[list[Type[FileHandler]]] = None):
        super().__init__()
        if children is None:
            children = [child() for child in self.DEFAULT_CHILDREN]
        self._children = [self.add_child(handler) for handler in children]

    def should_handle(self, path: str) -> bool:
        return any(handler.should_handle(path) for handler in self._children)

    def add_child(self, child):
        child.parent = self
        return child


class FirstHandlerOnly(CompositeHandler):
    """
    A composite handler that will only
    run the first handler that can handle the file.
    """

    def execute(
        self,
        path: str,
        context: Optional[Dict] = None,
        skip_cache: Optional[bool] = False,
    ) -> list[FileMetadata]:
        for handler in self._children:
            if handler.should_handle(path):
                return handler.execute(path, context=context, skip_cache=skip_cache)
        return []


class StageHandler(FirstHandlerOnly):
    @property
    @abstractmethod
    def STAGE(self) -> str:
        pass
