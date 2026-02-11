from le_utils.constants import content_kinds
from le_utils.constants import file_formats
from le_utils.constants import format_presets

from .file_handler import ExtensionMatchingHandler
from .file_handler import StageHandler
from ricecooker.utils.imscp import has_imscp_manifest
from ricecooker.utils.imscp import has_qti_items
from ricecooker.utils.imscp import has_webcontent_items
from ricecooker.utils.imscp import is_qti_resource
from ricecooker.utils.imscp import parse_imscp_manifest
from ricecooker.utils.pipeline.context import _content_node_metadata_from_dict
from ricecooker.utils.pipeline.context import ContentNodeMetadata
from ricecooker.utils.pipeline.context import FileMetadata
from ricecooker.utils.SCORM_metadata import metadata_dict_to_content_node_fields
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


class IMSCPMetadataExtractor(MetadataExtractor):
    """Extracts metadata from IMSCP content packages, producing nested ContentNodeMetadata."""

    EXTENSIONS = {file_formats.HTML5}

    def should_handle(self, path: str) -> bool:
        if not super().should_handle(path):
            return False
        return has_imscp_manifest(path)

    def _infer_preset_from_manifest(self, manifest):
        """Infer the primary preset from a parsed manifest dict.

        Returns QTI_ZIP for pure QTI packages, IMSCP_ZIP for everything else
        (pure webcontent, mixed QTI+webcontent, or manifests with no
        organizations/leaf items).
        """
        has_qti = has_qti_items(manifest)
        has_webcontent = has_webcontent_items(manifest)
        if has_qti and not has_webcontent:
            # Pure QTI package (assessments only)
            return format_presets.QTI_ZIP
        # IMSCP for: pure webcontent, mixed (QTI + webcontent), or
        # unknown resource types (safe default for any IMS package)
        return format_presets.IMSCP_ZIP

    def _build_children_metadata(self, items):
        """Recursively build ContentNodeMetadata list from parsed item dicts."""
        children = []
        for item in items:
            fields = metadata_dict_to_content_node_fields(item.get("metadata", {}))
            fields["title"] = item.get("title", fields.get("title"))
            fields["source_id"] = item.get("identifier", item.get("title"))

            if "children" in item:
                # This is a topic node
                fields["kind"] = "topic"
                fields["children"] = self._build_children_metadata(item["children"])
            else:
                # This is a leaf content node — detect QTI vs webcontent
                resource_type = item.get("type", "")
                if is_qti_resource(resource_type):
                    fields["kind"] = content_kinds.EXERCISE
                    fields["file_preset"] = format_presets.QTI_ZIP
                else:
                    fields["kind"] = content_kinds.HTML5
                    fields["file_preset"] = format_presets.IMSCP_ZIP
                entry = item.get("href", "")
                if item.get("parameters"):
                    entry += item["parameters"]
                fields["extra_fields"] = {"options": {"entry": entry}}

            children.append(_content_node_metadata_from_dict(fields))
        return children

    def handle_file(self, path):
        manifest = parse_imscp_manifest(path)
        root_fields = metadata_dict_to_content_node_fields(manifest.get("metadata", {}))

        organizations = manifest.get("organizations", [])
        if organizations:
            root_fields["kind"] = "topic"
            root_fields["children"] = self._build_children_metadata(organizations)

        preset = self._infer_preset_from_manifest(manifest)
        content_node_metadata = _content_node_metadata_from_dict(root_fields)

        return FileMetadata(
            preset=preset,
            content_node_metadata=content_node_metadata,
        )


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
        IMSCPMetadataExtractor,
        HTML5MetadataExtractor,
        BloomPubMetadataExtractor,
        VideoMetadataExtractor,
    ]
