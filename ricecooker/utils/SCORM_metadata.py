"""
Utilities for mapping from SCORM metadata to LE Utils metadata.
"""
from le_utils.constants.labels import learning_activities
from le_utils.constants.labels import needs
from le_utils.constants.labels import resource_type


imscp_metadata_keys = {
    "general": ["title", "description", "language", "keyword"],
    "rights": [],
    "educational": [
        "interactivityType",
        "interactivityLevel",
        "learningResourceType",
        "intendedEndUserRole",
    ],
    "lifecycle": [],
}


# Define mappings from SCORM educational types to LE Utils activity types
SCORM_to_learning_activities_mappings = {
    "exercise": learning_activities.PRACTICE,
    "simulation": learning_activities.EXPLORE,
    "questionnaire": learning_activities.PRACTICE,
    "diagram": learning_activities.EXPLORE,
    "figure": learning_activities.EXPLORE,
    "graph": learning_activities.EXPLORE,
    "index": learning_activities.READ,
    "slide": learning_activities.READ,
    "table": learning_activities.READ,
    "narrative text": learning_activities.READ,
    "exam": learning_activities.PRACTICE,
    "experiment": learning_activities.EXPLORE,
    "problem statement": learning_activities.REFLECT,
    "self assessment": learning_activities.REFLECT,
    "lecture": learning_activities.WATCH,
}


def map_scorm_to_le_utils_activities(metadata_dict):
    le_utils_activities = []

    # Adjustments based on interactivity
    interactive_adjustments = {
        learning_activities.EXPLORE: (
            learning_activities.READ,
            learning_activities.WATCH,
        )
    }

    # Determine the interactivity level and type
    interactivity_type = metadata_dict.get("interactivityType")
    interactivity_level = metadata_dict.get("interactivityLevel")

    is_interactive = (
        interactivity_type
        in [
            "active",
            "mixed",
        ]
        or interactivity_level in ["medium", "high"]
    )

    # Extract the learning resource types from the SCORM data
    learning_resource_types = metadata_dict.get("learningResourceType", [])

    # Map each SCORM type to an LE Utils activity type
    for learning_resource_type in learning_resource_types:
        le_utils_type = SCORM_to_learning_activities_mappings.get(
            learning_resource_type
        )
        # Adjust based on interactivity
        if not is_interactive and le_utils_type in interactive_adjustments:
            le_utils_type = (
                interactive_adjustments[le_utils_type][0]
                if learning_resource_type == "simulation"
                else interactive_adjustments[le_utils_type][1]
            )

        if le_utils_type and le_utils_type not in le_utils_activities:
            le_utils_activities.append(le_utils_type)

    return le_utils_activities


# Define mappings from SCORM educational types to educator-focused resource types
SCORM_to_resource_type_mappings = {
    "exercise": resource_type.EXERCISE,
    "simulation": resource_type.ACTIVITY,
    "questionnaire": resource_type.ACTIVITY,
    "diagram": resource_type.MEDIA,
    "figure": resource_type.MEDIA,
    "graph": resource_type.MEDIA,
    "index": resource_type.GUIDE,
    "slide": resource_type.LESSON,
    "table": resource_type.TUTORIAL,
    "narrative text": resource_type.TEXTBOOK,
    "exam": resource_type.EXERCISE,
    "experiment": resource_type.ACTIVITY,
    "problem statement": resource_type.ACTIVITY,
    "self assessment": resource_type.ACTIVITY,
    "lecture": resource_type.LESSON,
}


# Mapping for intendedEndUserRole when the resource is for educators
SCORM_intended_role_to_resource_type_mapping = {
    "teacher": resource_type.LESSON_PLAN,
    "author": resource_type.GUIDE,
    "manager": resource_type.GUIDE,
}


def map_scorm_to_educator_resource_types(metadata_dict):
    educator_resource_types = []

    # Extract the learning resource types and intended end user role from the SCORM data
    learning_resource_types = metadata_dict.get("learningResourceType", [])
    intended_roles = metadata_dict.get("intendedEndUserRole", [])

    # Map each SCORM type to an educator-focused resource type
    for learning_resource_type in learning_resource_types:
        mapped_type = SCORM_to_resource_type_mappings.get(learning_resource_type)
        if mapped_type and mapped_type not in educator_resource_types:
            educator_resource_types.append(mapped_type)

    # Check if the intended end user role matches any educator roles
    for role in intended_roles:
        if (
            role in SCORM_intended_role_to_resource_type_mapping
            and SCORM_intended_role_to_resource_type_mapping[role]
            not in educator_resource_types
        ):
            educator_resource_types.append(
                SCORM_intended_role_to_resource_type_mapping[role]
            )

    return educator_resource_types


def infer_beginner_level_from_difficulty(metadata_dict):
    # Beginner difficulty levels
    beginner_difficulties = {"very easy", "easy"}

    # Check if the difficulty level indicates beginner content
    difficulty = metadata_dict.get("difficulty")
    if difficulty in beginner_difficulties:
        return [needs.FOR_BEGINNERS]

    return []


def update_node_from_metadata(node, metadata_dict):
    # Update the node with the general metadata
    node.description = metadata_dict.get("description") or node.description
    if metadata_dict.get("language"):
        node.set_language(metadata_dict.get("language"))
    node.tags = node.tags + metadata_dict.get("keyword", [])

    # Update the node with the educational metadata
    node.learning_activities = (
        node.learning_activities + map_scorm_to_le_utils_activities(metadata_dict)
    )
    node.resource_types = node.resource_types + map_scorm_to_educator_resource_types(
        metadata_dict
    )
    node.learner_needs = node.learner_needs + infer_beginner_level_from_difficulty(
        metadata_dict
    )

    return node
