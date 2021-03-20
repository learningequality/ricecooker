from collections import defaultdict
import csv
import json
import os
import re
import requests
from unicodedata import normalize

from le_utils.constants import content_kinds, exercises
from ricecooker.config import LOGGER
from ricecooker.utils.libstudio import StudioApi

from ricecooker.classes.questions import MARKDOWN_IMAGE_REGEX


# CONSTANTS
################################################################################
DEFAULT_EXTRA_ITEMS_SEPARATOR = '🍣'  # used to separate list-like data in CSV
CSV_STR_TRUE_VALUES = ['on', 'yes', '1', 'true']
CSV_STR_FALSE_VALUES = ['off', 'no', '0', 'false']

DEFAULT_CHANNEL_INFO_FILENAME = 'Channel.csv'
CHANNEL_TITLE_KEY = 'Title'
CHANNEL_DESCRIPTION_KEY = 'Description'
CHANNEL_DOMAIN_KEY = 'Domain'
CHANNEL_SOURCEID_KEY = 'Source ID'
CHANNEL_LANGUAGE_KEY = 'Language'
CHANNEL_THUMBNAIL_KEY = 'Thumbnail'
CHANNEL_INFO_HEADER = [
    CHANNEL_TITLE_KEY,
    CHANNEL_DESCRIPTION_KEY,
    CHANNEL_DOMAIN_KEY,
    CHANNEL_SOURCEID_KEY,
    CHANNEL_LANGUAGE_KEY,
    CHANNEL_THUMBNAIL_KEY
]

DEFAULT_CONTENT_INFO_FILENAME = 'Content.csv'
CONTENT_PATH_KEY = 'Path *'
CONTENT_TITLE_KEY = 'Title *'
CONTENT_SOURCEID_KEY = 'Source ID'
CONTENT_DESCRIPTION_KEY = 'Description'
CONTENT_AUTHOR_KEY = 'Author'
CONTENT_LANGUAGE_KEY = 'Language'
CONTENT_LICENSE_ID_KEY = 'License ID *'
CONTENT_LICENSE_DESCRIPTION_KEY = 'License Description'
CONTENT_LICENSE_COPYRIGHT_HOLDER_KEY = 'Copyright Holder'
CONTENT_THUMBNAIL_KEY = 'Thumbnail'
CONTENT_INFO_HEADER = [
    CONTENT_PATH_KEY,
    CONTENT_TITLE_KEY,
    CONTENT_SOURCEID_KEY,
    CONTENT_DESCRIPTION_KEY,
    CONTENT_AUTHOR_KEY,
    CONTENT_LANGUAGE_KEY,
    CONTENT_LICENSE_ID_KEY,
    CONTENT_LICENSE_DESCRIPTION_KEY,
    CONTENT_LICENSE_COPYRIGHT_HOLDER_KEY,
    CONTENT_THUMBNAIL_KEY
]

DEFAULT_EXERCISES_INFO_FILENAME = 'Exercises.csv'
EXERCISE_SOURCEID_KEY = 'Source ID *'
EXERCISE_M_KEY = 'Number Correct'     # (integer)
EXERCISE_N_KEY = 'Out of Total'       # (integer)
EXERCISE_RANDOMIZE_KEY = 'Randomize'  # Use 'true' (default) or 'false'
EXERCISE_INFO_HEADER = [
    CONTENT_PATH_KEY,
    CONTENT_TITLE_KEY,
    EXERCISE_SOURCEID_KEY,
    CONTENT_DESCRIPTION_KEY,
    CONTENT_AUTHOR_KEY,
    CONTENT_LANGUAGE_KEY,
    CONTENT_LICENSE_ID_KEY,
    CONTENT_LICENSE_DESCRIPTION_KEY,
    CONTENT_LICENSE_COPYRIGHT_HOLDER_KEY,
    EXERCISE_M_KEY,
    EXERCISE_N_KEY,
    EXERCISE_RANDOMIZE_KEY,
    CONTENT_THUMBNAIL_KEY
]

DEFAULT_EXERCISE_QUESTIONS_INFO_FILENAME = 'ExerciseQuestions.csv'
EXERCISE_QUESTIONS_QUESTIONID_KEY = 'Question ID *'  # unique idendifier for this question
EXERCISE_QUESTIONS_TYPE_KEY = 'Question type *'      # one of ['SingleSelectQuestion', 'MultipleSelectQuestion', 'InputQuestion']
EXERCISE_QUESTIONS_QUESTION_KEY = 'Question *'       # string that contains the question setup and the prompt
EXERCISE_QUESTIONS_OPTION_A_KEY = 'Option A'
EXERCISE_QUESTIONS_OPTION_B_KEY = 'Option B'
EXERCISE_QUESTIONS_OPTION_C_KEY = 'Option C'
EXERCISE_QUESTIONS_OPTION_D_KEY = 'Option D'
EXERCISE_QUESTIONS_OPTION_E_KEY = 'Option E'
EXERCISE_QUESTIONS_OPTION_FGHI_KEY = 'Options F...' # This field can contain a list of multiple '🍣'-separated string values,
                                                    # e.g.,   'Anser F🍣Answer G🍣Answer H'  (or other suitable unicode character)
EXERCISE_QUESTIONS_CORRECT_ANSWER_KEY = 'Correct Answer *'   # A string that equals one of the options strings
EXERCISE_QUESTIONS_CORRECT_ANSWER2_KEY = 'Correct Answer 2'  # (for multiple select)
EXERCISE_QUESTIONS_CORRECT_ANSWER3_KEY = 'Correct Answer 3'  # (for multiple select)
EXERCISE_QUESTIONS_HINT_1_KEY = 'Hint 1'
EXERCISE_QUESTIONS_HINT_2_KEY = 'Hint 2'
EXERCISE_QUESTIONS_HINT_3_KEY = 'Hint 3'
EXERCISE_QUESTIONS_HINT_4_KEY = 'Hint 4'
EXERCISE_QUESTIONS_HINT_5_KEY = 'Hint 5'
EXERCISE_QUESTIONS_HINT_6789_KEY = 'Hint 6+'  # This field can contain a list of multiple '🍣'-separated string values,
                                              # e.g.,   'Hint 6 text🍣Hint 7 text🍣Hing 8 text'
EXERCISE_QUESTIONS_INFO_HEADER = [
    EXERCISE_SOURCEID_KEY,
    EXERCISE_QUESTIONS_QUESTIONID_KEY,
    EXERCISE_QUESTIONS_TYPE_KEY,
    EXERCISE_QUESTIONS_QUESTION_KEY,
    EXERCISE_QUESTIONS_OPTION_A_KEY,
    EXERCISE_QUESTIONS_OPTION_B_KEY,
    EXERCISE_QUESTIONS_OPTION_C_KEY,
    EXERCISE_QUESTIONS_OPTION_D_KEY,
    EXERCISE_QUESTIONS_OPTION_E_KEY,
    EXERCISE_QUESTIONS_OPTION_FGHI_KEY,
    EXERCISE_QUESTIONS_CORRECT_ANSWER_KEY,
    EXERCISE_QUESTIONS_CORRECT_ANSWER2_KEY,
    EXERCISE_QUESTIONS_CORRECT_ANSWER3_KEY,
    EXERCISE_QUESTIONS_HINT_1_KEY,
    EXERCISE_QUESTIONS_HINT_2_KEY,
    EXERCISE_QUESTIONS_HINT_3_KEY,
    EXERCISE_QUESTIONS_HINT_4_KEY,
    EXERCISE_QUESTIONS_HINT_5_KEY,
    EXERCISE_QUESTIONS_HINT_6789_KEY
]


# HELPER FUNCTIONS
################################################################################

def path_to_tuple(path):
    """
    Split a current file system path into individual parts and form a tuple for key lookups.
    """
    allparts = []
    while 1:
        parts = os.path.split(path)
        if parts[0] == path:  # sentinel for absolute paths
            allparts.insert(0, parts[0])
            break
        elif parts[1] == path:  # sentinel for relative paths
            allparts.insert(0, parts[1])
            break
        else:
            path = parts[0]
            allparts.insert(0, parts[1])

    # Normalize UTF-8 encoding to consistent form so cache lookups will work, see
    # https://docs.python.org/3.6/library/unicodedata.html#unicodedata.normalize
    path_tup = tuple(normalize('NFD', part) for part in allparts)
    return path_tup


def input_path_to_tuple(path, windows=False):
    """
    Split `chan_path` into individual parts and form a tuple (used as key).
    """
    if windows:
        path_tup = tuple(path.split('\\'))
    else:
        path_tup = tuple(path.split('/'))
    #
    # Normalize UTF-8 encoding to consistent form so cache lookups will work, see
    # https://docs.python.org/3.6/library/unicodedata.html#unicodedata.normalize
    path_tup = tuple(normalize('NFD', part) for part in path_tup)
    return path_tup

def get_metadata_file_path(channeldir, filename):
    """
    Return the path to the metadata file named `filename` that is a sibling of `channeldir`.
    """
    channelparentdir, channeldirname = os.path.split(channeldir)
    return os.path.join(channelparentdir, filename)



# METADATA PROVIDER BASE CLASS
################################################################################

class MetadataProvider(object):
    def validate(self):
        """Check if metadata provided is valid."""
        pass


class CsvMetadataProvider(MetadataProvider):

    def __init__(self, channeldir,
                 channelinfo=DEFAULT_CHANNEL_INFO_FILENAME,
                 contentinfo=DEFAULT_CONTENT_INFO_FILENAME,
                 exercisesinfo=DEFAULT_EXERCISES_INFO_FILENAME,
                 questionsinfo=DEFAULT_EXERCISE_QUESTIONS_INFO_FILENAME,
                 winpaths=False, validate_and_cache=True):
        """
        Load the metadata from CSV files `channelinfo`, `contentinfo`, and optionally
        exericies data from `exercisesinfo` and `questionsinfo` files.
          - Set winpaths=True if paths in .csv use Windows-style separator
          - Set validate_and_cache=False to use the class for generating .csv templates
        """
        if channeldir.endswith(os.path.sep):
            channeldir = channeldir.rstrip(os.path.sep)
        self.channeldir = channeldir
        self.channelinfo = channelinfo
        self.contentinfo = contentinfo
        self.exercisesinfo = exercisesinfo
        self.questionsinfo = questionsinfo
        self.contentcache = {}                # { ('chan', 'path','as','tuple's) --> node metadata dict
        self.exercise_filenames_in_dir = defaultdict(list)   # { ('chan', 'path','some','dir) --> list of exercises (virtual filenames)
        self.winpaths = winpaths  # paths separator in .csv is windows '\'
        if validate_and_cache:
            self.validate_headers()
            self.cache_contentinfo()   # read and parse CSV to build cache lookup table



    # MAIN METHODS
    ############################################################################

    def cache_contentinfo(self):
        """
        Main workhorse that runs at the end of __init__ which sets up:
          - self.contentcache   path_tuple --> metadata dict for any path
          - self.exercise_filenames_in_dir  path_tuple (to a folder)--> list
            virtual exercise filenams in that folder
        """
        csv_filename = get_metadata_file_path(self.channeldir, self.contentinfo)
        csv_lines = _read_csv_lines(csv_filename)
        dict_reader = csv.DictReader(csv_lines)
        for row in dict_reader:
            row_dict = self._map_content_row_to_dict(row)
            path_tuple = input_path_to_tuple(row_dict['chan_path'], windows=self.winpaths)
            self.contentcache[path_tuple] = row_dict

        # Additional handling of data in Exercises.csv and ExerciseQuestions.txt
        if self.has_exercises():
            # A. Load exercise questions
            questions_by_source_id = defaultdict(list)
            csv_filename = get_metadata_file_path(self.channeldir, self.questionsinfo)
            csv_lines = _read_csv_lines(csv_filename)
            dict_reader = csv.DictReader(csv_lines)
            for question_row in dict_reader:
                question_dict = self._map_exercise_question_row_to_dict(question_row)
                question_source_id = question_dict['source_id']
                del question_dict['source_id']
                questions_by_source_id[question_source_id].append(question_dict)

            # B. Load exercises
            csv_filename = get_metadata_file_path(self.channeldir, self.exercisesinfo)
            csv_lines = _read_csv_lines(csv_filename)
            dict_reader = csv.DictReader(csv_lines)
            for exercise_row in dict_reader:
                exercise_dict = self._map_exercise_row_to_dict(exercise_row)
                path_tuple = input_path_to_tuple(exercise_dict['chan_path'], windows=self.winpaths)
                question_source_id = exercise_dict['source_id']
                exercise_dict['questions'] = questions_by_source_id[question_source_id]
                # B1: exercises are standard content nodes, so add to contentcache
                self.contentcache[path_tuple] = exercise_dict
                # B2: add exercise to list of virtual filanames for current folder
                dir_path_tuple = path_tuple[0:-1]
                vfilename = path_tuple[-1]
                self.exercise_filenames_in_dir[dir_path_tuple].append(vfilename)

    def get(self, path_tuple):
        """
        Returns metadata dict for path in `path_tuple`.
        """
        if path_tuple in self.contentcache:
            metadata = self.contentcache[path_tuple]
        else:
            # TODO: make chef robust to missing metadata
            # LOGGER.error(
            LOGGER.warning('No metadata found for path_tuple ' + str(path_tuple))
            metadata = dict(
                filepath=os.path.sep.join(path_tuple),
                title=os.path.sep.join(path_tuple)
            )
        return metadata

    def get_channel_info(self):
        """
        Returns the first data row from Channel.csv
        """
        csv_filename = get_metadata_file_path(channeldir=self.channeldir, filename=self.channelinfo)
        csv_lines = _read_csv_lines(csv_filename)
        dict_reader = csv.DictReader(csv_lines)
        channel_csvs_list =  list(dict_reader)
        channel_csv = channel_csvs_list[0]
        if len(channel_csvs_list) > 1:
            raise ValueError('Found multiple channel rows in ' + self.channelinfo)
        channel_cleaned = _clean_dict(channel_csv)
        channel_info = self._map_channel_row_to_dict(channel_cleaned)
        return channel_info

    def get_thumbnail_paths(self):
        """
        Helper function used to avoid processing thumbnail files during `os.walk`.
        """
        thumbnail_path_tuples = []
        # channel thumbnail
        channel_info = self.get_channel_info()
        chthumbnail_path = channel_info.get('thumbnail_chan_path', None)
        if chthumbnail_path:
            chthumbnail_path_tuple = input_path_to_tuple(chthumbnail_path, windows=self.winpaths)
            thumbnail_path_tuples.append(chthumbnail_path_tuple)
        # content thumbnails
        for content_file_path_tuple, row in self.contentcache.items():
            thumbnail_path = row.get('thumbnail_chan_path', None)
            if thumbnail_path:
                thumbnail_path_tuple = input_path_to_tuple(thumbnail_path, windows=self.winpaths)
                thumbnail_path_tuples.append(thumbnail_path_tuple)
        return thumbnail_path_tuples



    # CHANNEL+CONTENT PARSING METHODS
    ############################################################################

    def _map_channel_row_to_dict(self, row):
        """
        Convert dictionary keys from raw csv format (see CHANNEL_INFO_HEADER),
        to ricecooker-like keys, e.g., ''Source ID' --> 'source_id'
        """
        channel_cleaned = _clean_dict(row)
        channel_dict = dict(
            title=channel_cleaned[CHANNEL_TITLE_KEY],
            description=channel_cleaned[CHANNEL_DESCRIPTION_KEY],
            source_domain=channel_cleaned[CHANNEL_DOMAIN_KEY],
            source_id=channel_cleaned[CHANNEL_SOURCEID_KEY],
            language=channel_cleaned[CHANNEL_LANGUAGE_KEY],
            thumbnail_chan_path=channel_cleaned[CHANNEL_THUMBNAIL_KEY]
        )
        return channel_dict

    def _map_content_row_to_dict(self, row):
        """
        Convert dictionary keys from raw csv format (see CONTENT_INFO_HEADER),
        to ricecooker-like keys, e.g., 'Title *' --> 'title'
        """
        row_cleaned = _clean_dict(row)
        license_id = row_cleaned[CONTENT_LICENSE_ID_KEY]
        if license_id:
            license_dict = dict(
                license_id=row_cleaned[CONTENT_LICENSE_ID_KEY],
                description=row_cleaned.get(CONTENT_LICENSE_DESCRIPTION_KEY, None),
                copyright_holder=row_cleaned.get(CONTENT_LICENSE_COPYRIGHT_HOLDER_KEY, None)
            )
        else:
            license_dict = None
        # row_dict represents either a topic node or a content node
        row_dict = dict(
            chan_path=row_cleaned[CONTENT_PATH_KEY],
            title=row_cleaned[CONTENT_TITLE_KEY],
            source_id=row_cleaned.get(CONTENT_SOURCEID_KEY, None),
            description=row_cleaned.get(CONTENT_DESCRIPTION_KEY, None),
            author=row_cleaned.get(CONTENT_AUTHOR_KEY, None),
            language=row_cleaned.get(CONTENT_LANGUAGE_KEY, None),
            license=license_dict,
            thumbnail_chan_path=row_cleaned.get(CONTENT_THUMBNAIL_KEY, None)
        )
        return row_dict



    # EXERCISES CSV PARSING METHODS
    ############################################################################

    def has_exercises(self):
        exercises_csv = get_metadata_file_path(self.channeldir, self.exercisesinfo)
        if os.path.exists(exercises_csv):
            return True
        else:
            return False

    def get_exercises_for_dir(self, dir_path_tuple):
        """
        Returns the list of virtual filenames that correspon to exercise nodes generated
        from the Exercises.csv file. These files don't exist in channeldir, but are needed
        to specify relative ordering between content items and exercises in CSV channels.
        """
        return self.exercise_filenames_in_dir[dir_path_tuple]


    def _map_exercise_row_to_dict(self, row):
        """
        Convert dictionary keys from raw CSV Exercise format to ricecooker keys.
        """
        row_cleaned = _clean_dict(row)
        license_id = row_cleaned[CONTENT_LICENSE_ID_KEY]
        if license_id:
            license_dict = dict(
                license_id=row_cleaned[CONTENT_LICENSE_ID_KEY],
                description=row_cleaned.get(CONTENT_LICENSE_DESCRIPTION_KEY, None),
                copyright_holder=row_cleaned.get(CONTENT_LICENSE_COPYRIGHT_HOLDER_KEY, None)
            )
        else:
            license_dict = None

        # Parse exercise_data
        randomize_raw = row_cleaned.get(EXERCISE_RANDOMIZE_KEY, None)
        if randomize_raw is None or randomize_raw.lower() in CSV_STR_TRUE_VALUES:
            randomize = True
        elif randomize_raw.lower() in CSV_STR_FALSE_VALUES:
            randomize = False
        else:
            raise ValueError('Unrecognized value ' + randomize_raw + ' for randomzied key')
        exercise_data = dict(
            mastery_model=exercises.M_OF_N,
            randomize=randomize,
        )
        m_value = row_cleaned.get(EXERCISE_M_KEY, None)
        if m_value:
            exercise_data['m'] = int(m_value)
        n_value = row_cleaned.get(EXERCISE_N_KEY, None)
        if n_value:
            exercise_data['n'] = int(n_value)

        exercise_dict = dict(
            chan_path=row_cleaned[CONTENT_PATH_KEY],
            title=row_cleaned[CONTENT_TITLE_KEY],
            source_id=row_cleaned[EXERCISE_SOURCEID_KEY],
            description=row_cleaned.get(CONTENT_DESCRIPTION_KEY, None),
            author=row_cleaned.get(CONTENT_AUTHOR_KEY, None),
            language=row_cleaned.get(CONTENT_LANGUAGE_KEY, None),
            license=license_dict,
            exercise_data=exercise_data,
            thumbnail_chan_path=row_cleaned.get(CONTENT_THUMBNAIL_KEY, None)
        )
        return exercise_dict

    def _map_exercise_question_row_to_dict(self, row):
        """
        Convert dictionary keys from raw CSV Exercise Question format to ricecooker keys.
        """
        row_cleaned = _clean_dict(row)

        # Parse answers
        all_answers = []
        ansA = row_cleaned[EXERCISE_QUESTIONS_OPTION_A_KEY]
        all_answers.append(ansA)
        ansB = row_cleaned.get(EXERCISE_QUESTIONS_OPTION_B_KEY, None)
        if ansB:
            all_answers.append(ansB)
        ansC = row_cleaned.get(EXERCISE_QUESTIONS_OPTION_C_KEY, None)
        if ansC:
            all_answers.append(ansC)
        ansD = row_cleaned.get(EXERCISE_QUESTIONS_OPTION_D_KEY, None)
        if ansD:
            all_answers.append(ansD)
        ansE = row_cleaned.get(EXERCISE_QUESTIONS_OPTION_E_KEY, None)
        if ansE:
            all_answers.append(ansE)
        more_answers_str = row_cleaned.get(EXERCISE_QUESTIONS_OPTION_FGHI_KEY, None)
        if more_answers_str:
            more_answers = more_answers_str.split(DEFAULT_EXTRA_ITEMS_SEPARATOR)
            all_answers.extend([ans.strip() for ans in more_answers])

        # Parse correct answers
        correct_answers = []
        correct_ans = row_cleaned[EXERCISE_QUESTIONS_CORRECT_ANSWER_KEY]
        correct_answers.append(correct_ans)
        correct_ans2 = row_cleaned.get(EXERCISE_QUESTIONS_CORRECT_ANSWER2_KEY, None)
        if correct_ans2:
            correct_answers.append(correct_ans2)
        correct_ans3 = row_cleaned.get(EXERCISE_QUESTIONS_CORRECT_ANSWER3_KEY, None)
        if correct_ans3:
            correct_answers.append(correct_ans3)

        # Parse hints
        hints = []
        hint1 = row_cleaned.get(EXERCISE_QUESTIONS_HINT_1_KEY, None)
        if hint1:
            hints.append(hint1)
        hint2 = row_cleaned.get(EXERCISE_QUESTIONS_HINT_2_KEY, None)
        if hint2:
            hints.append(hint2)
        hint3 = row_cleaned.get(EXERCISE_QUESTIONS_HINT_3_KEY, None)
        if hint3:
            hints.append(hint3)
        hint4 = row_cleaned.get(EXERCISE_QUESTIONS_HINT_4_KEY, None)
        if hint4:
            hints.append(hint4)
        hint5 = row_cleaned.get(EXERCISE_QUESTIONS_HINT_5_KEY, None)
        if hint5:
            hints.append(hint5)
        more_hints_str = row_cleaned.get(EXERCISE_QUESTIONS_HINT_6789_KEY, None)
        if more_hints_str:
            more_hints = more_hints_str.split(DEFAULT_EXTRA_ITEMS_SEPARATOR)
            hints.extend([hint.strip() for hint in more_hints])

        # Build appropriate dictionary depending on question_type
        question_type = row_cleaned[EXERCISE_QUESTIONS_TYPE_KEY]
        if question_type == exercises.MULTIPLE_SELECTION:
            question_dict = dict(
                question_type=exercises.MULTIPLE_SELECTION,
                source_id=row_cleaned[EXERCISE_SOURCEID_KEY],
                id=row_cleaned[EXERCISE_QUESTIONS_QUESTIONID_KEY],
                question=row_cleaned[EXERCISE_QUESTIONS_QUESTION_KEY],
                correct_answers=correct_answers,
                all_answers=all_answers,
                hints=hints,
            )
        elif question_type == exercises.SINGLE_SELECTION:
            question_dict = dict(
                question_type=exercises.SINGLE_SELECTION,
                source_id=row_cleaned[EXERCISE_SOURCEID_KEY],
                id=row_cleaned[EXERCISE_QUESTIONS_QUESTIONID_KEY],
                question=row_cleaned[EXERCISE_QUESTIONS_QUESTION_KEY],
                correct_answer=correct_answers[0],
                all_answers=all_answers,
                hints=hints,
            )
        elif question_type == exercises.INPUT_QUESTION:
            question_dict = dict(
                question_type=exercises.INPUT_QUESTION,
                source_id=row_cleaned[EXERCISE_SOURCEID_KEY],
                id=row_cleaned[EXERCISE_QUESTIONS_QUESTIONID_KEY],
                question=row_cleaned[EXERCISE_QUESTIONS_QUESTION_KEY],
                answers=correct_answers,
                hints=hints,
            )
        elif question_type == exercises.PERSEUS_QUESTION:
            raise ValueError('Perseus questions not currently supported in CSV workflow.')

        return question_dict





    # CSV VALIDATION METHODS
    ############################################################################

    def validate_headers(self):
        """
        Check if CSV metadata files have the right format.
        """
        super().validate()
        self.validate_header(self.channeldir, self.channelinfo, CHANNEL_INFO_HEADER)
        self.validate_header(self.channeldir, self.contentinfo, CONTENT_INFO_HEADER)
        if self.has_exercises():
            self.validate_header(self.channeldir, self.exercisesinfo, EXERCISE_INFO_HEADER)
            self.validate_header(self.channeldir, self.questionsinfo, EXERCISE_QUESTIONS_INFO_HEADER)

    def validate_header(self, channeldir, filename, expected_header):
        """
        Check if CSV metadata file `filename` have the expected header format.
        """
        expected = set(expected_header)
        csv_filename = get_metadata_file_path(channeldir, filename)
        csv_lines = _read_csv_lines(csv_filename)
        dict_reader = csv.DictReader(csv_lines)
        actual = set(dict_reader.fieldnames)
        if not actual == expected:
            raise ValueError('Unexpected CSV file header in ' + csv_filename \
                             + ' Expected header:' + str(expected))

    def validate(self):
        """
        Checks if provided .csv is valid as a whole.
        """
        pass  # TODO


    # Generate CSV metadata from a given studio_id
    ############################################################################

    def generate_exercises_from_importstudioid(self, args, options):
        """
        Create rows in Exercises.csv and ExerciseQuestions.csv from a Studio channel,
        specified based on a studio_id (e.g. studio_id of main_tree for some channel)'
        """
        print('Generating Exercises.csv and ExerciseQuestions.csv from a Studio channel')
        self.studioapi = StudioApi(token=args['token'])
        channel_dict = self.studioapi.get_tree_for_studio_id(args['importstudioid'])
        json.dump(channel_dict, open('chefdata/studiotree.json', 'w'), indent=4, ensure_ascii=False, sort_keys=True)

        soure_ids_seen = []
        def _generate_source_id(subtree):
            """
            Creates a Source ID form title and ensures it is unique withing channel.
            """
            candidate = subtree['title'].replace(' ', '_')
            if candidate not in soure_ids_seen:
                source_id = candidate
                soure_ids_seen.append(source_id)
            else:
                source_id = candidate + subtree['node_id'][0:7]
                soure_ids_seen.append(source_id)
            return source_id

        def _write_subtree(path_tuple, subtree, is_root=False):
            print('    '*len(path_tuple) + '  - ', subtree['title'])
            kind = subtree['kind']

            # TOPIC ############################################################
            if kind == 'topic':

                if is_root:
                    self.write_topic_row_from_studio_dict(path_tuple, subtree, is_root=is_root)
                    for child in subtree['children']:
                        _write_subtree(path_tuple, child)
                else:
                    self.write_topic_row_from_studio_dict(path_tuple, subtree)
                    for child in subtree['children']:
                        _write_subtree(path_tuple+[subtree['title']], child)

            # EXERCISE #########################################################
            elif kind == 'exercise':
                source_id = _generate_source_id(subtree)
                self.write_exercice_row_from_studio_dict(path_tuple, subtree, source_id)
                for question_dict in subtree['assessment_items']:
                    self.write_question_row_from_question_dict(source_id, question_dict)

            else:
                print('skipping node', subtree['title'])

        path_tuple = [ self.channeldir.split('/')[-1] ]
        _write_subtree(path_tuple, channel_dict, is_root=True)

    def write_commont_studio_dict_from_row(self, studio_dict, row):
        if studio_dict['license']:
            license_dict = self.studioapi.licenses_by_id[studio_dict['license']]
        else:
            license_dict = {'license_name': None}
        row[CONTENT_TITLE_KEY] = studio_dict['title']
        row[CONTENT_DESCRIPTION_KEY] = studio_dict['description']
        row[CONTENT_AUTHOR_KEY] = studio_dict['author']
        row[CONTENT_LANGUAGE_KEY] = 'en'
        row[CONTENT_LICENSE_ID_KEY] = license_dict['license_name']
        row[CONTENT_LICENSE_DESCRIPTION_KEY] = None
        row[CONTENT_LICENSE_COPYRIGHT_HOLDER_KEY] = studio_dict['copyright_holder']
        row[CONTENT_THUMBNAIL_KEY] = None


    def write_topic_row_from_studio_dict(self, path_tuple, studio_dict, is_root=False):
        if is_root:
            return
        # print('Generating Content.csv rows folders and file in channeldir for path_tuple ', path_tuple, studio_dict['title'])
        file_path = get_metadata_file_path(self.channeldir, self.contentinfo)
        with open(file_path, 'a') as csv_file:
            csvwriter = csv.DictWriter(csv_file, CONTENT_INFO_HEADER)
            title = studio_dict['title']
            path_with_self = '/'.join(path_tuple+[title])
            if not os.path.exists(path_with_self):
                os.makedirs(path_with_self, exist_ok=True)
            topic_row = {}
            self.write_commont_studio_dict_from_row(studio_dict, topic_row)
            # WRITE TOPIC ROW
            topic_row[CONTENT_PATH_KEY] = path_with_self
            topic_row[CONTENT_SOURCEID_KEY] = studio_dict['node_id'][0:7]
            csvwriter.writerow(topic_row)


    def write_exercice_row_from_studio_dict(self, path_tuple, studio_dict, source_id):
        file_path = get_metadata_file_path(self.channeldir, self.exercisesinfo)
        with open(file_path, 'a') as csv_file:
            csvwriter = csv.DictWriter(csv_file, EXERCISE_INFO_HEADER)
            exercise_row = {}
            self.write_commont_studio_dict_from_row(studio_dict, exercise_row)
            exercise_title = studio_dict['title']
            exercise_row[CONTENT_PATH_KEY] = '/'.join(path_tuple+[exercise_title])
            exercise_row[EXERCISE_SOURCEID_KEY] = source_id
            # Exercises specifics
            if isinstance(studio_dict['extra_fields'], str):
                extra_fields = json.loads(studio_dict['extra_fields'])
            else:
                extra_fields = studio_dict['extra_fields']
            exercise_row[EXERCISE_M_KEY] = int(extra_fields['m'])
            exercise_row[EXERCISE_N_KEY] = int(extra_fields['n'])
            exercise_row[EXERCISE_RANDOMIZE_KEY] = extra_fields['randomize']
            # WRITE EXERCISE ROW
            csvwriter.writerow(exercise_row)



    def _make_local_question_images(self, question_dict):
        """
        Process all mardown image links in question_dict:
          - download them to local files under exerciseimages/
        """
        question_dict = question_dict.copy()
        dest_path = 'exerciseimages/'

        if not os.path.exists(dest_path):
            os.mkdir(dest_path)

        # helper method
        def _process_string(string):
            image_regex = re.compile(MARKDOWN_IMAGE_REGEX, flags=re.IGNORECASE)
            contentstorage_prefix = '${☣ CONTENTSTORAGE}/'
            studio_storage = 'https://studio.learningequality.org/content/storage/'

            matches = image_regex.findall(string)

            # Parse all matches
            for match in matches:
                file_result = match[1]
                file_name = file_result.replace(contentstorage_prefix, '')
                file_url = studio_storage + file_name[0] + '/' + file_name[1] + '/' + file_name
                file_local_path = os.path.join(dest_path, file_name)
                response = requests.get(file_url)
                if response.status_code != 200:
                    print('Failed for image ' + str(response.status_code) + ' >> ' + file_url)
                    return string
                with open(file_local_path, 'wb') as local_file:
                    local_file.write(response.content)
                    print('saved image file', file_local_path)
                string = string.replace(file_result, file_local_path)

            return string

        # Process images in question
        new_question = _process_string(question_dict['question'])
        question_dict['question'] = new_question

        # Process images in answers
        answers = json.loads(question_dict['answers'])
        new_answers = []
        for ans in answers:
            new_ans = ans.copy()
            new_ans['answer'] = _process_string(new_ans['answer'])
            new_answers.append(new_ans)
        question_dict['answers'] = json.dumps(new_answers)

        # TODO: process hint images

        return question_dict



    def write_question_row_from_question_dict(self, source_id, question_dict):
        file_path = get_metadata_file_path(self.channeldir, self.questionsinfo)
        if question_dict['type'] == 'perseus_question':
            print('Skipping perseus_question -- not supported in CSV workflow.')
            return
        with open(file_path, 'a') as csv_file:
            csvwriter = csv.DictWriter(csv_file, EXERCISE_QUESTIONS_INFO_HEADER)

            def _safe_list_get(l, idx, default):
                try:
                    return l[idx]
                except IndexError:
                    return default

            # change image links to local
            question_dict = self._make_local_question_images(question_dict)

            type_lookup = {
                'single_selection': exercises.SINGLE_SELECTION,
                'true_false': exercises.SINGLE_SELECTION,
                'multiple_selection': exercises.MULTIPLE_SELECTION,
                'input_question': exercises.INPUT_QUESTION,
            }

            # ANSWERS
            answers = json.loads(question_dict['answers'])
            options = []  # all options
            correct = []  # correct andwers
            for ans in answers:
                options.append(ans['answer'])
                if ans['correct']:
                    correct.append(ans['answer'])
            extra_options = DEFAULT_EXTRA_ITEMS_SEPARATOR.join(options[5:])

            # HINTS
            hints_raw = json.loads(question_dict['hints'])
            if hints_raw:
                raise ValueError('Found hints but not handled..')

            LOGGER.info('     - writing question with studio_id=' + question_dict['assessment_id'])
            question_row = {}
            question_row[EXERCISE_SOURCEID_KEY] = source_id
            question_row[EXERCISE_QUESTIONS_QUESTIONID_KEY] = question_dict['assessment_id'] # question_dict['assessment_id']
            question_row[EXERCISE_QUESTIONS_TYPE_KEY] = type_lookup[question_dict['type']]
            question_row[EXERCISE_QUESTIONS_QUESTION_KEY] = question_dict['question']
            question_row[EXERCISE_QUESTIONS_OPTION_A_KEY] = _safe_list_get(options, 0, None)
            question_row[EXERCISE_QUESTIONS_OPTION_B_KEY] = _safe_list_get(options, 1, None)
            question_row[EXERCISE_QUESTIONS_OPTION_C_KEY] = _safe_list_get(options, 2, None)
            question_row[EXERCISE_QUESTIONS_OPTION_D_KEY] = _safe_list_get(options, 3, None)
            question_row[EXERCISE_QUESTIONS_OPTION_E_KEY] = _safe_list_get(options, 4, None)
            question_row[EXERCISE_QUESTIONS_OPTION_FGHI_KEY] = extra_options
            question_row[EXERCISE_QUESTIONS_CORRECT_ANSWER_KEY] = _safe_list_get(correct, 0, None)
            question_row[EXERCISE_QUESTIONS_CORRECT_ANSWER2_KEY] = _safe_list_get(correct, 1, None)
            question_row[EXERCISE_QUESTIONS_CORRECT_ANSWER3_KEY] = _safe_list_get(correct, 2, None)
            question_row[EXERCISE_QUESTIONS_HINT_1_KEY] = None # TODO
            question_row[EXERCISE_QUESTIONS_HINT_2_KEY] = None # TODO
            question_row[EXERCISE_QUESTIONS_HINT_3_KEY] = None # TODO
            question_row[EXERCISE_QUESTIONS_HINT_4_KEY] = None # TODO
            question_row[EXERCISE_QUESTIONS_HINT_5_KEY] = None # TODO
            question_row[EXERCISE_QUESTIONS_HINT_6789_KEY] = None # TODO
            # WRITE QUESTION ROW
            csvwriter.writerow(question_row)
            #            'files': [],
            #            'raw_data': '',
            #            'order': 2,
            #            'source_url': None,
            #            'randomize': True,
            #            'deleted': False},




    # Generate CSV from folder structure in channeldir
    ############################################################################

    def generate_contentinfo_from_channeldir(self, args, options):
        """
        Create rows in Content.csv for each folder and file in `self.channeldir`.
        """
        LOGGER.info('Generating Content.csv rows folders and file in channeldir')
        file_path = get_metadata_file_path(self.channeldir, self.contentinfo)
        with open(file_path, 'a') as csv_file:
            csvwriter = csv.DictWriter(csv_file, CONTENT_INFO_HEADER)

            channeldir = args['channeldir']
            if channeldir.endswith(os.path.sep):
                channeldir.rstrip(os.path.sep)

            # MAIN PROCESSING OF os.walk OUTPUT
            content_folders = sorted(os.walk(channeldir))
            _ = content_folders.pop(0)           # Skip over channel root folder
            for rel_path, _subfolders, filenames in content_folders:
                LOGGER.info('processing folder ' + str(rel_path))
                sorted_filenames = sorted(filenames)
                self.generate_contentinfo_from_folder(csvwriter, rel_path, sorted_filenames)
        LOGGER.info('Generted {} row for all folders and files in {}'.format(self.contentinfo, self.channeldir))

    def generate_contentinfo_from_folder(self, csvwriter, rel_path, filenames):
        """
        Create a topic node row in Content.csv for the folder at `rel_path` and
        add content node rows for all the files in the `rel_path` folder.
        """
        LOGGER.debug('IN process_folder ' + str(rel_path) + '     ' + str(filenames))
        from ricecooker.utils.linecook import filter_filenames, filter_thumbnail_files, chan_path_from_rel_path

        # WRITE TOPIC ROW
        topicrow = self.channeldir_node_to_row( rel_path.split(os.path.sep) )
        csvwriter.writerow(topicrow)

        # WRITE CONTENT NODE ROWS
        chan_path = chan_path_from_rel_path(rel_path, self.channeldir)
        filenames_cleaned = filter_filenames(filenames)
        # filenames_cleaned2 = filter_thumbnail_files(chan_path, filenames_cleaned, self)
        for filename in filenames_cleaned:
            path_tuple = rel_path.split(os.path.sep)
            path_tuple.append(filename)
            filerow = self.channeldir_node_to_row(path_tuple)
            csvwriter.writerow(filerow)


    def channeldir_node_to_row(self, path_tuple):
        """
        Return a dict with keys corresponding to Content.csv columns.
        """
        row = dict()
        for key in CONTENT_INFO_HEADER:
            row[key] = None
        row[CONTENT_PATH_KEY] = "/".join(path_tuple)  # use / in .csv on Windows and UNIX
        title = path_tuple[-1].replace('_', ' ')
        for ext in content_kinds.MAPPING.keys():
            if title.endswith(ext):
                title = title.replace('.'+ext, '')
        row[CONTENT_TITLE_KEY] = title
        row[CONTENT_SOURCEID_KEY] = path_tuple[-1]
        return row




    # UTILS
    ############################################################################

    def generate_templates(self, exercise_questions=False):
        """
        Create empty .csv files with the right headers and place them in the
        Will place files as siblings of directory `channeldir`.
        """
        self.generate_template(channeldir=self.channeldir,
                               filename=self.channelinfo,
                               header=CHANNEL_INFO_HEADER)
        self.generate_template(channeldir=self.channeldir,
                               filename=self.contentinfo,
                               header=CONTENT_INFO_HEADER)
        if exercise_questions:
            self.generate_template(channeldir=self.channeldir,
                                   filename=self.exercisesinfo,
                                   header=EXERCISE_INFO_HEADER)
            self.generate_template(channeldir=self.channeldir,
                                   filename=self.questionsinfo,
                                   header=EXERCISE_QUESTIONS_INFO_HEADER)

    def generate_template(self, channeldir, filename, header):
        """
        Create empty template .csv file called `filename` as siblings of the
        directory `channeldir` with header fields specified in `header`.
        """
        file_path = get_metadata_file_path(channeldir, filename)
        if not os.path.exists(file_path):
            with open(file_path, 'w') as csv_file:
                csvwriter = csv.DictWriter(csv_file, header)
                csvwriter.writeheader()


def _read_csv_lines(path):
    """
    Opens CSV file `path` and returns list of rows.
    Pass output of this function to `csv.DictReader` for reading data.
    """
    csv_file = open(path, 'r')
    csv_lines_raw = csv_file.readlines()
    csv_lines_clean = [line for line in csv_lines_raw if len(line.strip()) > 0]
    return csv_lines_clean


def _clean_dict(row):
    """
    Transform empty strings values of dict `row` to None.
    """
    row_cleaned = {}
    for key, val in row.items():
        if val is None or val == '':
            row_cleaned[key] = None
        else:
            row_cleaned[key] = val
    return row_cleaned




class ExcelMetadataProvider(MetadataProvider):
    # LIBRARIES COULD USE
    # https://github.com/jmcnamara/XlsxWriter/blob/95334f999d3a5fb58d8da3197260e920be357638/dev/docs/source/alternatives.rst

    def validate(self):
        """
        Checks if provided .xlsx/.xls is valid as a whole.
        """
        pass
