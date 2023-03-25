#!/usr/bin/env python
from ricecooker.chefs import SushiChef
from ricecooker.classes.files import AudioFile
from ricecooker.classes.files import DocumentFile
from ricecooker.classes.licenses import get_license
from ricecooker.classes.nodes import AudioNode
from ricecooker.classes.nodes import DocumentNode
from ricecooker.classes.nodes import RemoteContentNode
from ricecooker.classes.nodes import TopicNode

"""
This example shows how to use the RemoteContentNode to create a channel that
curates content from another channel already on Studio into a new channel.
"""

SOURCE_DOMAIN = "testdomain.org"  ## change me!

original_channel_data = {
    "channel_id": None,
    "doc_node_id": None,
    "audio_node_id": None,
}


class OriginalChannelChef(SushiChef):
    channel_info = {
        "CHANNEL_TITLE": "Original channel",
        "CHANNEL_SOURCE_DOMAIN": SOURCE_DOMAIN,
        "CHANNEL_SOURCE_ID": "originalchannel",
        "CHANNEL_LANGUAGE": "en",
    }

    def construct_channel(self, **kwargs):
        channel = self.get_channel(**kwargs)

        document_node = DocumentNode(
            title="Growing potatoes",
            description="An article about growing potatoes on your rooftop.",
            source_id="pubs/mafri-potatoe",
            license=get_license("CC BY", copyright_holder="University of Alberta"),
            files=[
                DocumentFile(
                    path="https://www.gov.mb.ca/inr/pdf/pubs/mafri-potatoe.pdf",
                    language="en",
                )
            ],
        )
        channel.add_child(document_node)

        audio_node = AudioNode(
            source_id="also-sprach",
            title="Also Sprach Zarathustra",
            author="Kevin MacLeod / Richard Strauss",
            description="Also Sprach Zarathustra, Op. 30, is a tone poem by Richard Strauss, composed in 1896.",
            license=get_license("CC BY", copyright_holder="Kevin MacLeod"),
            files=[
                AudioFile(
                    "https://ia600702.us.archive.org/33/items/Classical_Sampler-9615/Kevin_MacLeod_-_Also_Sprach_Zarathustra.mp3"
                )
            ],
        )
        channel.add_child(audio_node)

        return channel


class CuratedChannelChef(SushiChef):
    channel_info = {
        "CHANNEL_TITLE": "Curated channel",
        "CHANNEL_SOURCE_DOMAIN": SOURCE_DOMAIN,
        "CHANNEL_SOURCE_ID": "curatedchannel",
        "CHANNEL_LANGUAGE": "en",
    }

    def construct_channel(self, **kwargs):
        channel = self.get_channel(**kwargs)

        document_topic = TopicNode(
            title="Documents",
            source_id="documents",
        )
        channel.add_child(document_topic)
        remote_document = RemoteContentNode(
            title="Glorious new title for the potato doc",
            source_channel_id=original_channel_data["channel_id"],
            source_node_id=original_channel_data["doc_node_id"],
        )
        document_topic.add_child(remote_document)

        audio_topic = TopicNode(
            title="Audio",
            source_id="audio",
        )
        channel.add_child(audio_topic)
        remote_audio = RemoteContentNode(
            source_channel_id=original_channel_data["channel_id"],
            source_node_id=original_channel_data["audio_node_id"],
        )
        audio_topic.add_child(remote_audio)

        return channel


if __name__ == "__main__":
    """
    Run this script on the command line using:
        python sushichef.py --token=YOURTOKENHERE9139139f3a23232
    """
    original_chef = OriginalChannelChef()
    original_chef.main()
    original_channel = original_chef.construct_channel()

    original_channel_data["channel_id"] = original_channel.get_node_id().hex
    original_channel_data["doc_node_id"] = (
        original_channel.children[0].get_node_id().hex
    )
    original_channel_data["audio_node_id"] = (
        original_channel.children[1].get_node_id().hex
    )

    input(
        "Please visit the URL above and deploy the channel, and wait for it to finish. Then press enter to continue..."
    )

    curated_chef = CuratedChannelChef()
    curated_chef.main()
