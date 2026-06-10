import os
from unittest.mock import MagicMock
from unittest.mock import patch

import PIL
import pytest  # noqa F401
from le_utils.constants import format_presets
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
from ricecooker.classes.files import File
from ricecooker.classes.files import ThumbnailFile
from ricecooker.classes.files import TiledThumbnailFile
from ricecooker.classes.files import VideoFile
from ricecooker.classes.nodes import ContentNode
from ricecooker.classes.nodes import DocumentNode
from ricecooker.classes.nodes import HTML5AppNode
from ricecooker.classes.nodes import TopicNode
from ricecooker.classes.nodes import VideoNode
from ricecooker.managers.tree import ChannelManager
from ricecooker.utils.images import ThumbnailGenerationError
from ricecooker.utils.pipeline.context import NODE_HAS_THUMBNAIL


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


class TestIsThumbnail(object):
    """File.is_thumbnail() detects thumbnails by format preset, not class."""

    def test_plain_file_with_thumbnail_preset(self):
        f = File(preset=format_presets.DOCUMENT_THUMBNAIL, filename="abc.png")
        assert f.is_thumbnail() is True

    def test_plain_file_with_content_preset(self):
        f = File(preset=format_presets.DOCUMENT, filename="abc.pdf")
        assert f.is_thumbnail() is False

    def test_plain_file_without_preset(self):
        f = File(filename="abc.pdf")
        assert f.is_thumbnail() is False

    def test_thumbnail_file_attached_to_node(self, thumbnail_path):  # noqa F811
        node = DocumentNode(
            "doc-src-id", "Document", licenses.PUBLIC_DOMAIN, thumbnail=thumbnail_path
        )
        assert any(f.is_thumbnail() for f in node.files)

    def test_unattached_thumbnail_file_is_not_thumbnail(
        self,
        thumbnail_path,  # noqa F811
    ):
        # A ThumbnailFile with no node cannot resolve its preset.
        f = ThumbnailFile(thumbnail_path)
        assert f.is_thumbnail() is False

    def test_thumbnail_file_on_kindless_node_is_not_thumbnail(
        self,
        thumbnail_path,  # noqa F811
    ):
        # Attached to a node that has no kind yet (a uri-based node before
        # the pipeline has run), so the preset is unresolvable.
        node = ContentNode(
            "src-id", "Title", licenses.PUBLIC_DOMAIN, uri="/tmp/doc.pdf"
        )
        f = ThumbnailFile(thumbnail_path)
        node.add_file(f)
        assert f.is_thumbnail() is False


class TestHasThumbnail(object):
    """Node.has_thumbnail() detects provided and preset-based thumbnails."""

    def test_pipeline_generated_thumbnail_counts(self):
        node = DocumentNode("doc-src-id", "Document", licenses.PUBLIC_DOMAIN)
        node.add_file(
            File(preset=format_presets.DOCUMENT_THUMBNAIL, filename="abc.png")
        )
        assert node.has_thumbnail() is True

    def test_content_file_does_not_count(self):
        node = DocumentNode("doc-src-id", "Document", licenses.PUBLIC_DOMAIN)
        node.add_file(File(preset=format_presets.DOCUMENT, filename="abc.pdf"))
        assert node.has_thumbnail() is False

    def test_provided_thumbnail_counts_before_kind_is_known(
        self,
        thumbnail_path,  # noqa F811
    ):
        # uri-based ContentNode has no kind until the pipeline has run, so the
        # ThumbnailFile preset is unresolvable - self.thumbnail must count.
        node = ContentNode(
            "src-id",
            "Title",
            licenses.PUBLIC_DOMAIN,
            uri="/tmp/does-not-matter.pdf",
            thumbnail=thumbnail_path,
        )
        assert node.has_thumbnail() is True

    def test_process_uri_passes_node_has_thumbnail_context(
        self,
        thumbnail_path,  # noqa F811
    ):
        pipeline = MagicMock()
        pipeline.execute.return_value = []

        node = ContentNode(
            "src-id",
            "Title",
            licenses.PUBLIC_DOMAIN,
            uri="/tmp/doc.pdf",
            pipeline=pipeline,
        )
        node._process_uri()
        pipeline.execute.assert_called_once_with(
            "/tmp/doc.pdf",
            context={NODE_HAS_THUMBNAIL: False},
            skip_cache=config.UPDATE,
        )

        pipeline.reset_mock()
        node.set_thumbnail(thumbnail_path)
        node._process_uri()
        pipeline.execute.assert_called_once_with(
            "/tmp/doc.pdf",
            context={NODE_HAS_THUMBNAIL: True},
            skip_cache=config.UPDATE,
        )

    def test_process_uri_counts_thumbnail_file_passed_in_files(
        self,
        thumbnail_path,  # noqa F811
    ):
        # A ThumbnailFile in files=[...] cannot resolve its preset before the
        # node has a kind, but it must still suppress pipeline generation.
        pipeline = MagicMock()
        pipeline.execute.return_value = []

        node = ContentNode(
            "src-id",
            "Title",
            licenses.PUBLIC_DOMAIN,
            uri="/tmp/doc.pdf",
            pipeline=pipeline,
            files=[ThumbnailFile(thumbnail_path)],
        )
        node._process_uri()
        pipeline.execute.assert_called_once_with(
            "/tmp/doc.pdf",
            context={NODE_HAS_THUMBNAIL: True},
            skip_cache=config.UPDATE,
        )


class TestThumbnailGeneration(object):
    def setup_method(self, test_method):
        """
        Called before each test method executes.
        """
        _clear_ricecookerfilecache()
        config.FAILED_FILES = []

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
        filenames = node.process_files()
        assert len(filenames) == 2, "expected two filenames"
        self.check_has_thumbnail(node)

    def test_generate_thumbnail_from_epub(self, epub_file):
        node = DocumentNode(
            "doc-src-id", "Document", licenses.PUBLIC_DOMAIN, thumbnail=None
        )
        node.add_file(epub_file)
        filenames = node.process_files()
        assert len(filenames) == 2, "expected two filenames"
        self.check_has_thumbnail(node)

    def test_generate_thumbnail_from_html(self, html_file):
        node = HTML5AppNode(
            "html-src-id", "HTML5 App", licenses.PUBLIC_DOMAIN, thumbnail=None
        )
        node.add_file(html_file)
        filenames = node.process_files()
        assert len(filenames) == 2, "expected two filenames"
        self.check_has_thumbnail(node)

    def test_generate_thumbnail_from_video(self, video_file):
        node = VideoNode("vid-src-id", "Video", licenses.PUBLIC_DOMAIN, thumbnail=None)
        node.add_file(video_file)
        filenames = node.process_files()
        assert len(filenames) == 2, "expected two filenames"
        self.check_has_thumbnail(node)

    def test_topic_does_not_generate_thumbnail_in_process_files(
        self, document, html, video, audio
    ):
        topic = TopicNode("test-topic", "Topic")
        # Children are processed first so their thumbnails would be available;
        # the topic must still defer (the tree manager post-pass tiles later).
        for child in (document, html, video, audio):
            topic.add_child(child)
            child.process_files()
        filenames = topic.process_files()
        assert filenames == [], "topic thumbnail generation must be deferred"
        assert not topic.has_thumbnail()

    def test_legacy_file_processing_skips_pipeline_thumbnail_stage(self, document_file):
        # The legacy DownloadFile path only consumes the source metadata, so
        # the pipeline thumbnail stage must not generate an image for it
        # (node-level generate_missing_thumbnail handles legacy thumbnails).
        with patch(
            "ricecooker.utils.pipeline.thumbnails.create_image_from_pdf_page"
        ) as mock_create:
            filename = document_file.process_file()
        assert filename is not None
        assert not mock_create.called

    def test_generate_missing_thumbnail_noop_when_thumbnail_present(
        self,
        document_file,
        thumbnail_path,  # noqa F811
    ):
        node = DocumentNode(
            "doc-src-id", "Document", licenses.PUBLIC_DOMAIN, thumbnail=thumbnail_path
        )
        node.add_file(document_file)
        assert node.generate_missing_thumbnail() == []

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


class TestDeferredTopicThumbnails(object):
    def setup_method(self, test_method):
        _clear_ricecookerfilecache()
        config.FAILED_FILES = []

    def _content_node(self, cls, source_id, file_obj):
        node = cls(source_id, source_id, licenses.PUBLIC_DOMAIN)
        node.add_file(file_obj)
        return node

    def _build_topic(self, channel, children, thumbnail=None):
        topic = TopicNode("test-topic", "Topic", thumbnail=thumbnail)
        channel.add_child(topic)
        for child in children:
            topic.add_child(child)
        return topic

    def test_topic_gets_tiled_thumbnail_via_post_pass(
        self, channel, document_file, html_file, video_file
    ):
        children = [
            self._content_node(DocumentNode, "doc-src-id", document_file),
            self._content_node(HTML5AppNode, "html-src-id", html_file),
            self._content_node(VideoNode, "vid-src-id", video_file),
        ]
        topic = self._build_topic(channel, children)

        manager = ChannelManager(channel)
        filenames = manager.process_tree()

        assert topic.has_thumbnail(), "topic should have a generated tile"
        tile_files = [f for f in topic.files if f.is_thumbnail()]
        assert len(tile_files) == 1
        tile_filename = tile_files[0].get_filename()
        assert tile_filename in filenames, "tile must be registered for upload"
        assert os.path.exists(config.get_storage_path(tile_filename))

    def test_topic_with_provided_thumbnail_is_untouched(
        self,
        channel,
        document_file,
        thumbnail_path,  # noqa F811
    ):
        children = [self._content_node(DocumentNode, "doc-src-id", document_file)]
        topic = self._build_topic(channel, children, thumbnail=thumbnail_path)

        manager = ChannelManager(channel)
        manager.process_tree()

        thumb_files = [f for f in topic.files if f.is_thumbnail()]
        assert len(thumb_files) == 1, "no second thumbnail should be generated"
        assert isinstance(thumb_files[0], ThumbnailFile)
        assert not isinstance(thumb_files[0], TiledThumbnailFile)

    def test_tile_sources_include_generated_child_thumbnails(
        self, channel, document_file
    ):
        # The child has no provided thumbnail: it generates its own during
        # process_files, and the topic tile is built from that generated
        # thumbnail afterward.
        children = [self._content_node(DocumentNode, "doc-src-id", document_file)]
        topic = self._build_topic(channel, children)

        manager = ChannelManager(channel)
        manager.process_tree()
        assert topic.has_thumbnail()

    def test_topic_with_no_eligible_descendants_stays_thumbnail_less(self, channel):
        topic = self._build_topic(channel, [])

        manager = ChannelManager(channel)
        filenames = manager.process_tree()

        assert not topic.has_thumbnail()
        assert filenames == []

    def test_failed_tile_generation_is_recorded(
        self,
        channel,
        document_file,
        monkeypatch,
    ):
        children = [self._content_node(DocumentNode, "doc-src-id", document_file)]
        topic = self._build_topic(channel, children)

        def boom(*args, **kwargs):
            raise ThumbnailGenerationError("tile failure")

        monkeypatch.setattr("ricecooker.classes.files.create_tiled_image", boom)
        manager = ChannelManager(channel)
        manager.process_tree()

        assert not topic.has_thumbnail()
        failed = [f for f in config.FAILED_FILES if isinstance(f, TiledThumbnailFile)]
        assert len(failed) == 1
        assert failed[0].error == "tile failure"

    def test_tile_sources_skip_unprocessed_thumbnails(self):
        # A thumbnail file that failed to process (filename is None) must be
        # skipped as a tile source, not re-processed by the tile build.
        node = DocumentNode("doc-src-id", "Document", licenses.PUBLIC_DOMAIN)
        node.add_file(File(preset=format_presets.DOCUMENT_THUMBNAIL, filename=None))
        tiled = TiledThumbnailFile([node])
        assert tiled.sources == []
