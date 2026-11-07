import os

import PIL
import pytest
from conftest import assert_letterboxed_png
from le_utils.constants import format_presets
from le_utils.constants import licenses
from pypdf import PdfWriter
from test_tree import thumbnail_path  # noqa F401
from test_tree import thumbnail_path_jpg  # noqa F401
from test_videos import _clear_ricecookerfilecache
from test_videos import low_res_video  # noqa F401
from vcr_config import my_vcr

from ricecooker import config
from ricecooker.classes.files import DownloadFile
from ricecooker.classes.files import ExtractedEPubThumbnailFile
from ricecooker.classes.files import ExtractedHTMLZipThumbnailFile
from ricecooker.classes.files import ExtractedKPUBThumbnailFile
from ricecooker.classes.files import ExtractedPdfThumbnailFile
from ricecooker.classes.files import ExtractedVideoThumbnailFile
from ricecooker.classes.files import ThumbnailFile
from ricecooker.classes.files import TiledThumbnailFile
from ricecooker.classes.files import VideoFile
from ricecooker.classes.nodes import DocumentNode
from ricecooker.classes.nodes import HTML5AppNode
from ricecooker.classes.nodes import TopicNode
from ricecooker.classes.nodes import VideoNode
from ricecooker.utils import images
from ricecooker.utils import videos

SHOW_THUMBS = False  # set to True to show outputs when running tests locally


THUMBNAIL_URL = "https://raw.githubusercontent.com/learningequality/ricecooker/master/tests/testcontent/samples/thumbnail.png"


@pytest.fixture(autouse=True)
def no_chromium(monkeypatch):
    monkeypatch.setattr(images, "find_chromium_binary", lambda: None)


class TestThumbnailSetting(object):
    def setup_method(self, test_method):
        """
        Called before each test method executes.
        """
        _clear_ricecookerfilecache()
        config.FAILED_FILES = []

    def get_video_node(self, path, thumbnail=None):
        video_file = VideoFile(path, language="en")
        video_node = VideoNode(
            "vid-src-id", "Video", licenses.PUBLIC_DOMAIN, thumbnail=thumbnail
        )
        video_node.add_file(video_file)
        return video_node

    def check_correct_thumbnail(self, node):
        thumbnail_files = [f for f in node.files if isinstance(f, ThumbnailFile)]
        assert len(thumbnail_files) == 1, "multiple thumbnails found"
        assert_letterboxed_png(
            config.get_storage_path(thumbnail_files[0].get_filename())
        )

    def assert_failed_thumbnail(self, node):
        thumbnail_files = [f for f in node.files if isinstance(f, ThumbnailFile)]
        assert len(thumbnail_files) == 1, "multiple thumbnails found"
        thumbnail_file = thumbnail_files[0]
        assert thumbnail_file.filename is None, "filename should be None"
        failed_files = config.FAILED_FILES
        # for ff in failed_files:
        #     print(ff, ff.path, ff.error)
        assert len(failed_files) == 1, "multiple failed files found"
        failed_file = failed_files[0]
        assert failed_file.error, "must have error set"
        assert thumbnail_file == failed_file, (
            "bad thumbnail file not found in config.FAILED_FILES"
        )

    # HAPPY PATHS
    ############################################################################

    def test_set_png_thumbnail_from_local_path(
        self,
        low_res_video,
        thumbnail_path,  # noqa F811
    ):
        video_node = self.get_video_node(  # noqa F811
            path=low_res_video.name, thumbnail=thumbnail_path
        )
        video_node.validate()
        _ = video_node.process_files()
        self.check_correct_thumbnail(video_node)

    def test_set_jpg_thumbnail_from_local_path(
        self,
        low_res_video,
        thumbnail_path_jpg,  # noqa F811
    ):
        video_node = self.get_video_node(
            path=low_res_video.name, thumbnail=thumbnail_path_jpg
        )
        video_node.validate()
        _ = video_node.process_files()
        self.check_correct_thumbnail(video_node)

    @my_vcr.use_cassette
    def test_set_thumbnail_from_url(self, low_res_video):  # noqa F811
        video_node = self.get_video_node(
            path=low_res_video.name, thumbnail=THUMBNAIL_URL
        )
        video_node.validate()
        _ = video_node.process_files()
        self.check_correct_thumbnail(video_node)

    @my_vcr.use_cassette
    def test_set_thumbnail_from_url_with_querystring(self, low_res_video):  # noqa F811
        url = THUMBNAIL_URL + "?querystringkey=querystringvalue"
        video_node = self.get_video_node(path=low_res_video.name, thumbnail=url)
        video_node.validate()
        _ = video_node.process_files()
        self.check_correct_thumbnail(video_node)

    def test_set_thumbnail_from_ThumbnailFile(
        self,
        low_res_video,
        thumbnail_path,  # noqa F811
    ):
        thumbnail_file = ThumbnailFile(thumbnail_path)
        video_node = self.get_video_node(
            path=low_res_video.name, thumbnail=thumbnail_file
        )
        video_node.validate()
        _ = video_node.process_files()
        self.check_correct_thumbnail(video_node)

    def test_add_ThumbnailFile(self, low_res_video, thumbnail_path):  # noqa F811
        video_node = self.get_video_node(path=low_res_video.name, thumbnail=None)
        thumbnail_file = ThumbnailFile(thumbnail_path)
        video_node.add_file(thumbnail_file)
        video_node.validate()
        _ = video_node.process_files()
        self.check_correct_thumbnail(video_node)

    # ERROR PATHS
    ############################################################################

    def test_set_thumbnail_from_non_existent_path(self, low_res_video):  # noqa F811
        non_existent_path = "does/not/exist.png"
        video_node = self.get_video_node(
            path=low_res_video.name, thumbnail=non_existent_path
        )
        video_node.validate()
        _ = video_node.process_files()
        self.assert_failed_thumbnail(video_node)

    def test_set_thumbnail_from_bad_path(
        self,
        low_res_video,
        fake_thumbnail_file,  # noqa F811
    ):
        """
        File path exists, but is not a valid PNG file.
        """
        video_node = self.get_video_node(
            path=low_res_video.name, thumbnail=fake_thumbnail_file
        )
        video_node.validate()
        _ = video_node.process_files()
        self.assert_failed_thumbnail(video_node)


class TestThumbnailGeneration(object):
    def setup_method(self, test_method):
        """
        Called before each test method executes.
        """
        _clear_ricecookerfilecache()
        config.FAILED_FILES = []
        config.THUMBNAILS = False

    def check_has_thumbnail(self, node):
        thumbnail_files = [
            f
            for f in node.files
            if isinstance(f, ThumbnailFile) or isinstance(f, TiledThumbnailFile)
        ]
        assert len(thumbnail_files) == 1, "expected single thumbnail"
        thumbnail_file = thumbnail_files[0]
        thumbnail_filename = thumbnail_file.get_filename()
        thumbnail_path = config.get_storage_path(thumbnail_filename)  # noqa F811
        assert os.path.exists(thumbnail_path)
        img = PIL.Image.open(thumbnail_path)
        img.verify()
        if SHOW_THUMBS:
            img = PIL.Image.open(thumbnail_path)
            img.show()

    def assert_failed_thumbnail(self, node):
        thumbnail_files = [f for f in node.files if isinstance(f, ThumbnailFile)]
        assert len(thumbnail_files) == 1, "multiple thumbnails found"
        thumbnail_file = thumbnail_files[0]
        assert thumbnail_file.filename is None, "filename should be None"
        failed_files = config.FAILED_FILES
        # for ff in failed_files:
        #     print(ff, ff.path, ff.error)
        assert len(failed_files) == 1, "multiple failed files found"
        failed_file = failed_files[0]
        assert failed_file.error, "must have error set"
        assert thumbnail_file == failed_file, (
            "bad thumbnail file not found in config.FAILED_FILES"
        )

    # HAPPY PATHS
    ############################################################################

    def test_generate_thumbnail_from_pdf(self, document_file):
        node = DocumentNode(
            "doc-src-id", "Document", licenses.PUBLIC_DOMAIN, thumbnail=None
        )
        node.add_file(document_file)
        config.THUMBNAILS = True
        filenames = node.process_files()
        assert len(filenames) == 2, "expected two filenames"
        self.check_has_thumbnail(node)

    def test_generate_thumbnail_from_epub(self, epub_file):
        node = DocumentNode(
            "doc-src-id", "Document", licenses.PUBLIC_DOMAIN, thumbnail=None
        )
        node.add_file(epub_file)
        config.THUMBNAILS = True
        filenames = node.process_files()
        assert len(filenames) == 2, "expected two filenames"
        self.check_has_thumbnail(node)

    def test_generate_thumbnail_from_html(self, html_file):
        node = HTML5AppNode(
            "html-src-id", "HTML5 App", licenses.PUBLIC_DOMAIN, thumbnail=None
        )
        node.add_file(html_file)
        config.THUMBNAILS = True
        filenames = node.process_files()
        assert len(filenames) == 2, "expected two filenames"
        self.check_has_thumbnail(node)

    def test_generate_thumbnail_from_kpub(self):
        node = DocumentNode(
            "doc-src-id", "Document", licenses.PUBLIC_DOMAIN, thumbnail=None
        )
        kpub_file = DownloadFile("some.kpub", preset=format_presets.KPUB_ZIP)
        kpub_file.filename = "test.kpub"
        node.add_file(kpub_file)
        assert isinstance(node.generate_thumbnail(), ExtractedKPUBThumbnailFile)

    def test_generate_thumbnail_from_video(self, video_file):
        node = VideoNode("vid-src-id", "Video", licenses.PUBLIC_DOMAIN, thumbnail=None)
        node.add_file(video_file)
        config.THUMBNAILS = True
        filenames = node.process_files()
        assert len(filenames) == 2, "expected two filenames"
        self.check_has_thumbnail(node)

    def test_generate_tiled_thumbnail(self, document, html, video, audio):
        topic = TopicNode("test-topic", "Topic")
        topic.add_child(document)
        topic.add_child(html)
        topic.add_child(video)
        topic.add_child(audio)
        config.THUMBNAILS = True
        for child in topic.children:  # must process children before topic node
            child.process_files()
        filenames = topic.process_files()
        assert len(filenames) == 1, "expected one filename"
        self.check_has_thumbnail(topic)

    def test_tiled_thumbnail_is_built_from_unconverted_chef_thumbnail(self, tmp_path):
        source = str(tmp_path / "portrait.png")
        portrait = PIL.Image.new("RGB", (1200, 1800), "red")
        portrait.paste("blue", (0, 900, 1200, 1800))
        portrait.save(source)
        child = TopicNode("child", "child", thumbnail=ThumbnailFile(source))
        tiled = TiledThumbnailFile([child])
        expected = str(tmp_path / "expected.png")
        images.create_tiled_image([source], expected)
        os.remove(source)

        filename = tiled.process_file()

        assert config.FAILED_FILES == []
        with (
            PIL.Image.open(config.get_storage_path(filename)) as actual,
            PIL.Image.open(expected) as want,
        ):
            assert actual.tobytes() == want.tobytes()

    def test_unconverted_path_before_processing_is_source_image(self, tmp_path):
        source = str(tmp_path / "landscape.png")
        PIL.Image.new("RGB", (800, 300), "red").save(source)

        unconverted = ThumbnailFile(source).get_unconverted_path()

        with PIL.Image.open(unconverted) as img:
            assert img.size == (800, 300)

    def test_portrait_pdf_thumbnail_is_not_letterboxed(self, tmp_path):
        pdf_path = str(tmp_path / "portrait.pdf")
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=400)
        writer.write(pdf_path)
        filename = ExtractedPdfThumbnailFile(pdf_path).process_file()
        with PIL.Image.open(config.get_storage_path(filename)) as img:
            assert img.convert("RGBA").getchannel("A").getextrema()[0] == 255

    # ERROR PATHS
    ############################################################################

    def test_non_existent_pdf_fails(self):
        non_existent_path = "does/not/exist.pdf"
        thumbnail_file = ExtractedPdfThumbnailFile(non_existent_path)
        result = thumbnail_file.process_file()

        assert result is None, "expected None result for non-existent PDF"
        assert len(config.FAILED_FILES) == 1, "expected one failed file"
        assert thumbnail_file.filename is None, "filename should remain None"

    def test_invalid_pdf_fails(self, invalid_document_file):
        thumbnail_file = ExtractedPdfThumbnailFile(invalid_document_file.path)
        result = thumbnail_file.process_file()

        assert result is None, "expected None result for invalid PDF"
        assert len(config.FAILED_FILES) == 1, "expected one failed file"
        assert thumbnail_file.filename is None, "filename should remain None"

    def test_non_existent_epub_fails(self):
        non_existent_path = "does/not/exist.epub"
        thumbnail_file = ExtractedEPubThumbnailFile(non_existent_path)
        result = thumbnail_file.process_file()

        assert result is None, "expected None result for non-existent EPUB"
        assert len(config.FAILED_FILES) == 1, "expected one failed file"
        assert thumbnail_file.filename is None, "filename should remain None"

    def test_invalid_epub_fails(self, invalid_epub_file):
        thumbnail_file = ExtractedEPubThumbnailFile(invalid_epub_file.path)
        result = thumbnail_file.process_file()

        assert result is None, "expected None result for invalid EPUB"
        assert len(config.FAILED_FILES) == 1, "expected one failed file"
        assert thumbnail_file.filename is None, "filename should remain None"

    def test_non_existent_htmlzip_fails(self):
        non_existent_path = "does/not/exist.zip"
        thumbnail_file = ExtractedHTMLZipThumbnailFile(non_existent_path)
        result = thumbnail_file.process_file()

        assert result is None, "expected None result for non-existent HTML zip"
        assert len(config.FAILED_FILES) == 1, "expected one failed file"
        assert thumbnail_file.filename is None, "filename should remain None"

    def test_invalid_htmlzip_fails(self, html_invalid_file):
        thumbnail_file = ExtractedHTMLZipThumbnailFile(html_invalid_file.path)
        result = thumbnail_file.process_file()

        assert result is None, "expected None result for invalid HTML zip"
        assert len(config.FAILED_FILES) == 1, "expected one failed file"
        assert thumbnail_file.filename is None, "filename should remain None"

    def test_non_existent_mp4_fails(self):
        non_existent_path = "does/not/exist.mp4"
        thumbnail_file = ExtractedVideoThumbnailFile(non_existent_path)
        result = thumbnail_file.process_file()

        assert result is None, "expected None result for non-existent MP4"
        assert len(config.FAILED_FILES) == 1, "expected one failed file"
        assert thumbnail_file.filename is None, "filename should remain None"

    def test_invalid_mp4_fails(self, invalid_video_file):
        thumbnail_file = ExtractedVideoThumbnailFile(invalid_video_file.path)
        result = thumbnail_file.process_file()

        assert result is None, "expected None result for invalid MP4"
        assert len(config.FAILED_FILES) == 1, "expected one failed file"
        assert thumbnail_file.filename is None, "filename should remain None"

    @pytest.mark.parametrize("tool", ["ffprobe", "ffmpeg"])
    def test_hung_video_tool_fails_thumbnail(
        self, video_file, stub_on_path, monkeypatch, tool
    ):
        stub_on_path(tool)
        monkeypatch.setattr(videos, "PROBE_TIMEOUT", 1)
        thumbnail_file = ExtractedVideoThumbnailFile(video_file.path)
        assert thumbnail_file.process_file() is None
        assert config.FAILED_FILES == [thumbnail_file]
        assert "timed out" in thumbnail_file.error

    def test_missing_video_tool_fails_thumbnail(self, video_file, empty_path):
        thumbnail_file = ExtractedVideoThumbnailFile(video_file.path)
        assert thumbnail_file.process_file() is None
        assert config.FAILED_FILES == [thumbnail_file]
