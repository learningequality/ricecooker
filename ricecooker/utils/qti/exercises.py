"""Build the QTI 3.0 tests and items of an IMSCP package into exercises."""

import os
import posixpath
from functools import partial
from urllib.parse import urlparse

from le_utils.constants import content_kinds
from le_utils.constants import exercises
from le_utils.constants import format_presets
from le_utils.constants import modalities
from lxml import etree

from ricecooker.config import LOGGER
from ricecooker.utils.imscp import contained_path
from ricecooker.utils.imscp import node_content_fields
from ricecooker.utils.paths import extract_path_ext
from ricecooker.utils.pipeline.convert import ImageConversionHandler
from ricecooker.utils.pipeline.convert import SVGValidationHandler
from ricecooker.utils.pipeline.exceptions import ExpectedFileException
from ricecooker.utils.pipeline.exceptions import InvalidFileException
from ricecooker.utils.qti.items import QTI3_NAMESPACE
from ricecooker.utils.qti.items import read_qti3
from ricecooker.utils.qti.items import strip_unschematized
from ricecooker.utils.qti.items import validate_qti_item
from ricecooker.utils.references import QTIMapper
from ricecooker.utils.references import resolve_reference

QTI_TEST_TYPE_PREFIX = "imsqti_test_"
QTI_ITEM_TYPE_PREFIX = "imsqti_item_"
_ITEM_REF_TAG = f"{{{QTI3_NAMESPACE}}}qti-assessment-item-ref"
_SECTION_REF_TAG = f"{{{QTI3_NAMESPACE}}}qti-assessment-section-ref"


def media_member(item_member, ref):
    """Package path of media ``ref`` in ``item_member``; ``None`` for URLs and fragments."""
    if urlparse(ref).scheme:
        return None
    return resolve_reference(item_member, ref)


def assessment_item_members(package_dir, test_member, root, seen=None):
    """Item package paths ``root`` references, in document order, following section refs.

    Hrefs are relative to the file holding them.
    """
    seen = seen if seen is not None else {test_member}
    members = []
    for elem in root.iter(_ITEM_REF_TAG, _SECTION_REF_TAG):
        member = resolve_reference(test_member, elem.get("href") or "")
        if member is None:
            continue
        if elem.tag == _ITEM_REF_TAG:
            members.append(member)
        elif member not in seen:
            seen.add(member)
            try:
                section = read_qti3(package_dir, member, "qti-assessment-section")
            except ValueError as e:
                LOGGER.warning("IMSCP: skipping QTI section %s: %s", member, e)
                continue
            members += assessment_item_members(package_dir, member, section, seen)
    return members


class QTIExerciseBuilder:
    """Build the QTI 3.0 tests and items of one IMSCP package into exercise node dicts."""

    IMAGE_EXTENSIONS = (
        ImageConversionHandler.EXTENSIONS | SVGValidationHandler.EXTENSIONS
    )

    def __init__(self, package, pipeline):
        self.package = package
        self.pipeline = pipeline
        # Tests often share items and items share images: build each once per package.
        self.questions = {}
        self.images = {}

    def exercises(self, manifest):
        """One exercise per QTI test, else one holding every loose item."""
        tests, items = self._split_resources(manifest["qti_resources"])
        if tests:
            built = [self._build_test_exercise(test) for test in tests]
        elif items:
            loose = {"source_id": "qti-items", "metadata": manifest["metadata"]}
            built = [self._build_exercise(loose, items)]
        else:
            return []
        return [exercise for exercise in built if exercise is not None]

    @staticmethod
    def _split_resources(resources):
        """``([test resource], [item member])``, test and item paths normalised."""
        tests, items = [], []
        for resource in resources:
            if not resource.get("index_file"):
                continue
            member = posixpath.normpath(resource["index_file"])
            if resource["type"].startswith(QTI_TEST_TYPE_PREFIX):
                tests.append({**resource, "index_file": member})
            elif resource["type"].startswith(QTI_ITEM_TYPE_PREFIX):
                items.append(member)
            elif "v3p0" not in resource["type"]:
                LOGGER.warning(
                    "IMSCP: skipping QTI resource %s: only QTI 3.0 is supported",
                    resource["source_id"],
                )
        return tests, items

    def _build_test_exercise(self, test):
        member = test["index_file"]
        try:
            root = read_qti3(self.package.directory, member, "qti-assessment-test")
        except ValueError as e:
            LOGGER.warning("IMSCP: rejecting QTI test %s: %s", member, e)
            return None
        return self._build_exercise(
            {**test, "title": root.get("title")},
            assessment_item_members(self.package.directory, member, root),
        )

    def _build_exercise(self, node_dict, members):
        questions, ids = [], set()
        for member in members:
            question = self._question(member)
            if question is None:
                continue
            # Studio rejects a node with duplicate assessment_ids, which blocks the channel commit.
            if question["id"] in ids:
                LOGGER.warning("IMSCP: skipping repeated QTI item %s", member)
                continue
            ids.add(question["id"])
            questions.append(question)
        if not questions:
            LOGGER.warning(
                "IMSCP: skipping QTI exercise %s, every item was rejected",
                node_dict["source_id"],
            )
            return None
        return {
            **node_content_fields(node_dict),
            "kind": content_kinds.EXERCISE,
            "questions": questions,
            # Practice quiz by default (#337); the declaring node's extra_fields override.
            "extra_fields": {
                "mastery_model": exercises.DO_ALL,
                "randomize": False,
                "options": {"modality": modalities.QUIZ},
            },
        }

    def _question(self, member):
        """The cached question for item ``member``; ``None`` if the item is rejected."""
        if member not in self.questions:
            try:
                self.questions[member] = self._build_question(member)
            except (ValueError, InvalidFileException, ExpectedFileException) as e:
                LOGGER.warning("IMSCP: rejecting QTI item %s: %s", member, e)
                self.questions[member] = None
        return self.questions[member]

    def _build_question(self, member):
        item = read_qti3(self.package.directory, member, "qti-assessment-item")
        strip_unschematized(item)
        # Studio fails the whole channel commit on one schema-invalid item.
        validate_qti_item(item)
        files = []
        raw_data, _ = QTIMapper().map(
            etree.tostring(item, encoding="unicode"),
            partial(self._image_filename, member, files),
        )
        return {"id": item.get("identifier"), "raw_data": raw_data, "files": files}

    def _image_filename(self, member, files, ref):
        """Storage filename of image ``ref`` in item ``member``, added to ``files``; URLs and fragments unchanged."""
        media = media_member(member, ref)
        if media is None:
            return ref
        image = self._image(media, ref)
        if image not in files:
            files.append(image)
        return image["filename"]

    def _image(self, media, ref):
        """The cached file dict for image ``media``, which item markup references as ``ref``."""
        if media not in self.images:
            path = contained_path(self.package.directory, media)
            if path is None or not os.path.isfile(path):
                raise ValueError(f"references missing media {ref}")
            if extract_path_ext(path) not in self.IMAGE_EXTENSIONS:
                raise ValueError(f"references non-image media {ref}")
            file_metadata = self.pipeline.execute(path)[0]
            self.images[media] = {
                **file_metadata.to_dict(),
                "preset": format_presets.EXERCISE_IMAGE,
            }
        return self.images[media]
