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



""" Channel: model to handle channel data
    @param channel_id (string for unique channel id)
    @param domain (domain of where data is from)
    @param title (name of channel)
    @param thumbnail (channel thumbnail string- can be file path or url)
    @param description (description of channel)
"""
class Channel(TreeModel):
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

    """ to_dict: puts data in format CC expects
        @return dict of channel data
    """
    def to_dict(self):
        return {
            "id": self.id.hex,
            "name": self.name,
            "has_changed": True,
            "thumbnail": self.thumbnail,
            "description": self.description if self.description is not None else "",
            "children": [child_node.to_dict() for child_node in self.children],
        }

    """ encode_thumbnail: gets base64 encoding of thumbnail
        @param thumbnail (string of thumbnail's file path or url)
        @return base64 encoding of thumbnail
    """
    def encode_thumbnail(self, thumbnail):
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



""" Node: base model for different content node kinds
    @param id (content's original id)
    @param title (content's title)
    @param description (content's description)
    @param author (content's author)
    @param license (content's license)
    @param files (string or list of content's associated file(s))
"""
class Node(TreeModel):
    def __init__(self, id, title, description, author, license, files):
        self.id = id
        self.title = title
        self.description = description
        self.author = author
        self.license = license
        self.children = []
        self.files = [files] if isinstance(files, str) else files
        super(Node, self).__init__()

    """ to_dict: puts data in format CC expects
        @return dict of content data
    """
    def to_dict(self):
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

    """ set_ids: sets node's node_id and content_id
        @param domain (uuid of channel domain)
        @param parent_id (node's parent's node_id)
    """
    def set_ids(self, domain, parent_id):
        self.content_id = uuid.uuid5(domain, self.id)
        self.node_id = uuid.uuid5(parent_id, self.content_id.hex)


""" Topic: model for topic nodes
    @param id (content's original id)
    @param title (content's title)
    @param description (content's description)
    @param author (content's author)
"""
class Topic(Node):
    def __init__(self, id, title, description=None, author=None):
        self.kind = constants.CK_TOPIC
        super(Topic, self).__init__(id, title, description, author, None, [])



""" Video: model for video nodes
    @param id (content's original id)
    @param title (content's title)
    @param description (content's description)
    @param author (content's author)
    @param license (content's license)
    @param transcode_to_lower_resolutions (indicates whether to extract lower resolution)
    @param derive_thumbnail (indicates whether to derive thumbnail from video)
    @param preset (default preset for files)
    @param subtitle (subtitles for content)
    @param files (string or list of content's associated file(s))
"""
class Video(Node):
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
        pass

    def transcode_to_lower_resolutions(self):
        pass

""" Audio: model for audio nodes
    @param id (content's original id)
    @param title (content's title)
    @param description (content's description)
    @param author (content's author)
    @param license (content's license)
    @param subtitle (subtitles for content)
    @param files (string or list of content's associated file(s))
"""
class Audio(Node):
    default_preset = constants.FP_AUDIO
    def __init__(self, id, title, author=None, description=None, license=None, subtitle=None, files=[]):
        self.kind = constants.CK_AUDIO
        super(Audio, self).__init__(id, title, description, author, license, files)

""" Document: model for document nodes
    @param id (content's original id)
    @param title (content's title)
    @param description (content's description)
    @param author (content's author)
    @param license (content's license)
    @param files (string or list of content's associated file(s))
"""
class Document(Node):
    default_preset = constants.FP_DOCUMENT
    def __init__(self, id, title, author=None, description=None, license=None, files=[]):
        self.kind = constants.CK_DOCUMENT
        super(Document, self).__init__(id, title, description, author, license, files)

""" Exercise: model for exercise nodes
    @param id (content's original id)
    @param title (content's title)
    @param description (content's description)
    @param author (content's author)
    @param license (content's license)
    @param files (string or list of content's associated file(s))
"""
class Exercise(Node):
    default_preset = constants.FP_EXERCISE
    def __init__(self, id, title, author=None, description=None, license=None, files=[]):
        self.kind = constants.CK_EXERCISE
        super(Exercise, self).__init__(id, title, description, author, license, files)


""" guess_content_kind: determines what kind the content is
    @param files (string or list of files associated with content)
    @return string of kind
"""
def guess_content_kind(files):
    files = [files] if isinstance(files, str) else files
    if files is not None and len(files) > 0:
        for f in files:
            ext = f.rsplit('/', 1)[-1].split(".")[-1].lower()
            if ext in constants.CK_MAPPING:
                return constants.CK_MAPPING[ext]
        raise InvalidFormatException("Invalid file type: Allowed formats are {0}".format([key for key, value in constants.CK_MAPPING.items()]))
    else:
        return constants.CK_TOPIC