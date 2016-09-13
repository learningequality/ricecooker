import uuid
import hashlib
import base64
from fle_utils import constants
from ricecooker.managers import ChannelManager


class Channel:
    def __init__(self, channel_id, domain=None, title=None, thumbnail=None):
        self.domain = domain
        self.channel_id = self.generate_uuid(channel_id)
        self.title = title
        self.thumbnail = self.encode_thumbnail(thumbnail)
        self.root = Topic(
            id=self.channel_id.hex,
            title=self.title
        )
        self.objects = ChannelManager(self, self.root)

    def to_json(self):
        return {
            "id": self.channel_id,
            "title": self.title,
            "thumbnail": self.thumbnail,
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
    def __init__(self, id, title, description, author):
        self.id = id
        self.title = title
        self.description = description
        self.author = author

    def to_json(self):
        pass

    def set_ids(self, domain, parent_id):
        self.content_id = uuid.uuid5(domain, self.id)
        self.node_id = uuid.uuid5(parent_id, self.content_id.hex)


class Topic(Node):
    def __init__(self, id, title, description=None, author=None):
        self.children = []
        self.kind = constants.CK_TOPIC
        super(Topic, self).__init__(id, title, description, author)

class Video(Node):
    default_preset = constants.FP_VIDEO_HIGH_RES
    def __init__(self, id, title, author=None, description=None, transcode_to_lower_resolutions=False, derive_thumbnail=False, license=None):
        self.transcode_to_lower_resolutions = transcode_to_lower_resolutions
        self.derive_thumbnail = derive_thumbnail
        self.license = license
        self.kind = constants.CK_VIDEO
        super(Video, self).__init__(id, title, description, author)

    def derive_thumbnail(self):
        pass

    def transcode_to_lower_resolution(self):
        pass

class Audio(Node):
    default_preset = constants.FP_AUDIO
    def __init__(self, id, title, author=None, description=None, license=None):
        self.kind = constants.CK_AUDIO
        self.license = license
        super(Audio, self).__init__(id, title, description, author)

class Document(Node):
    default_preset = constants.FP_DOCUMENT
    def __init__(self, id, title, author=None, description=None, license=None):
        self.kind = constants.CK_DOCUMENT
        self.license = license
        super(Document, self).__init__(id, title, description, author)

class Exercise(Node):
    default_preset = constants.FP_EXERCISE
    def __init__(self, id, title, author=None, description=None, license=None):
        self.kind = constants.CK_EXERCISE
        self.license = license
        super(Exercise, self).__init__(id, title, description, author)