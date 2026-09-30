"""Tests for exercise nodes, questions, and files"""

import base64
import hashlib
import json
import os
import re
import sys
import uuid
from unittest.mock import patch

import pytest
from fake_session import fake_download_session
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
    (
        PerseusQuestion("q5", "{}", ka_language=None),
        "Perseus question must have a ka_language",
    ),
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


@pytest.mark.parametrize("field", ["question", "answer", "hint"])
def test_question_failed_image_download_fails_question(field):
    _clear_ricecookerfilecache()
    image = "![](http://h/missing.png)"
    question = SingleSelectQuestion(
        "q",
        image if field == "question" else "Q",
        "a",
        ["a", image if field == "answer" else "b"],
        hints=[image if field == "hint" else "hint"],
    )
    with fake_download_session({}):
        with pytest.raises(
            InvalidNodeException, match=re.escape("http://h/missing.png")
        ):
            question.process_question()


@pytest.mark.parametrize("scheme", ["data", "DATA"])
def test_question_failed_data_image_names_mimetype_not_payload(scheme):
    question = SingleSelectQuestion(
        "q", f"![]({scheme}:text/plain;base64,aGk=)", "a", ["a", "b"]
    )
    with pytest.raises(InvalidNodeException) as excinfo:
        question.process_question()
    assert str(excinfo.value).endswith(f"{scheme}:text/plain: invalid image")


def test_question_retried_after_failed_image_keeps_all_images(exercise_image_file):
    _clear_ricecookerfilecache()
    with open(exercise_image_file.path, "rb") as f:
        png = f.read()
    question = SingleSelectQuestion(
        "q",
        "Q ![](http://h/ok.png)",
        "a",
        ["a", "b"],
        hints=["![](http://h/flaky.png)"],
    )
    with fake_download_session({"http://h/ok.png": png}):
        with pytest.raises(InvalidNodeException):
            question.process_question()
    _clear_ricecookerfilecache()
    with fake_download_session({"http://h/ok.png": png, "http://h/flaky.png": png}):
        question.process_question()
    files = question.to_dict()["files"]
    assert {f["original_filename"] for f in files} == {"ok.png", "flaky.png"}


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
    item_data_link_envelope = json.load(inf)
    link_hashes = [
        "2672f777fd35a425ed221936cf29fb48",
        "9570c5339784b65baf6873ed8cfada9d",
        "c70736eb538798719445c79f8ff647a2",
        "e489fde9967e09feec04165f3b679c3b",
    ]
    perseus_test_data.append((item_data_link_envelope, link_hashes))
    perseus_test_data.append(
        (json.loads(item_data_link_envelope["itemData"]), link_hashes)
    )


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
    json.loads(testq.raw_data)
    assert "web+graphie://" not in testq.raw_data


def _perseus_item(content):
    return {"question": {"content": content, "images": {}, "widgets": {}}, "hints": []}


def _perseus_widget_item(widget):
    item = _perseus_item("[[☃ w 1]]")
    item["question"]["widgets"]["w 1"] = widget
    return item


@pytest.mark.parametrize(
    "item",
    [
        _perseus_item('see <a href="http://h/page.html">here</a>'),
        _perseus_widget_item(
            {
                "type": "phet-simulation",
                "options": {
                    "url": "https://phet.colorado.edu/sims/html/x/latest/x_en.html"
                },
            }
        ),
    ],
    ids=["quoted-link", "phet-simulation-url"],
)
def test_perseus_non_image_url_is_left_alone(item):
    q = PerseusQuestion("q", item, ka_language="en")
    with fake_download_session({}):
        assert q.process_question() == []
    assert json.loads(q.raw_data) == item


with open(os.path.join(TESTCONTENT_DIR, "exercises", "no-wifi.png"), "rb") as f:
    NO_WIFI_PNG = f.read()


def _perseus_radio_item(content):
    return _perseus_widget_item(
        {
            "type": "radio",
            "options": {"choices": [{"content": "[1,2]"}, {"content": '["é"]'}]},
        }
    ) | {"hints": [{"content": content}]}


def test_perseus_item_without_images_is_unchanged():
    raw = json.dumps(
        _perseus_radio_item("é"), separators=(",", ":"), ensure_ascii=False
    )
    q = PerseusQuestion("q", raw, ka_language="en")
    assert q.process_question() == []
    assert q.raw_data == raw


def test_perseus_json_like_strings_are_kept_verbatim(exercise_image_filename):
    _clear_ricecookerfilecache()
    q = PerseusQuestion(
        "q", _perseus_radio_item("![](http://h/pic.png)"), ka_language="en"
    )
    with fake_download_session({"http://h/pic.png": NO_WIFI_PNG}):
        assert q.process_question() == [exercise_image_filename]
    choices = json.loads(q.raw_data)["question"]["widgets"]["w 1"]["options"]["choices"]
    assert choices == [{"content": "[1,2]"}, {"content": '["é"]'}]


def _perseus_images_key_item(url):
    item = _perseus_item("no images here")
    item["question"]["images"] = {url: {"width": 1, "height": 1}}
    return item


@pytest.mark.parametrize(
    "item,full_path",
    [
        (_perseus_item("![](web+graphie://h/missing)"), "https://h/missing"),
        (_perseus_item("![](http://h/missing.png)"), "http://h/missing.png"),
        (_perseus_images_key_item("web+graphie://h/missing"), "https://h/missing"),
        (_perseus_images_key_item("http://h/missing.png"), "http://h/missing.png"),
    ],
)
def test_perseus_failed_image_download_fails_question(item, full_path):
    _clear_ricecookerfilecache()
    q = PerseusQuestion("q", item, ka_language="en")
    with (
        fake_download_session({}),
        pytest.raises(InvalidNodeException, match=re.escape(full_path)),
    ):
        q.process_question()


def test_perseus_failed_data_image_names_mimetype_not_payload():
    payload = base64.b64encode(b"<svg xmlns='http://www.w3.org/2000/svg'/>").decode()
    item = _perseus_item(f"![](data:image/svg+xml;base64,{payload})")
    q = PerseusQuestion("q", item, ka_language="en")
    with pytest.raises(InvalidNodeException) as excinfo:
        q.process_question()
    assert str(excinfo.value).endswith("data:image/svg+xml: invalid image")


def test_perseus_whole_string_graphie_is_downloaded_and_rewritten():
    _clear_ricecookerfilecache()
    item = _perseus_widget_item({"type": "x", "options": {"x": "web+graphie://h/g"}})
    q = PerseusQuestion("q", item, ka_language="en")
    with fake_download_session(
        {"https://h/g.svg": b"<svg/>", "https://h/g-data.json": b"{}"}
    ):
        assert len(q.process_question()) == 1
    options = json.loads(q.raw_data)["question"]["widgets"]["w 1"]["options"]
    assert options["x"] == "web+graphie:" + exercises.CONTENT_STORAGE_FORMAT.format("g")


@pytest.mark.parametrize(
    "item",
    [
        _perseus_item('$a<b$ <img alt="x" src="http://h/pic.png"> $c>d$'),
        _perseus_item('<img data-src="http://h/lazy.png" src="http://h/pic.png">'),
        _perseus_item('<IMG SRC="http://h/pic.png">'),
        _perseus_item('<img alt="a>b" src="http://h/pic.png">'),
        {
            "question": {
                "content": "![](http://h/pic.png)",
                "images": {"http://h/pic.png": {"width": 1, "height": 1}},
                "widgets": {},
            },
            "hints": [],
        },
        _perseus_widget_item(
            {
                "type": "image",
                "options": {"backgroundImage": {"url": "http://h/pic.png"}},
            }
        ),
        _perseus_widget_item(
            {"type": "measurer", "options": {"image": {"url": "http://h/pic.png"}}}
        ),
        _perseus_widget_item(
            {"type": "label-image", "options": {"imageUrl": "http://h/pic.png"}}
        ),
        _perseus_widget_item(
            {"type": "plotter", "options": {"picUrl": "http://h/pic.png"}}
        ),
        {"id": "x", "itemData": json.dumps(_perseus_item("![](http://h/pic.png)"))},
    ],
    ids=[
        "img-src",
        "img-data-src",
        "img-uppercase",
        "img-alt-gt",
        "images-key",
        "backgroundImage.url",
        "image.url",
        "imageUrl",
        "picUrl",
        "envelope",
    ],
)
def test_perseus_image_is_downloaded_and_rewritten(item, exercise_image_filename):
    def decode(raw_data):
        decoded = json.loads(raw_data)
        if "itemData" in decoded:
            decoded["itemData"] = json.loads(decoded["itemData"])
        return decoded

    _clear_ricecookerfilecache()
    stored = exercises.CONTENT_STORAGE_FORMAT.format(exercise_image_filename)
    q = PerseusQuestion("q", item, ka_language="en")
    with fake_download_session({"http://h/pic.png": NO_WIFI_PNG}):
        assert q.process_question() == [exercise_image_filename]
    assert decode(q.raw_data) == decode(
        json.dumps(item).replace("http://h/pic.png", stored)
    )
    assert exercises.CONTENT_STORAGE_PLACEHOLDER in q.raw_data


@pytest.mark.parametrize(
    "content,url",
    [
        ("![](http://h/thumbnail.png?lang=en)", "http://h/thumbnail.png?lang=en"),
        # the literal backslash-n seen in KA exports
        ("![](http://h/thumbnail.png\\n)", "http://h/thumbnail.png"),
    ],
)
def test_perseus_image_url_loses_only_encoded_newlines(
    content, url, exercise_image_filename
):
    _clear_ricecookerfilecache()
    q = PerseusQuestion("q", _perseus_item(content), ka_language="en")
    with fake_download_session({url: NO_WIFI_PNG}):
        assert q.process_question() == [exercise_image_filename]


def test_perseus_unpadded_base64_ending_in_n_is_stored_intact():
    # whole 3-byte groups need no padding; 0x27's low six bits encode "n"
    data = NO_WIFI_PNG + b"\0" * (-(len(NO_WIFI_PNG) + 1) % 3) + b"'"
    uri = "data:image/png;base64," + base64.b64encode(data).decode()
    q = PerseusQuestion("q", _perseus_item(f"![]({uri})"), ka_language="en")
    assert q.process_question() == [hashlib.md5(data).hexdigest() + ".png"]


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
