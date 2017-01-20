# Node models to represent channel's tree

import uuid
import json
import zipfile
import sys
from le_utils.constants import content_kinds,file_formats, format_presets, licenses, exercises
from ..exceptions import InvalidNodeException, InvalidFormatException
from ..managers.downloader import DownloadManager
from .. import config

def guess_content_kind(files, questions=None):
    """ guess_content_kind: determines what kind the content is
        Args:
            files (str or list): files associated with content
        Returns: string indicating node's kind
    """
    # Get files and questions into readable format
    files = [files] if isinstance(files, str) else files
    questions = [questions] if isinstance(questions, str) else questions

    # If there are any questions, return exercise
    if questions is not None and len(questions) > 0:
        return content_kinds.EXERCISE

    # See if any files match a content kind
    elif files is not None and len(files) > 0:
        for f in files:
            ext = f.rsplit('/', 1)[-1].split(".")[-1].lower()
            if ext in content_kinds.MAPPING:
                return content_kinds.MAPPING[ext]
        raise InvalidFormatException("Invalid file type: Allowed formats are {0}".format([key for key, value in content_kinds.MAPPING.items()]))

    # If there are no files/questions, return topic
    else:
        return content_kinds.TOPIC


class Node(object):
    """ Node: model to represent all nodes in the tree """
    def __init__(self):
        self.children = []
        self.parent = None

    def __str__(self):
        pass

    def to_dict(self):
        """ to_dict: puts data in format CC expects
            Args: None
            Returns: dict of channel data
        """
        pass

    def add_child(self, node):
        """ add_child: Adds child node to node
            Args: node to add as child
            Returns: None
        """
        assert isinstance(node, Node), "Child node must be a subclass of Node"
        node.parent = self
        self.children += [node]

    def count(self):
        """ count: get number of nodes in tree
            Args: None
            Returns: int
        """
        total = len(self.children)
        for child in self.children:
            total += child.count()
        return total

    def print_tree(self, indent=1):
        """ print_tree: prints out structure of tree
            Args: indent (int): What level of indentation at which to start printing
            Returns: None
        """
        config.LOGGER.info("{indent}{data}".format(indent="   " * indent, data=str(self)))
        for child in self.children:
            child.print_tree(indent + 1)

    def test_tree(self):
        """ test_tree: validate all nodes in this tree
            Args: None
            Returns: boolean indicating if tree is valid
        """
        self.validate()
        for child in self.children:
            assert child.test_tree()
        return True

    def validate(self):
        """ validate: Makes sure node is valid
            Args: None
            Returns: boolean indicating if node is valid
        """
        assert self.source_id is not None, "Assumption Failed: Node must have an id"
        assert isinstance(self.title, str), "Assumption Failed: Node title is not a string"
        assert isinstance(self.description, str) or self.description is None, "Assumption Failed: Node description is not a string"
        assert isinstance(self.children, list), "Assumption Failed: Node children is not a list"
        return True


class Channel(Node):
    """ Model representing the channel you are creating

        Used to store metadata on channel that is being created

        Attributes:
            source_id (str): channel's unique id
            source_domain (str): who is providing the content (e.g. learningequality.org)
            title (str): name of channel
            description (str): description of the channel (optional)
            thumbnail (str): file path or url of channel's thumbnail (optional)
    """
    thumbnail_preset = format_presets.CHANNEL_THUMBNAIL
    def __init__(self, source_id, source_domain, title, description="", thumbnail=None):
        # Map parameters to model variables
        self.source_domain = source_domain
        self.source_id = source_id
        self.title = title
        self.description = description
        self.thumbnail = thumbnail

        super(Channel, self).__init__()

    def get_domain_namespace(self):
        return uuid.uuid5(uuid.NAMESPACE_DNS, self.source_domain)

    def get_content_id(self):
        return uuid.uuid5(self.get_domain_namespace(), self.get_node_id().hex)

    def get_node_id(self):
        return uuid.uuid5(self.get_domain_namespace(), self.source_id)

    def __str__(self):
        count = self.count()
        metadata = "{0} {1}".format(count, "descendant" if count == 1 else "descendants")
        return "{title} ({kind}): {metadata}".format(title=self.title, kind=self.__class__.__name__, metadata=metadata)

    def to_dict(self):
        """ to_dict: puts data in format CC expects
            Args: None
            Returns: dict of channel data
        """
        return {
            "id": self.get_node_id().hex,
            "name": self.title,
            "thumbnail": self.thumbnail,
            "description": self.description if self.description is not None else "",
        }

    def validate(self):
        """ validate: Makes sure channel is valid
            Args: None
            Returns: boolean indicating if channel is valid
        """
        try:
            assert isinstance(self.source_domain, str), "Channel domain must be a string"
            assert isinstance(self.thumbnail, str) or self.thumbnail is None, "Channel thumbnail must be a string"
            return super(Channel, self).validate()
        except AssertionError as ae:
            raise InvalidNodeException("Invalid channel ({}): {} - {}".format(ae.args[0], self.title, self.__dict__))


class ContentNode(Node):
    """ Model representing the content nodes in the channel's tree

        Base model for different content node kinds (topic, video, exercise, etc.)

        Attributes:
            id (str): content's original id
            title (str): content's title
            description (str): description of content (optional)
            author (str): who created the content (optional)
            license (str): content's license based on le_utils.constants.licenses (optional)
            files (str or list): content's associated file(s)
            thumbnail (str): local path or url to thumbnail image (optional)
    """
    def __init__(self, source_id, title, description="", author="", files=None, thumbnail=None, license=None, questions=None, extra_fields=None, domain_ns=None):
        # Map parameters to model variables
        assert isinstance(source_id, str), "source_id must be a string"
        self.source_id = source_id
        self.title = title
        self.description = description or ""
        self.author = author or ""
        self.license = license
        self.domain_ns = domain_ns

        # Set files into list format (adding thumbnail if provided)
        self.files = files or []
        self.files = [self.files] if isinstance(self.files, str) else self.files
        self.thumbnail = thumbnail

        # Set any possible exercise data to standard format
        self.questions = questions or []
        self.extra_fields = extra_fields or {}
        super(ContentNode, self).__init__()

    def __str__(self):
        count = self.count()
        metadata = "{0} {1}".format(count, "descendant" if count == 1 else "descendants")
        return "{title} ({kind}): {metadata}".format(title=self.title, kind=self.__class__.__name__, metadata=metadata)

    def get_domain_namespace(self):
        if self.domain_ns:
            return self.domain_ns
        return self.parent.get_domain_namespace()

    def get_content_id(self):
        return uuid.uuid5(self.get_domain_namespace(), self.source_id)

    def get_node_id(self):
        assert self.parent, "Parent not found: node id must be calculated based on parent"
        return uuid.uuid5(self.parent.get_node_id(), self.get_content_id().hex)

    def to_dict(self):
        """ to_dict: puts data in format CC expects
            Args: None
            Returns: dict of node's data
        """
        return {
            "title": self.title,
            "description": self.description,
            "node_id": self.get_node_id().hex,
            "content_id": self.get_content_id().hex,
            "author": self.author,
            "files" : self.files,
            "kind": self.kind,
            "license": self.license,
            "questions": self.questions,
            "extra_fields": json.dumps(self.extra_fields),
        }

    def validate(self):
        """ validate: Makes sure content node is valid
            Args: None
            Returns: boolean indicating if content node is valid
        """
        assert isinstance(self.author, str) , "Assumption Failed: Author is not a string"
        assert isinstance(self.license, str) or self.license is None, "Assumption Failed: License is not a string or empty"
        assert isinstance(self.files, list), "Assumption Failed: Files is not a list"
        assert isinstance(self.questions, list), "Assumption Failed: Questions is not a list"
        assert isinstance(self.extra_fields, dict), "Assumption Failed: Extra fields is not a dict"
        return super(ContentNode, self).validate()


class Topic(ContentNode):
    """ Model representing channel topics

        Topic nodes are used to add organization to the channel's content

        Attributes:
            source_id (str): content's original id
            title (str): content's title
            description (str): description of content (optional)
            author (str): who created the content (optional)
    """
    def __init__(self, *args, **kwargs):
        self.kind = content_kinds.TOPIC
        super(Topic, self).__init__(*args, **kwargs)

    def __str__(self):
        count = self.count()
        metadata = "{0} {1}".format(count, "descendant" if count == 1 else "descendants")
        return "{title} ({kind}): {metadata}".format(title=self.title, kind=self.__class__.__name__, metadata=metadata)

    def validate(self):
        """ validate: Makes sure topic is valid
            Args: None
            Returns: boolean indicating if topic is valid
        """
        try:
            assert self.kind == content_kinds.TOPIC, "Assumption Failed: Node is supposed to be a topic"
            assert self.questions == [], "Assumption Failed: Topic nodes should not have questions"
            assert self.files == [], "Assumption Failed: Topic nodes should not have files"
            assert self.extra_fields == {}, "Assumption Failed: Node should have empty extra_fields"
            return super(Topic, self).validate()
        except AssertionError as ae:
            raise InvalidNodeException("Invalid node ({}): {} - {}".format(ae.args[0], self.title, self.__dict__))


class Video(ContentNode):
    """ Model representing videos in channel

        Videos must be mp4 format

        Attributes:
            source_id (str): content's original id
            title (str): content's title
            files (str or list): content's associated file(s)
            author (str): who created the content (optional)
            description (str): description of content (optional)
            transcode_to_lower_resolutions (bool): indicates whether to extract lower resolution (optional)
            derive_thumbnail (bool): indicates whether to derive thumbnail from video (optional)
            preset (str): default preset for files (optional)
            subtitle (str): path or url to file's subtitles (optional)
            license (str): content's license based on le_utils.constants.licenses (optional)
            thumbnail (str): local path or url to thumbnail image (optional)
    """
    default_preset = format_presets.VIDEO_HIGH_RES
    thumbnail_preset = format_presets.VIDEO_THUMBNAIL
    def __init__(self, source_id, title, files, preset=None, transcode_to_lower_resolutions=False, derive_thumbnail=False, **kwargs):
        self.kind = content_kinds.VIDEO
        self.derive_thumbnail = derive_thumbnail

        # If no preset is given, set to default
        if preset is not None:
            self.default_preset = preset

        # Transcode video to lower resoution
        if transcode_to_lower_resolutions:
            self.transcode_to_lower_resolutions()

        super(Video, self).__init__(source_id, title, files=files, **kwargs)

    def __str__(self):
        metadata = "{0} {1}".format(len(self.files), "file" if len(self.files) == 1 else "files")
        return "{title} ({kind}): {metadata}".format(title=self.title, kind=self.__class__.__name__, metadata=metadata)

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

    def validate(self):
        """ validate: Makes sure video is valid
            Args: None
            Returns: boolean indicating if video is valid
        """
        try:
            assert self.kind == content_kinds.VIDEO, "Assumption Failed: Node should be a video"
            assert self.questions == [], "Assumption Failed: Video should not have questions"
            assert len(self.files) > 0, "Assumption Failed: Video must have at least one video file"

            # Check if there are any .mp4 files
            files_valid = False
            for f in self.files:
                files_valid = files_valid or file_formats.MP4 in f
            assert files_valid , "Assumption Failed: Video should have at least one .mp4 file"

            return super(Video, self).validate()
        except AssertionError as ae:
            raise InvalidNodeException("Invalid node ({}): {} - {}".format(ae.args[0], self.title, self.__dict__))


class Audio(ContentNode):
    """ Model representing audio content in channel

        Audio can be in either mp3 or wav format

        Attributes:
            source_id (str): content's original id
            title (str): content's title
            files (str or list): content's associated file(s)
            author (str): who created the content (optional)
            description (str): description of content (optional)
            subtitle (str): path or url to file's subtitles (optional)
            license (str): content's license based on le_utils.constants.licenses (optional)
            thumbnail (str): local path or url to thumbnail image (optional)
    """
    thumbnail_preset = format_presets.AUDIO_THUMBNAIL
    default_preset = format_presets.AUDIO
    def __init__(self, *args, **kwargs):
        self.kind = content_kinds.AUDIO
        super(Audio, self).__init__(*args, **kwargs)

    def __str__(self):
        metadata = "{0} {1}".format(len(self.files), "file" if len(self.files) == 1 else "files")
        return "{title} ({kind}): {metadata}".format(title=self.title, kind=self.__class__.__name__, metadata=metadata)

    def validate(self):
        """ validate: Makes sure audio is valid
            Args: None
            Returns: boolean indicating if audio is valid
        """
        try:
            assert self.kind == content_kinds.AUDIO, "Assumption Failed: Node should be audio"
            assert self.questions == [], "Assumption Failed: Audio should not have questions"
            assert len(self.files) > 0, "Assumption Failed: Audio should have at least one file"

            # Check if there are any .mp3 or .wav files
            files_valid = False
            for f in self.files:
                files_valid = files_valid or file_formats.MP3  in f or file_formats.WAV  in f
            assert files_valid, "Assumption Failed: Audio should have at least one .mp3 or .wav file"

            return super(Audio, self).validate()
        except AssertionError as ae:
            raise InvalidNodeException("Invalid node ({}): {} - {}".format(ae.args[0], self.title, self.__dict__))


class Document(ContentNode):
    """ Model representing documents in channel

        Documents must be pdf format

        Attributes:
            source_id (str): content's original id
            title (str): content's title
            files (str or list): content's associated file(s)
            author (str): who created the content (optional)
            description (str): description of content (optional)
            license (str): content's license based on le_utils.constants.licenses (optional)
            thumbnail (str): local path or url to thumbnail image (optional)
    """
    default_preset = format_presets.DOCUMENT
    thumbnail_preset = format_presets.DOCUMENT_THUMBNAIL
    def __init__(self, *args, **kwargs):
        self.kind = content_kinds.DOCUMENT
        super(Document, self).__init__(*args, **kwargs)

    def __str__(self):
        metadata = "{0} {1}".format(len(self.files), "file" if len(self.files) == 1 else "files")
        return "{title} ({kind}): {metadata}".format(title=self.title, kind=self.__class__.__name__, metadata=metadata)

    def validate(self):
        """ validate: Makes sure document is valid
            Args: None
            Returns: boolean indicating if document is valid
        """
        try:
            assert self.kind == content_kinds.DOCUMENT, "Assumption Failed: Node should be a document"
            assert self.questions == [], "Assumption Failed: Document should not have questions"
            assert len(self.files) > 0, "Assumption Failed: Document should have at least one file"

            # Check if there are any .pdf files
            files_valid = False
            for f in self.files:
                files_valid = files_valid or file_formats.PDF
            assert files_valid, "Assumption Failed: Document should have at least one .pdf file"

            return super(Document, self).validate()
        except AssertionError as ae:
            raise InvalidNodeException("Invalid node ({}): {} - {}".format(ae.args[0], self.title, self.__dict__))


class Exercise(ContentNode):
    """ Model representing exercises in channel

        Exercises are sets of questions to assess learners'
        understanding of the content

        Attributes:
            source_id (str): content's original id
            title (str): content's title
            files (str or list): content's associated file(s)
            author (str): who created the content (optional)
            description (str): description of content (optional)
            license (str): content's license based on le_utils.constants.licenses (optional)
            exercise_data ({mastery_model:str, randomize:bool, m:int, n:int}): data on mastery requirements (optional)
            thumbnail (str): local path or url to thumbnail image (optional)
    """
    default_preset = format_presets.EXERCISE
    thumbnail_preset = format_presets.EXERCISE_THUMBNAIL
    def __init__(self, source_id, title, files, exercise_data=None, **kwargs):
        self.kind = content_kinds.EXERCISE
        self.questions = []
        files = [] if files is None else files

        # Set mastery model defaults if none provided
        exercise_data = {} if exercise_data is None else exercise_data
        exercise_data.update({
            'mastery_model': exercise_data.get('mastery_model') or exercises.M_OF_N,
            'randomize': exercise_data.get('randomize') or True,
        })

        super(Exercise, self).__init__(source_id, title, questions=self.questions, extra_fields=exercise_data, **kwargs)

    def __str__(self):
        metadata = "{0} {1}".format(len(self.questions), "question" if len(self.questions) == 1 else "questions")
        return "{title} ({kind}): {metadata}".format(title=self.title, kind=self.__class__.__name__, metadata=metadata)

    def add_question(self, question):
        """ add_question: adds question to question list
            Args: question to add to list
            Returns: None
        """
        self.questions += [question]

    def process_questions(self):
        """ process_questions: goes through question fields and replaces image strings
            Args: None
            Returns: None
        """
        for question in self.questions:
            question.process_question()

        # Update mastery model if parameters were not provided
        if self.extra_fields['mastery_model'] == exercises.M_OF_N:
            if 'n' not in self.extra_fields:
                self.extra_fields.update({'n':self.extra_fields.get('m') or max(len(self.questions), 1)})
            if 'm' not in self.extra_fields:
                self.extra_fields.update({'m':self.extra_fields.get('n') or max(len(self.questions), 1)})

    def to_dict(self):
        """ to_dict: puts data in format CC expects
            Args: None
            Returns: dict of node's data
        """
        return {
            "title": self.title,
            "description": self.description,
            "node_id": self.get_node_id().hex,
            "content_id": self.get_content_id().hex,
            "author": self.author,
            "files" : self.files,
            "kind": self.kind,
            "license": self.license,
            "questions": [question.to_dict() for question in self.questions],
            "extra_fields": json.dumps(self.extra_fields),
        }

    def validate(self):
        """ validate: Makes sure exercise is valid
            Args: None
            Returns: boolean indicating if exercise is valid
        """
        try:
            assert self.kind == content_kinds.EXERCISE, "Assumption Failed: Node should be an exercise"
            assert "mastery_model" in self.extra_fields, "Assumption Failed: Exercise must have a mastery model in extra_fields"

            # Check if there are any .perseus files
            files_valid = len(self.files) == 0
            for f in self.files:
                files_valid = files_valid or file_formats.PERSEUS
            assert files_valid , "Assumption Failed: Exercise does not have a .perseus file attached"

            # Check if questions are correct
            questions_valid = True
            for q in self.questions:
                questions_valid = questions_valid and q.validate()
            assert questions_valid, "Assumption Failed: Exercise does not have a question"

            return super(Exercise, self).validate()
        except AssertionError as ae:
            raise InvalidNodeException("Invalid node ({}): {} - {}".format(ae.args[0], self.title, self.__dict__))


class HTML5App(ContentNode):
    """ Model representing a zipped HTML5 application

        The zip file must contain a file called index.html, which will be the first page loaded.
        All links (e.g. href and src) must be relative URLs, pointing to other files in the zip.

        Attributes:
            source_id (str): content's original id
            title (str): content's title
            files (str or list): content's associated file(s)
            author (str): who created the content (optional)
            description (str): description of content (optional)
            license (str): content's license based on le_utils.constants.licenses (optional)
            thumbnail (str): local path or url to thumbnail image (optional)
    """

    default_preset = format_presets.HTML5_ZIP
    thumbnail_preset = format_presets.HTML5_THUMBNAIL
    def __init__(self, *args, **kwargs):
        self.kind = content_kinds.HTML5

        super(HTML5App, self).__init__(*args, **kwargs)

    def __str__(self):
        return "{title} ({kind})".format(title=self.title, kind=self.__class__.__name__)

    def validate(self):
        """ validate: Makes sure HTML5 app is valid
            Args: None
            Returns: boolean indicating if HTML5 app is valid
        """
        try:
            assert self.kind == content_kinds.HTML5, "Assumption Failed: Node should be an HTML5 app"
            assert self.questions == [], "Assumption Failed: HTML should not have questions"

            # Check if there are any .zip files
            zip_file_found = False
            for f in self.files:
                if f.endswith("." + file_formats.HTML5):
                    zip_file_found = True

                    # make sure index.html exists
                    with zipfile.ZipFile(f) as zf:
                        try:
                            info = zf.getinfo('index.html')
                        except KeyError:
                            assert False, "Assumption Failed: HTML zip must have an `index.html` file at topmost level"

            assert zip_file_found, "Assumption Failed: HTML does not have a .zip file attached"

            return super(HTML5App, self).validate()

        except AssertionError as ae:
            raise InvalidNodeException("Invalid node ({}): {} - {}".format(ae.args[0], self.title, self.__dict__))
