import uuid
import hashlib
from ricecooker.classes import *


class ChannelManager:
    def __init__(self, channel, root):
        self.channel = channel
        self.root = root
        self.calculate_channel_internal_metadata()

    def validate(self):
        assert isinstance(self.channel, Channel)
        assert isinstance(self.root, Topic)

    def to_json(self):
        pass

    def guess_content_kind(self, data):
        pass

    def extract_content_metadata(self):
        self.recurse_set_ids(self.root)
        return None

    def calculate_channel_internal_metadata(self):
        self.channel._internal_domain = uuid.uuid5(uuid.NAMESPACE_DNS, self.channel.domain)
        self.channel._internal_channel_id = uuid.uuid5(self.channel._internal_domain, self.channel.channel_id.hex)
        self.root.set_ids(self.channel._internal_domain, self.channel.channel_id)

    def recurse_set_ids(self, node):
        if node.kind == constants.CK_TOPIC:
            children = node.children

            for child in children:
                child.set_ids(self.channel._internal_domain, node.node_id)
                self.recurse_set_ids(child)
