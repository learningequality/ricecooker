# Question models for exercises

import uuid
import json
import re
from le_utils.constants import content_kinds,file_formats, format_presets, licenses, exercises
from ricecooker.exceptions import UnknownQuestionTypeError, InvalidQuestionException

WEB_GRAPHIE_URL_REGEX = r'web\+graphie:([^\)]+)'
FILE_REGEX = r'!\[([^\]]+)?\]\(([^\)]+)\)'

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
    def __init__(self, id, question, question_type, answers=None, hints=None, raw_data=""):
        self.question = question
        self.question_type = question_type
        self.answers = answers if answers is not None else []
        self.hints = [] if hints is None else [hints] if isinstance(hints,str) else hints
        self.raw_data = raw_data
        self.id = uuid.uuid5(uuid.NAMESPACE_DNS, id)

    def to_dict(self):
        """ to_dict: puts data in format CC expects
            Args: None
            Returns: dict of node's data
        """
        return {
            "assessment_id": self.id.hex,
            "type": self.question_type,
            "question": self.question,
            "hints": json.dumps(self.hints, ensure_ascii=False),
            "answers": json.dumps(self.answers, ensure_ascii=False),
            "raw_data": self.raw_data,
        }

    def create_answer(self, answer, correct=True):
        """ create_answer: Put answer in standard format
            Args:
                answer (str): text of answer
                correct (bool): indicates if answer is correct
            Returns: dict of formatted answer
        """
        return {"answer": str(answer), "correct":correct}

    def process_question(self, downloader):
        """ process_question: Parse data that needs to have image strings processed
            Args:
                downloader (DownloadManager): download manager to download images
            Returns: list of all downloaded files
        """
        # Process question
        self.question, question_files = self.set_images(self.question, downloader)

        # Process answers
        answers = []
        answer_files = []
        for answer in self.answers:
            processed_string, afiles = self.set_images(answer['answer'], downloader)
            answers += [{"answer": processed_string, "correct":answer['correct']}]
            answer_files += afiles
        self.answers = answers

        # Process hints
        hints = []
        hint_files = []
        for hint in self.hints:
            processed_string, hfiles = self.set_images(hint, downloader)
            hints += [{"hint":processed_string}]
            hint_files += hfiles
        self.hints = hints

        # Return all files
        return question_files + answer_files + hint_files

    def set_images(self, text, downloader):
        """ set_images: Replace image strings with downloaded image checksums
            Args:
                text (str): text to parse for image strings
                downloader (DownloadManager): download manager to download images
            Returns:string with checksums in place of image strings and
                list of files that were downloaded from string
        """
        # Set up return values and regex
        file_list = []
        processed_string = text
        reg = re.compile(FILE_REGEX, flags=re.IGNORECASE)
        graphie_reg = re.compile(WEB_GRAPHIE_URL_REGEX, flags=re.IGNORECASE)
        matches = reg.findall(processed_string)

        # Parse all matches
        for match in matches:
            # If it is a web+graphie, download svg and json files,
            # Otherwise, download like other files
            graphie_match = graphie_reg.match(match[1])
            if graphie_match is not None:
                link = graphie_match.group().replace("web+graphie:", "")
                filename, svg_filename, json_filename = downloader.download_graphie(link)
                processed_string = processed_string.replace(link, exercises.CONTENT_STORAGE_FORMAT.format(filename))
                file_list += [svg_filename, json_filename]
            else:
                filename = downloader.download_file(match[1], preset=format_presets.EXERCISE_IMAGE)
                processed_string = processed_string.replace(match[1], exercises.CONTENT_STORAGE_FORMAT.format(filename))
                file_list += [filename]
        return processed_string, file_list

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
            assert isinstance(h, str), "Assumption Failed: Hint in hint list is not a string"
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

    def __init__(self, id, raw_data):
        raw_data = raw_data if isinstance(raw_data, str) else json.dumps(raw_data)
        super(PerseusQuestion, self).__init__(id, "", exercises.PERSEUS_QUESTION, [], [], raw_data)

    def validate(self):
        """ validate: Makes sure perseus question is valid
            Args: None
            Returns: boolean indicating if perseus question is valid
        """
        try:
            assert self.question == "", "Assumption Failed: Perseus question should not have a question"
            assert self.question_type == exercises.PERSEUS_QUESTION, "Assumption Failed: Question should be perseus type"
            assert self.answers == [], "Assumption Failed: Answer list should be empty for perseus question"
            assert self.hints == [], "Assumption Failed: Hint list should be empty for perseus question"
            return super(PerseusQuestion, self).validate()
        except AssertionError as ae:
            raise InvalidQuestionException("Invalid question: {0}".format(self.__dict__))

    def process_question(self, downloader):
        """ process_question: Parse data that needs to have image strings processed
            Args:
                downloader (DownloadManager): download manager to download images
            Returns: list of all downloaded files
        """
        image_files=[]
        image_data = json.loads(self.raw_data)

        # Process question
        if 'question' in image_data:
            image_data['question']['images'], qfiles = self.process_image_field(image_data['question'], downloader)
            image_files += qfiles

        # Process hints
        if 'hints' in image_data:
            for hint in image_data['hints']:
                hint['images'], hfiles = self.process_image_field(hint, downloader)
                image_files += hfiles

        # Process answers
        if 'answers' in image_data:
            for answer in image_data['answers']:
                answer['images'], afiles = self.process_image_field(answer, downloader)
                image_files += afiles

        # Process raw data
        self.raw_data = json.dumps(image_data)
        self.raw_data, data_files = super(PerseusQuestion, self).set_images(self.raw_data, downloader)

        # Return all files
        return image_files + data_files

    def process_image_field(self, data, downloader):
        """ process_image_field: Specifically process perseus question image field
            Args:
                data (dict): data that contains 'images' field
                downloader (DownloadManager): download manager to download images
            Returns: list of all downloaded files
        """
        files = []
        new_data = data['images']
        for k, v in data['images'].items():
            new_key, fs = self.set_image(k, downloader)
            files += fs
            new_data[new_key] = new_data.pop(k)
        return new_data, files

    def set_image(self, text, downloader):
        """ set_images: Replace image strings with downloaded image checksums
            Args:
                text (str): text to parse for image strings
                downloader (DownloadManager): download manager to download images
            Returns:string with checksums in place of image strings and
                list of files that were downloaded from string
        """
        # Set up return values and regex
        file_list = []
        graphie_reg = re.compile(WEB_GRAPHIE_URL_REGEX, flags=re.IGNORECASE)
        graphie_match = graphie_reg.match(text)
        # If it is a web+graphie, download svg and json files,
        # Otherwise, download like other files
        if graphie_match is not None:
            link = graphie_match.group().replace("web+graphie:", "")
            filename, svg_filename, json_filename = downloader.download_graphie(link)
            text = text.replace(link, exercises.CONTENT_STORAGE_FORMAT.format(filename))
            file_list += [svg_filename, json_filename]
        else:
            filename = downloader.download_file(text, preset=format_presets.EXERCISE_IMAGE)
            text = text.replace(text, exercises.CONTENT_STORAGE_FORMAT.format(filename))
            file_list += [filename]
        return text, file_list

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
            hint (str): optional hint on how to answer question
            images ({key:str, ...}): a dict mapping image placeholder names to path to image
    """

    def __init__(self, id, question, correct_answers, all_answers, hints=None):
        hints = [] if hints is None else hints

        # Put answers into standard format
        set_all_answers = set(all_answers)
        all_answers += [answer for answer in correct_answers if answer not in set_all_answers]
        answers = [self.create_answer(answer, answer in correct_answers) for answer in all_answers]
        super(MultipleSelectQuestion, self).__init__(id, question, exercises.MULTIPLE_SELECTION, answers, hints)

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
            hint (str): optional hint on how to answer question
    """
    def __init__(self, id, question, correct_answer, all_answers, hints=None):
        hints = [] if hints is None else hints

        # Put answers into standard format
        if correct_answer not in all_answers:
            all_answers += [correct_answer]
        answers = [self.create_answer(answer, answer==correct_answer) for answer in all_answers]
        super(SingleSelectQuestion, self).__init__(id, question, exercises.SINGLE_SELECTION, answers, hints)

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
                assert isinstance(h, str), "Assumption Failed: Hint in hint list is not a string"
            return super(SingleSelectQuestion, self).validate()
        except AssertionError as ae:
            raise InvalidQuestionException("Invalid question: {0}".format(self.__dict__))


class FreeResponseQuestion(BaseQuestion):
    """ Model representing free response questions

        Free response questions are open-ended questions
        that have no set answer (e.g. Prove that the sum of
        every triangle's angles is 360 degrees.)

        Attributes:
            id (str): question's unique id
            question (str): question text
            hint (str): optional hint on how to answer question
    """
    def __init__(self, id, question, hints=None):
        hints = [] if hints is None else hints
        super(FreeResponseQuestion, self).__init__(id, question, exercises.FREE_RESPONSE, [], hints)

    def validate(self):
        """ validate: Makes sure free response question is valid
            Args: None
            Returns: boolean indicating if free response question is valid
        """
        try:
            assert self.question_type == exercises.FREE_RESPONSE, "Assumption Failed: Question should be free response type"
            for h in self.hints:
                assert isinstance(h, str), "Assumption Failed: Hint in hint list is not a string"
            assert self.answers == [], "Assumption Failed: Free response question should not have defined answers"
            return super(FreeResponseQuestion, self).validate()
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
            hint (str): optional hint on how to answer question
            images ({key:str, ...}): a dict mapping image placeholder names to path to image
    """
    def __init__(self, id, question, answers, hints=None):
        hints = [] if hints is None else hints
        answers = [self.create_answer(answer) for answer in answers]
        super(InputQuestion, self).__init__(id, question, exercises.INPUT_QUESTION, answers, hints)

    def validate(self):
        """ validate: Makes sure input question is valid
            Args: None
            Returns: boolean indicating if input question is valid
        """
        try:
            assert self.question_type == exercises.INPUT_QUESTION, "Assumption Failed: Question should be input answer type"
            assert len(self.answers) > 0, "Assumption Failed: Multiple selection question should have answers"
            for a in self.answers:
                assert 'answer' in a and isinstance(a['answer'], str), "Assumption Failed: Answer in answer list is not a string"
            for h in self.hints:
                assert isinstance(h, str), "Assumption Failed: Hint in hint list is not a string"
            return super(InputQuestion, self).validate()
        except AssertionError as ae:
            raise InvalidQuestionException("Invalid question: {0}".format(self.__dict__))