""" Tests for CSV exercises channel logic """
import os
import pytest
import tempfile

from ricecooker.chefs import LineCook
from ricecooker.utils.jsontrees import read_tree_from_json
from ricecooker.utils.metadata_provider import CsvMetadataProvider



@pytest.fixture
def channeldir():
    return 'tests/testchannels/csv_channel_with_exercises/channeldir'


def test_exercises_metadata_provider(channeldir):
    _, channeldirname = os.path.split(channeldir)
    mp = CsvMetadataProvider(channeldir)
    assert mp is not None, 'CsvMetadataProvider does not exist'
    mp.validate_headers()
    assert mp.has_exercises(), 'has exercises'
    assert mp.get_channel_info()['source_id'] == 'csv_channel_with_exercises', 'check source id'    
    #
    assert len(mp.contentcache.keys()) == 8, 'Found too many items'
    assert len(mp.get_exercises_for_dir((channeldirname,))) == 1, 'one exercise in root'
    assert len(mp.get_exercises_for_dir((channeldirname,'exercises'))) == 3, '3 exercise in exercises/'


def test_exercises_linecook(channeldir):
    tmpdir_path = tempfile.mkdtemp()

    linecook = LineCook()
    linecook.TREES_DATA_DIR = tmpdir_path
    linecook.RICECOOKER_JSON_TREE = 'test_ricecooker_json_tree.json'

    args = dict(
        channeldir=channeldir,
        channelinfo='Channel.csv',
        contentinfo='Content.csv',
        exercisesinfo='Exercises.csv',
        questionsinfo='ExerciseQuestions.csv',
        token='???',
    )
    options = {}
    linecook.pre_run(args, options)
    
    jsontree_path = os.path.join(tmpdir_path, linecook.RICECOOKER_JSON_TREE)
    assert os.path.exists(jsontree_path), 'output json exists'
    test_tree = read_tree_from_json(jsontree_path)
    assert len(test_tree['children']) == 3, 'exercise node + two dirs'

    # cleanup
    os.remove(jsontree_path)
    os.rmdir(tmpdir_path)


