import copy
import os
import string
import uuid
import zipfile

import pytest

from le_utils.constants import licenses, content_kinds, exercises, roles
from ricecooker.classes.files import *
from ricecooker.classes.files import _ExerciseImageFile, _ExerciseBase64ImageFile, _ExerciseGraphieFile
from ricecooker.classes.nodes import ChannelNode, TopicNode, VideoNode, AudioNode, DocumentNode, HTML5AppNode, ExerciseNode, SlideshowNode
from ricecooker.classes.questions import SingleSelectQuestion, InputQuestion

from ricecooker.__init__ import __version__



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
def channel_data(channel_node_id, channel_content_id, domain_namespace, channel_source_id):
    return {
        "id": channel_node_id.hex,
        "name": "Channel",
        "thumbnail": None,
        "description": "Channel description",
        "license": None,
        "source_domain": domain_namespace,
        "source_id": channel_source_id,
        "language": "en",
        "ricecooker_version": __version__,
    }

@pytest.fixture
def channel(domain_namespace, channel_source_id, channel_data):
    channel = ChannelNode(
        channel_source_id,
        domain_namespace,
        title=channel_data['name'],
        description=channel_data['description'],
        language=channel_data['language']
    )
    return channel

@pytest.fixture
def invalid_channel(channel_source_id, domain_namespace):
    channel = ChannelNode(
        channel_source_id,
        domain_namespace,
        title='Invalid Channel'
    )
    channel.source_id = None
    return channel




# ID, ARGS, AND KWARGS FIXTURE HELPERS
################################################################################

@pytest.fixture
def base_data(channel_domain_namespace, title):
    """
    The dictionary returned by this function resembles outpout of `to_dict` method.
    """
    return {
        "kind": None,
        "title": title,
        "description": "Description",
        "author": "Author",
        "source_domain": channel_domain_namespace.hex,
        "files" : [],
        "tags": [],
        "questions": [],
        "extra_fields": "{}",  # because Ricecookr uses `json.dumps` for this field
        "license": None,
        "copyright_holder": "",
        "license_description": None,
        "aggregator": "",           # New in ricecooker 0.6.20
        "provider": "",             # New in ricecooker 0.6.20
    }


def genrate_random_ids(channel_domain_namespace, channel_node_id):
    """
    Helper function to ensure all ContentNodes in test channel have unique `source_id`s.
    """
    source_id = uuid.uuid4().hex
    content_id = uuid.uuid5(channel_domain_namespace, source_id)
    node_id = uuid.uuid5(channel_node_id, content_id.hex)
    ids_dict = dict(
        source_id=source_id,
        content_id=content_id.hex,
        node_id=node_id.hex,
    )
    return ids_dict




# TOPIC FIXTURES
################################################################################

def get_topic_node_args(node_data):
    """
    Returns (source_id, title) from node_data dictionary.
    """
    node_data = copy.deepcopy(node_data)
    source_id = node_data.pop('source_id')
    title = node_data.pop('title')
    license = node_data.pop('license')
    return source_id, title

def get_topic_node_kwargs_data(node_data):
    """
    Returns all keywords data other than source_id, title, and license.
    """
    node_data = copy.deepcopy(node_data)
    del node_data['source_id']
    del node_data['title']
    # the following attributes will appear in `to_dict` method, but we don't need
    # to pass them in when creating a TopicNode
    del node_data['content_id']
    del node_data['node_id']
    del node_data['kind']
    del node_data['source_domain']
    del node_data['questions']
    del node_data['license']
    del node_data['license_description']
    del node_data['copyright_holder']
    return node_data


@pytest.fixture
def title():
    return "Title"


@pytest.fixture
def topic_data(base_data, channel_domain_namespace, channel_node_id):
    topic_data = copy.deepcopy(base_data)
    ids_dict = genrate_random_ids(channel_domain_namespace, channel_node_id)
    topic_data.update(ids_dict)
    topic_data.update({ "kind": content_kinds.TOPIC,
                        "extra_fields": {} })
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
    data.update({ "license": licenses.CC_BY,
                  "copyright_holder": "Copyright Holder",
                  "license_description": None,
                  "role": roles.LEARNER})
    return data


def get_content_node_args(node_data):
    """
    Returns (source_id, title, license) from node_data dictionary.
    """
    node_data = copy.deepcopy(node_data)
    source_id = node_data.pop('source_id')
    title = node_data.pop('title')
    license = node_data.pop('license')
    return source_id, title, license


def get_content_node_kwargs(node_data):
    """
    Returns all keywords data other than source_id, title, and license.
    """
    node_data = copy.deepcopy(node_data)
    del node_data['source_id']
    del node_data['title']
    del node_data['license']
    # below are vars from internal representation
    del node_data['content_id']
    del node_data['node_id']
    del node_data['kind']
    del node_data['source_domain']
    del node_data['questions']
    node_data['extra_fields'] = {}
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
    topic = TopicNode('some source id', title)
    topic.source_id = None
    return topic





# VIDEO FIXTURES
################################################################################

@pytest.fixture
def video_file(base_file_path):
    return VideoFile(base_file_path)

@pytest.fixture
def video_data(contentnode_base_data, channel_domain_namespace, channel_node_id):
    video_data = copy.deepcopy(contentnode_base_data)
    ids_dict = genrate_random_ids(channel_domain_namespace, channel_node_id)
    video_data.update(ids_dict)
    video_data.update({ "kind": content_kinds.VIDEO })
    return video_data

@pytest.fixture
def video(video_file, video_data, channel):
    args_data = get_content_node_args(video_data)
    contentnode_kwargs = get_content_node_kwargs(video_data)
    video = VideoNode(*args_data, **contentnode_kwargs)
    video.add_file(video_file)
    channel.add_child(video)
    video_data['files'].append(video_file)  # save it so we can compare later
    return video

@pytest.fixture
def video_invalid_files(video_data, document_file):
    args_data = get_content_node_args(video_data)
    contentnode_kwargs = get_content_node_kwargs(video_data)
    contentnode_kwargs['files'] = []  # clear files becuse added one above
    video = VideoNode(*args_data, **contentnode_kwargs)
    video.add_file(document_file)
    return video



# AUDIO FIXTURES
################################################################################

@pytest.fixture
def audio_file(base_file_path):
    return AudioFile(base_file_path)

@pytest.fixture
def audio_data(contentnode_base_data, audio_file, channel_domain_namespace, channel_node_id):
    audio_data = copy.deepcopy(contentnode_base_data)
    ids_dict = genrate_random_ids(channel_domain_namespace, channel_node_id)
    audio_data.update(ids_dict)
    audio_data.update({ "kind": content_kinds.AUDIO })
    return audio_data

@pytest.fixture
def audio(audio_file, audio_data, channel):
    args_data = get_content_node_args(audio_data)
    contentnode_kwargs = get_content_node_kwargs(audio_data)
    audio = AudioNode(*args_data, **contentnode_kwargs)
    audio.add_file(audio_file)
    channel.add_child(audio)
    audio_data['files'].append(audio_file)  # save it so we can compare later
    return audio

@pytest.fixture
def audio_invalid_files(audio_data, document_file):
    args_data = get_content_node_args(audio_data)
    contentnode_kwargs = get_content_node_kwargs(audio_data)
    contentnode_kwargs['files'] = []  # clear files becuse added one above
    audio = AudioNode(*args_data, **contentnode_kwargs)
    audio.add_file(document_file)
    return audio


# DOCUMENT FIXTURES
################################################################################

@pytest.fixture
def document_file(base_file_path):
    return DocumentFile(base_file_path)

@pytest.fixture
def document_data(contentnode_base_data, document_file, channel_domain_namespace, channel_node_id):
    document_data = copy.deepcopy(contentnode_base_data)
    ids_dict = genrate_random_ids(channel_domain_namespace, channel_node_id)
    document_data.update(ids_dict)
    document_data.update({ "kind": content_kinds.DOCUMENT })
    return document_data

@pytest.fixture
def document(document_file, document_data, channel):
    args_data = get_content_node_args(document_data)
    contentnode_kwargs = get_content_node_kwargs(document_data)
    document = DocumentNode(*args_data, **contentnode_kwargs)
    document.add_file(document_file)
    channel.add_child(document)
    document_data['files'].append(document_file)  # save it so we can compare later
    return document

@pytest.fixture
def document_invalid_files(document_data, audio_file):
    args_data = get_content_node_args(document_data)
    contentnode_kwargs = get_content_node_kwargs(document_data)
    contentnode_kwargs['files'] = []  # clear files becuse added one above
    document = DocumentNode(*args_data, **contentnode_kwargs)
    document.add_file(audio_file)
    return document


# HTML FIXTURES
################################################################################

@pytest.fixture
def html_file():
    if not os.path.exists("tests/testcontent/testhtml.zip"):
        with zipfile.ZipFile("tests/testcontent/testhtml.zip", 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('index.html', '<div></div>')
    return HTMLZipFile("tests/testcontent/testhtml.zip")

@pytest.fixture
def html_data(contentnode_base_data, html_file, channel_domain_namespace, channel_node_id):
    html_data = copy.deepcopy(contentnode_base_data)
    ids_dict = genrate_random_ids(channel_domain_namespace, channel_node_id)
    html_data.update(ids_dict)
    html_data.update({ "kind": content_kinds.HTML5 })
    return html_data

@pytest.fixture
def html(html_file, html_data, channel):
    args_data = get_content_node_args(html_data)
    contentnode_kwargs = get_content_node_kwargs(html_data)
    html = HTML5AppNode(*args_data, **contentnode_kwargs)
    html.add_file(html_file)
    channel.add_child(html)
    html_data['files'].append(html_file)  # save it so we can compare later
    return html


@pytest.fixture
def html_invalid_files(html_data, document_file):
    args_data = get_content_node_args(html_data)
    contentnode_kwargs = get_content_node_kwargs(html_data)
    contentnode_kwargs['files'] = []  # clear files becuse added one above
    html = HTML5AppNode(*args_data, **contentnode_kwargs)
    html.add_file(document_file)
    return html


@pytest.fixture
def html_invalid_file():
    if not os.path.exists("tests/testcontent/testinvalidhtml.zip"):
        with zipfile.ZipFile("tests/testcontent/testinvalidhtml.zip", 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("notindex.html", '<div></div>')
    return HTMLZipFile("tests/testcontent/testinvalidhtml.zip")

@pytest.fixture
def html_invalid_zip(html_data, html_invalid_file):
    args_data = get_content_node_args(html_data)
    contentnode_kwargs = get_content_node_kwargs(html_data)
    contentnode_kwargs['files'] = []  # clear files becuse added one above
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
    return {'mastery_model': exercises.M_OF_N, 'randomize': True, 'm': 1, 'n': 1}

@pytest.fixture
def exercise_data(contentnode_base_data, mastery_model, exercise_question, channel_domain_namespace, channel_node_id):
    exercise_data = copy.deepcopy(contentnode_base_data)
    ids_dict = genrate_random_ids(channel_domain_namespace, channel_node_id)
    exercise_data.update(ids_dict)
    exercise_data.update({ "kind": content_kinds.EXERCISE,
                           "questions":[],
                           "exercise_data": mastery_model})
    return exercise_data

@pytest.fixture
def exercise(exercise_question, exercise_data, channel):
    args_data = get_content_node_args(exercise_data)
    contentnode_kwargs = get_content_node_kwargs(exercise_data)
    del contentnode_kwargs['extra_fields']
    mastery_model_dict = contentnode_kwargs['exercise_data']
    exercise = ExerciseNode(*args_data, **contentnode_kwargs)
    exercise.add_question(exercise_question)
    channel.add_child(exercise)
    exercise_data['questions'] = [exercise_question]
    exercise_data['extra_fields'] = mastery_model_dict
    del exercise_data['exercise_data']
    return exercise

@pytest.fixture
def exercise_invalid_question(exercise):
    exercise = copy.deepcopy(exercise)
    exercise.add_question(InputQuestion("question_2", "Question 2", ["Answer"]))
    return exercise


# FILE FIXTURES
################################################################################
@pytest.fixture
def document_file():
    if not os.path.exists("tests/testcontent/testdocument.pdf"):
        with open("tests/testcontent/testdocument.pdf", 'wb') as docfile:
            docfile.write(b'testing')
    return DocumentFile("tests/testcontent/testdocument.pdf")

@pytest.fixture
def document_filename():
    return 'ae2b1fca515949e5d54fb22b8ed95575.pdf'

@pytest.fixture
def audio_file():
    if not os.path.exists("tests/testcontent/testaudio.mp3"):
        with open("tests/testcontent/testaudio.mp3", 'wb') as audiofile:
            audiofile.write(b'testing')
    return AudioFile("tests/testcontent/testaudio.mp3")

@pytest.fixture
def audio_filename():
    return 'ae2b1fca515949e5d54fb22b8ed95575.mp3'

@pytest.fixture
def video_file():
    if not os.path.exists("tests/testcontent/testvideo.mp4"):
        with open("tests/testcontent/testvideo.mp4", 'wb') as videofile:
            videofile.write(b'testing')
    return VideoFile("tests/testcontent/testvideo.mp4")

@pytest.fixture
def video_filename():
    return 'ae2b1fca515949e5d54fb22b8ed95575.mp4'

@pytest.fixture
def thumbnail_file():
    if not os.path.exists("tests/testcontent/testimage.png"):
        with open("tests/testcontent/testimage.png", 'wb') as imgfile:
            imgfile.write(b'testing')
    return ThumbnailFile("tests/testcontent/testimage.png")

@pytest.fixture
def thumbnail_filename():
    return 'ae2b1fca515949e5d54fb22b8ed95575.png'

@pytest.fixture
def subtitle_file():
    if not os.path.exists("tests/testcontent/testsubtitles.vtt"):
        with open("tests/testcontent/testsubtitles.vtt", 'wb') as subtitlefile:
            subtitlefile.write(b'WEBVTT\n')
            subtitlefile.write(b'\n')
            subtitlefile.write(b'00:01.000 --> 00:04.250\n')
            subtitlefile.write(b'Testing subtitles\n')
    return SubtitleFile("tests/testcontent/testsubtitles.vtt", language='en')

@pytest.fixture
def subtitle_filename():
    return '19faefeb0b8b8289923dc0c1c5adb7e5.vtt'

@pytest.fixture
def html_file():
    if not os.path.exists("tests/testcontent/testhtml.zip"):
        with zipfile.ZipFile("tests/testcontent/testhtml.zip", 'w', zipfile.ZIP_DEFLATED) as archive:
            info = zipfile.ZipInfo('index.html', date_time=(2013, 3, 14, 1, 59, 26))
            info.comment = "test file".encode()
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 0
            archive.writestr(info, '<div></div>')
    return HTMLZipFile("tests/testcontent/testhtml.zip")

@pytest.fixture
def html_filename():
    return '3ce367dc18043e18429432677e19e7c2.zip'



# EXERCISE IMAGES FIXTURES
################################################################################

@pytest.fixture
def exercise_image_file():
    return _ExerciseImageFile('tests/testcontent/no-wifi.png')

@pytest.fixture
def exercise_image_filename():
    return '599aa896313be22dea6c0257772a464e.png'


@pytest.fixture
def exercise_base64_image_file():
    with open('tests/testcontent/test_image_base64.data') as datafile:
        base64_data = datafile.read()
        return _ExerciseBase64ImageFile(base64_data)

@pytest.fixture
def exercise_base64_image_filename():
    return 'cd9635def904486701e7705ef29ece67.png'


@pytest.fixture
def exercise_graphie_file():
    return _ExerciseGraphieFile('tests/testcontent/eb3f3bf7c317408ee90995b5bcf4f3a59606aedd')

@pytest.fixture
def exercise_graphie_replacement_str():
    return 'eb3f3bf7c317408ee90995b5bcf4f3a59606aedd'

@pytest.fixture
def exercise_graphie_filename():
    return 'ea2269bb5cf487f8d883144b9c06fbc7.graphie'




# SLIDESHOW IMAGES FIXTURES
################################################################################

@pytest.fixture
def slideshow_files():
    fake_files = []
    for i in range(0,10):
        filename = 'tests/testcontent/slide' + str(i) + '.jpg'
        if not os.path.exists(filename):
            with open(filename, 'w') as f:
                f.write('jpgdatawouldgohere' + str(i))
        fake_files.append(
            SlideImageFile(filename, caption='slide ' + str(i))
        )
    return fake_files

@pytest.fixture
def slideshow_data(contentnode_base_data, slideshow_files, channel_domain_namespace, channel_node_id):
    slideshow_data = copy.deepcopy(contentnode_base_data)
    ids_dict = genrate_random_ids(channel_domain_namespace, channel_node_id)
    slideshow_data.update(ids_dict)
    slideshow_data.update({ "kind": content_kinds.SLIDESHOW })
    # TODO setup expected extra_fields['slideshow_data']
    return slideshow_data

@pytest.fixture
def slideshow(slideshow_files, slideshow_data, channel):
    args_data = get_content_node_args(slideshow_data)
    contentnode_kwargs = get_content_node_kwargs(slideshow_data)
    del contentnode_kwargs['extra_fields']
    slideshow = SlideshowNode(*args_data, **contentnode_kwargs)
    for slideshow_file in slideshow_files:
        slideshow.add_file(slideshow_file)
    channel.add_child(slideshow)
    slideshow_data['files'] = slideshow_files   # save it so we can compare later
    return slideshow

