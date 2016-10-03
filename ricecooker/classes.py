import uuid
import hashlib
import base64
import requests
import validators
import json
import tempfile
from PIL import Image
from io import BytesIO
from le_utils.constants import content_kinds,file_formats, format_presets, licenses, exercises
from ricecooker.exceptions import UnknownQuestionTypeError, InvalidInputAnswerException

def guess_content_kind(files, questions=[]):
    """ guess_content_kind: determines what kind the content is
        Args:
            files (str or list): files associated with content
        Returns: string indicating node's kind
    """
    files = [files] if isinstance(files, str) else files
    questions=[questions] if isinstance(questions, str) else questions
    if files is not None and len(files) > 0:
        for f in files:
            ext = f.rsplit('/', 1)[-1].split(".")[-1].lower()
            if ext in content_kinds.MAPPING:
                return content_kinds.MAPPING[ext]
        raise InvalidFormatException("Invalid file type: Allowed formats are {0}".format([key for key, value in content_kinds.MAPPING.items()]))
    elif questions is not None and len(questions) > 0:
        return content_kinds.EXERCISE
    else:
        return content_kinds.TOPIC

""" TreeModel: model to handle structure of channel """
class TreeModel:
    def __init__(self):
        self.children = []

    """ to_dict: formats data to what CC expects
        @return dict of model's data
    """
    def to_dict(self):
        pass

    """ add_child: adds children to root node
        @param node (node to add to children)
    """
    def add_child(self, node):
        self.children += [node]


class Channel(TreeModel):
    """ Model representing the channel you are creating

        Used to store metadata on channel that is being created

        Attributes:
            channel_id (str): channel's unique id
            domain (str): who is providing the content (e.g. learningequality.org)
            title (str): name of channel
            thumbnail (str): file path or url of channel's thumbnail
            description (str): description of the channel
    """
    def __init__(self, channel_id, domain=None, title=None, thumbnail=None, description=None):
        self.domain = domain
        self.id = uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid5(uuid.NAMESPACE_DNS, channel_id).hex)
        self.name = title
        self.thumbnail = self.encode_thumbnail(thumbnail)
        self.description = description

        # Add data to be used in next steps
        self._internal_domain = uuid.uuid5(uuid.NAMESPACE_DNS, self.domain)
        self.content_id = uuid.uuid5(self._internal_domain, self.id.hex)
        self.node_id = uuid.uuid5(self.id, self.content_id.hex)
        super(Channel, self).__init__()


    def to_dict(self):
        """ to_dict: puts data in format CC expects
            Args: None
            Returns: dict of channel data
        """
        return {
            "id": self.id.hex,
            "name": self.name,
            "has_changed": True,
            "thumbnail": self.thumbnail,
            "description": self.description if self.description is not None else "",
            "children": [child_node.to_dict() for child_node in self.children],
        }


    def encode_thumbnail(self, thumbnail):
        """ encode_thumbnail: gets base64 encoding of thumbnail
            Args:
                thumbnail (str): file path or url to channel's thumbnail
            Returns: base64 encoding of thumbnail
        """
        if thumbnail is None:
            return None
        else:
            if validators.url(thumbnail):
                r = requests.get(thumbnail, stream=True)
                if r.status_code == 200:
                    thumbnail = tempfile.TemporaryFile()
                    for chunk in r:
                        thumbnail.write(chunk)

            img = Image.open(thumbnail)
            width = 200
            height = int((float(img.size[1])*float(width/float(img.size[0]))))
            img.thumbnail((width,height), Image.ANTIALIAS)
            bufferstream = BytesIO()
            img.save(bufferstream, format="PNG")
            return "data:image/png;base64," + base64.b64encode(bufferstream.getvalue()).decode('utf-8')



class Node(TreeModel):
    """ Model representing the nodes in the channel's tree

        Base model for different content node kinds (topic, video, exercise, etc.)

        Attributes:
            id (str): content's original id
            title (str): content's title
            description (str): description of content
            author (str): who created the content
            license (str): content's license (using constants from fle_utils)
            files (str or list): content's associated file(s)
    """
    def __init__(self, id, title, description, author, license=None, files=[], questions=[], extra_fields={}):
        self.id = id
        self.title = title
        self.description = description
        self.author = author
        self.license = license
        self.children = []
        self.files = [files] if isinstance(files, str) else files
        self.questions=questions
        self.extra_fields = extra_fields
        super(Node, self).__init__()


    def to_dict(self):
        """ to_dict: puts data in format CC expects
            Args: None
            Returns: dict of node's data
        """
        return {
            "title": self.title,
            "description": self.description if self.description is not None else "",
            "node_id": self.node_id.hex,
            "content_id": self.content_id.hex,
            "author": self.author if self.author is not None else "",
            "children": [child_node.to_dict() for child_node in self.children],
            "files" : self.files,
            "kind": self.kind,
            "license": self.license,
            "questions": self.questions,
            "extra_fields": json.dumps(self.extra_fields),
        }

    def set_ids(self, domain, parent_id):
        """ set_ids: sets ids to be used in building tree
            Args:
                domain (uuid): uuid of channel domain
                parent_id (uuid): parent node's node_id
            Returns: None
        """
        self.content_id = uuid.uuid5(domain, self.id)
        self.node_id = uuid.uuid5(parent_id, self.content_id.hex)



class Topic(Node):
    """ Model representing channel topics

        Topic nodes are used to add organization to the channel's content

        Attributes:
            id (str): content's original id
            title (str): content's title
            description (str): description of content
            author (str): who created the content
    """
    def __init__(self, id, title, description=None, author=None):
        self.kind = content_kinds.TOPIC
        super(Topic, self).__init__(id, title, description, author)



class Video(Node):
    """ Model representing videos in channel

        Videos must be mp4 format

        Attributes:
            id (str): content's original id
            title (str): content's title
            author (str): who created the content
            description (str): description of content
            transcode_to_lower_resolutions (bool): indicates whether to extract lower resolution
            derive_thumbnail (bool): indicates whether to derive thumbnail from video
            preset (str): default preset for files
            subtitle (str): path or url to file's subtitles
            license (str): content's license (using constants from fle_utils)
            files (str or list): content's associated file(s)
    """
    default_preset = format_presets.VIDEO_HIGH_RES
    def __init__(self, id, title, author=None, description=None, transcode_to_lower_resolutions=False, derive_thumbnail=False, license=None, subtitle=None, files=[], preset=None):
        if preset is not None:
            self.default_preset = preset
        if transcode_to_lower_resolutions:
            self.transcode_to_lower_resolutions()
        if derive_thumbnail:
            self.derive_thumbnail()
        self.kind = content_kinds.VIDEO
        super(Video, self).__init__(id, title, description, author, license, files)

    def derive_thumbnail(self):
        """ derive_thumbnail: derive video's thumbnail
            Args: None
            Returns: None
        """
        pass

    def transcode_to_lower_resolutions(self):
        """ transcode_to_lower_resolutions: transcode video to lower resolution
            Args: None
            Returns: None
        """
        pass



class Audio(Node):
    """ Model representing audio content in channel

        Audio can be in either mp3 or wav format

        Attributes:
            id (str): content's original id
            title (str): content's title
            author (str): who created the content
            description (str): description of content
            subtitle (str): path or url to file's subtitles
            license (str): content's license (using constants from fle_utils)
            files (str or list): content's associated file(s)
    """
    default_preset = format_presets.AUDIO
    def __init__(self, id, title, author=None, description=None, license=None, subtitle=None, files=[]):
        self.kind = content_kinds.AUDIO
        super(Audio, self).__init__(id, title, description, author, license, files)



class Document(Node):
    """ Model representing documents in channel

        Documents must be pdf format

        Attributes:
            id (str): content's original id
            title (str): content's title
            author (str): who created the content
            description (str): description of content
            license (str): content's license (using constants from fle_utils)
            files (str or list): content's associated file(s)
    """
    default_preset = format_presets.DOCUMENT
    def __init__(self, id, title, author=None, description=None, license=None, files=[]):
        self.kind = content_kinds.DOCUMENT
        super(Document, self).__init__(id, title, description, author, license, files)



class Exercise(Node):
    """ Model representing exercises in channel

        Exercises are sets of questions to assess learners'
        understanding of the content

        Attributes:
            id (str): content's original id
            title (str): content's title
            author (str): who created the content
            description (str): description of content
            license (str): content's license (using constants from fle_utils)
            files (str or list): content's associated file(s)
    """
    default_preset = format_presets.EXERCISE
    def __init__(self, id, title, author=None, description=None, license=None, files=None, exercise_data=None):
        self.kind = content_kinds.EXERCISE
        self.questions = []
        files = [] if files is None else files
        exercise_data = {} if exercise_data is None else exercise_data
        super(Exercise, self).__init__(id, title, description, author, license, files, self.questions, exercise_data)

    def add_question(self, question):
        self.questions += [question.to_dict()]

class PerseusExercise(Exercise):
    """ Model representing exercises in channel

        Exercises that are in perseus format

        Attributes:
            id (str): content's original id
            title (str): content's title
            author (str): who created the content
            description (str): description of content
            license (str): content's license (using constants from fle_utils)
            files (str or list): content's associated file(s)
    """
    default_preset = format_presets.EXERCISE
    def __init__(self, id, title, author=None, description=None, license=None, files=None, exercise_data=None):
        super(PerseusExercise, self).__init__(id, title, description, author, license, files, exercise_data)

class BaseQuestion:
    """ Base model representing exercise questions

        Questions are used to assess learner's understanding

        Attributes:
            id (str): question's unique id
            question (str): question text
            question_type (str): what kind of question is this
            answers ([{'answer':str, 'correct':bool, 'hint':str}]): answers to question
            hint (str): optional hint on how to answer question
            images ([str]): list of paths to images in question
    """
    def __init__(self, id, question, question_type, answers, hint="", images=None):
        self.question = question
        self.question_type = question_type
        self.answers = answers
        self.hint = hint
        self.images = [] if images is None else images
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
            "help_text": self.hint if self.hint is not None else "",
            "answers": json.dumps(self.answers),
        }

    def create_answer(self, answer, correct=True):
        return {"answer": answer, "correct":correct}

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
            images ([str]): list of paths to images in question
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
            images ([str]): list of paths to images in question
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
            images ([str]): list of paths to images in question
    """
    def __init__(self, id, question, hint="", images=None):
        super(FreeResponseQuestion, self).__init__(id, question, exercises.FREE_RESPONSE, [], hint, images)

class InputQuestion(BaseQuestion):
    """ Model representing input questions

        Input questions are questions that have one or more numerical
        answers (e.g. Name a factor of 10. ____)

        Attributes:
            id (str): question's unique id
            question (str): question text
            answers ([{'answer':str, 'hint':str}]): answers to question
            hint (str): optional hint on how to answer question
            images ([str]): list of paths to images in question
    """
    def __init__(self, id, question, answers, hint="", images=None):
        try:
            answers = [self.create_answer(answer) for answer in answers]
            super(InputQuestion, self).__init__(id, question, exercises.INPUT_QUESTION, answers, hint, images)
        except ValueError as e:
            raise InvalidInputAnswerException(e)
