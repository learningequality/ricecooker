import os

import PIL
import pytest  # noqa F401
from le_utils.constants import licenses
from test_tree import thumbnail_path  # noqa F401
from test_tree import thumbnail_path_jpg  # noqa F401
from test_videos import _clear_ricecookerfilecache
from test_videos import low_res_video  # noqa F401

from ricecooker import config
from ricecooker.classes.files import ExtractedEPubThumbnailFile
from ricecooker.classes.files import ExtractedHTMLZipThumbnailFile
from ricecooker.classes.files import ExtractedPdfThumbnailFile
from ricecooker.classes.files import ExtractedVideoThumbnailFile
from ricecooker.classes.files import ThumbnailFile
from ricecooker.classes.files import TiledThumbnailFile
from ricecooker.classes.files import VideoFile
from ricecooker.classes.nodes import DocumentNode
from ricecooker.classes.nodes import HTML5AppNode
from ricecooker.classes.nodes import TopicNode
from ricecooker.classes.nodes import VideoNode


SHOW_THUMBS = False  # set to True to show outputs when running tests locally


THUMBNAIL_URL = "https://raw.githubusercontent.com/learningequality/ricecooker/master/tests/testcontent/samples/thumbnail.png"


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
        expected_thumbnail_filename = "eb79354ddd5774bb3436f9a19c282bff.png"
        thumbnail_files = [f for f in node.files if isinstance(f, ThumbnailFile)]
        assert len(thumbnail_files) == 1, "multiple thumbnails found"
        thumbnail_file = thumbnail_files[0]
        thumbnail_filename = thumbnail_file.get_filename()
        assert thumbnail_filename == expected_thumbnail_filename, "Wrong thumbnail"

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
        assert (
            thumbnail_file == failed_file
        ), "bad thumbnail file not found in config.FAILED_FILES"

    # HAPPY PATHS
    ############################################################################

    def test_set_png_thumbnail_from_local_path(
        self, low_res_video, thumbnail_path  # noqa F811
    ):
        video_node = self.get_video_node(  # noqa F811
            path=low_res_video.name, thumbnail=thumbnail_path
        )
        video_node.validate()
        _ = video_node.process_files()
        self.check_correct_thumbnail(video_node)

    def test_set_jpg_thumbnail_from_local_path(
        self, low_res_video, thumbnail_path_jpg  # noqa F811
    ):
        video_node = self.get_video_node(
            path=low_res_video.name, thumbnail=thumbnail_path_jpg
        )
        video_node.validate()
        _ = video_node.process_files()
        expected_thumbnail_filename = "d7ab03e4263fc374737d96ac2da156c1.jpg"
        thumbnail_files = [f for f in video_node.files if isinstance(f, ThumbnailFile)]
        assert len(thumbnail_files) == 1, "multiple thumbnails found"
        thumbnail_file = thumbnail_files[0]
        thumbnail_filename = thumbnail_file.get_filename()
        assert thumbnail_filename == expected_thumbnail_filename, "Wrong thumbnail"

    def test_set_thumbnail_from_url(self, low_res_video):  # noqa F811
        video_node = self.get_video_node(
            path=low_res_video.name, thumbnail=THUMBNAIL_URL
        )
        video_node.validate()
        _ = video_node.process_files()
        self.check_correct_thumbnail(video_node)

    def test_set_thumbnail_from_url_with_querystring(self, low_res_video):  # noqa F811
        url = THUMBNAIL_URL + "?querystringkey=querystringvalue"
        video_node = self.get_video_node(path=low_res_video.name, thumbnail=url)
        video_node.validate()
        _ = video_node.process_files()
        self.check_correct_thumbnail(video_node)

    def test_set_thumbnail_from_ThumbnailFile(
        self, low_res_video, thumbnail_path  # noqa F811
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
        self, low_res_video, fake_thumbnail_file  # noqa F811
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
        assert (
            thumbnail_file == failed_file
        ), "bad thumbnail file not found in config.FAILED_FILES"

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
