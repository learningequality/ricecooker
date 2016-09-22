import uuid
import hashlib
import base64
import requests
import validators
import tempfile
from PIL import Image
from io import BytesIO
from fle_utils import constants


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
    def __init__(self, id, title, description, author, license, files):
        self.id = id
        self.title = title
        self.description = description
        self.author = author
        self.license = license
        self.children = []
        self.files = [files] if isinstance(files, str) else files
        super(Node, self).__init__()


    def to_dict(self):
    """ to_dict: puts data in format CC expects
        Args: None
        Returns: dict of node's data
    """
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description if self.description is not None else "",
            "node_id": self.node_id.hex,
            "content_id": self.content_id.hex,
            "author": self.author if self.author is not None else "",
            "children": [child_node.to_dict() for child_node in self.children],
            "files" : self.files,
            "kind": self.kind,
            "license": self.license,
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
        self.kind = constants.CK_TOPIC
        super(Topic, self).__init__(id, title, description, author, None, [])



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
    default_preset = constants.FP_VIDEO_HIGH_RES
    def __init__(self, id, title, author=None, description=None, transcode_to_lower_resolutions=False, derive_thumbnail=False, license=None, subtitle=None, files=[], preset=None):
        if preset is not None:
            self.default_preset = preset
        if transcode_to_lower_resolutions:
            self.transcode_to_lower_resolutions()
        if derive_thumbnail:
            self.derive_thumbnail()
        self.kind = constants.CK_VIDEO
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
    default_preset = constants.FP_AUDIO
    def __init__(self, id, title, author=None, description=None, license=None, subtitle=None, files=[]):
        self.kind = constants.CK_AUDIO
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
    default_preset = constants.FP_DOCUMENT
    def __init__(self, id, title, author=None, description=None, license=None, files=[]):
        self.kind = constants.CK_DOCUMENT
        super(Document, self).__init__(id, title, description, author, license, files)



class Exercise(Node):
    """ Model representing exercises in channel

        Exercises must be perseus format

        Attributes:
            id (str): content's original id
            title (str): content's title
            author (str): who created the content
            description (str): description of content
            license (str): content's license (using constants from fle_utils)
            files (str or list): content's associated file(s)
    """
    default_preset = constants.FP_EXERCISE
    def __init__(self, id, title, author=None, description=None, license=None, files=[]):
        self.kind = constants.CK_EXERCISE
        super(Exercise, self).__init__(id, title, description, author, license, files)


def guess_content_kind(files):
    """ guess_content_kind: determines what kind the content is
        Args:
            files (str or list): files associated with content
        Returns: string indicating node's kind
    """
    files = [files] if isinstance(files, str) else files
    if files is not None and len(files) > 0:
        for f in files:
            ext = f.rsplit('/', 1)[-1].split(".")[-1].lower()
            if ext in constants.CK_MAPPING:
                return constants.CK_MAPPING[ext]
        raise InvalidFormatException("Invalid file type: Allowed formats are {0}".format([key for key, value in constants.CK_MAPPING.items()]))
    else:
        return constants.CK_TOPIC