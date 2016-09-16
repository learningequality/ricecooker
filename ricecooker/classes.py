import uuid
import hashlib
import base64
import requests
import validators
import tempfile
from PIL import Image
from io import BytesIO
from fle_utils import constants

class Channel:
    def __init__(self, channel_id, domain=None, title=None, thumbnail=None, description=None):
        self.domain = domain
        self.id = self.generate_uuid(channel_id)
        self.name = title
        self.thumbnail = self.encode_thumbnail(thumbnail)
        self.description = description
        self.children = []
        self._internal_domain = uuid.uuid5(uuid.NAMESPACE_DNS, self.domain)
        self.content_id = uuid.uuid5(self._internal_domain, self.id.hex)
        self.node_id = uuid.uuid5(self.id, self.content_id.hex)

    def to_dict(self):
        return {
            "id": self.id.hex,
            "name": self.name,
            "has_changed": True,
            "thumbnail": self.thumbnail,
            "description": self.description if self.description is not None else "",
            "children": [child_node.to_dict() for child_node in self.children],
        }

    def add_child(self, node):
        self.children += [node]

    def generate_uuid(self, name):
        return uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid5(uuid.NAMESPACE_DNS, name).hex)

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

class Node:
    def __init__(self, id, title, description, author, license, files):
        self.id = id
        self.title = title
        self.description = description
        self.author = author
        self.license = license
        self.children = []
        self.files = [files] if isinstance(files, str) else files

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

    def set_ids(self, domain, parent_id):
        self.content_id = uuid.uuid5(domain, self.id)
        self.node_id = uuid.uuid5(parent_id, self.content_id.hex)

    def add_child(self, node):
        self.children += [node]


class Topic(Node):
    def __init__(self, id, title, description=None, author=None):
        self.kind = constants.CK_TOPIC
        super(Topic, self).__init__(id, title, description, author, None, [])

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

class Audio(Node):
    default_preset = constants.FP_AUDIO
    def __init__(self, id, title, author=None, description=None, license=None, subtitle=None, files=[]):
        self.kind = constants.CK_AUDIO
        super(Audio, self).__init__(id, title, description, author, license, files)

class Document(Node):
    default_preset = constants.FP_DOCUMENT
    def __init__(self, id, title, author=None, description=None, license=None, files=[]):
        self.kind = constants.CK_DOCUMENT
        super(Document, self).__init__(id, title, description, author, license, files)

class Exercise(Node):
    default_preset = constants.FP_EXERCISE
    def __init__(self, id, title, author=None, description=None, license=None, files=[]):
        self.kind = constants.CK_EXERCISE
        super(Exercise, self).__init__(id, title, description, author, license, files)

def guess_content_kind(data):
    if 'file' in data and len(data['file']) > 0:
        data['file'] = [data['file']] if isinstance(data['file'], str) else data['file']
        for f in data['file']:
            ext = f.rsplit('/', 1)[-1].split(".")[-1].lower()
            if ext in constants.CK_MAPPING:
                return constants.CK_MAPPING[ext]
        raise InvalidFormatException("Invalid file type: Allowed formats are {0}".format([key for key, value in constants.CK_MAPPING.items()]))
    else:
        return constants.CK_TOPIC