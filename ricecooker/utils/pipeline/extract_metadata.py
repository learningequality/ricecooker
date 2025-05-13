from le_utils.constants import file_formats
from le_utils.constants import format_presets

from .file_handler import ExtensionMatchingHandler
from .file_handler import StageHandler
from ricecooker.utils.pipeline.context import ContentNodeMetadata
from ricecooker.utils.pipeline.context import FileMetadata
from ricecooker.utils.utils import extract_path_ext
from ricecooker.utils.videos import extract_duration_of_media
from ricecooker.utils.videos import guess_video_preset_by_resolution


PRESETS_FROM_EXTENSIONS = {
    file_formats.MP3: format_presets.AUDIO,
    file_formats.EPUB: format_presets.EPUB,
    file_formats.PDF: format_presets.DOCUMENT,
    file_formats.H5P: format_presets.H5P_ZIP,
    file_formats.BLOOMPUB: format_presets.BLOOMPUB,
    file_formats.BLOOMD: format_presets.BLOOMPUB,
    file_formats.HTML5: format_presets.HTML5_ZIP,
}

KIND_FROM_PRESET = {p.id: p.kind for p in format_presets.PRESETLIST}


class MetadataExtractor(ExtensionMatchingHandler):
    def infer_metadata(self, path):
        return {}

    def infer_preset(self, path):
        ext = extract_path_ext(path)
        return PRESETS_FROM_EXTENSIONS.get(ext)

    def handle_file(self, path):
        metadata = self.infer_metadata(path)
        preset = self.infer_preset(path)
        if preset:
            metadata["preset"] = preset
            kind = KIND_FROM_PRESET.get(preset)
            if kind:
                metadata["content_node_metadata"] = metadata.get(
                    "content_node_metadata", ContentNodeMetadata()
                )
                metadata["content_node_metadata"].kind = kind
        return FileMetadata(**metadata)


class MediaMetadataExtractorMixin:
    def infer_metadata(self, path):
        return {
            "duration": extract_duration_of_media(path, extract_path_ext(path)),
        }


class AudioMetadataExtractor(MediaMetadataExtractorMixin, MetadataExtractor):
    EXTENSIONS = {file_formats.MP3}


class EPUBMetadataExtractor(MetadataExtractor):
    EXTENSIONS = {file_formats.EPUB}


class PDFMetadataExtractor(MetadataExtractor):
    EXTENSIONS = {file_formats.PDF}


class HTML5MetadataExtractor(MetadataExtractor):
    EXTENSIONS = {file_formats.HTML5}


class H5PMetadataExtractor(MetadataExtractor):
    EXTENSIONS = {file_formats.H5P}


class BloomPubMetadataExtractor(MetadataExtractor):
    EXTENSIONS = {file_formats.BLOOMPUB, file_formats.BLOOMD}


class VideoMetadataExtractor(MediaMetadataExtractorMixin, MetadataExtractor):
    EXTENSIONS = {file_formats.MP4, file_formats.WEBM}

    def infer_preset(self, path):
        return guess_video_preset_by_resolution(path)


class ExtractMetadataStageHandler(StageHandler):
    STAGE = "EXTRACT_METADATA"
    DEFAULT_CHILDREN = [
        AudioMetadataExtractor,
        EPUBMetadataExtractor,
        PDFMetadataExtractor,
        H5PMetadataExtractor,
        HTML5MetadataExtractor,
        BloomPubMetadataExtractor,
        VideoMetadataExtractor,
    ]
