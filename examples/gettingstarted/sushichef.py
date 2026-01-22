#!/usr/bin/env python
"""
Getting Started Example: SushiChef

This example demonstrates a minimal SushiChef implementation for creating
a simple Kolibri channel with one topic and one document.

Note:
- This example is intended for demonstration purposes only.
- Some external URLs used here may become unavailable over time.
- The example may involve concepts that are not ideal for absolute beginners.
"""

from ricecooker.chefs import SushiChef
from ricecooker.classes.files import DocumentFile
from ricecooker.classes.licenses import get_license
from ricecooker.classes.nodes import DocumentNode
from ricecooker.classes.nodes import TopicNode


class SimpleChef(SushiChef):
    channel_info = {
        "CHANNEL_TITLE": "Potatoes info channel",
        "CHANNEL_SOURCE_DOMAIN": "<yourdomain.org>",  # where content comes from
        "CHANNEL_SOURCE_ID": "<unique id for the channel>",  # CHANGE ME!!!
        "CHANNEL_LANGUAGE": "en",  # le_utils language code
        "CHANNEL_THUMBNAIL": "https://upload.wikimedia.org/wikipedia/commons/b/b7/A_Grande_Batata.jpg",  # Example external image URL (may change or become unavailable)
        "CHANNEL_DESCRIPTION": "What is this channel about?",  # (optional)
    }

    def construct_channel(self, **kwargs):
        # Create the main channel object
        channel = self.get_channel(**kwargs)

        # Add a topic node for potatoes
        potato_topic = TopicNode(title="Potatoes!", source_id="<potatoes_id>")
        channel.add_child(potato_topic)

        # Add a document node under the potato topic
        document_node = DocumentNode(
            title="Growing potatoes",
            description="An article about growing potatoes on your rooftop.",
            source_id="pubs/mafri-potatoe",
            license=get_license("CC BY", copyright_holder="University of Alberta"),
            language="en",
            files=[
                DocumentFile(
                    path="https://www.gov.mb.ca/inr/pdf/pubs/mafri-potatoe.pdf",  # Example external PDF URL
                    language="en",
                )
            ],
        )
        potato_topic.add_child(document_node)

        return channel


if __name__ == "__main__":
    """
    Run this script from the command line using:
        python sushichef.py --token=YOUR_TOKEN_HERE

    Replace YOUR_TOKEN_HERE with a valid Kolibri Studio token.
    """
    simple_chef = SimpleChef()
    simple_chef.main()
