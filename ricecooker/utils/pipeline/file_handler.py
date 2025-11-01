import os
import tempfile
import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import ClassVar, Dict, Optional, Type, List, Union, get_type_hints

from .context import ContextMetadata, FileMetadata
from .exceptions import ExpectedFileException, InvalidFileException
from ricecooker import config
from ricecooker.utils.caching import get_cache_data, set_cache_data
from ricecooker.utils.utils import copy_file_to_storage, extract_path_ext


class Handler(ABC):
    """Base class for handling file fetching and processing"""

    def __init__(self, **context):
        self._fixed_context = context or {}
        self.parent = None

    @abstractmethod
    def should_handle(self, path: str) -> bool:
        pass

    @abstractmethod
    def execute(self, path: str, context: Optional[Dict] = None, skip_cache: bool = False) -> List[FileMetadata]:
        pass


class DualModeTemporaryFile:
    """Temporary file helper, similar to previous implementation."""

    def __init__(self, ext: str = ""):
        self._file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        self._write_handle = None
        self._read_handle = None
        self.name = self._file.name

    def __enter__(self):
        self._write_handle = open(self.name, "wb")
        return self

    def write(self, data):
        return self._write_handle.write(data)

    def file_not_empty(self):
        self._write_handle.flush()
        return os.path.getsize(self.name) > 0

    def __exit__(self, exc_type, exc_value, traceback):
        if self._write_handle:
            self._write_handle.close()
        try:
            os.unlink(self.name)
        except OSError:
            pass


class FileHandler(Handler):
    """Base class for handling file fetching and processing"""

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

    def _get_context(self, context: Optional[Dict] = None) -> Dict:
        merged_context = {**self._fixed_context, **(context or {})}
        if self.CONTEXT_CLASS:
            # Optional: validate fields using get_type_hints
            hints = get_type_hints(self.CONTEXT_CLASS)
            for key in hints:
                if key not in merged_context:
                    raise ValueError(f"Missing context field: {key}")
            return self.CONTEXT_CLASS(**merged_context)
        return merged_context

    @contextmanager
    def write_file(self, extension: str):
        with DualModeTemporaryFile(ext=extension) as tempf:
            yield tempf
            if not tempf.file_not_empty():
                raise InvalidFileException("File is empty")
            # Copy to storage
            self._output_path = copy_file_to_storage(tempf.name)

    @abstractmethod
    def handle_file(self, path: str, **kwargs) -> Union[None, FileMetadata]:
        """Subclasses must implement actual file handling"""
        context = {**self._fixed_context, **kwargs}
        pass

    def normalize_path(self, path: str) -> str:
        if path.startswith(os.path.abspath(config.STORAGE_DIRECTORY)):
            path = os.path.basename(path)
        return path

    def cached_file_outdated(self, filename: str) -> bool:
        return False

    def get_file_kwargs(self, context: ContextMetadata) -> List[Dict]:
        return [context.to_dict()]

    def _get_cached_and_uncached_files(
        self, path: str, context: ContextMetadata, skip_cache: bool
    ) -> tuple[List[FileMetadata], List[Dict]]:
        kwargs_list = self.get_file_kwargs(context)
        cached_files, uncached_files = [], []
        # Implement cache logic if needed
        return cached_files, uncached_files

    def execute(self, path: str, context: Optional[Dict] = None, skip_cache: bool = False) -> List[FileMetadata]:
        context = self._get_context(context)
        cached_files, uncached_kwargs = self._get_cached_and_uncached_files(path, context, skip_cache)
        results = cached_files.copy()
        for kwargs in uncached_kwargs:
            try:
                fm = self.handle_file(path, **kwargs)
            except Exception as e:
                raise ExpectedFileException(e)
            if fm:
                results.append(fm)
        self._output_path = None
        return results


class CompositeHandler(Handler):
    def __init__(self, **context):
        super().__init__(**context)
        self._children: List[Handler] = []

    def add_child(self, child: Handler) -> Handler:
        child.parent = self
        self._children.append(child)
        return child


class FirstHandlerOnly(CompositeHandler):
    def execute(self, path: str, context: Optional[Dict] = None, skip_cache: bool = False) -> List[FileMetadata]:
        for handler in self._children:
            if handler.should_handle(path):
                return handler.execute(path, context=context, skip_cache=skip_cache)
        return []


class StageHandler(FirstHandlerOnly):
    @property
    @abstractmethod
    def STAGE(self) -> str:
        pass

