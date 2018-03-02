# Question models for exercises

import uuid
import json
import html
import re
import copy
import sys
from bs4 import BeautifulSoup
from functools import partial
from le_utils.constants import content_kinds,file_formats, format_presets, licenses, exercises
from .. import config
from ..exceptions import UnknownQuestionTypeError, InvalidQuestionException
from .files import _ExerciseImageFile, _ExerciseGraphieFile, _ExerciseBase64ImageFile
from pressurecooker.encodings import get_base64_encoding

WEB_GRAPHIE_URL_REGEX = r'web\+graphie:([^\)]+)'
FILE_REGEX = r'!\[([^\]]+)?\]\(([^\)]+)\)'
IMG_REGEX = r'<\s*img[^>]+>'
IMG_SRC_REGEX = r'\ssrc\s*=\"([^"]+)\"'
IMG_ALT_REGEX = r'\salt\s*=\"([^"]+)\"'

class BaseQuestion:
    """ Base model representing exercise questions

        Questions are used to assess learner's understanding

        Attributes:
            id (str): question's unique id
            question (str): question text
            question_type (str): what kind of question is this
            answers ([{'answer':str, 'correct':bool}]): answers to question
            hints (str or [str]): optional hints on how to answer question
            raw_data (str): raw data for perseus file
    """
    def __init__(self, id, question, question_type, answers=None, hints=None, raw_data="", source_url=None, randomize=False):
        self.question = question
        self.question_type = question_type
        self.files = []
        self.answers = answers if answers is not None else []
        self.hints = [] if hints is None else [hints] if isinstance(hints,str) else hints
        self.raw_data = raw_data
        self.source_id = id
        self.source_url = source_url
        self.randomize = randomize
        self.id = uuid.uuid5(uuid.NAMESPACE_DNS, id)

    def truncate_fields(self):
        if self.source_url and len(self.source_url) > config.MAX_SOURCE_URL_LENGTH:
            config.print_truncate("question_source_url", self.source_id, self.source_url)
            self.source_url = self.source_url[:config.MAX_SOURCE_URL_LENGTH]

    def to_dict(self):
        """ to_dict: puts data in format CC expects
            Args: None
            Returns: dict of node's data
        """
        return {
            "assessment_id": self.id.hex,
            "type": self.question_type,
            "files": [f.to_dict() for f in filter(lambda x: x and x.filename, self.files)],
            "question": self.question,
            "hints": json.dumps(self.hints, ensure_ascii=False),
            "answers": json.dumps(self.answers, ensure_ascii=False),
            "raw_data": self.raw_data,
            "source_url": self.source_url,
            "randomize": self.randomize,
        }

    def create_answer(self, answer, correct=True):
        """ create_answer: Put answer in standard format
            Args:
                answer (str): text of answer
                correct (bool): indicates if answer is correct
            Returns: dict of formatted answer
        """
        return {"answer": str(answer), "correct":correct}

    def process_question(self):
        """ process_question: Parse data that needs to have image strings processed
            Args: None
            Returns: list of all downloaded files
        """
        # Process question
        self.question, question_files = self.set_images(self.question)

        # Process answers
        answers = []
        answer_files = []
        answer_index = 0
        for answer in self.answers:
            processed_string, afiles = self.set_images(answer['answer'])
            answers.append({"answer": processed_string, "correct": answer['correct'], "order": answer_index})
            answer_index += 1
            answer_files += afiles
        self.answers = answers

        # Process hints
        hints = []
        hint_files = []
        hint_index = 0
        for hint in self.hints:
            processed_string, hfiles = self.set_images(hint)
            hints.append({"hint": processed_string, "order": hint_index})
            hint_index += 1
            hint_files += hfiles
        self.hints = hints

        self.files += question_files + answer_files + hint_files
        return [f.filename for f in self.files]

    def set_images(self, text):
        """ set_images: Replace image strings with downloaded image checksums
            Args:
                text (str): text to parse for image strings
            Returns:string with checksums in place of image strings and
                list of files that were downloaded from string
        """
        # Set up return values and regex
        file_list = []
        processed_string = self.parse_html(text)
        reg = re.compile(FILE_REGEX, flags=re.IGNORECASE)
        matches = reg.findall(processed_string)

        # Parse all matches
        for match in matches:
            file_result = self.set_image(match[1])
            if file_result[0] != "":
                replacement, new_files = file_result
                processed_string = processed_string.replace(match[1], replacement)
                file_list += new_files
        return processed_string, file_list

    def parse_html(self, text):
        """ parse_html: Properly formats any img tags that might be in content
            Args:
                text (str): text to parse
            Returns: string with properly formatted images
        """
        bs = BeautifulSoup(text, "html5lib")
        file_reg = re.compile(FILE_REGEX, flags=re.IGNORECASE)
        tags = bs.findAll('img')

        for tag in tags:
            # Look for src attribute, remove formatting if added to image
            src_text = tag.get("src") or ""
            formatted_src_match = file_reg.search(src_text)
            src_text = formatted_src_match.group(2) if formatted_src_match else src_text

            alt_text = tag.get("alt") or ""
            tag.replaceWith("![{alt}]({src})".format(alt=alt_text, src=src_text))
        return html.unescape(bs.find('body').renderContents().decode('utf-8'))

    def set_image(self, text):
        """ set_image: Replace image string with downloaded image checksum
            Args:
                text (str): text to parse for image strings
            Returns:string with checksums in place of image strings and
                list of files that were downloaded from string
        """
        # Make sure image hasn't already been replaced
        if exercises.CONTENT_STORAGE_PLACEHOLDER in text:
            return text, []

        # Set up return values and regex
        exercise_file = None
        path_text = text.strip().replace('\\n', '')
        graphie_reg = re.compile(WEB_GRAPHIE_URL_REGEX, flags=re.IGNORECASE)
        graphie_match = graphie_reg.match(path_text)
        # If it is a web+graphie, download svg and json files,
        # Otherwise, download like other files
        if graphie_match:
            path_text = graphie_match.group().replace("web+graphie://", "https://")
            exercise_file = _ExerciseGraphieFile(path_text)
        elif get_base64_encoding(text):
            exercise_file = _ExerciseBase64ImageFile(path_text)
        else:
            exercise_file = _ExerciseImageFile(path_text)

        exercise_file.assessment_item = self
        filename = exercise_file.process_file()

        text = text.replace(path_text, exercises.CONTENT_STORAGE_FORMAT.format(exercise_file.get_replacement_str()))

        return text, [exercise_file]

    def validate(self):
        """ validate: Makes sure question is valid
            Args: None
            Returns: boolean indicating if question is valid
        """
        assert self.id is not None, "Assumption Failed: Question must have an id"
        assert isinstance(self.question, str) or self.question is None, "Assumption Failed: Question must be a string"
        assert isinstance(self.question_type, str), "Assumption Failed: Question type must be a string"
        assert isinstance(self.answers, list), "Assumption Failed: Answers must be a list"
        assert isinstance(self.hints, list), "Assumption Failed: Hints must be a list"
        for a in self.answers:
            assert isinstance(a, dict), "Assumption Failed: Answer in answer list is not a dict"
        for h in self.hints:
            assert isinstance(h, str), "Assumption Failed: Hint in hints list is not a string"
        return True


class PerseusQuestion(BaseQuestion):
    """ Model representing perseus questions

        Perseus questions have already been formatted to the
        .perseus format and can therefore be created with just
        raw data (no need to parse the data)

        Attributes:
            id (str): question's unique id
            raw_data (str): pre-formatted perseus question
            images ({key:str, ...}): a dict mapping image string to replace to path to image
    """

    def __init__(self, id, raw_data, source_url=None, **kwargs):
        raw_data = raw_data if isinstance(raw_data, str) else json.dumps(raw_data)
        super(PerseusQuestion, self).__init__(id, "", exercises.PERSEUS_QUESTION, [], [], raw_data, source_url=source_url, **kwargs)

    def validate(self):
        """ validate: Makes sure perseus question is valid
            Args: None
            Returns: boolean indicating if perseus question is valid
        """
        try:
            assert self.question == "", "Assumption Failed: Perseus question should not have a question"
            assert self.question_type == exercises.PERSEUS_QUESTION, "Assumption Failed: Question should be perseus type"
            assert self.answers == [], "Assumption Failed: Answer list should be empty for perseus question"
            assert self.hints == [], "Assumption Failed: Hints list should be empty for perseus question"
            return super(PerseusQuestion, self).validate()
        except AssertionError as ae:
            raise InvalidQuestionException("Invalid question: {0}".format(self.__dict__))

    def process_question(self):
        """ process_question: Parse data that needs to have image strings processed
            Args: None
            Returns: list of all downloaded files
        """
        image_files = []
        image_data = json.loads(self.raw_data)

        # process urls for widgets
        self._recursive_url_find(image_data, image_files)

        # Process question
        if 'question' in image_data and 'images' in image_data['question']:
            image_data['question']['images'], qfiles = self.process_image_field(image_data['question'])
            image_files += qfiles

        # Process hints
        if 'hints' in image_data:
            for hint in image_data['hints']:
                if 'images' in hint:
                    hint['images'], hfiles = self.process_image_field(hint)
                    image_files += hfiles

        # Process answers
        if 'answers' in image_data:
            for answer in image_data['answers']:
                if 'images' in answer:
                    answer['images'], afiles = self.process_image_field(answer)
                    image_files += afiles

        # Process raw data
        self.raw_data = json.dumps(image_data, ensure_ascii=False)
        self.raw_data, data_files = super(PerseusQuestion, self).set_images(self.raw_data)

        # Return all files
        self.files += image_files + data_files
        return [f.filename for f in self.files]

    def process_image_field(self, data):
        """ process_image_field: Specifically process perseus question image field
            Args:
                data (dict): data that contains 'images' field
            Returns: list of all downloaded files
        """
        files = []

        new_data = copy.deepcopy(data['images'])
        for k, v in data['images'].items():
            new_key, fs = self.set_image(k)
            files += fs
            new_data[new_key] = new_data.pop(k)
        return new_data, files

    def _recursive_url_find(self, item, image_list):
        """ Utility function specifically for Khan Academy assessment items. Recursively iterates item
            to find and replace all url image tags.
            Args:
                item (dict): KA assessment item
                image_list (list): list of image file objects
            Returns: None
        """

        recursive_fn = partial(self._recursive_url_find, image_list=image_list)

        if isinstance(item, list):
            list(map(recursive_fn, item))

        elif isinstance(item, dict):
            if 'url' in item:
                if item['url']:
                    item['url'], image_file = self.set_image(item['url'])
                    image_list += image_file

            for field, field_data in item.items():
                if isinstance(field_data, dict):
                    self._recursive_url_find(field_data, image_list)
                elif isinstance(field_data, list):
                    list(map(recursive_fn, field_data))


class MultipleSelectQuestion(BaseQuestion):
    """ Model representing multiple select questions

        Multiple select questions have a set of answers for
        the learner to select. There can be multiple answers for
        a question (e.g. Which of the following are prime numbers?
        A. 1, B. 2, C. 3, D. 4)

        Attributes:
            id (str): question's unique id
            question (str): question text
            correct_answers ([str]): list of correct answers
            all_answers ([str]): list of all possible answers
            hints ([str]): optional hints on how to answer question
            images ({key:str, ...}): a dict mapping image placeholder names to path to image
    """

    def __init__(self, id, question, correct_answers, all_answers, **kwargs):
        # Put answers into standard format
        set_all_answers = set(all_answers)
        all_answers += [answer for answer in correct_answers if answer not in set_all_answers]
        answers = [self.create_answer(answer, answer in correct_answers) for answer in all_answers]
        if len(answers) == 0:
            answers = [self.create_answer('No answers provided.')]
            config.LOGGER.warning("\tWARNING: Question {id} does not have any answers (set to default)".format(id=id))
        super(MultipleSelectQuestion, self).__init__(id, question, exercises.MULTIPLE_SELECTION, answers, **kwargs)

    def validate(self):
        """ validate: Makes sure multiple selection question is valid
            Args: None
            Returns: boolean indicating if multiple selection question is valid
        """
        try:
            assert self.question_type == exercises.MULTIPLE_SELECTION, "Assumption Failed: Question should be multiple selection type"
            assert len(self.answers) > 0, "Assumption Failed: Multiple selection question should have answers"
            for a in self.answers:
                assert 'answer' in a and isinstance(a['answer'], str), "Assumption Failed: Answer in answer list is not a string"
                assert 'correct' in a and isinstance(a['correct'], bool), "Assumption Failed: Correct indicator is not a boolean in answer list"
            for h in self.hints:
                assert isinstance(h, str), "Assumption Failed: Hint in hint list is not a string"
            return super(MultipleSelectQuestion, self).validate()
        except AssertionError as ae:
            raise InvalidQuestionException("Invalid question: {0}".format(self.__dict__))


class SingleSelectQuestion(BaseQuestion):
    """ Model representing single select questions

        Single select questions have a set of answers for
        with only one correct answer. (e.g. How many degrees are in a right angle?
        A. 45, B. 90, C. 180, D. None of the above)

        Attributes:
            id (str): question's unique id
            question (str): question text
            correct_answer (str): correct answer
            all_answers ([str]): list of all possible answers
            hints ([str]): optional hints on how to answer question
    """
    def __init__(self, id, question, correct_answer, all_answers, **kwargs):
        # Put answers into standard format
        if correct_answer not in all_answers:
            all_answers += [correct_answer]
        answers = [self.create_answer(answer, answer==correct_answer) for answer in all_answers]
        if len(answers) == 0:
            answers = [self.create_answer('No answers provided.')]
            config.LOGGER.warning("\tWARNING: Question {id} does not have any answers (set to default)".format(id=id))
        super(SingleSelectQuestion, self).__init__(id, question, exercises.SINGLE_SELECTION, answers, **kwargs)

    def validate(self):
        """ validate: Makes sure single selection question is valid
            Args: None
            Returns: boolean indicating if single selection question is valid
        """
        try:
            assert self.question_type == exercises.SINGLE_SELECTION, "Assumption Failed: Question should be single selection type"
            assert len(self.answers) > 0, "Assumption Failed: Multiple selection question should have answers"
            correct_answers = 0
            for a in self.answers:
                assert 'answer' in a and isinstance(a['answer'], str), "Assumption Failed: Answer in answer list is not a string"
                assert 'correct' in a and isinstance(a['correct'], bool), "Assumption Failed: Correct indicator is not a boolean in answer list"
                correct_answers += 1 if a['correct'] else 0
            assert correct_answers == 1, "Assumption Failed: Single selection question should have only one correct answer"
            for h in self.hints:
                assert isinstance(h, str), "Assumption Failed: Hint in hints list is not a string"
            return super(SingleSelectQuestion, self).validate()
        except AssertionError as ae:
            raise InvalidQuestionException("Invalid question: {0}".format(self.__dict__))


class InputQuestion(BaseQuestion):
    """ Model representing input questions

        Input questions are questions that have one or more
        answers (e.g. Name a factor of 10. ____)

        Attributes:
            id (str): question's unique id
            question (str): question text
            answers ([{'answer':str, 'hint':str}]): answers to question
            hints ([str]): optional hints on how to answer question
            images ({key:str, ...}): a dict mapping image placeholder names to path to image
    """
    def __init__(self, id, question, answers, **kwargs):
        answers = [self.create_answer(answer) for answer in answers]
        if len(answers) == 0:
            answers = [self.create_answer('No answers provided.')]
            config.LOGGER.warning("\tWARNING: Question {id} does not have any answers (set to default)".format(id=id))
        super(InputQuestion, self).__init__(id, question, exercises.INPUT_QUESTION, answers, **kwargs)

    def validate(self):
        """ validate: Makes sure input question is valid
            Args: None
            Returns: boolean indicating if input question is valid
        """
        try:
            assert self.question_type == exercises.INPUT_QUESTION, "Assumption Failed: Question should be input answer type"
            assert len(self.answers) > 0, "Assumption Failed: Multiple selection question should have answers"
            for a in self.answers:
                assert 'answer' in a, "Assumption Failed: Answers must have an answer field"
                try:
                    float(a['answer'])
                except ValueError:
                    assert False, "Assumption Failed: Answer {} must be numeric".format(a['answer'])
            for h in self.hints:
                assert isinstance(h, str), "Assumption Failed: Hint in hints list is not a string"
            return super(InputQuestion, self).validate()
        except AssertionError as ae:
            raise InvalidQuestionException("Invalid question: {0}".format(self.__dict__))
