""" Tests for exercise nodes, questions, and files """

import pytest
import uuid
import tempfile
from le_utils.constants import licenses, content_kinds, exercises
from ricecooker.classes.nodes import *


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
def exercise(exercise_data, channel_internal_domain, topic_node_id):
    node = ExerciseNode(
		source_id=exercise_data['id'],
		# description=exercise_data['description'],
		title=exercise_data['title'],
		author=exercise_data['author'],
		license=exercise_data['license'],
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
