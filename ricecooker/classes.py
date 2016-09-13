import uuid
import hashlib
from fle_utils import constants

def generate_uuid(name):
    id5 = uuid.uuid5(uuid.NAMESPACE_DNS, name).hex
    return uuid.uuid3(uuid.NAMESPACE_DNS, id5).hex

class Channel:
    def __init__(self, channel_id, domain=None, title=None):
        self.domain = domain
        self.channel_id = generate_uuid(channel_id)
        self.title = title
        self.root = Topic(
            id=self.channel_id,
            title="root"
        )

    def to_json(self):
        return {
            "id": self.channel_id,
            "title": self.title,
            "thumbnail": self.thumbnail,
        }

def generate_content_id(domain, id):
    return uuid.uuid5(domain, id)

def generate_node_id(parent_id, content_id):
    return uuid.uuid5(parent_id, content_id)

class Node:
    def __init__(self, id, title, description, author):
        self.id = id
        self.title = title
        self.description = description
        self.author = author

    def guess_content_kind(self):
        pass

    def to_json(self):
        pass

    def set_ids(self, domain, parent):
        self.content_id = generate_content_id(domain, self.id)
        self.node_id = generate_node_id(parent.id, self.content_id)


# def propagate_content_ids(channeltree):
#     assert isinstance(channeltree, Channel)


# def set_ids(root):
#     children = channeltree.children

#     for child in children:
#         child.content_id = uuid(channel.domain_id, child.id)

#     propagate_content_ids(channeltree)

class Topic(Node):
    def __init__(self, id, title, description=None, author=None):
        self.children = []
        self.kind = constants.CK_TOPIC
        super(Topic, self).__init__(id, title, description, author)

class Video(Node):
    default_preset = constants.FP_VIDEO_HIGH_RES
    def __init__(self, id, title, author=None, description=None, transcode_to_lower_resolutions=False, derive_thumbnail=False):
        self.transcode_to_lower_resolutions = transcode_to_lower_resolutions
        self.derive_thumbnail = derive_thumbnail
        self.kind = constants.CK_VIDEO
        super(Video, self).__init__(id, title, description, author)

    def derive_thumbnail(self):
        pass

    def transcode_to_lower_resolution(self):
        pass

class Audio(Node):
    default_preset = constants.FP_AUDIO
    def __init__(self, id, title, author=None, description=None):
        self.kind = constants.CK_AUDIO
        super(Audio, self).__init__(id, title, description, author)

class Document(Node):
    default_preset = constants.FP_DOCUMENT
    def __init__(self, id, title, author=None, description=None):
        self.kind = constants.CK_DOCUMENT
        super(Document, self).__init__(id, title, description, author)

class Exercise(Node):
    default_preset = constants.FP_EXERCISE
    def __init__(self, id, title, author=None, description=None):
        self.kind = constants.CK_EXERCISE
        super(Exercise, self).__init__(id, title, description, author)