import uuid
import hashlib
import base64
from fle_utils import constants

class Channel:
    def __init__(self, channel_id, domain=None, title=None, thumbnail=None, description=None):
        self.domain = domain
        self.id = self.generate_uuid(channel_id)
        self.title = title
        self.thumbnail = self.encode_thumbnail(thumbnail)
        self.description = description
        self._nodes = {'Topic': [], 'Video':[]}

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.title,
            "has_changed": True,
            "thumbnail": self.thumbnail,
            "description": self.description,
        }

    def generate_uuid(self, name):
        return uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid5(uuid.NAMESPACE_DNS, name).hex)

    def encode_thumbnail(self, thumbnail):
        if thumbnail is None:
            return None
        else:
            with open(thumbnail, "rb") as image:
                return base64.b64encode(image.read())

class Node:
    def __init__(self, id, title, description, author, license):
        self.id = id
        self.title = title
        self.description = description
        self.author = author
        self.license = license
        self.children = []
        self.files = []

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "node_id": self.node_id.hex,
            "content_id": self.content_id.hex,
            "author": self.author,
            "children": self.children,
            "files" : self.files,
            "kind": self.kind,
            "license": self.license,
        }

    def set_ids(self, domain, parent_id):
        self.content_id = uuid.uuid5(domain, self.id)
        self.node_id = uuid.uuid5(parent_id, self.content_id.hex)


class Topic(Node):
    def __init__(self, id, title, description=None, author=None):
        self.kind = constants.CK_TOPIC
        super(Topic, self).__init__(id, title, description, author, None)

class Video(Node):
    default_preset = constants.FP_VIDEO_HIGH_RES
    def __init__(self, id, title, author=None, description=None, transcode_to_lower_resolutions=False, derive_thumbnail=False, license=None):
        self.transcode_to_lower_resolutions = transcode_to_lower_resolutions
        self.derive_thumbnail = derive_thumbnail
        self.kind = constants.CK_VIDEO
        super(Video, self).__init__(id, title, description, author, license)

    def derive_thumbnail(self):
        pass

    def transcode_to_lower_resolution(self):
        pass

class Audio(Node):
    default_preset = constants.FP_AUDIO
    def __init__(self, id, title, author=None, description=None, license=None):
        self.kind = constants.CK_AUDIO
        super(Audio, self).__init__(id, title, description, author, license)

class Document(Node):
    default_preset = constants.FP_DOCUMENT
    def __init__(self, id, title, author=None, description=None, license=None):
        self.kind = constants.CK_DOCUMENT
        super(Document, self).__init__(id, title, description, author, license)

class Exercise(Node):
    default_preset = constants.FP_EXERCISE
    def __init__(self, id, title, author=None, description=None, license=None):
        self.kind = constants.CK_EXERCISE
        super(Exercise, self).__init__(id, title, description, author, license)