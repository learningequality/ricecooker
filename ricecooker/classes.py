import uuid
import hashlib
from fle_utils import constants

def generate_uuid(name):
    id5 = uuid.uuid5(uuid.NAMESPACE_DNS, name).hex
    return uuid.uuid3(uuid.NAMESPACE_DNS, id5).hex

class Channel:
    def __init__(self, channel_id, domain=None, title=None):
        channel_uuid = generate_uuid(channel_id)
        self.domain = domain
        self.channel_id = channel_uuid
        self.title = title

    def to_json(self):
        return {
            "id": self.channel_id,
            "title": self.title,
            "thumbnail": self.thumbnail,
        }