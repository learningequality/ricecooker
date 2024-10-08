import copy
import glob
import os
import shutil
import uuid
import zipfile

import pytest
import requests
from le_utils.constants import content_kinds
from le_utils.constants import exercises
from le_utils.constants import licenses
from le_utils.constants import roles

from ricecooker.__init__ import __version__
from ricecooker.classes.files import _ExerciseBase64ImageFile
from ricecooker.classes.files import _ExerciseGraphieFile
from ricecooker.classes.files import _ExerciseImageFile
from ricecooker.classes.files import AudioFile
from ricecooker.classes.files import DocumentFile
from ricecooker.classes.files import EPubFile
from ricecooker.classes.files import HTMLZipFile
from ricecooker.classes.files import SlideImageFile
from ricecooker.classes.files import SubtitleFile
from ricecooker.classes.files import ThumbnailFile
from ricecooker.classes.files import VideoFile
from ricecooker.classes.nodes import AudioNode
from ricecooker.classes.nodes import ChannelNode
from ricecooker.classes.nodes import DocumentNode
from ricecooker.classes.nodes import ExerciseNode
from ricecooker.classes.nodes import HTML5AppNode
from ricecooker.classes.nodes import kind_activity_map
from ricecooker.classes.nodes import SlideshowNode
from ricecooker.classes.nodes import TopicNode
from ricecooker.classes.nodes import VideoNode
from ricecooker.classes.questions import InputQuestion
from ricecooker.classes.questions import SingleSelectQuestion


# GLOBAL TEST SETUP/TEARDOWN UTILS
################################################################################


def pytest_sessionfinish(session, exitstatus):
    """
    Cleanup testcontent/generated/ directory after each test run is finished.
    """
    generated_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "testcontent", "generated")
    )
    for path in glob.glob(generated_path + os.path.sep + "*"):
        os.remove(path)


TEMP_RICECOOKER_STORAGE = "./.pytest_storage"
TEMP_RICECOOKER_FILECACHE = "./.pytest_filecache"


@pytest.fixture(scope="session", autouse=True)
def global_fixture():
    if not os.path.exists(TEMP_RICECOOKER_STORAGE):
        os.mkdir(TEMP_RICECOOKER_STORAGE)
    if not os.path.exists(TEMP_RICECOOKER_FILECACHE):
        os.mkdir(TEMP_RICECOOKER_FILECACHE)
    yield  # wait until the test ended
    if os.path.exists(TEMP_RICECOOKER_STORAGE):
        try:
            shutil.rmtree(TEMP_RICECOOKER_STORAGE)
        except OSError:
            # Don't fail a test just because we failed to cleanup
            pass
    if os.path.exists(TEMP_RICECOOKER_FILECACHE):
        try:
            shutil.rmtree(TEMP_RICECOOKER_FILECACHE)
        except OSError:
            # Don't fail a test just because we failed to cleanup
            pass


# CHANNEL FIXTURES
################################################################################


@pytest.fixture
def domain_namespace():
    return "testing.learningequality.org"


@pytest.fixture
def channel_source_id():
    return "channel-id"


@pytest.fixture
def channel_domain_namespace(domain_namespace):
    return uuid.uuid5(uuid.NAMESPACE_DNS, domain_namespace)


@pytest.fixture
def channel_node_id(channel_domain_namespace, channel_source_id):
    return uuid.uuid5(channel_domain_namespace, channel_source_id)


@pytest.fixture
def channel_content_id(channel_domain_namespace, channel_node_id):
    return uuid.uuid5(channel_domain_namespace, channel_node_id.hex)


@pytest.fixture
def channel_data(
    channel_node_id, channel_content_id, domain_namespace, channel_source_id
):
    return {
        "id": channel_node_id.hex,
        "name": "Channel",
        "thumbnail": None,
        "description": "Long channel description that can be up to 400 characters.",
        "tagline": "Short channel description to show on content cards",
        "license": None,
        "source_domain": domain_namespace,
        "source_id": channel_source_id,
        "language": "en",
        "ricecooker_version": __version__,
        "files": [],
        "extra_fields": "{}",
    }


@pytest.fixture
def channel(domain_namespace, channel_source_id, channel_data):
    channel = ChannelNode(
        channel_source_id,
        domain_namespace,
        title=channel_data["name"],
        description=channel_data["description"],
        tagline=channel_data["tagline"],
        language=channel_data["language"],
    )
    return channel


@pytest.fixture
def invalid_channel(channel_source_id, domain_namespace):
    channel = ChannelNode(channel_source_id, domain_namespace, title="Invalid Channel")
    channel.source_id = None
    return channel


# ID, ARGS, AND KWARGS FIXTURE HELPERS
################################################################################


@pytest.fixture
def base_data(channel_domain_namespace, title):
    """
    The dictionary returned by this function resembles output of `to_dict` except
    for `extra_fields` which is dict when used as input kwarg but serialized as
    string when sending to Studio.
    """
    return {
        "kind": None,
        "title": title,
        "description": "Description",
        "author": "Author",
        "source_domain": channel_domain_namespace.hex,
        "files": [],
        "tags": [],
        "questions": [],
        "extra_fields": {},  # dict as input kwarg, but json.dumps-ed in to_dict
        "license": None,
        "copyright_holder": "",
        "license_description": None,
        "aggregator": "",  # New in ricecooker 0.6.20
        "provider": "",  # New in ricecooker 0.6.20
        "grade_levels": [],
        "resource_types": [],
        "learning_activities": [],
        "accessibility_labels": [],
        "categories": [],
        "learner_needs": [],
    }


def genrate_random_ids(channel_domain_namespace, channel_node_id):
    """
    Helper function to ensure all ContentNodes in test channel have unique `source_id`s.
    """
    source_id = uuid.uuid4().hex
    content_id = uuid.uuid5(channel_domain_namespace, source_id)
    node_id = uuid.uuid5(channel_node_id, content_id.hex)
    ids_dict = dict(source_id=source_id, content_id=content_id.hex, node_id=node_id.hex)
    return ids_dict


# TOPIC FIXTURES
################################################################################


def get_topic_node_args(node_data):
    """
    Returns (source_id, title) from node_data dictionary.
    """
    node_data = copy.deepcopy(node_data)
    source_id = node_data.pop("source_id")
    title = node_data.pop("title")
    node_data.pop("license")
    return source_id, title


def get_topic_node_kwargs_data(node_data):
    """
    Returns all keywords data other than source_id, title, and license.
    """
    node_data = copy.deepcopy(node_data)
    del node_data["source_id"]
    del node_data["title"]
    # the following attributes will appear in `to_dict` method, but we don't need
    # to pass them in when creating a TopicNode
    del node_data["content_id"]
    del node_data["node_id"]
    del node_data["kind"]
    del node_data["source_domain"]
    del node_data["questions"]
    del node_data["license"]
    del node_data["license_description"]
    del node_data["copyright_holder"]
    return node_data


@pytest.fixture
def title():
    return "Title"


@pytest.fixture
def topic_data(base_data, channel_domain_namespace, channel_node_id):
    topic_data = copy.deepcopy(base_data)
    ids_dict = genrate_random_ids(channel_domain_namespace, channel_node_id)
    topic_data.update(ids_dict)
    topic_data.update({"kind": content_kinds.TOPIC, "role": roles.LEARNER})
    return topic_data


@pytest.fixture
def topic(channel, title, topic_data):
    args_data = get_topic_node_args(topic_data)
    topic_kwargs = get_topic_node_kwargs_data(topic_data)
    topic = TopicNode(*args_data, **topic_kwargs)
    channel.add_child(topic)
    return topic


# CONTENT NODE FIXTURES
################################################################################


@pytest.fixture
def contentnode_base_data(base_data):
    """
    Shared data for all ContentNode fixtures.
    """
    data = copy.deepcopy(base_data)
    data.update(
        {
            "license": licenses.CC_BY,
            "copyright_holder": "Copyright Holder",
            "license_description": None,
            "role": roles.LEARNER,
            "grade_levels": [],
            "resource_types": [],
            "learning_activities": [],
            "accessibility_labels": [],
            "categories": [],
            "learner_needs": [],
        }
    )
    return data


def get_content_node_args(node_data):
    """
    Returns (source_id, title, license) from node_data dictionary.
    """
    node_data = copy.deepcopy(node_data)
    source_id = node_data.pop("source_id")
    title = node_data.pop("title")
    license = node_data.pop("license")
    return source_id, title, license


def get_content_node_kwargs(node_data):
    """
    Returns all keywords data other than source_id, title, and license.
    """
    node_data = copy.deepcopy(node_data)
    del node_data["source_id"]
    del node_data["title"]
    del node_data["license"]
    # below are vars from internal representation
    del node_data["content_id"]
    del node_data["node_id"]
    del node_data["kind"]
    del node_data["source_domain"]
    del node_data["questions"]
    node_data["extra_fields"] = {}
    return node_data


@pytest.fixture
def base_file_path():
    return "test/file/path"


@pytest.fixture
def contentnode_invalid_license(video):
    video = copy.deepcopy(video)
    video.license = None
    return video


@pytest.fixture
def contentnode_invalid_files(video):
    video = copy.deepcopy(video)
    video.files = []
    return video


@pytest.fixture
def contentnode_no_source_id(title):
    topic = TopicNode("some source id", title)
    topic.source_id = None
    return topic


# VIDEO FIXTURES
################################################################################


@pytest.fixture
def video_file():  # uses same file as test_videos.low_res_video fixture
    source_url = (
        "https://archive.org/download/vd_is_for_everybody/vd_is_for_everybody_512kb.mp4"
    )
    local_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "testcontent", "downloaded", "low_res_video.mp4"
        )
    )
    download_fixture_file(source_url, local_path)
    assert os.path.exists(local_path)
    return VideoFile(local_path)


@pytest.fixture
def video_filename():
    return "897d83a2e5389d454d37feb574587516.mp4"


@pytest.fixture
def subtitle_file():
    local_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "testcontent", "generated", "testsubtitles.vtt"
        )
    )
    if not os.path.exists(local_path):
        with open(local_path, "wb") as subtitlefile:
            subtitlefile.write(b"WEBVTT\n")
            subtitlefile.write(b"\n")
            subtitlefile.write(b"00:01.000 --> 00:04.250\n")
            subtitlefile.write(b"Testing subtitles\n")
    return SubtitleFile(local_path, language="en")


@pytest.fixture
def subtitle_filename():
    return "19faefeb0b8b8289923dc0c1c5adb7e5.vtt"


@pytest.fixture
def video_data(contentnode_base_data, channel_domain_namespace, channel_node_id):
    video_data = copy.deepcopy(contentnode_base_data)
    ids_dict = genrate_random_ids(channel_domain_namespace, channel_node_id)
    video_data.update(ids_dict)
    video_data.update(
        {
            "kind": content_kinds.VIDEO,
            "learning_activities": [kind_activity_map.get(content_kinds.VIDEO)],
        }
    )
    return video_data


@pytest.fixture
def video(video_file, video_data, channel):
    args_data = get_content_node_args(video_data)
    contentnode_kwargs = get_content_node_kwargs(video_data)
    video = VideoNode(*args_data, **contentnode_kwargs)
    video.add_file(video_file)
    channel.add_child(video)
    video_data["files"].append(video_file)  # save it so we can compare later
    return video


@pytest.fixture
def video_invalid_files(video_data, document_file):
    args_data = get_content_node_args(video_data)
    contentnode_kwargs = get_content_node_kwargs(video_data)
    contentnode_kwargs["files"] = []  # clear files becuse added one above
    video = VideoNode(*args_data, **contentnode_kwargs)
    video.add_file(document_file)
    return video


@pytest.fixture
def invalid_video_file():
    local_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "testcontent", "generated", "invalid_video.mp4"
        )
    )
    if not os.path.exists(local_path):
        with open(local_path, "wb") as f:
            f.write(b"this is an invalid video file")
    return DocumentFile(local_path)


@pytest.fixture
def youtube_video_dict():
    """
    A short 17 sec video that won't slow down tests too much.
    """
    return {"youtube_id": "C0DPdy98e4c"}


@pytest.fixture
def youtube_video_with_subs_dict():
    """
    A test video that has subtitles in several languages.
    """
    return {
        "youtube_id": "USq6DX7byoY",
        "subtitles_langs": [
            "nl",
            "en",
            "en-GB",
            "fr",
            "el",
            "hu",
            "it",
            "pt",
            "ro",
            "es",
        ],
    }


# AUDIO FIXTURES
################################################################################


@pytest.fixture
def audio_file():
    source_url = (
        "https://ia800203.us.archive.org/26/items/Bach_Original_works_and_transcriptions-6556"
        "/Felipe_Sarro_-_08_-_Bach_Sinfonia_11_BWV_797.mp3"
    )
    local_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "testcontent", "downloaded", "testaudio.mp3"
        )
    )
    download_fixture_file(source_url, local_path)
    assert os.path.exists(local_path)
    return AudioFile(local_path)


@pytest.fixture
def audio_filename():
    return "7f78f74d9428d6394fb8a2fbd095965a.mp3"


@pytest.fixture
def audio_data(
    contentnode_base_data, audio_file, channel_domain_namespace, channel_node_id
):
    audio_data = copy.deepcopy(contentnode_base_data)
    ids_dict = genrate_random_ids(channel_domain_namespace, channel_node_id)
    audio_data.update(ids_dict)
    audio_data.update(
        {
            "kind": content_kinds.AUDIO,
            "learning_activities": [kind_activity_map.get(content_kinds.AUDIO)],
        }
    )
    return audio_data


@pytest.fixture
def audio(audio_file, audio_data, channel):
    args_data = get_content_node_args(audio_data)
    contentnode_kwargs = get_content_node_kwargs(audio_data)
    audio = AudioNode(*args_data, **contentnode_kwargs)
    audio.add_file(audio_file)
    channel.add_child(audio)
    audio_data["files"].append(audio_file)  # save it so we can compare later
    return audio


@pytest.fixture
def audio_invalid_files(audio_data, document_file):
    args_data = get_content_node_args(audio_data)
    contentnode_kwargs = get_content_node_kwargs(audio_data)
    contentnode_kwargs["files"] = []  # clear files because added one above
    audio = AudioNode(*args_data, **contentnode_kwargs)
    audio.add_file(document_file)
    return audio


@pytest.fixture
def invalid_audio_file():
    local_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "testcontent", "generated", "invalid_audio.mp3"
        )
    )

    if not os.path.exists(local_path):
        with open(local_path, "wb") as f:
            f.write(b"invalid MP3")
    return DocumentFile(local_path)


# DOCUMENT FIXTURES
################################################################################


@pytest.fixture
def document_file():
    source_url = "https://archive.org/download/manualzz-id-707752/707752.pdf"
    local_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "testcontent", "downloaded", "testdocument.pdf"
        )
    )

    download_fixture_file(source_url, local_path)
    assert os.path.exists(local_path)
    return DocumentFile(local_path)


@pytest.fixture
def document_filename():
    return "480fe2b9d6b10d8f4fc0ab4a68d787a0.pdf"


@pytest.fixture
def document_data(
    contentnode_base_data, document_file, channel_domain_namespace, channel_node_id
):
    document_data = copy.deepcopy(contentnode_base_data)
    ids_dict = genrate_random_ids(channel_domain_namespace, channel_node_id)
    document_data.update(ids_dict)
    document_data.update(
        {
            "kind": content_kinds.DOCUMENT,
            "learning_activities": [kind_activity_map.get(content_kinds.DOCUMENT)],
        }
    )
    return document_data


@pytest.fixture
def document(document_file, document_data, channel):
    args_data = get_content_node_args(document_data)
    contentnode_kwargs = get_content_node_kwargs(document_data)
    document = DocumentNode(*args_data, **contentnode_kwargs)
    document.add_file(document_file)
    channel.add_child(document)
    document_data["files"].append(document_file)  # save it so we can compare later
    return document


@pytest.fixture
def document_invalid_files(document_data, audio_file):
    args_data = get_content_node_args(document_data)
    contentnode_kwargs = get_content_node_kwargs(document_data)
    contentnode_kwargs["files"] = []  # clear files becuse added one above
    document = DocumentNode(*args_data, **contentnode_kwargs)
    document.add_file(audio_file)
    return document


@pytest.fixture
def epub_file():
    path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "testcontent", "samples", "testdocument.epub"
        )
    )
    assert os.path.exists(path)
    return EPubFile(path)


@pytest.fixture
def epub_filename():
    return "5f91b55a7648206343b609cae692e08c.epub"


@pytest.fixture
def invalid_document_file():
    local_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "testcontent",
            "generated",
            "invalid_document.pdf",
        )
    )

    if not os.path.exists(local_path):
        with open(local_path, "wb") as f:
            f.write(b"invalid PDF")
    return DocumentFile(local_path)


@pytest.fixture
def invalid_epub_file():
    local_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "testcontent",
            "generated",
            "invalid_document.epub",
        )
    )

    if not os.path.exists(local_path):
        with open(local_path, "wb") as f:
            f.write(b"invalid ePub")
    return EPubFile(local_path)


# HTML FIXTURES
################################################################################


@pytest.fixture
def html_file():
    source_url = (
        "https://studio.learningequality.org/content/storage/"
        "e/d/ed494d6547b603b8ff22095cf5f5b624.zip"
    )
    local_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "testcontent", "downloaded", "testhtml.zip"
        )
    )
    download_fixture_file(source_url, local_path)
    assert os.path.exists(local_path)
    return HTMLZipFile(local_path)


@pytest.fixture
def html_filename():
    return "ed494d6547b603b8ff22095cf5f5b624.zip"


@pytest.fixture
def html_data(
    contentnode_base_data, html_file, channel_domain_namespace, channel_node_id
):
    html_data = copy.deepcopy(contentnode_base_data)
    ids_dict = genrate_random_ids(channel_domain_namespace, channel_node_id)
    html_data.update(ids_dict)
    html_data.update(
        {
            "kind": content_kinds.HTML5,
            "learning_activities": [kind_activity_map.get(content_kinds.HTML5)],
        }
    )
    return html_data


@pytest.fixture
def html(html_file, html_data, channel):
    args_data = get_content_node_args(html_data)
    contentnode_kwargs = get_content_node_kwargs(html_data)
    html = HTML5AppNode(*args_data, **contentnode_kwargs)
    html.add_file(html_file)
    channel.add_child(html)
    html_data["files"].append(html_file)  # save it so we can compare later
    return html


@pytest.fixture
def html_invalid_files(html_data, document_file):
    """
    Invalid because adding a PDF document to a HTML5AppNode.
    """
    args_data = get_content_node_args(html_data)
    contentnode_kwargs = get_content_node_kwargs(html_data)
    contentnode_kwargs["files"] = []  # clear files becuse added one above
    html = HTML5AppNode(*args_data, **contentnode_kwargs)
    html.add_file(document_file)
    return html


@pytest.fixture
def html_invalid_file():
    local_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "testcontent", "generated", "testinvalidhtml.zip"
        )
    )

    if not os.path.exists(local_path):
        with zipfile.ZipFile(local_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("notindex.html", "<div></div>")
    return HTMLZipFile(local_path)


@pytest.fixture
def html_invalid_zip(html_data, html_invalid_file):
    args_data = get_content_node_args(html_data)
    contentnode_kwargs = get_content_node_kwargs(html_data)
    contentnode_kwargs["files"] = []  # clear files because added one above
    html = HTML5AppNode(*args_data, **contentnode_kwargs)
    html.add_file(html_invalid_file)
    return html


# EXERCISE FIXTURES
################################################################################


@pytest.fixture
def exercise_question():
    return SingleSelectQuestion("question_1", "Question", "Answer", ["Answer"])


@pytest.fixture
def mastery_model():
    return {"mastery_model": exercises.M_OF_N, "randomize": True, "m": 1, "n": 1}


@pytest.fixture
def exercise_data(
    contentnode_base_data,
    mastery_model,
    exercise_question,
    channel_domain_namespace,
    channel_node_id,
):
    exercise_data = copy.deepcopy(contentnode_base_data)
    ids_dict = genrate_random_ids(channel_domain_namespace, channel_node_id)
    exercise_data.update(ids_dict)
    exercise_data.update(
        {
            "kind": content_kinds.EXERCISE,
            "questions": [],
            "exercise_data": mastery_model,
            "learning_activities": [kind_activity_map.get(content_kinds.EXERCISE)],
        }
    )
    return exercise_data


@pytest.fixture
def exercise(exercise_question, exercise_data, channel):
    args_data = get_content_node_args(exercise_data)
    contentnode_kwargs = get_content_node_kwargs(exercise_data)
    del contentnode_kwargs["extra_fields"]
    mastery_model_dict = contentnode_kwargs["exercise_data"]
    exercise = ExerciseNode(*args_data, **contentnode_kwargs)
    exercise.add_question(exercise_question)
    channel.add_child(exercise)
    exercise_data["questions"] = [exercise_question]
    exercise_data["extra_fields"] = mastery_model_dict
    del exercise_data["exercise_data"]
    return exercise


@pytest.fixture
def exercise_invalid_question(exercise):
    exercise = copy.deepcopy(exercise)
    exercise.add_question(InputQuestion("question_2", "Question 2", ["Answer"]))
    return exercise


# THUMBNAIL FILE FIXTURES
################################################################################


@pytest.fixture
def thumbnail_file():
    local_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "testcontent", "samples", "thumbnail.png"
        )
    )
    assert os.path.exists(local_path)
    return ThumbnailFile(local_path)


@pytest.fixture
def thumbnail_filename():
    return "eb79354ddd5774bb3436f9a19c282bff.png"


@pytest.fixture
def fake_thumbnail_file():
    local_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "testcontent", "generated", "invalidimage.png"
        )
    )
    if not os.path.exists(local_path):
        with open(local_path, "wb") as imgfile:
            imgfile.write(b"not_a_valid_PNG")
    return ThumbnailFile(local_path)


# EXERCISE IMAGES FIXTURES
################################################################################


@pytest.fixture
def exercise_image_file():
    path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "testcontent", "exercises", "no-wifi.png"
        )
    )
    return _ExerciseImageFile(path)


@pytest.fixture
def exercise_image_filename():
    return "599aa896313be22dea6c0257772a464e.png"


@pytest.fixture
def exercise_base64_image_file():
    with open("tests/testcontent/exercises/test_image_base64.data") as datafile:
        base64_data = datafile.read()
        return _ExerciseBase64ImageFile(base64_data)


@pytest.fixture
def exercise_base64_image_filename():
    return "cd9635def904486701e7705ef29ece67.png"


@pytest.fixture
def exercise_graphie_file():
    file_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "testcontent",
            "exercises",
            "eb3f3bf7c317408ee90995b5bcf4f3a59606aedd",
        )
    )
    return _ExerciseGraphieFile(file_path)


@pytest.fixture
def exercise_graphie_replacement_str():
    return "eb3f3bf7c317408ee90995b5bcf4f3a59606aedd"


@pytest.fixture
def exercise_graphie_filename():
    return "7060edbbf6c5548fd7a5b69989c9e58a.graphie"


# SLIDESHOW IMAGES FIXTURES
################################################################################


@pytest.fixture
def slideshow_files():
    src_file = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "testcontent",
            "samples",
            "thumbnail.jpg",
        )
    )
    fake_files = []
    for i in range(0, 10):
        filename = "tests/testcontent/generated/slide" + str(i) + ".jpg"
        if not os.path.exists(filename):
            shutil.copy(src_file, filename)
        fake_files.append(SlideImageFile(filename, caption="slide " + str(i)))
    return fake_files


@pytest.fixture
def slideshow_data(
    contentnode_base_data, slideshow_files, channel_domain_namespace, channel_node_id
):
    slideshow_data = copy.deepcopy(contentnode_base_data)
    ids_dict = genrate_random_ids(channel_domain_namespace, channel_node_id)
    slideshow_data.update(ids_dict)
    slideshow_data.update(
        {
            "kind": content_kinds.SLIDESHOW,
            "learning_activities": [kind_activity_map.get(content_kinds.SLIDESHOW)],
        }
    )
    # TODO setup expected extra_fields['slideshow_data']
    return slideshow_data


@pytest.fixture
def slideshow(slideshow_files, slideshow_data, channel):
    args_data = get_content_node_args(slideshow_data)
    contentnode_kwargs = get_content_node_kwargs(slideshow_data)
    del contentnode_kwargs["extra_fields"]
    slideshow = SlideshowNode(*args_data, **contentnode_kwargs)
    for slideshow_file in slideshow_files:
        slideshow.add_file(slideshow_file)
    channel.add_child(slideshow)
    slideshow_data["files"] = slideshow_files  # save it so we can compare later
    return slideshow


# FIXTURE DOWNLOADING UTILS
################################################################################


def download_fixture_file(source_url, local_path):
    """
    Download fixture file `source_url` to `local_path` if not present already.
    """
    if os.path.exists(local_path):
        return
    with open(local_path, "wb") as f:
        response = requests.get(source_url, stream=True)
        assert (
            response.status_code == 200
        ), "Fixture file with url: {} not found".format(source_url)
        for chunk in response.iter_content(chunk_size=1048576):
            f.write(chunk)
        f.flush()
        f.close()
