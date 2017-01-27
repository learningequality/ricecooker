# Node models to represent channel's tree

import uuid
import json
import sys
from le_utils.constants import content_kinds,file_formats, format_presets, licenses, exercises
from ..exceptions import InvalidNodeException, InvalidFormatException
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
    def __init__(self, title, description=None, thumbnail=None, license=None, copyright_holder=None, files=None):
        self.children = []
        self.files = []
        self.parent = None
        self.node_id = None
        self.content_id = None
        self.title = title
        self.description = description or ""
        self.license = license
        self.copyright_holder = copyright_holder

        for f in files or []:
            self.add_file(f)

        if thumbnail and isinstance(thumbnail, str):
            from .files import ThumbnailFile
            self.thumbnail = ThumbnailFile(path=thumbnail)
            self.add_file(self.thumbnail)


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

    def add_file(self, file_to_add):
        """ add_file: Add to node's associated files
            Args: file_to_add (File): file model to add to node
            Returns: None
        """
        file_to_add.node = self
        self.files.append(file_to_add)

    def process_files(self):
        """ process_files: Process node's files
            Args: None
            Returns: None
        """
        filenames = []
        for f in self.files:
            filenames.append(f.process_file())
        return filenames

    def count(self):
        """ count: get number of nodes in tree
            Args: None
            Returns: int
        """
        total = len(self.children)
        for child in self.children:
            total += child.count()
        return total

    def print_tree(self, indent=2):
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
        from .files import File

        assert self.source_id is not None, "Assumption Failed: Node must have an id"
        assert isinstance(self.title, str), "Assumption Failed: Node title is not a string"
        assert isinstance(self.description, str) or self.description is None, "Assumption Failed: Node description is not a string"
        assert isinstance(self.children, list), "Assumption Failed: Node children is not a list"
        for f in self.files:
            assert isinstance(f, File), "Assumption Failed: files must be file class"
            f.validate()
        return True


class ChannelNode(Node):
    """ Model representing the channel you are creating

        Used to store metadata on channel that is being created

        Attributes:
            source_id (str): channel's unique id
            source_domain (str): who is providing the content (e.g. learningequality.org)
            title (str): name of channel
            description (str): description of the channel (optional)
            thumbnail (str): file path or url of channel's thumbnail (optional)
            license (str): default license to use if nodes don't have license specified (optional)
            copyright_holder (str): name of person or organization who owns license
            files ([<File>]): list of file objects for node (optional)
    """
    kind = "Channel"
    def __init__(self, source_id, source_domain, *args, **kwargs):
        # Map parameters to model variables
        self.source_domain = source_domain
        self.source_id = source_id

        super(ChannelNode, self).__init__(*args, **kwargs)

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
            "thumbnail": self.thumbnail.filename if self.thumbnail else None,
            "description": self.description or "",
            "license": self.license,
            "copyright_holder": self.copyright_holder or "",
        }

    def validate(self):
        """ validate: Makes sure channel is valid
            Args: None
            Returns: boolean indicating if channel is valid
        """
        try:
            assert isinstance(self.source_domain, str), "Channel domain must be a string"
            return super(ChannelNode, self).validate()
        except AssertionError as ae:
            raise InvalidNodeException("Invalid channel ({}): {} - {}".format(ae.args[0], self.title, self.__dict__))


class ContentNode(Node):
    """ Model representing the content nodes in the channel's tree

        Base model for different content node kinds (topic, video, exercise, etc.)

        Attributes:
            source_id (str): content's original id
            title (str): content's title
            description (str): description of content (optional)
            author (str): who created the content (optional)
            license (str): content's license based on le_utils.constants.licenses
            thumbnail (str): local path or url to thumbnail image (optional)
            copyright_holder (str): name of person or organization who owns license (optional)
            files ([<File>]): list of file objects for node (optional)
            extra_fields (dict): any additional data needed for node (optional)
            domain_ns (str): who is providing the content (e.g. learningequality.org) (optional)
    """
    def __init__(self, source_id, title, author="", extra_fields=None, domain_ns=None, **kwargs):
        # Map parameters to model variables
        assert isinstance(source_id, str), "source_id must be a string"
        self.source_id = source_id
        self.author = author or ""
        self.license = license
        self.domain_ns = domain_ns
        self.questions = self.questions if hasattr(self, 'questions') else [] # Needed for to_dict method
        self.extra_fields = extra_fields or {}
        super(ContentNode, self).__init__(title, **kwargs)

    def __str__(self):
        count = self.count()
        metadata = "{0} {1}".format(count, "descendant" if count == 1 else "descendants")
        return "{title} ({kind}): {metadata}".format(title=self.title, kind=self.__class__.__name__, metadata=metadata)

    def get_domain_namespace(self):
        if not self.domain_ns:
            self.domain_ns = self.parent.get_domain_namespace()
        return self.domain_ns

    def get_content_id(self):
        if not self.content_id:
            self.content_id = uuid.uuid5(self.get_domain_namespace(), self.source_id)
        return self.content_id

    def get_node_id(self):
        assert self.parent, "Parent not found: node id must be calculated based on parent"
        if not self.node_id:
            self.node_id = uuid.uuid5(self.parent.get_node_id(), self.get_content_id().hex)
        return self.node_id

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
            "files" : [f.to_dict() for f in filter(lambda x: x and x.filename, self.files)], # Filter out failed downloads
            "kind": self.kind,
            "license": self.license,
            "copyright_holder": self.copyright_holder or "",
            "questions": [question.to_dict() for question in self.questions],
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


class TopicNode(ContentNode):
    """ Model representing channel topics

        Topic nodes are used to add organization to the channel's content

        Attributes:
            source_id (str): content's original id
            title (str): content's title
            description (str): description of content (optional)
            author (str): who created the content (optional)
            license (str): default license for content under this topic
            thumbnail (str): local path or url to thumbnail image (optional)
            copyright_holder (str): name of person or organization who owns license (optional)
            extra_fields (dict): any additional data needed for node (optional)
            domain_ns (str): who is providing the content (e.g. learningequality.org) (optional)
    """

    def __init__(self, *args, **kwargs):
        self.kind = content_kinds.TOPIC
        super(TopicNode, self).__init__(*args, **kwargs)

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
            return super(TopicNode, self).validate()
        except AssertionError as ae:
            raise InvalidNodeException("Invalid node ({}): {} - {}".format(ae.args[0], self.title, self.__dict__))


class VideoNode(ContentNode):
    """ Model representing videos in channel

        Videos must be mp4 format

        Attributes:
            source_id (str): content's original id
            title (str): content's title
            author (str): who created the content (optional)
            description (str): description of content (optional)
            derive_thumbnail (bool): indicates whether to derive thumbnail from video (optional)
            license (str): content's license based on le_utils.constants.licenses
            thumbnail (str): local path or url to thumbnail image (optional)
            copyright_holder (str): name of person or organization who owns license (optional)
            extra_fields (dict): any additional data needed for node (optional)
            domain_ns (str): who is providing the content (e.g. learningequality.org) (optional)
            files ([<File>]): list of file objects for node (optional)
    """
    def __init__(self, source_id, title, derive_thumbnail=False, **kwargs):
        self.kind = content_kinds.VIDEO
        self.derive_thumbnail = derive_thumbnail

        super(VideoNode, self).__init__(source_id, title, **kwargs)

    def __str__(self):
        metadata = "{0} {1}".format(len(self.files), "file" if len(self.files) == 1 else "files")
        return "{title} ({kind}): {metadata}".format(title=self.title, kind=self.__class__.__name__, metadata=metadata)

    def process_files(self):
        """ download_files: Download video's files
            Args: None
            Returns: None
        """
        from .files import VideoFile, ThumbnailFile, ExtractedVideoThumbnailFile

        downloaded = super(VideoNode, self).process_files()

        try:
            # Extract thumbnail if one hasn't been provided and derive_thumbnail is set
            if self.derive_thumbnail and len(list(filter(lambda f: isinstance(f, ThumbnailFile), self.files))) == 0:
                videos = list(filter(lambda f: isinstance(f, VideoFile), self.files))
                assert len(videos) > 0 and videos[0].filename, "No videos downloaded for this node"

                thumbnail = ExtractedVideoThumbnailFile(config.get_storage_path(videos[0].filename))
                self.add_file(thumbnail)
                downloaded.append(thumbnail.process_file())

        except AssertionError as ae:
            config.LOGGER.warning("\tWARNING: Cannot extract thumbnail ({0})".format(ae))

        return downloaded

    def validate(self):
        """ validate: Makes sure video is valid
            Args: None
            Returns: boolean indicating if video is valid
        """
        try:
            assert self.kind == content_kinds.VIDEO, "Assumption Failed: Node should be a video"
            assert self.license, "Assumption Failed: Video content must have a license"
            assert self.questions == [], "Assumption Failed: Video should not have questions"
            assert len(self.files) > 0, "Assumption Failed: Video must have at least one video file"

            # Check if there are any .mp4 files
            files_valid = False
            for f in self.files:
                files_valid = files_valid or file_formats.MP4 in f.path
            assert files_valid , "Assumption Failed: Video should have at least one .mp4 file"

            return super(VideoNode, self).validate()
        except AssertionError as ae:
            raise InvalidNodeException("Invalid node ({}): {} - {}".format(ae.args[0], self.title, self.__dict__))


class AudioNode(ContentNode):
    """ Model representing audio content in channel

        Audio must be in mp3 format

        Attributes:
            source_id (str): content's original id
            title (str): content's title
            author (str): who created the content (optional)
            description (str): description of content (optional)
            license (str): content's license based on le_utils.constants.licenses
            thumbnail (str): local path or url to thumbnail image (optional)
            copyright_holder (str): name of person or organization who owns license (optional)
            extra_fields (dict): any additional data needed for node (optional)
            domain_ns (str): who is providing the content (e.g. learningequality.org) (optional)
            files ([<File>]): list of file objects for node (optional)
    """
    def __init__(self, *args, **kwargs):
        self.kind = content_kinds.AUDIO
        super(AudioNode, self).__init__(*args, **kwargs)

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
            assert self.license, "Assumption Failed: Audio content must have a license"
            assert self.questions == [], "Assumption Failed: Audio should not have questions"
            assert len(self.files) > 0, "Assumption Failed: Audio should have at least one file"

            # Check if there are any .mp3 or .wav files
            files_valid = False
            for f in self.files:
                files_valid = files_valid or file_formats.MP3  in f.path
            assert files_valid, "Assumption Failed: Audio should have at least one .mp3 file"

            return super(AudioNode, self).validate()
        except AssertionError as ae:
            raise InvalidNodeException("Invalid node ({}): {} - {}".format(ae.args[0], self.title, self.__dict__))


class DocumentNode(ContentNode):
    """ Model representing documents in channel

        Documents must be pdf format

        Attributes:
            source_id (str): content's original id
            title (str): content's title
            author (str): who created the content (optional)
            description (str): description of content (optional)
            license (str): content's license based on le_utils.constants.licenses
            thumbnail (str): local path or url to thumbnail image (optional)
            copyright_holder (str): name of person or organization who owns license (optional)
            extra_fields (dict): any additional data needed for node (optional)
            domain_ns (str): who is providing the content (e.g. learningequality.org) (optional)
            files ([<File>]): list of file objects for node (optional)
    """
    def __init__(self, *args, **kwargs):
        self.kind = content_kinds.DOCUMENT
        super(DocumentNode, self).__init__(*args, **kwargs)

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
            assert self.license, "Assumption Failed: Documents must have a license"
            assert self.questions == [], "Assumption Failed: Document should not have questions"
            assert len(self.files) > 0, "Assumption Failed: Document should have at least one file"

            # Check if there are any .pdf files
            files_valid = False
            for f in self.files:
                files_valid = files_valid or file_formats.PDF in f.path
            assert files_valid, "Assumption Failed: Document should have at least one .pdf file"

            return super(DocumentNode, self).validate()
        except AssertionError as ae:
            raise InvalidNodeException("Invalid node ({}): {} - {}".format(ae.args[0], self.title, self.__dict__))


class HTML5AppNode(ContentNode):
    """ Model representing a zipped HTML5 application

        The zip file must contain a file called index.html, which will be the first page loaded.
        All links (e.g. href and src) must be relative URLs, pointing to other files in the zip.

        Attributes:
            source_id (str): content's original id
            title (str): content's title
            author (str): who created the content (optional)
            description (str): description of content (optional)
            license (str): content's license based on le_utils.constants.licenses
            thumbnail (str): local path or url to thumbnail image (optional)
            copyright_holder (str): name of person or organization who owns license (optional)
            extra_fields (dict): any additional data needed for node (optional)
            domain_ns (str): who is providing the content (e.g. learningequality.org) (optional)
            files ([<File>]): list of file objects for node (optional)
    """
    def __init__(self, *args, **kwargs):
        self.kind = content_kinds.HTML5
        super(HTML5AppNode, self).__init__(*args, **kwargs)

    def __str__(self):
        metadata = "{0} {1}".format(len(self.files), "file" if len(self.files) == 1 else "files")
        return "{title} ({kind}): {metadata}".format(title=self.title, kind=self.__class__.__name__, metadata=metadata)

    def validate(self):
        """ validate: Makes sure HTML5 app is valid
            Args: None
            Returns: boolean indicating if HTML5 app is valid
        """
        try:
            assert self.kind == content_kinds.HTML5, "Assumption Failed: Node should be an HTML5 app"
            assert self.license, "Assumption Failed: HTML content must have a license"
            assert self.questions == [], "Assumption Failed: HTML should not have questions"

            # Check if there are any .zip files
            zip_file_found = False
            for f in self.files:
                if f.get_preset() == format_presets.HTML5_ZIP:
                    zip_file_found = True
            assert zip_file_found, "Assumption Failed: HTML does not have a .zip file attached"

            return super(HTML5AppNode, self).validate()

        except AssertionError as ae:
            raise InvalidNodeException("Invalid node ({}): {} - {}".format(ae.args[0], self.title, self.__dict__))


class ExerciseNode(ContentNode):
    """ Model representing exercises in channel

        Exercises are sets of questions to assess learners'
        understanding of the content

        Attributes:
            source_id (str): content's original id
            title (str): content's title
            author (str): who created the content (optional)
            description (str): description of content (optional)
            license (str): content's license based on le_utils.constants.licenses (optional)
            exercise_data ({mastery_model:str, randomize:bool, m:int, n:int}): data on mastery requirements (optional)
            thumbnail (str): local path or url to thumbnail image (optional)
            copyright_holder (str): name of person or organization who owns license (optional)
            extra_fields (dict): any additional data needed for node (optional)
            domain_ns (str): who is providing the content (e.g. learningequality.org) (optional)
            questions ([<Question>]): list of question objects for node (optional)
    """
    default_preset = format_presets.EXERCISE
    def __init__(self, source_id, title, license, questions=None, exercise_data=None, **kwargs):
        self.kind = content_kinds.EXERCISE
        self.questions = questions or []

        # Set mastery model defaults if none provided
        exercise_data = {} if exercise_data is None else exercise_data
        exercise_data.update({
            'mastery_model': exercise_data.get('mastery_model') or exercises.M_OF_N,
            'randomize': exercise_data.get('randomize') or True,
        })

        super(ExerciseNode, self).__init__(source_id, title, extra_fields=exercise_data, **kwargs)

    def __str__(self):
        metadata = "{0} {1}".format(len(self.questions), "question" if len(self.questions) == 1 else "questions")
        return "{title} ({kind}): {metadata}".format(title=self.title, kind=self.__class__.__name__, metadata=metadata)

    def add_question(self, question):
        """ add_question: adds question to question list
            Args: question to add to list
            Returns: None
        """
        self.questions += [question]

    def process_files(self):
        """ process_files: goes through question fields and replaces image strings
            Args: None
            Returns: None
        """
        config.LOGGER.info("\t*** Processing images for exercise: {}".format(self.title))
        downloaded = super(ExerciseNode, self).process_files()
        for question in self.questions:
            downloaded += question.process_question()

        # Update mastery model if parameters were not provided
        if self.extra_fields['mastery_model'] == exercises.M_OF_N:
            if 'n' not in self.extra_fields:
                self.extra_fields.update({'n':self.extra_fields.get('m') or max(len(self.questions), 1)})
            if 'm' not in self.extra_fields:
                self.extra_fields.update({'m':self.extra_fields.get('n') or max(len(self.questions), 1)})

        config.LOGGER.info("\t*** Images for {} have been processed".format(self.title))
        return downloaded

    def validate(self):
        """ validate: Makes sure exercise is valid
            Args: None
            Returns: boolean indicating if exercise is valid
        """
        try:
            assert self.kind == content_kinds.EXERCISE, "Assumption Failed: Node should be an exercise"
            assert "mastery_model" in self.extra_fields, "Assumption Failed: Exercise must have a mastery model in extra_fields"

            # Check if questions are correct
            questions_valid = True
            for q in self.questions:
                questions_valid = questions_valid and q.validate()
            assert questions_valid, "Assumption Failed: Exercise does not have a question"
            return super(ExerciseNode, self).validate()
        except AssertionError as ae:
            raise InvalidNodeException("Invalid node ({}): {} - {}".format(ae.args[0], self.title, self.__dict__))
