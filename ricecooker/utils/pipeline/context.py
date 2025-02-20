from dataclasses import asdict
from dataclasses import dataclass
from typing import Optional
from typing import Type


class AutoDataClassMetaClass(type):
    def __new__(mcs, name: str, bases: tuple, namespace: dict) -> Type:
        cls = super().__new__(mcs, name, bases, namespace)
        return dataclass(frozen=True)(cls)


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

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v is not None}

    def merge(self, other):
        """
        Create a new FileMetadata object by the result of overwriting self
        fields with other fields when defined.
        """
        new_dict = self.to_dict()
        new_dict.update(other.to_dict())
        return self.__class__(**new_dict)


class ContextMetadata(metaclass=AutoDataClassMetaClass):
    def to_dict(self):
        return asdict(self)
