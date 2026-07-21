import shutil
import threading
from unittest.mock import patch

import pytest

from ricecooker.utils.pipeline import FilePipeline
from ricecooker.utils.pipeline.context import FileMetadata
from ricecooker.utils.pipeline.convert import ConversionStageHandler
from ricecooker.utils.pipeline.convert import VideoCompressionHandler
from ricecooker.utils.pipeline.exceptions import InvalidFileException
from ricecooker.utils.pipeline.extract_metadata import ExtractMetadataStageHandler
from ricecooker.utils.pipeline.file_handler import FileHandler
from ricecooker.utils.pipeline.transfer import DownloadStageHandler


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


class ThreadRaceTestHandler(FileHandler):
    def __init__(self):
        super().__init__()
        self.barrier = threading.Barrier(2)  # Synchronize two threads

    def should_handle(self, path: str) -> bool:
        return path.startswith("race-test://")

    def handle_file(self, path, **kwargs):
        file_id = path.split("/")[-1]

        # Set _output_path for this file
        self._output_path = f"/storage/{file_id}.txt"

        # Wait for both threads to reach this point
        self.barrier.wait()

        # Now both threads continue - without thread-local storage,
        # the second one would overwrite _output_path
        return FileMetadata(original_filename=f"{file_id}.txt")


def test_output_path_thread_safety():
    """Test that _output_path is thread-safe and doesn't have race conditions."""
    handler = ThreadRaceTestHandler()
    results = {}

    def thread_a():
        handler._output_path = None
        path = "race-test://file_A"
        output = handler.execute(path)
        results["A"] = output[0].path

    def thread_b():
        handler._output_path = None
        path = "race-test://file_B"
        output = handler.execute(path)
        results["B"] = output[0].path

    thread1 = threading.Thread(target=thread_a)
    thread2 = threading.Thread(target=thread_b)

    thread1.start()
    thread2.start()

    thread1.join()
    thread2.join()

    # Each thread should get its own correct path, not interfere with each other
    assert results["A"] == "/storage/file_A.txt"
    assert results["B"] == "/storage/file_B.txt"


def test_unknown_init_context_field_raises():
    with pytest.raises(TypeError, match="unexpected context"):
        VideoCompressionHandler(bogus=1)


def test_handler_with_no_context_fields_rejects_init_context():
    with pytest.raises(TypeError, match="unexpected context"):
        TestFileHandler(anything=1)


def _fake_compress(path, outpath, overwrite=True, **settings):
    shutil.copyfile(path, outpath)


def _pipeline_with_video_init_context(crf):
    convert = ConversionStageHandler(
        children=[VideoCompressionHandler(video_settings={"crf": crf})]
    )
    return FilePipeline(
        children=[DownloadStageHandler(), convert, ExtractMetadataStageHandler()]
    )


def test_handler_init_context_flows_through_pipeline(video_file):
    pipeline = _pipeline_with_video_init_context(30)
    with patch(
        "ricecooker.utils.pipeline.convert.compress_video", side_effect=_fake_compress
    ) as m:
        pipeline.execute(video_file.path, skip_cache=True)
    assert m.called and m.call_args.kwargs["crf"] == 30


def test_call_context_overrides_handler_init_context(video_file):
    pipeline = _pipeline_with_video_init_context(30)
    with patch(
        "ricecooker.utils.pipeline.convert.compress_video", side_effect=_fake_compress
    ) as m:
        pipeline.execute(
            video_file.path, context={"video_settings": {"crf": 24}}, skip_cache=True
        )
    assert m.called and m.call_args.kwargs["crf"] == 24


def test_file_pipeline_default_context_supplies_compression_settings(video_file):
    """Settings in the pipeline's default_context are passed to handlers."""
    pipeline = FilePipeline(default_context={"video_settings": {"crf": 30}})
    with patch(
        "ricecooker.utils.pipeline.convert.compress_video", side_effect=_fake_compress
    ) as mock_compress:
        pipeline.execute(video_file.path, skip_cache=True)

    assert mock_compress.called, "Video compression should use default context settings"
    assert mock_compress.call_args.kwargs["crf"] == 30


def test_file_pipeline_execute_context_overrides_default_context(video_file):
    """Context passed to execute() takes precedence over default_context."""
    pipeline = FilePipeline(default_context={"video_settings": {"crf": 30}})
    with patch(
        "ricecooker.utils.pipeline.convert.compress_video", side_effect=_fake_compress
    ) as mock_compress:
        pipeline.execute(
            video_file.path, context={"video_settings": {"crf": 24}}, skip_cache=True
        )

    assert mock_compress.called
    assert mock_compress.call_args.kwargs["crf"] == 24
