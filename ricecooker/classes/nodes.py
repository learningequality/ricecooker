import uuid
import json
from ricecooker.managers import DownloadManager
from le_utils.constants import content_kinds,file_formats, format_presets, licenses, exercises

downloader = DownloadManager()

def guess_content_kind(files, questions=None):
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

    def count(self):
        total = len(self.children)
        for child in self.children:
            total += child.count()
        return total

    def print_tree(self, indent=1):
        print("{indent}{data}".format(indent="   " * indent, data=str(self)))
        for child in self.children:
            child.print_tree(indent + 1)

    def __str__(self):
        pass


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
        self.title = title
        self.thumbnail = downloader.encode_thumbnail(thumbnail)
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
            "name": self.title,
            "has_changed": True,
            "thumbnail": self.thumbnail,
            "description": self.description if self.description is not None else "",
            "children": [child_node.to_dict() for child_node in self.children],
        }

    def __str__(self):
        count = self.count()
        metadata = "{0} {1}".format(count, "descendant" if count == 1 else "descendants")
        return "{title} ({kind}): {metadata}".format(title=self.title, kind=self.__class__.__name__, metadata=metadata)


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
    def __init__(self, *args, **kwargs):
        self.id = args[0]
        self.title = args[1]
        self.description = kwargs.get('description') or ""
        self.author = kwargs.get('author') or ""
        self.license = kwargs.get('license')

        files = kwargs.get('files') or []
        self.files = [files] if isinstance(files, str) else files
        if kwargs.get('thumbnail') is not None:
            self.files.append(kwargs.get('thumbnail'))

        self.questions = kwargs.get('questions') or []
        self.extra_fields = kwargs.get('extra_fields') or {}
        super(Node, self).__init__()


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



class Topic(Node):
    """ Model representing channel topics

        Topic nodes are used to add organization to the channel's content

        Attributes:
            id (str): content's original id
            title (str): content's title
            description (str): description of content
            author (str): who created the content
    """
    def __init__(self, id, title, description="", author=""):
        self.kind = content_kinds.TOPIC
        super(Topic, self).__init__(id, title, description=description, author=author)

    def __str__(self):
        count = self.count()
        metadata = "{0} {1}".format(count, "descendant" if count == 1 else "descendants")
        return "{title} ({kind}): {metadata}".format(title=self.title, kind=self.__class__.__name__, metadata=metadata)


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
    def __init__(self, id, title, author="", description="", transcode_to_lower_resolutions=False, derive_thumbnail=False, license=None, subtitle=None, files=None, preset=None, thumbnail=None):
        if preset is not None:
            self.default_preset = preset
        if transcode_to_lower_resolutions:
            self.transcode_to_lower_resolutions()
        if derive_thumbnail:
            thumbnail = self.derive_thumbnail()
        self.kind = content_kinds.VIDEO
        super(Video, self).__init__(id, title, description=description, author=author, license=license, files=files, thumbnail=thumbnail)

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

    def __str__(self):
        metadata = "{0} {1}".format(len(self.files), "file" if len(self.files) == 1 else "files")
        return "{title} ({kind}): {metadata}".format(title=self.title, kind=self.__class__.__name__, metadata=metadata)


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
    def __init__(self, id, title, author="", description="", license=None, subtitle=None, files=None, thumbnail=None):
        self.kind = content_kinds.AUDIO
        super(Audio, self).__init__(id, title, description=description, author=author, license=license, files=files, thumbnail=thumbnail)

    def __str__(self):
        metadata = "{0} {1}".format(len(self.files), "file" if len(self.files) == 1 else "files")
        return "{title} ({kind}): {metadata}".format(title=self.title, kind=self.__class__.__name__, metadata=metadata)

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
    def __init__(self, id, title, author="", description="", license=None, files=None, thumbnail=None):
        self.kind = content_kinds.DOCUMENT
        super(Document, self).__init__(id, title, description=description, author=author, license=license, files=files, thumbnail=thumbnail)

    def __str__(self):
        metadata = "{0} {1}".format(len(self.files), "file" if len(self.files) == 1 else "files")
        return "{title} ({kind}): {metadata}".format(title=self.title, kind=self.__class__.__name__, metadata=metadata)

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
    def __init__(self, id, title, author="", description="", license=None, files=None, exercise_data=None, thumbnail=None):
        self.kind = content_kinds.EXERCISE
        self.questions = []
        files = [] if files is None else files
        exercise_data = {'mastery_model': exercises.M_OF_N, 'randomize': True, 'm': 3, 'n': 5} if exercise_data is None else exercise_data
        super(Exercise, self).__init__(id, title, description=description, author=author, license=license, files=files, questions=self.questions, extra_fields=exercise_data,thumbnail=thumbnail)

    def add_question(self, question):
        self.questions += [question]

    def process_questions(self, downloader):
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

    def __str__(self):
        metadata = "{0} {1}".format(len(self.questions), "question" if len(self.questions) == 1 else "questions")
        return "{title} ({kind}): {metadata}".format(title=self.title, kind=self.__class__.__name__, metadata=metadata)
