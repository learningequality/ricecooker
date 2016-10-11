import uuid
import json
from ricecooker.classes.nodes import download_file
from le_utils.constants import content_kinds,file_formats, format_presets, licenses, exercises
from ricecooker.exceptions import UnknownQuestionTypeError, InvalidInputAnswerException

def download_image(path):
    filename, original_filename, path, file_size = download_file(path, '.{}'.format(file_formats.PNG))
    return '![]' + exercises.IMG_FORMAT.format(filename), filename, original_filename, path, file_size

class BaseQuestion:
    """ Base model representing exercise questions

        Questions are used to assess learner's understanding

        Attributes:
            id (str): question's unique id
            question (str): question text
            question_type (str): what kind of question is this
            answers ([{'answer':str, 'correct':bool, 'hint':str}]): answers to question
            hint (str): optional hint on how to answer question
            images ({key:str, ...}): a dict mapping image placeholder names to path to image
    """
    def __init__(self, id, question, question_type, answers=None, hint=None, images=None, raw_data=""):
        self.question = question
        self.question_type = question_type
        self.answers = answers if answers is not None else []
        self.hint = [] if hint is None else [hint] if isinstance(hint,str) else hint
        self._file_mapping = {}
        self.files = []
        self.raw_data = raw_data
        self.images = {} if images is None else self.download_images(images)
        self.id = uuid.uuid5(uuid.NAMESPACE_DNS, id)
        print(json.dumps([{"answer": self.map_images(answer['answer']), "correct":answer['correct']} for answer in self.answers], ensure_ascii=False).encode('utf-8'))

    def to_dict(self):
        """ to_dict: puts data in format CC expects
            Args: None
            Returns: dict of node's data
        """
        return {
            "assessment_id": self.id.hex,
            "type": self.question_type,
            "question": self.map_images(self.question),
            "hint": self.hint if self.hint is not None else "",
            "answers": json.dumps([{"answer": self.map_images(answer['answer']), "correct":answer['correct']} for answer in self.answers], ensure_ascii=False),
            "raw_data": self.raw_data,
        }

    def create_answer(self, answer, correct=True):
        return {"answer": str(answer), "correct":correct}

    def download_images(self, images):
        for key in images:
            formatted_name, filename, original_filename, path, file_size = download_image(images[key])
            images[key] = formatted_name
            self.files += [filename]
            self._file_mapping.update({filename : {'original_filename': original_filename, 'source_url': path, 'size': file_size, 'preset': False}})
        return images

    def map_images(self, text):
        try:
            mapping = self.images if self.images is not None else {}
            return text.format(**mapping)
        except KeyError:
            raise ObjectDoesNotExist("Missing key from images: {} (use double braces for text if not an image)".format(mapping))

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

    def __init__(self, id, raw_data, images=None):
        raw_data = raw_data if isinstance(raw_data, str) else json.dumps(raw_data)
        super(PerseusQuestion, self).__init__(id, "", exercises.PERSEUS_QUESTION, [], [], images, raw_data)

    def download_images(self, images):
        for key in images:
            formatted_name, filename, original_filename, path, file_size = download_image(images[key])
            images[key] = formatted_name
            self.files += [filename]
            self._file_mapping.update({filename : {'original_filename': original_filename, 'source_url': path, 'size': file_size, 'preset': False}})
            self.raw_data = self.raw_data.replace(key, formatted_name)
        return images

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

    def __init__(self, id, question, correct_answers, all_answers, hint="", images=None):
        set_all_answers = set(all_answers)
        all_answers += [answer for answer in correct_answers if answer not in set_all_answers]
        answers = [self.create_answer(answer, answer in correct_answers) for answer in all_answers]
        super(MultipleSelectQuestion, self).__init__(id, question, exercises.MULTIPLE_SELECTION, answers, hint, images)

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
    def __init__(self, id, question, correct_answer, all_answers, hint="", images=None):
        if correct_answer not in all_answers:
            all_answers += [correct_answer]
        answers = [self.create_answer(answer, answer==correct_answer) for answer in all_answers]
        super(SingleSelectQuestion, self).__init__(id, question, exercises.SINGLE_SELECTION, answers, hint, images)

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
    def __init__(self, id, question, hint="", images=None):
        super(FreeResponseQuestion, self).__init__(id, question, exercises.FREE_RESPONSE, [], hint, images)

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
    def __init__(self, id, question, answers, hint="", images=None):
        answers = [self.create_answer(answer) for answer in answers]
        super(InputQuestion, self).__init__(id, question, exercises.INPUT_QUESTION, answers, hint, images)