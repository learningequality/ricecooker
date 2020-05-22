#!/usr/bin/env python
from ricecooker.chefs import SushiChef
from ricecooker.classes.nodes import ChannelNode, TopicNode, DocumentNode
from ricecooker.classes.files import DocumentFile
from ricecooker.classes.licenses import get_license


class SimpleChef(SushiChef):
    channel_info = {
        "CHANNEL_TITLE": "Potatoes info channel",
        "CHANNEL_SOURCE_DOMAIN": "<yourdomain.org>",  # where content comes from
        "CHANNEL_SOURCE_ID": "<unique id for the channel>",  # CHANGE ME!!!
        "CHANNEL_LANGUAGE": "en",  # le_utils language code
        "CHANNEL_THUMBNAIL": "https://upload.wikimedia.org/wikipedia/commons/b/b7/A_Grande_Batata.jpg",  # (optional)
        "CHANNEL_DESCRIPTION": "What is this channel about?",  # (optional)
    }

    def construct_channel(self, **kwargs):
        channel = self.get_channel(**kwargs)
        potato_topic = TopicNode(title="Potatoes!", source_id="<potatoes_id>")
        channel.add_child(potato_topic)
        document_node = DocumentNode(
            title="Growing potatoes",
            description="An article about growing potatoes on your rooftop.",
            source_id="pubs/mafri-potatoe",
            license=get_license("CC BY", copyright_holder="University of Alberta"),
            language="en",
            files=[
                DocumentFile(
                    path="https://www.gov.mb.ca/inr/pdf/pubs/mafri-potatoe.pdf",
                    language="en",
                )
            ],
        )
        potato_topic.add_child(document_node)
        return channel


if __name__ == "__main__":
    """
    Run this script on the command line using:
        python sushichef.py  --token=YOURTOKENHERE9139139f3a23232
    """
    simple_chef = SimpleChef()
    simple_chef.main()
