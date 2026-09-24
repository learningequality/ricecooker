"""Tests for mapping raw LOM metadata onto content-node fields."""

import pytest
from le_utils.constants import licenses
from le_utils.constants.labels import learning_activities
from le_utils.constants.labels import needs
from le_utils.constants.labels import resource_type

from ricecooker.utils.SCORM_metadata import extract_lifecycle_contributors
from ricecooker.utils.SCORM_metadata import infer_license_from_rights
from ricecooker.utils.SCORM_metadata import metadata_dict_to_content_node_fields


def test_metadata_dict_to_content_node_fields():
    fields = metadata_dict_to_content_node_fields(
        {
            "title": "Intro to Widgets",
            "description": "A short lesson.",
            "language": "en-US",
            "keyword": "widgets",
            "learningResourceType": "narrative text",
            "intendedEndUserRole": "teacher",
            "rights_description": "Creative Commons Attribution 4.0",
            "difficulty": "very easy",
            "contribute": [
                {"role": "author", "entity": "FN:Grace Hopper"},
                {"role": "publisher", "entity": "ORG:Acme Ed"},
                {"role": "content provider", "entity": "ORG:Widget Trust"},
            ],
        }
    )
    assert fields == {
        "title": "Intro to Widgets",
        "description": "A short lesson.",
        "language": "en",
        "tags": ["widgets"],
        "learning_activities": [learning_activities.READ],
        "resource_types": [resource_type.TEXTBOOK, resource_type.LESSON_PLAN],
        "learner_needs": [needs.FOR_BEGINNERS],
        "license": licenses.CC_BY,
        "license_description": "Creative Commons Attribution 4.0",
        "author": "Grace Hopper",
        "provider": "Acme Ed",
        "copyright_holder": "Widget Trust",
    }


def test_multilingual_lom_fields_reduce_to_single_values():
    # LOM repeats a field per language, so the parser hands back lists (and lists
    # of lists for repeated elements). Node fields that must be strings take the
    # first value, and mapping lookups must not be handed an unhashable list.
    fields = metadata_dict_to_content_node_fields(
        {
            "title": ["Intro to Widgets", "Introducción a los Widgets"],
            "description": ["A short lesson.", "Una lección corta."],
            "language": ["en-US", "es"],
            "keyword": [["widgets", "gears"], "cogs"],
            "learningResourceType": [["narrative text"], "lecture"],
            "intendedEndUserRole": [["teacher"]],
        }
    )
    assert fields["title"] == "Intro to Widgets"
    assert fields["description"] == "A short lesson."
    assert fields["language"] == "en"
    assert fields["tags"] == ["widgets", "gears", "cogs"]
    assert fields["learning_activities"] == [
        learning_activities.READ,
        learning_activities.WATCH,
    ]
    assert resource_type.LESSON_PLAN in fields["resource_types"]


@pytest.mark.parametrize(
    "lom,expected",
    [
        ({"copyrightAndOtherRestrictions": "no"}, licenses.PUBLIC_DOMAIN),
        # A license needing attribution is only usable with someone to attribute.
        ({"rights_description": "Attribution-ShareAlike"}, None),
        (
            {
                "rights_description": "Attribution-ShareAlike",
                "contribute": {
                    "role": "content provider",
                    "entity": "ORG:Widget Trust",
                },
            },
            licenses.CC_BY_SA,
        ),
        ({}, None),
    ],
)
def test_license_inference(lom, expected):
    assert metadata_dict_to_content_node_fields(lom).get("license") == expected


@pytest.mark.parametrize(
    "description,expected",
    [
        ("Attribution-NoDerivatives 4.0", licenses.CC_BY_ND),
        ("Attribution-NonCommercial-NoDerivatives 4.0", licenses.CC_BY_NC_ND),
        ("Attribution Non-Commercial Share Alike", licenses.CC_BY_NC_SA),
        ("All rights reserved", None),
    ],
)
def test_cc_license_names(description, expected):
    assert infer_license_from_rights({"rights_description": description})[0] == expected


@pytest.mark.parametrize(
    "vcard",
    [
        "FN:Ada Lovelace",
        # eXe writes the whole vCard on one line.
        "BEGIN:VCARD VERSION:3.0 FN:Ada Lovelace N:Lovelace;Ada END:VCARD",
        "BEGIN:VCARD\n  FN;CHARSET=UTF-8:Ada Lovelace\n  N:Lovelace;Ada\nEND:VCARD",
    ],
)
def test_vcard_name_forms(vcard):
    fields = extract_lifecycle_contributors(
        {"contribute": {"role": "Author", "entity": vcard}}
    )
    assert fields == {"author": "Ada Lovelace"}


@pytest.mark.parametrize(
    "lom,expected",
    [
        # A simulation with no interactivity signal downgrades EXPLORE -> READ.
        ({"learningResourceType": "simulation"}, learning_activities.READ),
        # A diagram (also EXPLORE) downgrades to WATCH, not READ.
        ({"learningResourceType": "diagram"}, learning_activities.WATCH),
        # An interactivity signal keeps EXPLORE.
        (
            {"learningResourceType": "simulation", "interactivityType": "active"},
            learning_activities.EXPLORE,
        ),
    ],
)
def test_activities_downgrade_when_not_interactive(lom, expected):
    fields = metadata_dict_to_content_node_fields(lom)
    assert fields["learning_activities"] == [expected]


def test_over_long_keywords_are_dropped():
    # LOM keywords are often whole phrases, and a tag over 30 characters fails
    # node validation — dropping it must not take the whole package down with it.
    fields = metadata_dict_to_content_node_fields(
        {"keyword": ["widgets", "Data (especially computer data)!"]}
    )
    assert fields["tags"] == ["widgets"]
