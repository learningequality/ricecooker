#!/usr/bin/env python
import random
import string

from le_utils.constants import licenses

from ricecooker.chefs import SushiChef
from ricecooker.classes.files import AudioFile
from ricecooker.classes.files import DocumentFile
from ricecooker.classes.files import VideoFile
from ricecooker.classes.licenses import get_license
from ricecooker.classes.nodes import AudioNode
from ricecooker.classes.nodes import DocumentNode
from ricecooker.classes.nodes import TopicNode
from ricecooker.classes.nodes import VideoNode


class TestChef(SushiChef):
    """
    Used as an integration test by actually using Ricecooker to chef local test content into Studio.

    For anything you need to test, add it to the channel created in the `construct_channel`.

    Copied from examples/tutorial/sushichef.py
    """

    # Be sure we don't conflict with a channel someone else pushed before us when running this test
    # as the channel source domain and ID determine which Channel is updated on Studio and since
    # you'll run this with your own API key we can use this random (enough) string generator (thanks SO)
    # to append a random set of characters to the two values.
    def randomstring():
        return "".join(
            random.choice(string.ascii_uppercase + string.digits) for _ in range(8)
        )

    channel_info = {
        "CHANNEL_SOURCE_DOMAIN": "RicecookerIntegrationTest.{}".format(
            randomstring()
        ),  # who is providing the content (e.g. learningequality.org)
        "CHANNEL_SOURCE_ID": "RicecookerTests.{}".format(
            randomstring()
        ),  # channel's unique id
        "CHANNEL_TITLE": "Ricecooker Testing!",
        "CHANNEL_LANGUAGE": "en",
    }

    # CONSTRUCT CHANNEL
    def construct_channel(self, *args, **kwargs):
        """
        This method is reponsible for creating a `ChannelNode` object and
        populating it with `TopicNode` and `ContentNode` children.
        """
        # Create channel
        ########################################################################
        channel = self.get_channel(*args, **kwargs)  # uses self.channel_info

        # Create topics to add to your channel
        ########################################################################
        # Here we are creating a topic named 'Example Topic'
        exampletopic = TopicNode(source_id="topic-1", title="Example Topic")

        # Now we are adding 'Example Topic' to our channel
        channel.add_child(exampletopic)

        # You can also add subtopics to topics
        # Here we are creating a subtopic named 'Example Subtopic'
        examplesubtopic = TopicNode(source_id="topic-1a", title="Example Subtopic")

        # Now we are adding 'Example Subtopic' to our 'Example Topic'
        exampletopic.add_child(examplesubtopic)

        # Content
        # You can add documents (pdfs and ePubs), videos, audios, and other content
        # let's create a document file called 'Example PDF'
        document_file = DocumentFile(path="http://www.pdf995.com/samples/pdf.pdf")
        examplepdf = DocumentNode(
            title="Example PDF",
            source_id="example-pdf",
            files=[document_file],
            license=get_license(licenses.PUBLIC_DOMAIN),
        )

        # We are also going to add a video file called 'Example Video'
        video_file = VideoFile(
            path="https://ia600209.us.archive.org/27/items/RiceChef/Rice Chef.mp4"
        )
        fancy_license = get_license(
            licenses.SPECIAL_PERMISSIONS,
            description="Special license for ricecooker fans only.",
            copyright_holder="The chef video makers",
        )
        examplevideo = VideoNode(
            title="Example Video",
            source_id="example-video",
            files=[video_file],
            license=fancy_license,
        )

        # Finally, we are creating an audio file called 'Example Audio'
        audio_file = AudioFile(
            path="https://ia802508.us.archive.org/5/items/testmp3testfile/mpthreetest.mp3"
        )
        exampleaudio = AudioNode(
            title="Example Audio",
            source_id="example-audio",
            files=[audio_file],
            license=get_license(licenses.PUBLIC_DOMAIN),
        )

        # Now that we have our files, let's add them to our channel
        channel.add_child(examplepdf)  # Adding 'Example PDF' to your channel
        exampletopic.add_child(
            examplevideo
        )  # Adding 'Example Video' to 'Example Topic'
        examplesubtopic.add_child(
            exampleaudio
        )  # Adding 'Example Audio' to 'Example Subtopic'

        # the `construct_channel` method returns a ChannelNode that will be
        # processed by the ricecooker framework
        return channel


if __name__ == "__main__":
    """
    This code will run when the sushi chef is called from the command line.
    """
    chef = TestChef()
    print(
        "Note that you will need your Studio API key for this. It will upload to your account."
    )
    chef.main()
