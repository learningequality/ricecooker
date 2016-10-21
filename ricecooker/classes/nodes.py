# Node models to represent channel's tree

import uuid
import json
from ricecooker.managers import DownloadManager
from le_utils.constants import content_kinds,file_formats, format_presets, licenses, exercises
from ricecooker.exceptions import InvalidNodeException, InvalidFormatException

def guess_content_kind(files, questions=None):
    """ guess_content_kind: determines what kind the content is
        Args:
            files (str or list): files associated with content
        Returns: string indicating node's kind
    """
    # Get files and questions into readable format
    files = [files] if isinstance(files, str) else files
    questions=[questions] if isinstance(questions, str) else questions

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


class Node:
    """ Node: model to represent all nodes in the tree """
    def __init__(self):
        self.children = []

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
            Args: indent (int): What level of indentation to start printing at
            Returns: None
        """
        print("{indent}{data}".format(indent="   " * indent, data=str(self)))
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
        assert self.id is not None, "Assumption Failed: Node must have an id"
        assert isinstance(self.title, str), "Assumption Failed: Node title is not a string"
        assert isinstance(self.description, str) or self.description is None, "Assumption Failed: Node description is not a string"
        assert isinstance(self.children, list), "Assumption Failed: Node children is not a list"
        return True


class Channel(Node):
    """ Model representing the channel you are creating

        Used to store metadata on channel that is being created

        Attributes:
            channel_id (str): channel's unique id
            domain (str): who is providing the content (e.g. learningequality.org)
            title (str): name of channel
            thumbnail (str): file path or url of channel's thumbnail
            description (str): description of the channel (optional)
    """
    def __init__(self, channel_id, domain, title, description=None, thumbnail=None):
        # Map parameters to model variables
        self.domain = domain
        self.id = uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid5(uuid.NAMESPACE_DNS, channel_id).hex)
        self.title = title
        self.description = "" if description is None else description

        # Encode thumbnail to base64
        downloader = DownloadManager()
        self.thumbnail = downloader.encode_thumbnail(thumbnail)

        # Add data to be used in next steps
        self._internal_domain = uuid.uuid5(uuid.NAMESPACE_DNS, self.domain)
        self.content_id = uuid.uuid5(self._internal_domain, self.id.hex)
        self.node_id = uuid.uuid5(self.id, self.content_id.hex)

        super(Channel, self).__init__()

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
            "id": self.id.hex,
            "name": self.title,
            "has_changed": True,
            "thumbnail": self.thumbnail,
            "description": self.description if self.description is not None else "",
            "children": [child_node.to_dict() for child_node in self.children],
        }

    def validate(self):
        """ validate: Makes sure channel is valid
            Args: None
            Returns: boolean indicating if channel is valid
        """
        try:
            assert isinstance(self.domain, str)
            assert isinstance(self.thumbnail, str) or self.thumbnail is None
            return super(Channel, self).validate()
        except AssertionError as ae:
            raise InvalidNodeException("Invalid node: {0} - {1}".format(self.title, ae))


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
    def __init__(self, *args, **kwargs):
        # Map parameters to model variables
        self.id = args[0]
        self.original_id = args[0]
        self.title = args[1]
        self.description = kwargs.get('description') or ""
        self.author = kwargs.get('author') or ""
        self.license = kwargs.get('license')

        # Set files into list format (adding thumbnail if provided)
        files = kwargs.get('files') or []
        self.files = [files] if isinstance(files, str) else files
        self.thumbnail = kwargs.get('thumbnail')

        # Set any possible exercise data to standard format
        self.questions = kwargs.get('questions') or []
        self.extra_fields = kwargs.get('extra_fields') or {}
        super(ContentNode, self).__init__()

    def __str__(self):
        count = self.count()
        metadata = "{0} {1}".format(count, "descendant" if count == 1 else "descendants")
        return "{title} ({kind}): {metadata}".format(title=self.title, kind=self.__class__.__name__, metadata=metadata)

    def to_dict(self):
        """ to_dict: puts data in format CC expects
            Args: None
            Returns: dict of node's data
        """
        return {
            "title": self.title,
            "description": self.description,
            "node_id": self.node_id.hex,
            "content_id": self.content_id.hex,
            "author": self.author,
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
            id (str): content's original id
            title (str): content's title
            description (str): description of content (optional)
            author (str): who created the content (optional)
    """
    def __init__(self, id, title, description="", author=""):
        self.kind = content_kinds.TOPIC
        super(Topic, self).__init__(id, title, description=description, author=author)

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
            raise InvalidNodeException("Invalid node: {0} - {1}".format(self.title, self.__dict__))


class Video(ContentNode):
    """ Model representing videos in channel

        Videos must be mp4 format

        Attributes:
            id (str): content's original id
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
    def __init__(self, id, title, files, author="", description="", transcode_to_lower_resolutions=False, derive_thumbnail=False, license=None, subtitle=None, preset=None, thumbnail=None):
        self.kind = content_kinds.VIDEO
        # If no preset is given, set to default
        if preset is not None:
            self.default_preset = preset

        # Transcode video to lower resoution
        if transcode_to_lower_resolutions:
            self.transcode_to_lower_resolutions()

        # Derive thumbnail from video
        if derive_thumbnail:
            thumbnail = self.derive_thumbnail()

        super(Video, self).__init__(id, title, description=description, author=author, license=license, files=files, thumbnail=thumbnail)

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
            raise InvalidNodeException("Invalid node: {0} - {1}".format(self.title, self.__dict__))


class Audio(ContentNode):
    """ Model representing audio content in channel

        Audio can be in either mp3 or wav format

        Attributes:
            id (str): content's original id
            title (str): content's title
            files (str or list): content's associated file(s)
            author (str): who created the content (optional)
            description (str): description of content (optional)
            subtitle (str): path or url to file's subtitles (optional)
            license (str): content's license based on le_utils.constants.licenses (optional)
            thumbnail (str): local path or url to thumbnail image (optional)
    """

    default_preset = format_presets.AUDIO
    def __init__(self, id, title, files, author="", description="", license=None, subtitle=None, thumbnail=None):
        self.kind = content_kinds.AUDIO
        super(Audio, self).__init__(id, title, description=description, author=author, license=license, files=files, thumbnail=thumbnail)

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
            raise InvalidNodeException("Invalid node: {0} - {1}".format(self.title, self.__dict__))


class Document(ContentNode):
    """ Model representing documents in channel

        Documents must be pdf format

        Attributes:
            id (str): content's original id
            title (str): content's title
            files (str or list): content's associated file(s)
            author (str): who created the content (optional)
            description (str): description of content (optional)
            license (str): content's license based on le_utils.constants.licenses (optional)
            thumbnail (str): local path or url to thumbnail image (optional)
    """
    default_preset = format_presets.DOCUMENT
    def __init__(self, id, title, files, author="", description="", license=None, thumbnail=None):
        self.kind = content_kinds.DOCUMENT
        super(Document, self).__init__(id, title, description=description, author=author, license=license, files=files, thumbnail=thumbnail)

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
            raise InvalidNodeException("Invalid node: {0} - {1}".format(self.title, self.__dict__))


class Exercise(ContentNode):
    """ Model representing exercises in channel

        Exercises are sets of questions to assess learners'
        understanding of the content

        Attributes:
            id (str): content's original id
            title (str): content's title
            files (str or list): content's associated file(s)
            author (str): who created the content (optional)
            description (str): description of content (optional)
            license (str): content's license based on le_utils.constants.licenses (optional)
            thumbnail (str): local path or url to thumbnail image (optional)
    """
    default_preset = format_presets.EXERCISE
    def __init__(self, id, title, files, author="", description="", license=None, exercise_data=None, thumbnail=None):
        self.kind = content_kinds.EXERCISE
        self.questions = []
        files = [] if files is None else files

        # Set mastery model defaults if none provided
        exercise_data = {'mastery_model': exercises.M_OF_N, 'randomize': True, 'm': 3, 'n': 5} if exercise_data is None else exercise_data

        super(Exercise, self).__init__(id, title, description=description, author=author, license=license, files=files, questions=self.questions, extra_fields=exercise_data,thumbnail=thumbnail)

    def __str__(self):
        metadata = "{0} {1}".format(len(self.questions), "question" if len(self.questions) == 1 else "questions")
        return "{title} ({kind}): {metadata}".format(title=self.title, kind=self.__class__.__name__, metadata=metadata)

    def add_question(self, question):
        """ add_question: adds question to question list
            Args: question to add to list
            Returns: None
        """
        self.questions += [question]

    def process_questions(self, downloader):
        """ process_questions: goes through question fields and replaces image strings
            Args: DownloadManager to download images
            Returns: None
        """
        for question in self.questions:
            self.files += question.process_question(downloader)

    def to_dict(self):
        """ to_dict: puts data in format CC expects
            Args: None
            Returns: dict of node's data
        """
        return {
            "title": self.title,
            "description": self.description,
            "node_id": self.node_id.hex,
            "content_id": self.content_id.hex,
            "author": self.author,
            "children": [child_node.to_dict() for child_node in self.children],
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
            assert len(self.files) > 0 or len(self.questions) > 0, "Assumption Failed: Exercise should have at least one question or .perseus file"
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
            raise InvalidNodeException("Invalid node: {0} - {1}".format(self.title, self.__dict__))
