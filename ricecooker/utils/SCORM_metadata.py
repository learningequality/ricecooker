"""
Utilities for mapping from SCORM metadata to LE Utils metadata.
"""
import re

from le_utils.constants import licenses
from le_utils.constants.labels import learning_activities
from le_utils.constants.labels import needs
from le_utils.constants.labels import resource_type
from le_utils.constants.languages import getlang


imscp_metadata_keys = {
    "general": ["title", "description", "language", "keyword"],
    "rights": ["cost", "copyrightAndOtherRestrictions", "description"],
    "educational": [
        "interactivityType",
        "interactivityLevel",
        "learningResourceType",
        "intendedEndUserRole",
    ],
    "lifeCycle": ["contribute"],
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


def _ensure_list(value):
    """Normalize a value to a list: None -> [], str -> [str], other -> list."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


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
    learning_resource_types = _ensure_list(metadata_dict.get("learningResourceType"))

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
    learning_resource_types = _ensure_list(metadata_dict.get("learningResourceType"))
    intended_roles = _ensure_list(metadata_dict.get("intendedEndUserRole"))

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


def parse_vcard_fn(vcard_text):
    """Extract FN (Full Name) from a VCARD string."""
    if not vcard_text:
        return None
    match = re.search(r"^FN:(.+)$", vcard_text, re.MULTILINE)
    return match.group(1).strip() if match else None


def parse_vcard_org(vcard_text):
    """Extract ORG (Organization) from a VCARD string."""
    if not vcard_text:
        return None
    match = re.search(r"^ORG:(.+)$", vcard_text, re.MULTILINE)
    return match.group(1).strip() if match else None


# CC license patterns, ordered most specific first to avoid partial matches
_CC_LICENSE_PATTERNS = [
    ("Attribution-NonCommercial-ShareAlike", licenses.CC_BY_NC_SA),
    ("Attribution-NonCommercial-NoDerivs", licenses.CC_BY_NC_ND),
    ("Attribution-ShareAlike", licenses.CC_BY_SA),
    ("Attribution-NoDerivs", licenses.CC_BY_ND),
    ("Attribution-NonCommercial", licenses.CC_BY_NC),
    ("Attribution", licenses.CC_BY),
]


def infer_license_from_rights(metadata_dict):
    """Infer a license ID from rights metadata fields.

    Args:
        metadata_dict: dict with rights_description, copyrightAndOtherRestrictions, etc.

    Returns:
        (license_id, license_description) tuple. Either or both may be None.
    """
    description = metadata_dict.get("rights_description")
    copyright_restrictions = metadata_dict.get("copyrightAndOtherRestrictions")

    if description:
        for pattern, license_id in _CC_LICENSE_PATTERNS:
            if pattern in description:
                return license_id, description

    if copyright_restrictions == "no":
        return licenses.PUBLIC_DOMAIN, description

    return None, description


def _resolve_entity_name(entity, prefer_org=False):
    """Extract a name from a VCARD entity string.

    If prefer_org is True, tries ORG first, then falls back to FN.
    Otherwise returns FN directly.
    """
    if prefer_org:
        return parse_vcard_org(entity) or parse_vcard_fn(entity)
    return parse_vcard_fn(entity)


# Maps contribute role -> (result field name, whether to prefer ORG over FN)
_ROLE_TO_FIELD = {
    "author": ("author", False),
    "publisher": ("provider", True),
    "content provider": ("copyright_holder", True),
}


def extract_lifecycle_contributors(metadata_dict):
    """Extract author, provider, copyright_holder from lifeCycle contribute data.

    Args:
        metadata_dict: dict that may contain a 'contribute' key with VCARD entity data

    Returns:
        dict with any of: author, provider, copyright_holder
    """
    result = {}
    contribute = metadata_dict.get("contribute")
    if not contribute:
        return result

    if isinstance(contribute, dict):
        contribute = [contribute]

    for entry in contribute:
        role_value = entry.get("role", {})
        if isinstance(role_value, dict):
            role_value = role_value.get("value", "")
        entity = entry.get("entity", "")

        field_config = _ROLE_TO_FIELD.get(role_value)
        if not field_config:
            continue
        field_name, prefer_org = field_config
        name = _resolve_entity_name(entity, prefer_org)
        if name:
            result[field_name] = name

    return result


def _normalize_language(lang_code):
    """Normalize a language code, returning None if unrecognized."""
    if not lang_code:
        return None
    if getlang(lang_code) is None:
        lang_code = lang_code.split("-")[0].lower()
    return lang_code if getlang(lang_code) else None


def _normalize_keywords(keyword):
    """Normalize keyword field to a list, or None if empty."""
    if not keyword:
        return None
    if isinstance(keyword, str):
        return [keyword]
    return keyword


def metadata_dict_to_content_node_fields(metadata_dict):
    """Convert a SCORM/IMSCP metadata dict to fields suitable for ContentNodeMetadata.

    Maps:
        title -> title
        description -> description
        language -> language (normalized: e.g. en-US -> en)
        keyword -> tags (as list)
        educational fields -> learning_activities, resource_types, learner_needs
        rights fields -> license, license_description
        lifeCycle contribute -> author, provider, copyright_holder

    Returns:
        dict of fields (only includes non-empty values)
    """
    result = {}

    if metadata_dict.get("title"):
        result["title"] = metadata_dict["title"]

    if metadata_dict.get("description"):
        result["description"] = metadata_dict["description"]

    language = _normalize_language(metadata_dict.get("language", ""))
    if language:
        result["language"] = language

    tags = _normalize_keywords(metadata_dict.get("keyword", []))
    if tags:
        result["tags"] = tags

    activities = map_scorm_to_le_utils_activities(metadata_dict)
    if activities:
        result["learning_activities"] = activities

    resource_types = map_scorm_to_educator_resource_types(metadata_dict)
    if resource_types:
        result["resource_types"] = resource_types

    learner_needs = infer_beginner_level_from_difficulty(metadata_dict)
    if learner_needs:
        result["learner_needs"] = learner_needs

    license_id, license_description = infer_license_from_rights(metadata_dict)
    if license_id:
        result["license"] = license_id
    if license_description:
        result["license_description"] = license_description

    contributors = extract_lifecycle_contributors(metadata_dict)
    result.update(contributors)

    return result
