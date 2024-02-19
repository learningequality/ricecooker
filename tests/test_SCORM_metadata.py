import pytest
from le_utils.constants.labels import learning_activities
from le_utils.constants.labels import needs
from le_utils.constants.labels import resource_type

from ricecooker.utils.SCORM_metadata import infer_beginner_level_from_difficulty
from ricecooker.utils.SCORM_metadata import map_scorm_to_educator_resource_types
from ricecooker.utils.SCORM_metadata import map_scorm_to_le_utils_activities


@pytest.mark.parametrize(
    "scorm_dict, expected_result",
    [
        (
            {
                "educational": {
                    "interactivityType": "active",
                    "interactivityLevel": "high",
                    "learningResourceType": ["exercise", "simulation"],
                }
            },
            [learning_activities.PRACTICE, learning_activities.EXPLORE],
        ),
        (
            {"educational": {"learningResourceType": ["lecture", "self assessment"]}},
            [learning_activities.REFLECT, learning_activities.WATCH],
        ),
        (
            {
                "educational": {
                    "interactivityType": "mixed",
                    "interactivityLevel": "medium",
                    "learningResourceType": ["simulation", "graph"],
                }
            },
            [learning_activities.EXPLORE],
        ),
        (
            {
                "educational": {
                    "interactivityType": "expositive",
                    "interactivityLevel": "low",
                    "learningResourceType": ["simulation", "graph"],
                }
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
                "educational": {
                    "learningResourceType": ["exercise", "lecture"],
                    "intendedEndUserRole": ["teacher"],
                }
            },
            [resource_type.EXERCISE, resource_type.LESSON, resource_type.LESSON_PLAN],
        ),
        (
            {
                "educational": {
                    "learningResourceType": ["simulation", "figure"],
                    "intendedEndUserRole": ["author"],
                }
            },
            [resource_type.ACTIVITY, resource_type.MEDIA, resource_type.GUIDE],
        ),
    ],
)
def test_map_scorm_to_educator_resource_types(scorm_dict, expected_result):
    assert set(map_scorm_to_educator_resource_types(scorm_dict)) == set(expected_result)


def test_infer_beginner_level_from_difficulty():
    scorm_dict_easy = {"educational": {"difficulty": "easy"}}
    assert infer_beginner_level_from_difficulty(scorm_dict_easy) == [
        needs.FOR_BEGINNERS
    ]

    scorm_dict_hard = {"educational": {"difficulty": "difficult"}}
    assert infer_beginner_level_from_difficulty(scorm_dict_hard) == []
