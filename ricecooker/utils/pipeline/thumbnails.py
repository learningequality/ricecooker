"""
Pipeline stage that extracts thumbnail images from processed files.

Runs after conversion, so it sees files in their final formats. For each
supported file it emits an additional FileMetadata for the generated PNG
with the appropriate thumbnail preset, alongside the source file.
Generation is skipped when the node already provides a thumbnail (see the
NODE_HAS_THUMBNAIL context key).

Thumbnail generation is best-effort: if extraction fails, the source
file passes through unaffected.
"""

from typing import Dict
from typing import Optional

from le_utils.constants import file_formats
from le_utils.constants import format_presets

from .file_handler import ExtensionMatchingHandler
from .file_handler import StageHandler
from ricecooker import config
from ricecooker.utils.images import create_image_from_epub
from ricecooker.utils.images import create_image_from_pdf_page
from ricecooker.utils.images import create_image_from_zip
from ricecooker.utils.images import ThumbnailGenerationError
from ricecooker.utils.pipeline.context import ContextMetadata
from ricecooker.utils.pipeline.context import FileMetadata
from ricecooker.utils.pipeline.exceptions import ExpectedFileException
from ricecooker.utils.pipeline.exceptions import InvalidFileException
from ricecooker.utils.utils import extract_path_ext
from ricecooker.utils.videos import extract_thumbnail_from_video


THUMBNAIL_PRESETS = {
    file_formats.PDF: format_presets.DOCUMENT_THUMBNAIL,
    file_formats.EPUB: format_presets.DOCUMENT_THUMBNAIL,
    file_formats.HTML5_ARTICLE: format_presets.DOCUMENT_THUMBNAIL,
    file_formats.HTML5: format_presets.HTML5_THUMBNAIL,
    file_formats.MP4: format_presets.VIDEO_THUMBNAIL,
    file_formats.WEBM: format_presets.VIDEO_THUMBNAIL,
}


class ThumbnailContextMetadata(ContextMetadata):
    node_has_thumbnail: bool = False


class ThumbnailExtractionHandler(ExtensionMatchingHandler):
    """Generates a PNG thumbnail from a processed file."""

    EXTENSIONS = set(THUMBNAIL_PRESETS)

    HANDLED_EXCEPTIONS = [ThumbnailGenerationError]

    CONTEXT_CLASS = ThumbnailContextMetadata

    def get_file_kwargs(self, context):
        if context.node_has_thumbnail:
            # The node already has a thumbnail; nothing to generate.
            # Returning [] bypasses both cache lookup and generation
            # entirely - any cached thumbnail for this path is not consulted.
            return []
        return [{}]

    def handle_file(self, path):
        ext = extract_path_ext(path)
        with self.write_file(file_formats.PNG) as fh:
            if ext == file_formats.PDF:
                create_image_from_pdf_page(path, fh.name, max_width=1000)
            elif ext == file_formats.EPUB:
                create_image_from_epub(path, fh.name)
            elif ext in (file_formats.HTML5, file_formats.HTML5_ARTICLE):
                create_image_from_zip(path, fh.name)
            else:
                extract_thumbnail_from_video(path, fh.name, overwrite=True)
        return FileMetadata(preset=THUMBNAIL_PRESETS[ext])


class ThumbnailStageHandler(StageHandler):
    STAGE = "THUMBNAIL"
    DEFAULT_CHILDREN = [ThumbnailExtractionHandler]

    def execute(
        self,
        path: str,
        context: Optional[Dict] = None,
        skip_cache: Optional[bool] = False,
    ) -> list[FileMetadata]:
        """
        Pass the source file through unchanged, plus the extracted
        thumbnail if generation succeeded.
        """
        try:
            thumbnails = super().execute(path, context=context, skip_cache=skip_cache)
        except (ExpectedFileException, InvalidFileException) as e:
            # InvalidFileException covers an extractor that completes without
            # writing any bytes; a failed thumbnail must never fail the node.
            config.LOGGER.warning(f"\tFailed to extract thumbnail from {path}: {e}")
            thumbnails = []
        return [FileMetadata(path=path)] + thumbnails
