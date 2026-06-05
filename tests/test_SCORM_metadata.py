import pytest
from le_utils.constants import licenses
from le_utils.constants.labels import learning_activities
from le_utils.constants.labels import needs
from le_utils.constants.labels import resource_type

from ricecooker.utils.SCORM_metadata import extract_lifecycle_contributors
from ricecooker.utils.SCORM_metadata import infer_beginner_level_from_difficulty
from ricecooker.utils.SCORM_metadata import infer_license_from_rights
from ricecooker.utils.SCORM_metadata import map_scorm_to_educator_resource_types
from ricecooker.utils.SCORM_metadata import map_scorm_to_le_utils_activities
from ricecooker.utils.SCORM_metadata import parse_vcard_fn
from ricecooker.utils.SCORM_metadata import parse_vcard_org


@pytest.mark.parametrize(
    "scorm_dict, expected_result",
    [
        (
            {
                "interactivityType": "active",
                "interactivityLevel": "high",
                "learningResourceType": ["exercise", "simulation"],
            },
            [learning_activities.PRACTICE, learning_activities.EXPLORE],
        ),
        (
            {"learningResourceType": ["lecture", "self assessment"]},
            [learning_activities.REFLECT, learning_activities.WATCH],
        ),
        (
            {
                "interactivityType": "mixed",
                "interactivityLevel": "medium",
                "learningResourceType": ["simulation", "graph"],
            },
            [learning_activities.EXPLORE],
        ),
        (
            {
                "interactivityType": "expositive",
                "interactivityLevel": "low",
                "learningResourceType": ["simulation", "graph"],
            },
            [learning_activities.READ, learning_activities.WATCH],
        ),
    ],
)
def test_map_scorm_to_le_utils_activities(scorm_dict, expected_result):
    assert set(map_scorm_to_le_utils_activities(scorm_dict)) == set(expected_result)


@pytest.mark.parametrize(
    "scorm_dict, expected_result",
    [
        (
            {
                "learningResourceType": ["exercise", "lecture"],
                "intendedEndUserRole": ["teacher"],
            },
            [resource_type.EXERCISE, resource_type.LESSON, resource_type.LESSON_PLAN],
        ),
        (
            {
                "learningResourceType": ["simulation", "figure"],
                "intendedEndUserRole": ["author"],
            },
            [resource_type.ACTIVITY, resource_type.MEDIA, resource_type.GUIDE],
        ),
    ],
)
def test_map_scorm_to_educator_resource_types(scorm_dict, expected_result):
    assert set(map_scorm_to_educator_resource_types(scorm_dict)) == set(expected_result)


def test_infer_beginner_level_from_difficulty():
    scorm_dict_easy = {"difficulty": "easy"}
    assert infer_beginner_level_from_difficulty(scorm_dict_easy) == [
        needs.FOR_BEGINNERS
    ]

    scorm_dict_hard = {"difficulty": "difficult"}
    assert infer_beginner_level_from_difficulty(scorm_dict_hard) == []


# --- VCARD parsing tests ---


def test_parse_vcard_fn():
    vcard = "BEGIN:VCARD\nVERSION:2.1\nFN:John Doe\nORG:Example Org\nEND:VCARD"
    assert parse_vcard_fn(vcard) == "John Doe"


def test_parse_vcard_fn_none():
    assert parse_vcard_fn(None) is None
    assert parse_vcard_fn("BEGIN:VCARD\nVERSION:2.1\nEND:VCARD") is None


def test_parse_vcard_org():
    vcard = "BEGIN:VCARD\nVERSION:2.1\nFN:John Doe\nORG:Example Organization\nEND:VCARD"
    assert parse_vcard_org(vcard) == "Example Organization"


def test_parse_vcard_org_none():
    assert parse_vcard_org(None) is None
    assert parse_vcard_org("BEGIN:VCARD\nVERSION:2.1\nFN:John\nEND:VCARD") is None


# --- License inference tests ---


def test_infer_license_cc_by_nc_sa():
    metadata = {
        "rights_description": "Content is protected under Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.",
        "copyrightAndOtherRestrictions": "yes",
    }
    license_id, license_desc = infer_license_from_rights(metadata)
    assert license_id == licenses.CC_BY_NC_SA


def test_infer_license_cc_by():
    metadata = {
        "rights_description": "Licensed under Creative Commons Attribution 4.0",
        "copyrightAndOtherRestrictions": "yes",
    }
    license_id, license_desc = infer_license_from_rights(metadata)
    assert license_id == licenses.CC_BY


def test_infer_license_public_domain():
    metadata = {
        "copyrightAndOtherRestrictions": "no",
    }
    license_id, license_desc = infer_license_from_rights(metadata)
    assert license_id == licenses.PUBLIC_DOMAIN


def test_infer_license_no_match():
    metadata = {
        "rights_description": "All rights reserved. Custom license.",
        "copyrightAndOtherRestrictions": "yes",
    }
    license_id, license_desc = infer_license_from_rights(metadata)
    assert license_id is None
    assert license_desc == "All rights reserved. Custom license."


def test_infer_license_empty():
    license_id, license_desc = infer_license_from_rights({})
    assert license_id is None
    assert license_desc is None


# --- Lifecycle contributor extraction tests ---


def test_extract_lifecycle_publisher():
    metadata = {
        "contribute": {
            "role": {"value": "publisher"},
            "entity": "BEGIN:VCARD\nVERSION:2.1\nFN:John Doe\nORG:Example Organization\nEND:VCARD",
        }
    }
    result = extract_lifecycle_contributors(metadata)
    assert result["provider"] == "Example Organization"


def test_extract_lifecycle_author():
    metadata = {
        "contribute": {
            "role": {"value": "author"},
            "entity": "BEGIN:VCARD\nVERSION:2.1\nFN:Jane Smith\nEND:VCARD",
        }
    }
    result = extract_lifecycle_contributors(metadata)
    assert result["author"] == "Jane Smith"


def test_extract_lifecycle_multiple_contributors():
    metadata = {
        "contribute": [
            {
                "role": {"value": "author"},
                "entity": "BEGIN:VCARD\nVERSION:2.1\nFN:Jane Smith\nEND:VCARD",
            },
            {
                "role": {"value": "publisher"},
                "entity": "BEGIN:VCARD\nVERSION:2.1\nFN:John Doe\nORG:Pub Corp\nEND:VCARD",
            },
        ]
    }
    result = extract_lifecycle_contributors(metadata)
    assert result["author"] == "Jane Smith"
    assert result["provider"] == "Pub Corp"


def test_extract_lifecycle_empty():
    result = extract_lifecycle_contributors({})
    assert result == {}
