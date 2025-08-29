""" Tests for file downloading and processing """
import base64
import hashlib
import os.path
import tempfile
import zipfile
from io import BytesIO
from shutil import copyfile
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from le_utils.constants import file_formats
from le_utils.constants import format_presets
from le_utils.constants import languages
from le_utils.constants.exercises import GRAPHIE_DELIMITER
from PIL import Image
from PyPDF2 import PdfFileWriter
from requests import ConnectionError
from requests import HTTPError
from test_pdfutils import _save_file_url_to_path
from vcr_config import my_vcr

from ricecooker import config
from ricecooker.classes.files import _ExerciseGraphieFile
from ricecooker.classes.files import AudioFile
from ricecooker.classes.files import Base64ImageFile
from ricecooker.classes.files import CONVERTIBLE_FORMATS
from ricecooker.classes.files import DocumentFile
from ricecooker.classes.files import DownloadFile
from ricecooker.classes.files import File
from ricecooker.classes.files import H5PFile
from ricecooker.classes.files import HTMLZipFile
from ricecooker.classes.files import StudioFile
from ricecooker.classes.files import SubtitleFile
from ricecooker.classes.files import VideoFile
from ricecooker.classes.files import YouTubeVideoFile
from ricecooker.utils.audio import AudioCompressionError
from ricecooker.utils.pipeline.convert import PDFValidationHandler
from ricecooker.utils.pipeline.exceptions import InvalidFileException
from ricecooker.utils.videos import VideoCompressionError
from ricecooker.utils.zip import create_predictable_zip


@pytest.fixture
def mock_filecache():
    """
    Mock cache that stores key/value pairs in a dict
    Useful to have the cache isolated from the other tests
    """

    class MockFileCache:
        def __init__(self):
            self.cache = {}

        def get(self, key):
            return self.cache.get(key)

        def set(self, key, value):
            self.cache[key] = value

    mock_cache = MockFileCache()
    with patch("ricecooker.utils.caching.FILECACHE", mock_cache):
        yield mock_cache


# Process all of the files
def process_files(
    video_file,
    html_file,
    audio_file,
    document_file,
    epub_file,
    thumbnail_file,
    subtitle_file,
):
    video_file.process_file()
    html_file.process_file()
    audio_file.process_file()
    document_file.process_file()
    epub_file.process_file()
    thumbnail_file.process_file()
    subtitle_file.process_file()


""" *********** DOWNLOAD TESTS *********** """


def test_download(
    video_file,
    html_file,
    audio_file,
    document_file,
    epub_file,
    thumbnail_file,
    subtitle_file,
):
    try:
        process_files(
            video_file,
            html_file,
            audio_file,
            document_file,
            epub_file,
            thumbnail_file,
            subtitle_file,
        )
        assert True
    except Exception:
        assert False, "One or more of the files failed to download"


def test_download_filenames(
    video_file,
    video_filename,
    html_file,
    html_filename,
    audio_file,
    audio_filename,
    document_file,
    document_filename,
    epub_file,
    epub_filename,
    thumbnail_file,
    thumbnail_filename,
    subtitle_file,
    subtitle_filename,
):
    assert (
        video_file.process_file() == video_filename
    ), "Video file should have filename {}".format(video_filename)
    assert (
        html_file.process_file() == html_filename
    ), "HTML file should have filename {}".format(html_filename)
    assert (
        audio_file.process_file() == audio_filename
    ), "Audio file should have filename {}".format(audio_filename)
    assert (
        document_file.process_file() == document_filename
    ), "PDF document file should have filename {}".format(document_filename)
    assert (
        epub_file.process_file() == epub_filename
    ), "ePub document file should have filename {}".format(epub_filename)
    assert (
        thumbnail_file.process_file() == thumbnail_filename
    ), "Thumbnail file should have filename {}".format(thumbnail_filename)
    assert (
        subtitle_file.process_file() == subtitle_filename
    ), "Subtitle file should have filename {}".format(subtitle_filename)


def read_file_hash(filepath):
    BUF_SIZE = 65536

    md5 = hashlib.md5()

    with open(filepath, "rb") as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            md5.update(data)
    return md5.hexdigest()


def test_download_to_storage(
    video_file,
    video_filename,
    html_file,
    html_filename,
    audio_file,
    audio_filename,
    document_file,
    document_filename,
    epub_file,
    epub_filename,
    thumbnail_file,
    thumbnail_filename,
    subtitle_file,
    subtitle_filename,
):
    process_files(
        video_file,
        html_file,
        audio_file,
        document_file,
        epub_file,
        thumbnail_file,
        subtitle_file,
    )
    video_path = config.get_storage_path(video_filename)
    html_path = config.get_storage_path(html_filename)
    audio_path = config.get_storage_path(audio_filename)
    document_path = config.get_storage_path(document_filename)
    epub_path = config.get_storage_path(epub_filename)
    thumbnail_path = config.get_storage_path(thumbnail_filename)
    subtitle_path = config.get_storage_path(subtitle_filename)

    assert os.path.isfile(video_path), "Video should be stored at {}".format(video_path)
    assert (
        read_file_hash(video_path) == video_filename.split(".")[0]
    ), "Video hash should match"
    assert os.path.isfile(html_path), "HTML should be stored at {}".format(html_path)
    assert (
        read_file_hash(html_path) == html_filename.split(".")[0]
    ), "HTML hash should match"
    assert os.path.isfile(audio_path), "Audio should be stored at {}".format(audio_path)
    assert (
        read_file_hash(audio_path) == audio_filename.split(".")[0]
    ), "Audio hash should match"
    assert os.path.isfile(document_path), "PDF document should be stored at {}".format(
        document_path
    )
    assert (
        read_file_hash(document_path) == document_filename.split(".")[0]
    ), "PDF hash should match"
    assert os.path.isfile(epub_path), "ePub document should be stored at {}".format(
        epub_path
    )
    assert (
        read_file_hash(epub_path) == epub_filename.split(".")[0]
    ), "ePub hash should match"
    assert os.path.isfile(thumbnail_path), "Thumbnail should be stored at {}".format(
        thumbnail_path
    )
    assert (
        read_file_hash(thumbnail_path) == thumbnail_filename.split(".")[0]
    ), "Thumbnail hash should match"
    assert os.path.isfile(subtitle_path), "Subtitle should be stored at {}".format(
        subtitle_path
    )
    assert (
        read_file_hash(subtitle_path) == subtitle_filename.split(".")[0]
    ), "Subtitle hash should match"


# Base File class method tests


@pytest.fixture
def mock_node():
    """Mock node with source_id for testing truncation logs"""

    class MockNode:
        def __init__(self):
            self.source_id = "test_123"

    return MockNode()


def test_truncate_original_filename(mock_node):
    """Test that original_filename gets truncated to max length"""
    test_file = File()
    test_file.original_filename = "x" * (config.MAX_ORIGINAL_FILENAME_LENGTH + 10)

    test_file.node = mock_node

    test_file.truncate_fields()

    assert len(test_file.original_filename) == config.MAX_ORIGINAL_FILENAME_LENGTH


def test_truncate_source_url(mock_node):
    """Test that source_url gets truncated to max length"""
    test_file = File()
    test_file.source_url = "http://example.com/" + "x" * config.MAX_SOURCE_URL_LENGTH
    test_file.node = mock_node
    test_file.truncate_fields()

    assert len(test_file.source_url) == config.MAX_SOURCE_URL_LENGTH


def test_truncate_preserves_extension(mock_node):
    """Test that truncation preserves the file extension"""
    test_file = File()
    long_name = "x" * config.MAX_ORIGINAL_FILENAME_LENGTH + ".pdf"
    test_file.original_filename = long_name
    test_file.node = mock_node
    test_file.truncate_fields()

    assert test_file.original_filename.endswith(".pdf")
    assert len(test_file.original_filename) == config.MAX_ORIGINAL_FILENAME_LENGTH


def test_truncate_non_ascii(mock_node):
    """Test truncation with non-ASCII characters"""
    test_file = File()
    # Unicode characters: é (2 bytes), 世 (3 bytes), 🌍 (4 bytes)
    test_file.original_filename = "é世🌍" * (config.MAX_ORIGINAL_FILENAME_LENGTH)
    test_file.node = mock_node
    test_file.truncate_fields()

    assert len(test_file.original_filename) == config.MAX_ORIGINAL_FILENAME_LENGTH
    # Verify we still have valid UTF-8 after truncation
    assert (
        test_file.original_filename.encode("utf-8").decode("utf-8")
        == test_file.original_filename
    )


# Basic file download error handling tests


@pytest.fixture
def mock_session():
    with patch.object(config, "DOWNLOAD_SESSION") as mock_session:
        yield mock_session


def test_download_file_404_error(mock_session):
    """Test that 404 errors are properly caught"""
    mock_session.get.side_effect = HTTPError("404 Client Error: Not Found")

    download_file = DownloadFile("http://fake.url/file.txt")
    result = download_file.process_file()

    assert result is None
    assert "404 Client Error" in download_file.error
    assert download_file in config.FAILED_FILES


def test_download_file_connection_timeout(mock_session):
    """Test handling of connection timeouts"""
    mock_session.get.side_effect = ConnectionError("Connection timed out")

    download_file = DownloadFile("http://fake.url/file.txt")
    result = download_file.process_file()

    assert result is None
    assert "Connection timed out" in download_file.error
    assert download_file in config.FAILED_FILES


# Check basic caching for downloaded files


def test_downloadfile_basic_caching(document_file):
    """Test that DocumentFile caches processed files"""
    # First download should process and cache
    filename1 = document_file.process_file()
    assert filename1 is not None

    # Second download should use cache
    doc_file2 = DocumentFile(document_file.path)
    with patch(
        "ricecooker.utils.pipeline.transfer.DiskResourceHandler.handle_file"
    ) as mock_write:
        filename2 = doc_file2.process_file()
        assert not mock_write.called
        assert filename2 == filename1


def test_file_cache_invalidation_with_update(document_file):
    """Test cache invalidation when UPDATE flag is set"""
    # Initial download
    filename1 = document_file.process_file()
    assert filename1 is not None

    # With UPDATE flag should reprocess
    with patch("ricecooker.config.UPDATE", True):
        doc_file2 = DocumentFile(document_file.path)
        filename2 = doc_file2.process_file()
        # But should get same hash since content unchanged
        assert filename2 == filename1


# Test caching and error handling for media compression


def test_videofile_compression_caching(video_file):
    """Test VideoFile caches both raw and compressed versions"""
    # Process with no compression
    filename1 = video_file.process_file()
    assert filename1 is not None

    # Process with compression settings
    video_file2 = VideoFile(video_file.path, ffmpeg_settings={"max_height": 480})
    filename2 = video_file2.process_file()

    # Should get different cache entries due to different settings
    assert filename2 != filename1

    with patch("ricecooker.utils.pipeline.convert.compress_video") as mock_compress:
        # Third file with same settings should use cache
        video_file3 = VideoFile(video_file.path, ffmpeg_settings={"max_height": 480})
        filename3 = video_file3.process_file()
        assert not mock_compress.called
        assert filename3 == filename2


def test_video_compression_error(video_file):
    """Test that video compression errors are properly handled"""
    with patch("ricecooker.utils.pipeline.convert.compress_video") as mock_compress:
        mock_compress.side_effect = VideoCompressionError("FFmpeg failed")

        video_file = VideoFile(video_file.path, ffmpeg_settings={"crf": 32})
        result = video_file.process_file()

        assert result is None
        assert video_file in config.FAILED_FILES


def test_audiofile_compression_caching(audio_file):
    """Test AudioFile caches compressed versions separately"""
    # Process with default compression
    filename1 = audio_file.process_file()
    assert filename1 is not None

    # Process with custom compression
    audio_file2 = AudioFile(audio_file.path, ffmpeg_settings={"bit_rate": 32})
    filename2 = audio_file2.process_file()

    # Should be different cache entries
    assert filename2 != filename1

    # Same settings should use cache
    audio_file3 = AudioFile(audio_file.path, ffmpeg_settings={"bit_rate": 32})
    with patch("ricecooker.utils.pipeline.convert.compress_audio") as mock_compress:
        filename3 = audio_file3.process_file()
        assert not mock_compress.called
        assert filename3 == filename2


def test_audio_compression_error(audio_file):
    """Test that audio compression errors are properly handled"""
    with patch("ricecooker.utils.pipeline.convert.compress_audio") as mock_compress:
        mock_compress.side_effect = AudioCompressionError("Audio compression failed")

        audio_file = AudioFile(audio_file.path, ffmpeg_settings={"bitrate": "32k"})
        result = audio_file.process_file()

        assert result is None
        assert audio_file in config.FAILED_FILES


def test_set_language():
    sub1 = SubtitleFile("path", language="en")
    sub2 = SubtitleFile("path", language=languages.getlang("es"))
    assert isinstance(
        sub1.language, str
    ), "Subtitles must be converted to Language class"
    assert isinstance(sub2.language, str), "Subtitles can be passed as Langauge models"
    assert sub1.language == "en", "Subtitles must have a language"
    assert sub2.language == "es", "Subtitles must have a language"
    pytest.raises(TypeError, SubtitleFile, "path", language="notalanguage")


# Video validation tests


def test_allowed_video_formats():
    # MP4 and WEBM are allowed formats
    for ext in [file_formats.MP4, file_formats.WEBM]:
        video = VideoFile(f"/path/to/video.{ext}")
        try:
            video.validate()  # Should not raise error
        except ValueError as e:
            pytest.fail(f"Validation failed for {ext}: {str(e)}")


def test_disallowed_video_formats():
    video = VideoFile("/path/to/video.xyz")
    with pytest.raises(ValueError) as excinfo:
        video.validate()
    assert "Incompatible extension" in str(excinfo.value)


def test_convertible_video_formats():
    # AVI and MOV are convertible formats
    for ext in CONVERTIBLE_FORMATS[format_presets.VIDEO_HIGH_RES]:
        video = VideoFile(f"/path/to/video.{ext}")
        try:
            video.validate()  # Should not raise error
        except ValueError as e:
            pytest.fail(f"Validation failed for {ext}: {str(e)}")


def test_video_default_ext():
    video = VideoFile("/path/to/video", default_ext=file_formats.MP4)
    try:
        video.validate()  # Should not raise error
    except ValueError as e:
        pytest.fail(f"Validation failed: {str(e)}")


def test_video_no_extension_no_default():
    video = VideoFile("/path/to/video")
    video.default_ext = None
    with pytest.raises(ValueError) as excinfo:
        video.validate()
    assert "No extension" in str(excinfo.value)


# Audio validation tests
def test_allowed_audio_formats():
    # Only MP3 is allowed
    audio = AudioFile("/path/to/audio.mp3")
    try:
        audio.validate()  # Should not raise error
    except ValueError as e:
        pytest.fail(f"Validation failed: {str(e)}")


def test_convertible_audio_formats():
    # wav and ogg are convertible formats
    for ext in CONVERTIBLE_FORMATS[format_presets.AUDIO]:
        audio = AudioFile(f"/path/to/audio.{ext}")
        try:
            audio.validate()  # Should not raise error
        except ValueError as e:
            pytest.fail(f"Validation failed for {ext}: {str(e)}")


def test_disallowed_audio_format():
    audio = AudioFile("/path/to/audio.xyz")
    with pytest.raises(ValueError) as excinfo:
        audio.validate()
    assert "Incompatible extension" in str(excinfo.value)


def test_audio_default_ext():
    audio = AudioFile("/path/to/audio", default_ext=file_formats.MP3)
    try:
        audio.validate()  # Should not raise error
    except ValueError as e:
        pytest.fail(f"Validation failed: {str(e)}")


def test_audio_no_extension_no_default():
    audio = AudioFile("/path/to/audio")
    audio.default_ext = None
    with pytest.raises(ValueError) as excinfo:
        audio.validate()
    assert "No extension" in str(excinfo.value)


# Subtitle validation tests


def test_vtt_format_validation():
    """Test .vtt subtitle format passes validation"""
    subtitle = SubtitleFile("/path/to/subs.vtt", language="en")
    subtitle.validate()  # Should not raise error


def test_convertible_subtitle_formats():
    """Test convertible formats (.srt, .ttml, etc) pass validation"""
    for fmt in CONVERTIBLE_FORMATS[format_presets.VIDEO_SUBTITLE]:
        subtitle = SubtitleFile(f"/path/to/subs.{fmt}", language="en")
        try:
            subtitle.validate()  # Should not raise error
        except ValueError as e:
            pytest.fail(f"Validation failed for {fmt}: {str(e)}")


def test_subtitle_format_specified():
    """Test validation passes when subtitlesformat is specified"""
    subtitle = SubtitleFile("/path/to/subs", language="en", subtitlesformat="srt")
    subtitle.validate()  # Should not raise error


def test_invalid_format_validation():
    """Test invalid format fails validation when no subtitlesformat specified"""
    subtitle = SubtitleFile("/path/to/subs.xyz", language="en")
    with pytest.raises(ValueError) as excinfo:
        subtitle.validate()
    assert "Incompatible extension" in str(excinfo.value)


def test_missing_language_validation():
    """Test validation fails when language is not specified"""
    with pytest.raises(AssertionError) as excinfo:
        SubtitleFile("/path/to/subs.vtt")  # No language specified
    assert "Subtitles must have a language" in str(excinfo.value)


# Zip file validation tests


@pytest.fixture
def valid_zip():
    # Create a temporary zip file with index.html
    fd, path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)

    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("index.html", "<html><body>Test</body></html>")

    yield path
    os.unlink(path)


@pytest.fixture
def invalid_zip():
    # Create a temporary zip file without index.html
    fd, path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)

    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("notindex.html", "<html><body>Test</body></html>")

    yield path
    os.unlink(path)


@pytest.fixture
def nested_index_zip():
    # Create a temporary zip file with nested index.html
    fd, path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)

    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("folder/index.html", "<html><body>Test</body></html>")

    yield path
    os.unlink(path)


def test_valid_htmlzip_validation(valid_zip):
    html_file = HTMLZipFile(valid_zip)
    html_file.process_file()

    assert html_file.filename is not None
    assert html_file.error is None


def test_invalid_htmlzip_validation(invalid_zip):
    html_file = HTMLZipFile(invalid_zip)
    html_file.process_file()

    assert html_file.filename is None
    assert html_file.error is not None
    assert "index.html" in html_file.error


def test_nested_index_htmlzip_validation(nested_index_zip):
    html_file = HTMLZipFile(nested_index_zip)
    html_file.process_file()

    assert html_file.filename is None
    assert html_file.error is not None
    assert "index.html" in html_file.error


@pytest.mark.skip(
    "Currently leaving this disabled as it is not a common use case - and the new validation is too strict for this case"
)
def test_dependency_zip_validation(invalid_zip):
    html_file = HTMLZipFile(invalid_zip, preset=format_presets.HTML5_DEPENDENCY_ZIP)
    html_file.process_file()

    assert html_file.filename is not None
    assert html_file.error is None


# H5P file validation tests


@pytest.fixture
def valid_h5p():
    # Create a temporary h5p file with valid json files
    fd, path = tempfile.mkstemp(suffix=".h5p")
    os.close(fd)

    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("h5p.json", '{"valid": "json"}')
        zf.writestr("content/content.json", '{"valid": "content"}')

    yield path
    os.unlink(path)


@pytest.fixture
def missing_h5p_json():
    fd, path = tempfile.mkstemp(suffix=".h5p")
    os.close(fd)

    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("content/content.json", '{"valid": "content"}')

    yield path
    os.unlink(path)


@pytest.fixture
def missing_content_json():
    fd, path = tempfile.mkstemp(suffix=".h5p")
    os.close(fd)

    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("h5p.json", '{"valid": "json"}')

    yield path
    os.unlink(path)


@pytest.fixture
def malformed_jsons():
    fd, path = tempfile.mkstemp(suffix=".h5p")
    os.close(fd)

    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("h5p.json", "{invalid json")
        zf.writestr("content/content.json", "{also invalid")

    yield path
    os.unlink(path)


def test_valid_h5p_validation(valid_h5p):
    h5p_file = H5PFile(valid_h5p)
    h5p_file.process_file()

    assert h5p_file.filename is not None
    assert h5p_file.error is None


def test_missing_h5p_json_validation(missing_h5p_json):
    h5p_file = H5PFile(missing_h5p_json)
    h5p_file.process_file()

    assert h5p_file.filename is None
    assert h5p_file.error is not None
    assert "h5p.json" in h5p_file.error


def test_missing_content_json_validation(missing_content_json):
    h5p_file = H5PFile(missing_content_json)
    h5p_file.process_file()

    assert h5p_file.filename is None
    assert h5p_file.error is not None
    assert "content.json" in h5p_file.error


def test_malformed_json_validation(malformed_jsons):
    h5p_file = H5PFile(malformed_jsons)
    h5p_file.process_file()

    assert h5p_file.filename is None
    assert h5p_file.error is not None
    # The error from zipfile will be about not finding valid JSON files
    # since it won't be able to parse them
    assert any(x in h5p_file.error for x in ["h5p.json", "content.json"])


@pytest.mark.skip(
    "Skipping one-off create_predictable_zip stress test because long running..."
)
def test_create_many_predictable_zip_files(ndirs=8193):
    """
    Regression test for `OSError: [Errno 24] Too many open files` when using
    ricecooker.utils.zip.create_predictable_zip helper method:
    https://github.com/learningequality/ricecooker/issues/185
    Run `ulimit -a` to see the limits for # open files on your system and set ndirs
    to higher number to use this test. Also comment out the @pytest.mark.skip
    """
    zip_paths = []
    for _ in range(0, ndirs):
        inputdir = tempfile.mkdtemp()
        with open(os.path.join(inputdir, "index.html"), "w") as testf:
            testf.write("something something")
        zip_path = create_predictable_zip(inputdir)
        zip_paths.append(zip_path)
    assert len(zip_paths) == ndirs, "wrong number of zip files created"


""" *********** YOUTUBEVIDEOFILE TESTS *********** """


@my_vcr.use_cassette
def test_youtubevideo_process_file(youtube_video_dict):
    video_file = YouTubeVideoFile(youtube_id=youtube_video_dict["youtube_id"])
    filename = video_file.process_file()
    assert filename is not None, "Processing YouTubeVideoFile file failed"
    assert filename.endswith(".mp4"), "Wrong extenstion for video"


""" *********** SUBTITLEFILE TESTS *********** """


def test_convertible_substitles_ar_srt():
    """
    Basic check that srt --> vtt conversion works.
    """
    local_path = os.path.join("tests", "testcontent", "samples", "testsubtitles_ar.srt")
    assert os.path.exists(local_path)
    subtitle_file = SubtitleFile(local_path, language="ar")
    filename = subtitle_file.process_file()
    assert filename, "converted filename must exist"
    assert filename.endswith(".vtt"), "converted filename must have .vtt extension"
    storage_path = config.get_storage_path(filename)
    with open(storage_path, encoding="utf-8") as converted_vtt:
        filecontents = converted_vtt.read()
        check_words = "لناس على"
        assert check_words in filecontents, "expected words not found in converted subs"


@pytest.fixture
def bad_subtitles_file():
    local_path = os.path.join("tests", "testcontent", "generated", "unconvetible.sub")
    if not os.path.exists(local_path):
        with open(local_path, "wb") as f:
            f.write(b"this is an invalid subtitle file that cant be converted.")
            f.flush()
    else:
        f = open(local_path, "rb")
        f.close()
    return f  # returns a closed file descriptor which we use for name attribute


def test_bad_subtitles_raises(bad_subtitles_file):
    subs_file = SubtitleFile(bad_subtitles_file.name, language="en")
    assert subs_file.process_file() is None


PRESSURECOOKER_REPO_URL = "https://raw.githubusercontent.com/bjester/pressurecooker/"
PRESSURECOOKER_FILES_URL_BASE = (
    PRESSURECOOKER_REPO_URL + "pycaption/tests/files/subtitles/"
)
PRESSURECOOKER_SUBS_FIXTURES = [
    {
        "srcfilename": "basic.srt",
        "subtitlesformat": "srt",
        "language": languages.getlang("ar"),
        "check_words": "البعض أكثر",
    },
    {
        "srcfilename": "encapsulated.sami",
        "subtitlesformat": "sami",
        "language": "en",
        "check_words": "we have this vision of Einstein",
    },
    {
        "srcfilename": "basic.vtt",
        "subtitlesformat": "vtt",
        "language": "ar",
        "check_words": "البعض أكثر",
    },
    {
        "srcfilename": "encapsulated.vtt",
        "subtitlesformat": "vtt",
        "language": "en",
        "check_words": "we have this vision of Einstein",
    },
]


def download_fixture_files(fixtures_list):
    """
    Downloads all the subtitles test files and return as list of fixutes dicts.
    """
    fixtures = []
    for fixture in fixtures_list:
        srcfilename = fixture["srcfilename"]
        # localpath = os.path.join("tests", "testcontent", "downloaded", srcfilename)
        local_path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__), "testcontent", "downloaded", srcfilename
            )
        )

        if not os.path.exists(local_path):
            url = (
                fixture["url"]
                if "url" in fixture.keys()
                else PRESSURECOOKER_FILES_URL_BASE + srcfilename
            )
            _save_file_url_to_path(url, local_path)
            assert os.path.exists(local_path), (
                "Error mising local test file " + local_path
            )
        fixture["localpath"] = local_path
        fixtures.append(fixture)
    return fixtures


@pytest.fixture
def pressurecooker_test_files():
    """
    Downloads all the subtitles test files and return as list of fixutes dicts.
    """
    return download_fixture_files(PRESSURECOOKER_SUBS_FIXTURES)


def test_convertible_subtitles_from_pressurecooker(pressurecooker_test_files):
    """
    Try to load all the test files used in pressurecooker as ricecooker `SubtitleFile`s.
    All subs have the appropriate extension so no need to specify `subtitlesformat`.
    """
    for fixture in pressurecooker_test_files:
        localpath = fixture["localpath"]
        assert os.path.exists(localpath), "Error mising local test file " + localpath
        subtitle_file = SubtitleFile(localpath, language=fixture["language"])
        filename = subtitle_file.process_file()
        assert filename, "converted filename must exist"
        assert filename.endswith(".vtt"), "converted filename must have .vtt extension"
        storage_path = config.get_storage_path(filename)
        with open(storage_path, encoding="utf-8") as converted_vtt:
            filecontents = converted_vtt.read()
            assert (
                fixture["check_words"] in filecontents
            ), "missing check_words in converted subs"


def test_convertible_substitles_ar_ttml():
    """
    Regression test to make sure correct lang_code is detected from .ttml data.
    """
    local_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "testcontent",
            "samples",
            "testsubtitles_ar.ttml",
        )
    )

    assert os.path.exists(local_path)
    subtitle_file = SubtitleFile(local_path, language="ar")
    filename = subtitle_file.process_file()
    assert filename, "converted filename must exist"
    assert filename.endswith(".vtt"), "converted filename must have .vtt extension"


def test_convertible_subtitles_noext_subtitlesformat():
    """
    Check that we handle correctly cases when path doesn't contain extension.
    """
    local_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "testcontent",
            "samples",
            "testsubtitles_ar.ttml",
        )
    )
    assert os.path.exists(local_path)
    local_path_no_ext = local_path.replace(".ttml", "")
    copyfile(local_path, local_path_no_ext)
    assert os.path.exists(local_path_no_ext)
    try:
        subtitle_file = SubtitleFile(
            local_path_no_ext,
            language="ar",
            subtitlesformat="ttml",  # settting subtitlesformat becaue no ext
        )
        filename = subtitle_file.process_file()
        assert filename, "converted filename must exist"
        assert filename.endswith(".vtt"), "converted filename must have .vtt extension"
    finally:
        os.remove(local_path_no_ext)


def test_convertible_substitles_weirdext_subtitlesformat():
    """
    Check that we handle cases when ext cannot be guessed from URL or localpath.
    Passing `subtitlesformat` allows chef authors to manually specify subs format.
    """
    # Create a temporary file copy without extension
    source_path = os.path.join(
        os.path.dirname(__file__), "testcontent", "samples", "testsubtitles_ar.srt"
    )
    temp_file = tempfile.NamedTemporaryFile(suffix="", delete=False)
    temp_file.close()

    try:
        copyfile(source_path, temp_file.name)

        subtitle_file = SubtitleFile(
            temp_file.name,
            language="ar",
            subtitlesformat="srt",  # set subtitlesformat when can't inferr ext form url
        )
        filename = subtitle_file.process_file()
        assert filename, "converted filename must exist"
        assert filename.endswith(".vtt"), "converted filename must have .vtt extension"
        storage_path = config.get_storage_path(filename)
        with open(storage_path, encoding="utf-8") as converted_vtt:
            filecontents = converted_vtt.read()
            assert "لناس على" in filecontents, "missing check words in converted subs"
    finally:
        # Clean up temporary file
        if os.path.exists(temp_file.name):
            os.remove(temp_file.name)


# Tests for Base64 image files


def create_test_image(format="PNG", size=(1, 1), color="black"):
    """Create a test image and return its base64 encoding and MD5 hash"""
    img = Image.new("RGB", size, color=color)

    # Save to bytes buffer and get MD5
    buffer = BytesIO()
    img.save(buffer, format=format)
    raw_bytes = buffer.getvalue()
    md5 = hashlib.md5(raw_bytes).hexdigest()

    # Convert to base64 with data URI scheme
    b64 = base64.b64encode(raw_bytes).decode("utf-8")
    data_uri = f"data:image/{format.lower()};base64,{b64}"

    return data_uri, md5


# Generate test image data
TEST_PNG_BASE64, EXPECTED_PNG_MD5 = create_test_image(format="PNG")
TEST_JPG_BASE64, EXPECTED_JPG_MD5 = create_test_image(format="JPEG")


def test_png_hash():
    """Test that a base64 PNG gets converted correctly"""
    img = Base64ImageFile(encoding=TEST_PNG_BASE64)
    filename = img.process_file()
    assert filename == f"{EXPECTED_PNG_MD5}.png"


def test_jpeg_hash():
    """Test that a base64 JPEG gets converted correctly"""
    img = Base64ImageFile(encoding=TEST_JPG_BASE64)
    filename = img.process_file()
    assert filename == f"{EXPECTED_JPG_MD5}.jpg"


def test_invalid_base64():
    """Test handling of invalid base64 encoding"""
    invalid_data = "data:image/png;base64,THIS_IS_NOT_VALID_BASE64!@#$"
    img = Base64ImageFile(encoding=invalid_data)
    filename = img.process_file()
    assert filename is None
    assert img.error is not None
    assert img in config.FAILED_FILES


def test_wrong_header():
    """Test handling of base64 data with invalid header"""
    # Valid base64 but wrong header
    wrong_header = "data:text/plain;base64," + TEST_PNG_BASE64.split("base64,")[1]
    img = Base64ImageFile(encoding=wrong_header)
    filename = img.process_file()
    assert filename is None
    assert img.error is not None
    assert img in config.FAILED_FILES


def test_non_image_data():
    """Test handling of base64 data that isn't an image"""
    # Valid base64 of non-image data
    text_bytes = b"This is not an image"
    b64_text = base64.b64encode(text_bytes).decode("utf-8")
    data_uri = f"data:image/png;base64,{b64_text}"

    img = Base64ImageFile(encoding=data_uri)
    filename = img.process_file()
    assert filename is None
    assert img.error is not None
    assert img in config.FAILED_FILES


def test_caching():
    """Test that converted files are properly cached"""
    # First conversion
    img1 = Base64ImageFile(encoding=TEST_PNG_BASE64)
    filename1 = img1.process_file()

    # Second conversion of same content
    img2 = Base64ImageFile(encoding=TEST_PNG_BASE64)
    filename2 = img2.process_file()

    # Should return same filename
    assert filename1 == filename2
    assert filename1 == f"{EXPECTED_PNG_MD5}.png"

    # Key encoding tests
    def test_missing_header():
        """Test handling of base64 without required data URI header"""
        # Just the base64 part without header
        raw_base64 = TEST_PNG_BASE64.split("base64,")[1]
        img = Base64ImageFile(encoding=raw_base64)
        filename = img.process_file()
        assert filename is None
        assert img.error is not None
        assert img in config.FAILED_FILES


def test_different_images():
    """Test that different images get different hashes"""
    # Create two different test images
    base64_1, md5_1 = create_test_image(size=(1, 1), color="black")
    base64_2, md5_2 = create_test_image(size=(1, 1), color="white")

    img1 = Base64ImageFile(encoding=base64_1)
    img2 = Base64ImageFile(encoding=base64_2)

    assert img1.process_file() != img2.process_file()


# Tests for Graphie files


# Sample SVG and JSON content for tests
SAMPLE_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
    <rect width="100" height="100" fill="blue"/>
</svg>"""

SAMPLE_JSON = """{
    "version": 0.1,
    "elements": {
        "rect1": {"type": "rect", "x": 0, "y": 0, "width": 100, "height": 100}
    }
}"""


@pytest.fixture
def mock_download_session():
    """Mock the download session to return appropriate content for SVG and JSON requests"""
    with patch("ricecooker.config.DOWNLOAD_SESSION") as mock_session:
        mock_response = MagicMock()
        mock_response.headers = {}

        def iter_content(chunk_size=None):
            content = None
            if mock_response.url.endswith(".svg"):
                content = SAMPLE_SVG.encode("utf-8")
            elif mock_response.url.endswith("-data.json"):
                content = SAMPLE_JSON.encode("utf-8")
            else:
                raise Exception(f"Unexpected URL pattern: {mock_response.url}")

            if chunk_size is None:
                yield content
                return

            # Yield content in chunks of specified size
            for i in range(0, len(content), chunk_size):
                yield content[i : i + chunk_size]

        mock_response.iter_content.side_effect = iter_content
        mock_response.__iter__.side_effect = iter_content

        def get_content(url, stream=True):
            # Track requested URL path since iter_content needs it
            mock_response.url = url
            return mock_response

        mock_session.get.side_effect = get_content
        yield mock_session


def test_graphie_url_processing(mock_download_session):
    """Test processing of web+graphie:// URLs"""
    path = "https://example.com/graphie/test-graph"
    graphie = _ExerciseGraphieFile(path, "en")
    filename = graphie.process_file()

    assert filename is not None

    # Verify correct URLs were requested
    calls = mock_download_session.get.call_args_list
    assert len(calls) == 2
    assert calls[0][0][0] == "https://example.com/graphie/test-graph.svg"
    assert calls[1][0][0] == "https://example.com/graphie/test-graph-data.json"


def test_graphie_content_combination(mock_download_session):
    """Test that SVG and JSON content are properly combined"""
    path = "https://example.com/graphie/test-graph"
    graphie = _ExerciseGraphieFile(path, "en")
    filename = graphie.process_file()

    assert filename is not None

    # Read generated file and verify contents
    with open(config.get_storage_path(filename), "rb") as f:
        content = f.read()

    # Split on delimiter and verify parts
    svg_part, json_part = content.split(GRAPHIE_DELIMITER.encode("utf-8"))

    assert svg_part.decode("utf-8").strip() == SAMPLE_SVG.strip()
    assert json_part.decode("utf-8").strip() == SAMPLE_JSON.strip()


def test_graphie_download_failure(mock_download_session):
    """Test handling of download failures"""
    mock_download_session.get.side_effect = HTTPError("Download failed")

    path = "https://error.com/graphie/test-graph"
    graphie = _ExerciseGraphieFile(path, "en")
    filename = graphie.process_file()

    assert filename is None
    assert graphie in config.FAILED_FILES


def test_graphie_get_replacement_str():
    """Test get_replacement_str with https URLs"""
    path = "https://site.com/content/graph-name"
    graphie = _ExerciseGraphieFile(path, "en")
    # The replacement string should be the base filename without https:// prefix
    assert graphie.get_replacement_str() == "graph-name"


def test_graphie_original_filename():
    """Test extraction of original filename from https URLs"""
    path = "https://site.com/content/graph-name"
    graphie = _ExerciseGraphieFile(path, "en")
    assert graphie.original_filename == "graph-name"


def test_graphie_caching(mock_download_session):
    """Test caching of downloaded graphie files"""
    # Use different path to other tests to avoid cache hits
    path = "https://exemple.com/graphie/test-graph"

    # First run
    graphie1 = _ExerciseGraphieFile(path, "en")
    filename1 = graphie1.process_file()
    assert filename1 is not None

    # Second run - should use cached file
    graphie2 = _ExerciseGraphieFile(path, "en")
    filename2 = graphie2.process_file()

    assert filename1 == filename2
    # Verify downloads only happened once
    assert mock_download_session.get.call_count == 2  # Once for SVG, once for JSON


# Tests to ensure that cache keys remains stable as we update ricecooker code


def test_video_compression_cache_keys_with_settings(
    mock_filecache, video_file, video_filename
):
    """Test cache key generation for video compression with custom settings"""
    path = video_file.path
    video = VideoFile(path, ffmpeg_settings={"max_height": 480, "crf": 28})
    video.process_file()

    # Verify exact cache keys generated
    expected_keys = {
        f"DOWNLOAD:{path}",
        f"COMPRESSED: {video_filename} [('crf', 28), ('max_height', 480)]",
    }
    # We only assert that the above keys are in the cache
    # as the key for the EXTRACT_METADATA step will depend on the exact hash
    # of the video compression - which is not stable across invocations of ffmpeg
    # on different software.
    assert set(mock_filecache.cache.keys()) > expected_keys


def test_video_compression_cache_keys_no_settings(
    mock_filecache, video_file, video_filename
):
    """Test cache key generation for video compression with default settings"""
    path = video_file.path
    video = VideoFile(path)
    with patch("ricecooker.utils.pipeline.convert.config.COMPRESS", True):
        video.process_file()

    expected_keys = {
        f"DOWNLOAD:{path}",
        f"COMPRESSED: {video_filename}  (default compression)",
    }
    # We only assert that the above keys are in the cache
    # as the key for the EXTRACT_METADATA step will depend on the exact hash
    # of the video compression - which is not stable across invocations of ffmpeg
    # on different software.
    assert set(mock_filecache.cache.keys()) > expected_keys


def test_audio_compression_cache_keys_with_settings(
    mock_filecache, audio_file, audio_filename
):
    """Test cache key generation for audio compression with custom settings"""
    path = audio_file.path
    audio = AudioFile(path, ffmpeg_settings={"bit_rate": 32})
    audio.process_file()

    expected_keys = {
        f"DOWNLOAD:{path}",
        f"COMPRESSED: {audio_filename} [('bit_rate', 32)]",
    }
    # We only assert that the above keys are in the cache
    # as the key for the EXTRACT_METADATA step will depend on the exact hash
    # of the video compression - which is not stable across invocations of ffmpeg
    # on different software.
    assert set(mock_filecache.cache.keys()) > expected_keys


def test_audio_compression_cache_keys_no_settings(
    mock_filecache, audio_file, audio_filename
):
    """Test cache key generation for audio compression with default settings"""
    path = audio_file.path
    audio = AudioFile(path)
    with patch("ricecooker.utils.pipeline.convert.config.COMPRESS", True):
        audio.process_file()

    expected_keys = {
        f"DOWNLOAD:{path}",
        f"COMPRESSED: {audio_filename}  (default compression)",
    }
    # We only assert that the above keys are in the cache
    # as the key for the EXTRACT_METADATA step will depend on the exact hash
    # of the video compression - which is not stable across invocations of ffmpeg
    # on different software.
    assert set(mock_filecache.cache.keys()) > expected_keys


# Assuming document_file is a fixture from conftest.py that provides a DocumentFile object
def test_pdf_validation_handler_valid_pdf(document_file):
    """
    Test that PDFValidationHandler does not raise an exception for a valid PDF.
    """
    handler = PDFValidationHandler()
    try:
        handler.execute(document_file.path)
    except InvalidFileException:
        pytest.fail(
            "PDFValidationHandler raised InvalidFileException unexpectedly for a valid PDF."
        )


def test_pdf_validation_handler_invalid_pdf():
    """
    Test that PDFValidationHandler raises an InvalidFileException for an invalid PDF.
    """
    handler = PDFValidationHandler()
    broken_pdf_path = os.path.join(
        os.path.dirname(__file__), "testcontent", "samples", "broken.pdf"
    )
    # Ensure the broken PDF file actually exists for the test
    if not os.path.exists(broken_pdf_path):
        # Create a dummy broken PDF file if it doesn't exist.
        with open(broken_pdf_path, "w") as f:
            f.write("This is definitely not a PDF.")

    with pytest.raises(InvalidFileException):
        handler.execute(broken_pdf_path)


def test_pdf_validation_handler_empty_pdf(tmpdir):
    """
    Test that PDFValidationHandler raises an InvalidFileException for a PDF with no pages.
    """
    handler = PDFValidationHandler()
    empty_pdf_path = os.path.join(str(tmpdir), "empty.pdf")

    # Create an empty PDF file using PyPDF2
    writer = PdfFileWriter()
    with open(empty_pdf_path, "wb") as f:
        writer.write(f)

    with pytest.raises(InvalidFileException):
        handler.execute(empty_pdf_path)


def test_subtitle_cache_keys_with_format(mock_filecache, subtitle_file):
    """Test cache key generation for subtitle processing with format specified"""
    path = subtitle_file.path
    sub = SubtitleFile(
        path,
        language="en",
    )
    sub.process_file()

    expected_keys = {
        f"DOWNLOAD:{path}",
        f"CONVERT:{sub.filename}",
    }
    assert set(mock_filecache.cache.keys()) == expected_keys


def test_html5_zip_cache_keys(mock_filecache, html_file):
    """Test cache key generation for HTML5 zip processing"""
    path = html_file.path
    html = HTMLZipFile(path)
    html.process_file()

    expected_keys = {
        f"DOWNLOAD:{path}",
        f"CONVERT:{html.filename}",
        f"EXTRACT_METADATA:{html.filename}",
    }
    assert set(mock_filecache.cache.keys()) == expected_keys


def test_base64_image_cache_keys(mock_filecache):
    """Test cache key generation for base64 image processing"""
    img_data = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="

    img = Base64ImageFile(img_data)
    img.process_file()

    # Hash of the base64 content
    content_hash = "8e49fd838705faf3665e6f1ec22b0e3f"  # example hash
    expected_keys = {
        f"ENCODED: {content_hash} (base64 encoded)",
        f"CONVERT:{img.filename}",
    }
    assert set(mock_filecache.cache.keys()) == expected_keys


# StudioFile tests - regression test for constructor ordering bug


def test_studiofile_initialization():
    """Test that StudioFile initializes correctly with proper constructor ordering"""
    checksum = "abc123def456"
    ext = "mp4"
    preset = format_presets.VIDEO_HIGH_RES

    studio_file = StudioFile(checksum=checksum, ext=ext, preset=preset)

    # Verify basic properties are set correctly
    assert studio_file.filename == f"{checksum}.{ext}"
    assert studio_file.get_preset() == preset
    assert studio_file.skip_upload is True
    assert studio_file.is_primary is False
    assert studio_file._validated is False


def test_studiofile_with_primary():
    """Test StudioFile initialization with is_primary=True"""
    checksum = "def789ghi012"
    ext = "pdf"
    preset = format_presets.DOCUMENT

    studio_file = StudioFile(checksum=checksum, ext=ext, preset=preset, is_primary=True)

    assert studio_file.filename == f"{checksum}.{ext}"
    assert studio_file.is_primary is True


@patch("ricecooker.config.get_storage_url")
def test_studiofile_validation_success(mock_get_storage_url):
    """Test that StudioFile validation works when file exists on remote"""
    checksum = "valid123hash456"
    ext = "mp3"
    preset = format_presets.AUDIO

    # Mock successful HEAD request
    with patch("ricecooker.config.DOWNLOAD_SESSION") as mock_session:
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_session.head.return_value = mock_response
        mock_get_storage_url.return_value = (
            f"https://storage.example.com/{checksum}.{ext}"
        )

        studio_file = StudioFile(checksum=checksum, ext=ext, preset=preset)
        studio_file.validate()  # Should not raise exception

        assert studio_file._validated is True
        mock_session.head.assert_called_once()
        mock_get_storage_url.assert_called_with(f"{checksum}.{ext}")


@patch("ricecooker.config.get_storage_url")
def test_studiofile_validation_failure(mock_get_storage_url):
    """Test that StudioFile validation fails when file doesn't exist on remote"""
    checksum = "missing123hash456"
    ext = "png"
    preset = format_presets.EXERCISE_IMAGE

    # Mock failed HEAD request
    with patch("ricecooker.config.DOWNLOAD_SESSION") as mock_session:
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = HTTPError("404 Not Found")
        mock_session.head.return_value = mock_response
        mock_get_storage_url.return_value = (
            f"https://storage.example.com/{checksum}.{ext}"
        )

        studio_file = StudioFile(checksum=checksum, ext=ext, preset=preset)

        with pytest.raises(ValueError) as excinfo:
            studio_file.validate()

        assert "Could not find remote file" in str(excinfo.value)
        assert f"{checksum}.{ext}" in str(excinfo.value)
        assert studio_file._validated is False


def test_studiofile_str_representation():
    """Test StudioFile string representation"""
    checksum = "str123test456"
    ext = "zip"
    preset = format_presets.HTML5_ZIP

    studio_file = StudioFile(checksum=checksum, ext=ext, preset=preset)

    assert str(studio_file) == f"{checksum}.{ext}"
