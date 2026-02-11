from __future__ import annotations

import logging
from dataclasses import asdict
from dataclasses import dataclass
from typing import Optional
from typing import Type

logger = logging.getLogger(__name__)


class AutoDataClassMetaClass(type):
    def __new__(mcs, name: str, bases: tuple, namespace: dict) -> Type:
        cls = super().__new__(mcs, name, bases, namespace)
        return dataclass(frozen=True)(cls)


@dataclass
class ContentNodeMetadata:
    """
    A dataclass for storing metadata about a content node.

    Intentionally mutable (not frozen) because MetadataExtractor.handle_file()
    sets .kind in place after construction (see extract_metadata.py line ~50).
    This differs from ContextMetadata which uses frozen=True.
    """

    title: Optional[str] = None
    description: Optional[str] = None
    thumbnail: Optional[str] = None
    license: Optional[str] = None
    license_description: Optional[str] = None
    author: Optional[str] = None
    aggregator: Optional[str] = None
    copyright_holder: Optional[str] = None
    provider: Optional[str] = None
    grade_levels: Optional[list[str]] = None
    categories: Optional[list[str]] = None
    resource_types: Optional[list[str]] = None
    learning_activities: Optional[list[str]] = None
    accessibility_labels: Optional[list[str]] = None
    learner_needs: Optional[list[str]] = None
    role: Optional[str] = None
    language: Optional[str] = None
    source_id: Optional[str] = None
    kind: Optional[str] = None
    extra_fields: Optional[dict] = None
    tags: Optional[list[str]] = None
    children: Optional[list[ContentNodeMetadata]] = None
    file_preset: Optional[str] = None  # preset to assign to parent file for this child


def _content_node_metadata_from_dict(d):
    """Reconstruct a ContentNodeMetadata (with nested children) from a dict."""
    children = d.get("children")
    if children is not None:
        d = dict(
            d,
            children=[
                _content_node_metadata_from_dict(c) if isinstance(c, dict) else c
                for c in children
            ],
        )
    valid_keys = ContentNodeMetadata.__dataclass_fields__
    dropped = {k for k in d if k not in valid_keys}
    if dropped:
        logger.debug("Dropped unknown keys from ContentNodeMetadata dict: %s", dropped)
    valid = {k: v for k, v in d.items() if k in valid_keys}
    return ContentNodeMetadata(**valid)


def _recursive_update(target, source):
    for k, v in source.items():
        if k in target and isinstance(v, dict):
            target[k] = _recursive_update(target[k], v)
        else:
            target[k] = v
    return target


@dataclass
class FileMetadata:
    filename: Optional[str] = None
    path: Optional[str] = None
    original_filename: Optional[str] = None
    language: Optional[str] = None
    duration: Optional[int] = None
    license: Optional[str] = None
    license_description: Optional[str] = None
    preset: Optional[str] = None
    content_node_metadata: Optional[ContentNodeMetadata] = None

    def to_dict(self):
        return asdict(
            self, dict_factory=lambda x: {k: v for k, v in x if v is not None}
        )

    def merge(self, other):
        """
        Create a new FileMetadata object by the result of overwriting self
        fields with other fields when defined.
        """
        new_dict = _recursive_update(self.to_dict(), other.to_dict())
        # Reconstruct ContentNodeMetadata from dict if present
        cnm = new_dict.get("content_node_metadata")
        if isinstance(cnm, dict):
            new_dict["content_node_metadata"] = _content_node_metadata_from_dict(cnm)
        return self.__class__(**new_dict)


class ContextMetadata(metaclass=AutoDataClassMetaClass):
    def to_dict(self):
        return asdict(self)
