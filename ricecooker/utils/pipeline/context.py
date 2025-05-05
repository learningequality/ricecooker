from dataclasses import asdict
from dataclasses import dataclass
from typing import Optional
from typing import Type


class AutoDataClassMetaClass(type):
    def __new__(mcs, name: str, bases: tuple, namespace: dict) -> Type:
        cls = super().__new__(mcs, name, bases, namespace)
        return dataclass(frozen=True)(cls)


@dataclass
class ContentNodeMetadata:
    """
    A dataclass for storing metadata about a content node.
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
    source_id: Optional[str] = None
    kind: Optional[str] = None
    extra_fields: Optional[dict] = None


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
        return self.__class__(**new_dict)


class ContextMetadata(metaclass=AutoDataClassMetaClass):
    def to_dict(self):
        return asdict(self)
