"""Tests for the thumbnail extraction pipeline stage."""

import os
import shutil
import tempfile
from unittest.mock import patch

from le_utils.constants import format_presets

from ricecooker.utils.pipeline.context import NODE_HAS_THUMBNAIL
from ricecooker.utils.pipeline.thumbnails import ThumbnailStageHandler


def _assert_source_and_thumbnail(results, source_path, expected_preset):
    assert len(results) == 2, "expected source pass-through plus thumbnail"
    source, thumb = results
    assert source.path == source_path
    assert thumb.preset == expected_preset
    assert thumb.path.endswith(".png")
    assert os.path.getsize(thumb.path) > 0


def test_generates_thumbnail_from_pdf(document_file):
    results = ThumbnailStageHandler().execute(document_file.path, skip_cache=True)
    _assert_source_and_thumbnail(
        results, document_file.path, format_presets.DOCUMENT_THUMBNAIL
    )


def test_generates_thumbnail_from_epub(epub_file):
    results = ThumbnailStageHandler().execute(epub_file.path, skip_cache=True)
    _assert_source_and_thumbnail(
        results, epub_file.path, format_presets.DOCUMENT_THUMBNAIL
    )


def test_generates_thumbnail_from_html_zip(html_file):
    results = ThumbnailStageHandler().execute(html_file.path, skip_cache=True)
    _assert_source_and_thumbnail(
        results, html_file.path, format_presets.HTML5_THUMBNAIL
    )


def test_generates_thumbnail_from_mp4(video_file):
    # webm is also a supported extension but shares the
    # extract_thumbnail_from_video code path with mp4; no webm fixture
    # exists, so mp4 covers the video path.
    results = ThumbnailStageHandler().execute(video_file.path, skip_cache=True)
    _assert_source_and_thumbnail(
        results, video_file.path, format_presets.VIDEO_THUMBNAIL
    )


def test_generates_thumbnail_from_kpub(html_file):
    # kpub (HTML5_ARTICLE) zips share the zip extraction path with html5,
    # but map to the document thumbnail preset.
    tempdir = tempfile.mkdtemp()
    try:
        path = os.path.join(tempdir, "test.kpub")
        shutil.copy(html_file.path, path)
        results = ThumbnailStageHandler().execute(path, skip_cache=True)
        _assert_source_and_thumbnail(results, path, format_presets.DOCUMENT_THUMBNAIL)
    finally:
        shutil.rmtree(tempdir)


def test_unsupported_format_passes_through(audio_file):
    results = ThumbnailStageHandler().execute(audio_file.path, skip_cache=True)
    assert len(results) == 1
    assert results[0].path == audio_file.path


def test_invalid_pdf_passes_source_through(invalid_document_file):
    results = ThumbnailStageHandler().execute(
        invalid_document_file.path, skip_cache=True
    )
    assert len(results) == 1
    assert results[0].path == invalid_document_file.path


def test_empty_thumbnail_output_passes_source_through(document_file):
    # An extractor that completes without writing any bytes triggers
    # write_file's InvalidFileException; the stage treats it as best-effort
    # and passes the source through rather than failing the node.
    with patch(
        "ricecooker.utils.pipeline.thumbnails.create_image_from_pdf_page"
    ) as mock_create:
        results = ThumbnailStageHandler().execute(document_file.path, skip_cache=True)
    assert mock_create.called
    assert len(results) == 1
    assert results[0].path == document_file.path


def test_skips_generation_when_node_has_thumbnail(document_file):
    with patch(
        "ricecooker.utils.pipeline.thumbnails.create_image_from_pdf_page"
    ) as mock_create:
        results = ThumbnailStageHandler().execute(
            document_file.path,
            context={NODE_HAS_THUMBNAIL: True},
            skip_cache=True,
        )
    # The length check below is the real guard: when generation is skipped,
    # handle_file is never invoked, so the mock can never be reached.
    assert not mock_create.called
    assert len(results) == 1
    assert results[0].path == document_file.path


def test_generates_when_node_has_thumbnail_is_false(document_file):
    results = ThumbnailStageHandler().execute(
        document_file.path,
        context={NODE_HAS_THUMBNAIL: False},
        skip_cache=True,
    )
    assert len(results) == 2
    assert results[1].preset == format_presets.DOCUMENT_THUMBNAIL


def test_thumbnail_cached_on_second_run(document_file):
    # Copy to a unique path so this test never collides with cache entries
    # written by other tests or earlier runs.
    tempdir = tempfile.mkdtemp()
    try:
        path = os.path.join(tempdir, "cached_thumbnail_test.pdf")
        shutil.copy(document_file.path, path)
        stage = ThumbnailStageHandler()
        first = stage.execute(path, skip_cache=True)
        with patch(
            "ricecooker.utils.pipeline.thumbnails.create_image_from_pdf_page"
        ) as mock_create:
            second = stage.execute(path)
        assert not mock_create.called, "second run should be served from cache"
        assert second[1].filename == first[1].filename
    finally:
        shutil.rmtree(tempdir)
