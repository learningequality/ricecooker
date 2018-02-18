#!/usr/bin/env python
import os
os.environ['CONTENTWORKSHOP_URL']= 'http://127.0.0.1:8000'

from le_utils.constants import languages as languages
from le_utils.constants import licenses

from ricecooker.chefs import SushiChef
from ricecooker.classes.nodes import ChannelNode, TopicNode, DocumentNode
from ricecooker.classes.files import DocumentFile, EPubFile


class EPubSushiChef(SushiChef):
    """
    This is simple sushi chef to test the new ePub files work inside DocumentNodes.
    """
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': 'learningequality.org',       # make sure to change this when testing
        'CHANNEL_SOURCE_ID': 'tutorial_test_02',   # channel's unique id
        'CHANNEL_TITLE': 'ePub test channel',
        'CHANNEL_LANGUAGE': 'en',
        'CHANNEL_THUMBNAIL': 'https://upload.wikimedia.org/wikipedia/en/thumb/1/14/EPUB_logo.svg/349px-EPUB_logo.svg.png',
        'CHANNEL_DESCRIPTION': 'This is a test channel with ePub files in it. Do not import into old version of Kolibri.'
    }

    def construct_channel(self, **kwargs):
        # create channel
        channel = self.get_channel(**kwargs)

        # create a topic "Ebooks" and add it to channel
        topic = TopicNode(
            source_id="ebooksfolder",
            title="Ebooks",
            language=languages.getlang('en').code,
        )
        channel.add_child(topic)

        # Create an ePub file and add ePub file to a DocumentNode
        epub_file = EPubFile(path='samplefiles/documents/laozi_tao-te-ching.epub')
        doc_node = DocumentNode(
            source_id="<en_doc_id>",
            title='Tao Te Ching',
            author='Lao Zi',
            description='This is a sample epub document',
            license=licenses.PUBLIC_DOMAIN,
            language=languages.getlang('en').code,
            files=[epub_file],
        )

        # Add document node to the topic
        topic.add_child(doc_node)

        return channel


if __name__ == '__main__':
    mychef = EPubSushiChef()
    mychef.main()
