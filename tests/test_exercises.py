""" Tests for exercise nodes, questions, and files """
import json
import os
import re
import sys
import uuid

import pytest
from le_utils.constants import exercises
from le_utils.constants import licenses
from test_videos import _clear_ricecookerfilecache

from ricecooker.classes.nodes import ExerciseNode
from ricecooker.classes.nodes import InvalidNodeException
from ricecooker.classes.questions import BaseQuestion
from ricecooker.classes.questions import MARKDOWN_IMAGE_REGEX
from ricecooker.classes.questions import PerseusQuestion
from ricecooker.classes.questions import SingleSelectQuestion
from ricecooker.config import STORAGE_DIRECTORY

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
TESTCONTENT_DIR = os.path.join(TESTS_DIR, "testcontent")

WAYBACK_PREFIX = "https://web.archive.org/web/20240621071535/"
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

image_texts_fixtures = [
    (
        "{}https://learningequality.org/static/img/le-logo.svg".format(WAYBACK_PREFIX),
        WEB_PREFIX + "52b097901664f83e6b7c92ae1af1721b.svg",
        "52b097901664f83e6b7c92ae1af1721b",
    ),
    (
        "{}https://learningequality.org/static/img/no-wifi.png".format(WAYBACK_PREFIX),
        WEB_PREFIX + "599aa896313be22dea6c0257772a464e.png",
        "599aa896313be22dea6c0257772a464e",
    ),
    (  # slightly modified version of the above
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
    assert (
        new_text == replacement_str
    ), "Unexpected replacement text produced by set_image"

    # check 2
    assert len(images) == 1, "Should find exactly one image"

    # check 3
    image_file = images[0]
    filename = image_file.get_filename()
    assert hash in filename, "wrong content hash for file"
    expected_storage_dir = os.path.join(STORAGE_DIRECTORY, filename[0], filename[1])
    expected_storage_path = os.path.join(expected_storage_dir, filename)
    assert os.path.exists(
        expected_storage_path
    ), "Image file not saved to ricecooker storage dir"


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
    assert len(filenames) == len(
        expected_image_hashes
    ), "wrong number of filenames found"

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
    assert (
        filename == exercise_base64_image_filename
    ), "wrong filename for _ExerciseBase64ImageFile"


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
    assert (
        filename == exercise_graphie_filename
    ), "wrong filename for _ExerciseGraphieFile"
    replacement_str = exercise_graphie_file.get_replacement_str()
    assert (
        replacement_str == exercise_graphie_replacement_str
    ), "wrong replacement string for _ExerciseGraphieFile "
