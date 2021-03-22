""" Tests for exercise nodes, questions, and files """
import os
import pytest
import re
import uuid
import tempfile
from le_utils.constants import licenses, content_kinds, exercises
from ricecooker.classes.nodes import *
from ricecooker.classes.questions import BaseQuestion, PerseusQuestion, SingleSelectQuestion
from ricecooker.config import STORAGE_DIRECTORY
from test_videos import _clear_ricecookerfilecache

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
TESTCONTENT_DIR = os.path.join(TESTS_DIR, 'testcontent')


""" *********** EXERCISE FIXTURES *********** """
@pytest.fixture
def exercise_id():
    return "exercise-id"

@pytest.fixture
def channel_internal_domain():
    return "learningequality.org".encode('utf-8')

@pytest.fixture
def topic_node_id():
    return 'some-node-id'

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
        "id" : exercise_id,
        "author": None,
        "license": licenses.PUBLIC_DOMAIN,
    }

@pytest.fixture
def exercise_questions():
    return [
            SingleSelectQuestion(
                id='123',
                question='What is your quest?',
                correct_answer='To spectacularly fail',
                all_answers=[
                    'To seek the grail',
                    'To eat some hail',
                    'To spectacularly fail',
                    'To post bail'
                ]
            )
        ]

@pytest.fixture
def exercise(exercise_data, channel_internal_domain, topic_node_id, exercise_questions):
    node = ExerciseNode(
        source_id=exercise_data['id'],
        # description=exercise_data['description'],
        title=exercise_data['title'],
        author=exercise_data['author'],
        license=exercise_data['license'],
        questions=exercise_questions
    )
    # node.set_ids(channel_internal_domain, topic_node_id)
    return node

@pytest.fixture
def exercise_json(exercise_data, exercise_content_id, exercise_node_id):
    return {
        "id" : exercise_data['id'],
        "title": exercise_data['title'],
        "description": "",
        "node_id": exercise_node_id.hex,
        "content_id": exercise_content_id.hex,
        "author": "",
        "children": [],
        "files": [],
        "kind": exercises.PERSEUS_QUESTION,
        "license": exercise_data['license'],
    }


""" *********** EXERCISE TESTS *********** """
def test_exercise_created(exercise):
    assert exercise is not None

def test_exercise_validate(exercise, exercise_data):
    assert exercise.source_id == exercise_data['id']
    assert exercise.title == exercise_data['title']
    # assert exercise.description == exercise_data['description']
    # assert exercise.author == exercise_data['author']
    # assert exercise.license == exercise_data['license']
    # assert exercise.kind == exercises.PERSEUS_QUESTION

def test_exercise_extra_fields_string(exercise):
    exercise.extra_fields = {
        'mastery_model': exercises.M_OF_N,
        'm': '3',
        'n': '5'
    }

    # validate should call process_exercise_data, which will convert the values to
    # integers and validate values after that.
    exercise.validate()

    # conversion tools may fail to properly convert these fields to int values,
    # so make sure an int string gets read as a string.
    assert exercise.extra_fields['m'] == 3
    assert exercise.extra_fields['n'] == 5

    # Make sure we throw an error if we have non-int strings
    exercise.extra_fields = {
        'mastery_model': exercises.M_OF_N,
        'm': '3.0',
        'n': '5.1'
    }

    with pytest.raises(ValueError):
        exercise.process_files()

    with pytest.raises(InvalidNodeException):
        exercise.validate()

    # or any other type of string...
    exercise.extra_fields = {
        'mastery_model': exercises.M_OF_N,
        'm': 'three',
        'n': 'five'
    }

    with pytest.raises(ValueError):
        exercise.process_files()

    with pytest.raises(InvalidNodeException):
        exercise.validate()

def test_exercise_extra_fields_float(exercise):
    exercise.extra_fields = {
        'mastery_model': exercises.M_OF_N,
        'm': 3.0,
        'n': 5.6
    }

    exercise.process_files()
    # ensure the fields end up as pure ints, using floor.
    assert exercise.extra_fields['m'] == 3
    assert exercise.extra_fields['n'] == 5

    exercise.validate()

#
# def test_exercise_to_dict(exercise):
#     assert exercise.default_preset == exercises.PERSEUS_QUESTION
#
# def test_exercise_add_question(exercise):
#     assert exercise.default_preset == exercises.PERSEUS_QUESTION
#
# def test_exercise_process_file(exercise):
#     assert exercise.default_preset == exercises.PERSEUS_QUESTION
#
# def test_exercise_process_exercise_data(exercise):
#     assert exercise.default_preset == exercises.PERSEUS_QUESTION


""" *********** BASE64FILE TESTS *********** """
def test_base64_process_file():
    assert True

def test_base64_validate():
    assert True

def test_base64_to_dict():
    assert True

def test_base64_convert_base64_to_file():
    assert True


""" *********** EXERCISEBASE64FILE TESTS *********** """
def test_exercisebase64_process_file():
    assert True

def test_exercisebase64_validate():
    assert True

def test_exercisebase64_to_dict():
    assert True

def test_exercisebase64_get_replacement_str():
    assert True


""" *********** EXERCISEIMAGEFILE TESTS *********** """
def test_exerciseimage_process_file():
    assert True

def test_exerciseimage_validate():
    assert True

def test_exerciseimage_to_dict():
    assert True

def test_exerciseimage_get_replacement_str():
    assert True


""" *********** EXERCISEGRAPHIEFILE TESTS *********** """
def test_exercisegraphie_process_file():
    assert True

def test_exercisegraphie_validate():
    assert True

def test_exercisegraphie_to_dict():
    assert True

def test_exercisegraphie_get_replacement_str():
    assert True

def test_exercisegraphie_generate_graphie_file():
    assert True


""" *********** QUESTION TESTS *********** """
def test_question_to_dict():
    assert True

def test_question_create_answer():
    assert True

def test_question_process_question():
    assert True

def test_question_set_images():
    assert True

def test_question_parse_html():
    assert True

def test_question_set_image():
    assert True

def test_question_validate():
    assert True


""" *********** PERSEUSQUESTION TESTS *********** """
def test_perseusquestion_to_dict():
    assert True

def test_perseusquestion_validate():
    assert True

def test_perseusquestion_process_question():
    assert True

def test_perseusquestion_process_image_field():
    assert True


""" *********** MULTIPLESELECTQUESTION TESTS *********** """
def test_multipleselectquestion_to_dict():
    assert True

def test_multipleselectquestion_validate():
    assert True


""" *********** SINGLESELECTQUESTION TESTS *********** """
def test_singleselectquestion_to_dict():
    assert True

def test_singleselectquestion_validate():
    assert True


""" *********** INPUTQUESTION TESTS *********** """
def test_inputquestion_to_dict():
    assert True

def test_inputquestion_validate():
    assert True




################################################################################
# Perseus image asset processing and image loading tests
################################################################################


# Regex tests
################################################################################

@pytest.fixture
def graphie_strings_and_rawpath():
    """
    Return patterns that should match the
    WEB_GRAPHIE_URL_REGEX = r'web\+graphie:(?P<rawpath>[^\)]+)'
    """
    test_data = {
        '![](web+graphie:somechunk)': 'somechunk',
        'alksjalksj ![](web+graphie:somechunk)': 'somechunk',
        '![](web+graphie:http://yahoo.com/path/url.png)': 'http://yahoo.com/path/url.png',
        '![graph](web+graphie://ka.s3.aws.com/fefe)': '//ka.s3.aws.com/fefe',
    }
    return test_data

def test_WEB_GRAPHIE_URL_REGEX_matches(graphie_strings_and_rawpath):
    from ricecooker.classes.questions import WEB_GRAPHIE_URL_REGEX
    pat = re.compile(WEB_GRAPHIE_URL_REGEX,  flags=re.IGNORECASE)
    for sample_str, expected_rawpath in graphie_strings_and_rawpath.items():
        m = pat.search(sample_str)
        rawpath = m.groupdict()['rawpath']
        assert m, 'WEB_GRAPHIE_URL_REGEX failed to match string ' + sample_str
        assert rawpath == expected_rawpath, 'found ' + rawpath + ' expected ' + expected_rawpath


@pytest.fixture
def markdown_link_strings_and_match():
    """
    Return patterns that should match the RE for markdown file/image includes:
    MARKDOWN_IMAGE_REGEX = r'!\[([^\]]+)?\]\(([^\)]+)\)'
    """
    test_data = {
        '![smth](path)': ('smth', 'path'),
        'blah ![smth](path) bof': ('smth', 'path'),
        '![smth](http://url.org/path/file.png)': ('smth', 'http://url.org/path/file.png'),
        '![smth](https://url.org/path/file.png)': ('smth', 'https://url.org/path/file.png'),
        '![smth](//url.org/path/file.png)': ('smth', '//url.org/path/file.png'),
        '![smth](web+graphie://ka.s3.aws.com/fefe)': ('smth', 'web+graphie://ka.s3.aws.com/fefe'),
    }
    return test_data

def test_MARKDOWN_IMAGE_REGEX_matches(markdown_link_strings_and_match):
    from ricecooker.classes.questions import MARKDOWN_IMAGE_REGEX
    pat = re.compile(MARKDOWN_IMAGE_REGEX,  flags=re.IGNORECASE)
    for sample_str, expected_matches in markdown_link_strings_and_match.items():
        m = pat.search(sample_str)
        assert m, 'MARKDOWN_IMAGE_REGEX failed to match string ' + sample_str
        assert m.groups() == expected_matches, 'found ' + m.groups() + ' expected ' + expected_matches






## Tests to make sure BaseQuestion.set_image works correctly
################################################################################

@pytest.fixture
def image_texts_fixtures():
    """
    Return texts and corresponding content hashes for various types of image resources.
    """
    WEB_GRAPHIE_PREFIX = 'web+graphie:${☣ CONTENTSTORAGE}/'
    WEB_PREFIX = '${☣ CONTENTSTORAGE}/'

    test_data = [
        {
            'text': 'web+graphie://ka-perseus-graphie.s3.amazonaws.com/eb3f3bf7c317408ee90995b5bcf4f3a59606aedd',
            'replacement_str': WEB_GRAPHIE_PREFIX + 'eb3f3bf7c317408ee90995b5bcf4f3a59606aedd',
            'hash': 'ea2269bb5cf487f8d883144b9c06fbc7'
        },
        {
            'text': 'web+graphie://ka-perseus-graphie.s3.amazonaws.com/d8daa074ec7d09ce3819d6259b3e4670701d2540',
            'replacement_str': WEB_GRAPHIE_PREFIX + 'd8daa074ec7d09ce3819d6259b3e4670701d2540',
            'hash': 'db98ca9d35b2fb97cde378a1fabddd26'
        },
        {
            'text': 'https://learningequality.org/static/img/le-logo.svg',
            'replacement_str': WEB_PREFIX + '52b097901664f83e6b7c92ae1af1721b.svg',
            'hash': '52b097901664f83e6b7c92ae1af1721b',
         },
         {
            'text': 'https://learningequality.org/static/img/no-wifi.png',
            'replacement_str': WEB_PREFIX + '599aa896313be22dea6c0257772a464e.png',
            'hash': '599aa896313be22dea6c0257772a464e'
         },
         {  # slightly modified version of the above
            'text': os.path.relpath(os.path.join(TESTCONTENT_DIR, 'exercises', 'no-wifi.png')),
            'replacement_str': WEB_PREFIX + '599aa896313be22dea6c0257772a464e.png',
            'hash': '599aa896313be22dea6c0257772a464e'
         },
    ]
    return test_data


def test_base_question_set_image(image_texts_fixtures):
    """
    Create a test question and check that `set_image` method performs the right image string
    replacement logic.
    """

    for datum in image_texts_fixtures:
        # setup
        _clear_ricecookerfilecache()  # clear file cache each time to avoid test interactions
        text = datum['text']
        replacement_str = datum['replacement_str']


        # SIT ##################################################################
        testq = BaseQuestion(id='someid', question='somequestion', question_type='input', raw_data={})
        new_text, images = testq.set_image(text)

        # check 1
        assert new_text == replacement_str, 'Unexpected replacement text produced by set_image'

        # check 2
        assert len(images) == 1, 'Should find exactly one image'

        # check 3
        image_file = images[0]
        filename = image_file.get_filename()
        assert datum['hash'] in filename, 'wront content hash for file'
        # print('filename=', filename)
        if text.startswith('web+graphie:'):
            assert new_text.startswith('web+graphie:'), 'web+graphie: was lost'
            assert filename.endswith('.graphie'), 'wrong extension for web+graphie text'
        expected_storage_dir = os.path.join(STORAGE_DIRECTORY, filename[0], filename[1])
        expected_storage_path = os.path.join(expected_storage_dir, filename)
        assert os.path.exists(expected_storage_path), 'Image file not saved to ricecooker storage dir'


# Test _recursive_url_find method
################################################################################

def test_perseus__recursive_url_find(persues_question_json_fixtures):
    """
    Run _recursive_url_find to check it correctly recognizes and rewrites `url` fields.
    """
    # fixtures
    sample_data_with_backgroundImage_url =  {
        "question": {
            "content": "[[☃ interactive-graph 1]]\n\n",
            "images": {},
            "widgets": {
                "interactive-graph 1": {
                    "type": "interactive-graph",
                    "alignment": "default",
                    "static": False,
                    "graded": True,
                    "options": {
                        "step": [1,1],
                        "backgroundImage": {
                            "url": "https://learningequality.org/static/img/no-wifi.png",
                            "width": 184,
                            "height": 184
                        },
                        "markings": "graph",
                        "labels": ["x","y"],
                    }
                }
            }
        }
    }
    hash = '599aa896313be22dea6c0257772a464e'


    # setup
    image_files = []
    test_data = sample_data_with_backgroundImage_url

    # SIT
    testq = PerseusQuestion(id='someid', raw_data={})
    testq._recursive_url_find(test_data, image_files)

    # checks
    new_url = test_data['question']['widgets']['interactive-graph 1']['options']['backgroundImage']['url']
    assert '☣ CONTENTSTORAGE' in new_url, 'url replacement not done'
    assert hash in new_url, 'wrong url replacement'
    assert len(image_files) == 1
    image_file = image_files[0]
    filename = image_file.get_filename()
    assert filename is not None, 'missing file'
    assert hash in filename, 'wrong file hash'




# Test PerseusQuestion process_image_field method
################################################################################

@pytest.fixture
def persues_contentimages_field_fixtures():
    """
    Returns a list of data needed to test the `process_image_field` method:
      - `field`: input sample data
      - `new_content`: what the content field should get rewritten to
      - `image_hashes`: content hash of image files that should get downloaded
    """
    test_data = [
      # Known good test cases from KA English exercise
      {
         'field': { 'content': 'a ![graph](web+graphie://ka-perseus-graphie.s3.amazonaws.com/eb3f3bf7c317408ee90995b5bcf4f3a59606aedd)\nb',
                    'images': { 'web+graphie://ka-perseus-graphie.s3.amazonaws.com/eb3f3bf7c317408ee90995b5bcf4f3a59606aedd': {'width': 425, 'height': 425}},
                  },
          'new_content': 'a ![graph](web+graphie:${☣ CONTENTSTORAGE}/eb3f3bf7c317408ee90995b5bcf4f3a59606aedd)\nb',
          'image_hashes': ['ea2269bb5cf487f8d883144b9c06fbc7'],
      },
      {
          'field': {'content': 'The function $f$\n![graph](web+graphie://ka-perseus-graphie.s3.amazonaws.com/d8daa074ec7d09ce3819d6259b3e4670701d2540)',
                    'images': {'web+graphie://ka-perseus-graphie.s3.amazonaws.com/d8daa074ec7d09ce3819d6259b3e4670701d2540': {'width': 425, 'height': 425}},
                    'widgets': {}
                   },
          'new_content': 'The function $f$\n![graph](web+graphie:${☣ CONTENTSTORAGE}/d8daa074ec7d09ce3819d6259b3e4670701d2540)',
          'image_hashes': ['db98ca9d35b2fb97cde378a1fabddd26'],
      },
      #
      # Same as above two but with missing images
      {
         'field': { 'content': 'a ![graph](web+graphie://ka-perseus-graphie.s3.amazonaws.com/eb3f3bf7c317408ee90995b5bcf4f3a59606aedd)\nb',
                    'images': {},
                  },
          'new_content': 'a ![graph](web+graphie:${☣ CONTENTSTORAGE}/eb3f3bf7c317408ee90995b5bcf4f3a59606aedd)\nb',
          'image_hashes': ['ea2269bb5cf487f8d883144b9c06fbc7'],
      },
      {
          'field': {'content': 'The function $f$\n![graph](web+graphie://ka-perseus-graphie.s3.amazonaws.com/d8daa074ec7d09ce3819d6259b3e4670701d2540)',
                    'images': {},
                    'widgets': {}
                   },
          'new_content': 'The function $f$\n![graph](web+graphie:${☣ CONTENTSTORAGE}/d8daa074ec7d09ce3819d6259b3e4670701d2540)',
          'image_hashes': ['db98ca9d35b2fb97cde378a1fabddd26'],
      },
    ]
    return test_data


def test_persues_question_process_image_field(persues_contentimages_field_fixtures):
    """
    Create a PerseusQuestion test object and check that `process_image_field` method works
    correctly for differnet snippets of the form:
        data = {
            "content": "Some string possibly including image URLs like ![smth](URL-key)",
            "images": {
                "URL-key":  {"width": 425, "height": 425},
                "URL-key2": {"width": 425, "height": 425}
            }
        }
    """

    for fixture in persues_contentimages_field_fixtures:
        # setup
        _clear_ricecookerfilecache()  # clear file cache each time to avoid test interactions
        field = fixture['field']
        expected_new_content = fixture['new_content']
        expected_image_hashes = set(fixture['image_hashes'])

        # SIT
        testq = PerseusQuestion(id='x43bbec76d5f14f88_bg', raw_data={})
        new_images, image_files = testq.process_image_field(fixture['field'])

        # check 1
        assert field['content'] == expected_new_content, 'Image URL replacement failed'
        #
        # check 2
        for image_key, image_attrs in new_images.items():
            assert 'http' not in image_key, 'Images URLs not replace with local paths'
        #
        # check 3
        image_hashes = set()
        for image_file in image_files:
            assert image_file is not None, 'image_file should not be None'
            filehash, ext =  os.path.splitext(image_file.get_filename())
            image_hashes.add(filehash)
        assert image_hashes == expected_image_hashes, 'Unexpected image files set'



# Test PerseusQuestion process_question method
################################################################################

@pytest.fixture
def persues_question_json_fixtures():
    """
    Load entire perseus questions
    """
    test_data = []
    with open(os.path.join(TESTCONTENT_DIR, 'exercises', 'perseus_question_x43bbec76d5f14f88_en.json'), encoding="utf-8") as inf:
        # ENGLISH JSON = KNOWN GOOD
        item_data_en = json.load(inf)
        datum = {
            'item': item_data_en,
            'image_hashes': ['ea2269bb5cf487f8d883144b9c06fbc7', 'db98ca9d35b2fb97cde378a1fabddd26']
        }
        test_data.append(datum)
    # Missing images in the KA BULGARIAN channel BUG
    # see https://github.com/learningequality/ricecooker/issues/178
    with open(os.path.join(TESTCONTENT_DIR, 'exercises', 'perseus_question_x43bbec76d5f14f88_bg.json'), encoding="utf-8") as inf:

        item_data_bg = json.load(inf)
        datum = {
            'item': item_data_bg,
            'image_hashes': ['ea2269bb5cf487f8d883144b9c06fbc7', 'db98ca9d35b2fb97cde378a1fabddd26']
        }
        test_data.append(datum)

    return test_data


def test_perseus_process_question(persues_question_json_fixtures):
    """
    Process a persues question and check that it finds all images, and returns
    correcrt image files -- i.e not more, not less.
    """

    for datum in persues_question_json_fixtures:

        # setup
        perseus_question = datum['item']
        expected_image_hashes = set(datum['image_hashes'])
        _clear_ricecookerfilecache()  # clear file cache each time to avoid test interactions

        # SIT
        testq = PerseusQuestion(id='x43bbec76d5f14f88_en', raw_data=perseus_question)
        filenames = testq.process_question()

        # check 1
        assert len(filenames) == 2, 'wrong number of filenames found'

        # check 2
        image_hashes = set()
        for filename in filenames:
            filehash, ext =  os.path.splitext(filename)
            image_hashes.add(filehash)
        assert image_hashes == expected_image_hashes, 'Unexpected image file set'


# Test exercise images
################################################################################

def test_exercise_image_file(exercise_image_file, exercise_image_filename):
    filename = exercise_image_file.get_filename()
    assert filename == exercise_image_filename, 'wrong filename for _ExerciseImageFile'

def test_exercise_base64_image_file(exercise_base64_image_file, exercise_base64_image_filename):
    filename = exercise_base64_image_file.get_filename()
    assert filename == exercise_base64_image_filename, 'wrong filename for _ExerciseBase64ImageFile'

def test_exercise_graphie_filename(exercise_graphie_file, exercise_graphie_replacement_str, exercise_graphie_filename):
    filename = exercise_graphie_file.get_filename()
    assert filename == exercise_graphie_filename, 'wrong filename for _ExerciseGraphieFile'
    replacement_str = exercise_graphie_file.get_replacement_str()
    assert replacement_str == exercise_graphie_replacement_str, 'wrong replacement string for _ExerciseGraphieFile '
