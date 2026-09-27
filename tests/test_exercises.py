"""Tests for exercise nodes, questions, and files"""

import json
import os
import re
import sys
import uuid
from unittest.mock import patch

import pytest
from le_utils.constants import exercises
from le_utils.constants import format_presets
from le_utils.constants import licenses
from test_videos import _clear_ricecookerfilecache
from vcr_config import my_vcr

from ricecooker.classes.nodes import ExerciseNode
from ricecooker.classes.nodes import InvalidNodeException
from ricecooker.classes.questions import BaseQuestion
from ricecooker.classes.questions import InputQuestion
from ricecooker.classes.questions import MARKDOWN_IMAGE_REGEX
from ricecooker.classes.questions import MultipleSelectQuestion
from ricecooker.classes.questions import PerseusQuestion
from ricecooker.classes.questions import QTIQuestion
from ricecooker.classes.questions import SingleSelectQuestion
from ricecooker.config import STORAGE_DIRECTORY
from ricecooker.exceptions import InvalidQuestionException
from ricecooker.managers.tree import ChannelManager

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
TESTCONTENT_DIR = os.path.join(TESTS_DIR, "testcontent")

""" *********** EXERCISE FIXTURES *********** """


@pytest.fixture
def exercise_id():
    return "exercise-id"


@pytest.fixture
def channel_internal_domain():
    return "learningequality.org".encode("utf-8")


@pytest.fixture
def topic_node_id():
    return "some-node-id"


@pytest.fixture
def exercise_content_id(channel_internal_domain, exercise_id):
    return uuid.uuid5(channel_internal_domain, exercise_id)


@pytest.fixture
def exercise_node_id(topic_node_id, exercise_content_id):
    return uuid.uuid5(topic_node_id, exercise_content_id.hex)


@pytest.fixture
def exercise_data(exercise_id):
    return {
        "title": "exercise node test",
        "description": None,
        "id": exercise_id,
        "author": None,
        "license": licenses.PUBLIC_DOMAIN,
    }


@pytest.fixture
def exercise_questions():
    return [
        SingleSelectQuestion(
            id="123",
            question="What is your quest?",
            correct_answer="To spectacularly fail",
            all_answers=[
                "To seek the grail",
                "To eat some hail",
                "To spectacularly fail",
                "To post bail",
            ],
        )
    ]


@pytest.fixture
def exercise(exercise_data, channel_internal_domain, topic_node_id, exercise_questions):
    node = ExerciseNode(
        source_id=exercise_data["id"],
        # description=exercise_data['description'],
        title=exercise_data["title"],
        author=exercise_data["author"],
        license=exercise_data["license"],
        questions=exercise_questions,
    )
    # node.set_ids(channel_internal_domain, topic_node_id)
    return node


@pytest.fixture
def exercise_json(exercise_data, exercise_content_id, exercise_node_id):
    return {
        "id": exercise_data["id"],
        "title": exercise_data["title"],
        "description": "",
        "node_id": exercise_node_id.hex,
        "content_id": exercise_content_id.hex,
        "author": "",
        "children": [],
        "files": [],
        "kind": exercises.PERSEUS_QUESTION,
        "license": exercise_data["license"],
    }


""" *********** EXERCISE TESTS *********** """


def test_exercise_created(exercise):
    assert exercise is not None


def test_exercise_validate(exercise, exercise_data):
    assert exercise.source_id == exercise_data["id"]
    assert exercise.title == exercise_data["title"]
    # assert exercise.description == exercise_data['description']
    # assert exercise.author == exercise_data['author']
    # assert exercise.license == exercise_data['license']
    # assert exercise.kind == exercises.PERSEUS_QUESTION


def test_exercise_extra_fields_string(exercise):
    exercise.extra_fields = {"mastery_model": exercises.M_OF_N, "m": "3", "n": "5"}

    # validate should call process_exercise_data, which will convert the values to
    # integers and validate values after that.
    exercise.validate()

    # conversion tools may fail to properly convert these fields to int values,
    # so make sure an int string gets read as a string.
    assert exercise.extra_fields["m"] == 3
    assert exercise.extra_fields["n"] == 5

    # Make sure we throw an error if we have non-int strings
    exercise.extra_fields = {"mastery_model": exercises.M_OF_N, "m": "3.0", "n": "5.1"}

    with pytest.raises(InvalidNodeException):
        exercise.process_files()

    with pytest.raises(InvalidNodeException):
        exercise.validate()

    # or any other type of string...
    exercise.extra_fields = {
        "mastery_model": exercises.M_OF_N,
        "m": "three",
        "n": "five",
    }

    with pytest.raises(InvalidNodeException):
        exercise.process_files()

    with pytest.raises(InvalidNodeException):
        exercise.validate()


def test_exercise_extra_fields_float(exercise):
    exercise.extra_fields = {"mastery_model": exercises.M_OF_N, "m": 3.0, "n": 5.6}

    exercise.process_files()
    # ensure the fields end up as pure ints, using floor.
    assert exercise.extra_fields["m"] == 3
    assert exercise.extra_fields["n"] == 5

    exercise.validate()


def _exercise(source_id, exercise_data, question_count):
    return ExerciseNode(
        source_id=source_id,
        title=source_id,
        license=licenses.PUBLIC_DOMAIN,
        exercise_data=exercise_data,
        questions=[
            SingleSelectQuestion(f"q{i}", "Q", "A", ["A", "B"])
            for i in range(question_count)
        ],
    )


mastery_defaults = [
    (None, 3, (3, 3)),
    (None, 7, (5, 5)),
    ({"mastery_model": exercises.M_OF_N}, 3, (3, 3)),
    ({"mastery_model": exercises.M_OF_N, "m": 2}, 7, (2, 2)),
    ({"mastery_model": exercises.M_OF_N, "n": 4}, 7, (4, 4)),
    ({"mastery_model": exercises.NUM_CORRECT_IN_A_ROW_10, "m": 2}, 7, (10, 10)),
]


@pytest.mark.parametrize("exercise_data,question_count,expected", mastery_defaults)
def test_exercise_mastery_defaults(exercise_data, question_count, expected):
    node = _exercise("e", exercise_data, question_count)
    node.process_files()
    assert (node.extra_fields["m"], node.extra_fields["n"]) == expected


ignored_mastery_values = [
    ({"mastery_model": exercises.QUIZ}, (None, None)),
    ({"mastery_model": exercises.PRE_POST_TEST}, (None, None)),
    ({"mastery_model": exercises.QUIZ, "m": 0}, (None, None)),
    ({"mastery_model": exercises.PRE_POST_TEST, "n": ""}, (None, None)),
    ({"mastery_model": exercises.DO_ALL, "m": None}, (2, 2)),
    ({"mastery_model": exercises.DO_ALL, "m": "three"}, (2, 2)),
]


@pytest.mark.parametrize("exercise_data,expected", ignored_mastery_values)
def test_mastery_values_ignored_outside_m_of_n(channel, exercise_data, expected):
    node = _exercise("e", exercise_data, 2)
    channel.add_child(node)
    manager = ChannelManager(channel)
    with patch("ricecooker.config.STRICT", False):
        manager.validate()
        manager.process_tree()
        manager.validate()
    assert node.valid, node._error
    assert (node.extra_fields["m"], node.extra_fields["n"]) == expected


uncoercible_mastery = [
    (
        {"mastery_model": exercises.M_OF_N, "m": None, "n": 3},
        "M must be an integer coerceable value",
    ),
    (
        {"mastery_model": exercises.M_OF_N, "m": "three", "n": 3},
        "M must be an integer coerceable value",
    ),
    (
        {"mastery_model": exercises.M_OF_N, "m": 3, "n": None},
        "N must be an integer coerceable value",
    ),
    (
        {"mastery_model": exercises.M_OF_N, "m": float("inf"), "n": 3},
        "M must be an integer coerceable value",
    ),
]


@pytest.mark.parametrize("exercise_data,message", uncoercible_mastery)
def test_uncoercible_mastery_value_fails_only_its_node(channel, exercise_data, message):
    bad = _exercise("bad", exercise_data, 1)
    good = _exercise("good", {"mastery_model": exercises.M_OF_N, "m": 1, "n": 1}, 1)
    channel.add_child(bad)
    channel.add_child(good)
    manager = ChannelManager(channel)
    with patch("ricecooker.config.STRICT", False):
        manager.validate()
        manager.process_tree()
    assert message in bad._error
    assert not bad.valid
    assert good.valid


def test_shared_exercise_data_defaults_per_node(channel):
    data = {"mastery_model": exercises.M_OF_N}
    small = _exercise("small", data, 2)
    large = _exercise("large", data, 7)
    channel.add_child(small)
    channel.add_child(large)
    manager = ChannelManager(channel)
    manager.validate()
    manager.process_tree()
    assert (small.extra_fields["m"], small.extra_fields["n"]) == (2, 2)
    assert (large.extra_fields["m"], large.extra_fields["n"]) == (5, 5)


invalid_questions = [
    (
        SingleSelectQuestion("q1", "Q", "2", ["2", "2"]),
        "Single selection question should have only one correct answer",
    ),
    (InputQuestion("q2", "Q", ["abc"]), "Answer abc must be numeric"),
    (
        MultipleSelectQuestion("q3", "Q", ["A"], ["A", "B"], hints=[1]),
        "Hint in hint list is not a string",
    ),
    (QTIQuestion("q4", "<x/>", hints=5), "Hints must be a list"),
]


@pytest.mark.parametrize("question,message", invalid_questions)
def test_invalid_question_raises_with_assertion_message(question, message):
    with pytest.raises(InvalidQuestionException, match=message):
        question.validate()


################################################################################
# Perseus image asset processing and image loading tests
################################################################################


# Regex tests
################################################################################


"""
Return patterns that should match the RE for markdown file/image includes:
MARKDOWN_IMAGE_REGEX = r'!\\[([^\\]]+)?\\]\\(([^\\)]+)\\)'
"""
markdown_link_strings_and_match = [
    ("![smth](path)", ("smth", "path")),
    ("blah ![smth](path) bof", ("smth", "path")),
    (
        "![smth](http://url.org/path/file.png)",
        (
            "smth",
            "http://url.org/path/file.png",
        ),
    ),
    (
        "![smth](https://url.org/path/file.png)",
        (
            "smth",
            "https://url.org/path/file.png",
        ),
    ),
    ("![smth](//url.org/path/file.png)", ("smth", "//url.org/path/file.png")),
]

markdown_pat = re.compile(MARKDOWN_IMAGE_REGEX, flags=re.IGNORECASE)


@pytest.mark.parametrize("sample_str,expected_matches", markdown_link_strings_and_match)
def test_MARKDOWN_IMAGE_REGEX_matches(sample_str, expected_matches):
    m = markdown_pat.search(sample_str)
    assert m, "MARKDOWN_IMAGE_REGEX failed to match string " + sample_str
    assert m.groups() == expected_matches, (
        "found " + m.groups() + " expected " + expected_matches
    )


# Tests to make sure BaseQuestion.set_image works correctly
################################################################################


WEB_PREFIX = "${☣ CONTENTSTORAGE}/"

# Committed image fixtures (bytes are identical to what the tests used to fetch
# from the Wayback Machine, so the content hashes are unchanged) keep this test
# offline and deterministic.
image_texts_fixtures = [
    (
        os.path.relpath(os.path.join(TESTCONTENT_DIR, "exercises", "le-logo.svg")),
        WEB_PREFIX + "52b097901664f83e6b7c92ae1af1721b.svg",
        "52b097901664f83e6b7c92ae1af1721b",
    ),
    (
        os.path.relpath(os.path.join(TESTCONTENT_DIR, "exercises", "no-wifi.png")),
        WEB_PREFIX + "599aa896313be22dea6c0257772a464e.png",
        "599aa896313be22dea6c0257772a464e",
    ),
]


@pytest.mark.parametrize("text,replacement_str,hash", image_texts_fixtures)
def test_base_question_set_image(text, replacement_str, hash):
    """
    Create a test question and check that `set_image` method performs the right image string
    replacement logic.
    """

    # setup
    _clear_ricecookerfilecache()  # clear file cache each time to avoid test interactions

    # SIT ##################################################################
    testq = BaseQuestion(
        id="someid", question="somequestion", question_type="input", raw_data={}
    )
    new_text, images = testq.set_image(text)

    # check 1
    assert new_text == replacement_str, (
        "Unexpected replacement text produced by set_image"
    )

    # check 2
    assert len(images) == 1, "Should find exactly one image"

    # check 3
    image_file = images[0]
    filename = image_file.get_filename()
    assert hash in filename, "wrong content hash for file"
    expected_storage_dir = os.path.join(STORAGE_DIRECTORY, filename[0], filename[1])
    expected_storage_path = os.path.join(expected_storage_dir, filename)
    assert os.path.exists(expected_storage_path), (
        "Image file not saved to ricecooker storage dir"
    )


# Test PerseusQuestion process_question method
################################################################################

perseus_test_data = []
with open(
    os.path.join(
        TESTCONTENT_DIR, "exercises", "perseus_question_x43bbec76d5f14f88_en.json"
    ),
    encoding="utf-8",
) as inf:
    # ENGLISH JSON = KNOWN GOOD
    item_data_en = json.load(inf)
    datum = (
        item_data_en,
        [
            "ea2269bb5cf487f8d883144b9c06fbc7",
            "db98ca9d35b2fb97cde378a1fabddd26",
        ],
    )
    perseus_test_data.append(datum)
# Missing images in the KA BULGARIAN channel BUG
# see https://github.com/learningequality/ricecooker/issues/178
with open(
    os.path.join(
        TESTCONTENT_DIR, "exercises", "perseus_question_x43bbec76d5f14f88_bg.json"
    ),
    encoding="utf-8",
) as inf:
    item_data_bg = json.load(inf)
    datum = (
        item_data_bg,
        [
            "ea2269bb5cf487f8d883144b9c06fbc7",
            "db98ca9d35b2fb97cde378a1fabddd26",
        ],
    )
    perseus_test_data.append(datum)

# Missing images in KA channel for new widget type
# see https://github.com/learningequality/kolibri-library/issues/20
with open(
    os.path.join(TESTCONTENT_DIR, "exercises", "perseus_question_new_bar_graphs.json"),
    encoding="utf-8",
) as inf:
    item_data_bar = json.load(inf)
    datum = (
        item_data_bar,
        [
            "8a3a10c84b314d2a656ab241398e0f32",
            "d850efb4cd92e11280fb6d90e650b5d5",
            "543b70e5067e21981aa6de7e7b1d895f",
        ],
    )
    perseus_test_data.append(datum)


# False positive image match for inline link
with open(
    os.path.join(TESTCONTENT_DIR, "exercises", "perseus_question_inline_link.json"),
    encoding="utf-8",
) as inf:
    item_data_link = json.load(inf)
    datum = (
        item_data_link,
        [
            "2672f777fd35a425ed221936cf29fb48",
            "9570c5339784b65baf6873ed8cfada9d",
            "c70736eb538798719445c79f8ff647a2",
            "e489fde9967e09feec04165f3b679c3b",
        ],
    )
    perseus_test_data.append(datum)


@pytest.mark.parametrize("item,image_hashes", perseus_test_data)
@my_vcr.use_cassette
def test_perseus_process_question(item, image_hashes):
    """
    Process a persues question and check that it finds all images, and returns
    correcrt image files -- i.e not more, not less.
    """

    # setup
    expected_image_hashes = set(image_hashes)
    _clear_ricecookerfilecache()  # clear file cache each time to avoid test interactions

    # SIT
    testq = PerseusQuestion(id="x43bbec76d5f14f88_en", raw_data=item, ka_language="en")
    filenames = testq.process_question()

    # check 1
    assert len(filenames) == len(expected_image_hashes), (
        "wrong number of filenames found"
    )

    # check 2
    image_hashes = set()
    for filename in filenames:
        filehash, ext = os.path.splitext(filename)
        image_hashes.add(filehash)
    assert image_hashes == expected_image_hashes, "Unexpected image file set"


# Test exercise images
################################################################################


def test_exercise_image_file(exercise_image_file, exercise_image_filename):
    filename = exercise_image_file.get_filename()
    assert filename == exercise_image_filename, "wrong filename for _ExerciseImageFile"


def test_exercise_base64_image_file(
    exercise_base64_image_file, exercise_base64_image_filename
):
    filename = exercise_base64_image_file.get_filename()
    assert filename == exercise_base64_image_filename, (
        "wrong filename for _ExerciseBase64ImageFile"
    )


def test_exercise_base64_image_preset(exercise_base64_image_file):
    # Exercise images are attached to a question, not a node, so get_preset
    # must not rely on ThumbnailPresetMixin's node dereference.
    assert exercise_base64_image_file.get_preset() == format_presets.EXERCISE_IMAGE, (
        "wrong preset for _ExerciseBase64ImageFile"
    )


@pytest.mark.xfail(
    sys.platform == "win32",
    reason="Passes on Windows 10, but fails on Github Action Windows runner",
)
def test_exercise_graphie_filename(
    exercise_graphie_file,
    exercise_graphie_replacement_str,
    exercise_graphie_filename,
    exercise_graphie_mock_download_session,
):
    filename = exercise_graphie_file.get_filename()
    assert filename == exercise_graphie_filename, (
        "wrong filename for _ExerciseGraphieFile"
    )
    replacement_str = exercise_graphie_file.get_replacement_str()
    assert replacement_str == exercise_graphie_replacement_str, (
        "wrong replacement string for _ExerciseGraphieFile "
    )
