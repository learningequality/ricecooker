import pytest

from ricecooker.utils.pipeline.exceptions import InvalidFileException
from ricecooker.utils.pipeline.file_handler import FileHandler


class TestFileHandler(FileHandler):
    """Test implementation of FileHandler for testing purposes"""

    def should_handle(self, path: str) -> bool:
        return True

    def handle_file(self, path, **kwargs):
        return None


def test_write_file_with_exception_still_checks_file_not_empty():
    """
    Test that file_not_empty check runs even when an exception is caught
    within the context manager. This verifies the try/finally behavior.

    Without the try/finally block, this test would fail because the exception
    would prevent the file_not_empty check from running.
    """
    handler = TestFileHandler()

    # This should raise InvalidFileException from the finally block,
    # not the RuntimeError from the try block
    with pytest.raises(InvalidFileException, match="failed to write \\(corrupted\\)"):
        with handler.write_file("txt"):
            # Don't write anything to file (will make it empty)
            # Then raise an exception that would normally prevent cleanup
            raise RuntimeError("This exception should be caught by try/finally")
