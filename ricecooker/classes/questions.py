import uuid
import json
import re
from le_utils.constants import content_kinds,file_formats, format_presets, licenses, exercises
from ricecooker.exceptions import UnknownQuestionTypeError, InvalidInputAnswerException, MissingKeyException

WEB_GRAPHIE_URL_REGEX = r'web\+graphie:([^\)]+)'
FILE_REGEX = r'!\[([^\]]+)?\]\(([^\)]+)\)'

class BaseQuestion:
    """ Base model representing exercise questions

        Questions are used to assess learner's understanding

        Attributes:
            id (str): question's unique id
            question (str): question text
            question_type (str): what kind of question is this
            answers ([{'answer':str, 'correct':bool, 'hint':str}]): answers to question
            hints (str or [str]): optional hints on how to answer question
            images ({key:str, ...}): a dict mapping image placeholder names to path to image
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
        return {"answer": str(answer), "correct":correct}

    def process_question(self, downloader):
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

        # Process raw data
        self.raw_data, data_files = self.set_images(self.raw_data, downloader)

        # Return all files
        return question_files + answer_files + hint_files + data_files

    def set_images(self, text, downloader):
        file_list = []
        processed_string = text
        reg = re.compile(FILE_REGEX, flags=re.IGNORECASE)
        graphie_reg = re.compile(WEB_GRAPHIE_URL_REGEX, flags=re.IGNORECASE)
        matches = reg.findall(processed_string)
        for match in matches:
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


class MultipleSelectQuestion(BaseQuestion):
    """ Model representing multiple select questions

        Multiple select questions have a set of answers for
        the learner to select. There can be multiple answers for
        a question (e.g. Which of the following are prime numbers?
        A. 1, B. 2, C. 3, D. 4)

        Attributes:
            id (str): question's unique id
            question (str): question text
            answers ([{'answer':str, 'correct':bool, 'hint':str}]): answers to question
            hint (str): optional hint on how to answer question
            images ({key:str, ...}): a dict mapping image placeholder names to path to image
    """

    def __init__(self, id, question, correct_answers, all_answers, hints=""):
        set_all_answers = set(all_answers)
        all_answers += [answer for answer in correct_answers if answer not in set_all_answers]
        answers = [self.create_answer(answer, answer in correct_answers) for answer in all_answers]
        super(MultipleSelectQuestion, self).__init__(id, question, exercises.MULTIPLE_SELECTION, answers, hints)

class SingleSelectQuestion(BaseQuestion):
    """ Model representing single select questions

        Single select questions have a set of answers for
        with only one correct answer. (e.g. How many degrees are in a right angle?
        A. 45, B. 90, C. 180, D. None of the above)

        Attributes:
            id (str): question's unique id
            question (str): question text
            answers ([{'answer':str, 'correct':bool, 'hint':str}]): answers to question
            hint (str): optional hint on how to answer question
            images ({key:str, ...}): a dict mapping image placeholder names to path to image
    """
    def __init__(self, id, question, correct_answer, all_answers, hints=""):
        if correct_answer not in all_answers:
            all_answers += [correct_answer]
        answers = [self.create_answer(answer, answer==correct_answer) for answer in all_answers]
        super(SingleSelectQuestion, self).__init__(id, question, exercises.SINGLE_SELECTION, answers, hints)

class FreeResponseQuestion(BaseQuestion):
    """ Model representing free response questions

        Free response questions are open-ended questions
        that have no set answer (e.g. Prove that the sum of
        every triangle's angles is 360 degrees.)

        Attributes:
            id (str): question's unique id
            question (str): question text
            hint (str): optional hint on how to answer question
            images ({key:str, ...}): a dict mapping image placeholder names to path to image
    """
    def __init__(self, id, question, hints=""):
        super(FreeResponseQuestion, self).__init__(id, question, exercises.FREE_RESPONSE, [], hints)

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
    def __init__(self, id, question, answers, hints=""):
        answers = [self.create_answer(answer) for answer in answers]
        super(InputQuestion, self).__init__(id, question, exercises.INPUT_QUESTION, answers, hints)