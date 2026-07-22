#!/usr/bin/env python
from le_utils.constants import licenses

from ricecooker.chefs import SushiChef
from ricecooker.classes.files import SubtitleFile
from ricecooker.classes.licenses import get_license
from ricecooker.classes.nodes import ContentNode
from ricecooker.classes.nodes import TopicNode


class TutorialChef(SushiChef):
    """
    The SushiChef class takes care of uploading channel to Kolibri Studio.
    """

    # 1. PROVIDE CHANNEL INFO  (replace <placeholders> with your own values)
    ############################################################################
    channel_info = {
        "CHANNEL_SOURCE_DOMAIN": "<yourdomain.org>",  # who is providing the content (e.g. learningequality.org)
        "CHANNEL_SOURCE_ID": "<yourid>",  # channel's unique id
        "CHANNEL_TITLE": "The tutorial channel",
        "CHANNEL_LANGUAGE": "en",
        # 'CHANNEL_THUMBNAIL': 'http://yourdomain.org/img/logo.jpg', # (optional) local path or url to image file
        # 'CHANNEL_DESCRIPTION': 'What is this channel about?',      # (optional) description of the channel (optional)
    }

    # 2. CONSTRUCT CHANNEL
    ############################################################################
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
        # TODO: Create your topic here

        # Now we are adding 'Example Topic' to our channel
        channel.add_child(exampletopic)
        # TODO: Add your topic to channel here

        # You can also add subtopics to topics
        # Here we are creating a subtopic named 'Example Subtopic'
        examplesubtopic = TopicNode(source_id="topic-1a", title="Example Subtopic")
        # TODO: Create your subtopic here

        # Now we are adding 'Example Subtopic' to our 'Example Topic'
        exampletopic.add_child(examplesubtopic)
        # TODO: Add your subtopic to your topic here

        # Content
        # You can add documents (pdfs and ePubs), videos, audios, and other content
        ########################################################################
        # let's create a document node called 'Example PDF'
        examplepdf = ContentNode(
            title="Example PDF",
            source_id="example-pdf",
            license=get_license(licenses.PUBLIC_DOMAIN),
            uri="http://www.pdf995.com/samples/pdf.pdf",
        )
        # TODO: Create your pdf node here (use any url to a .pdf file)

        # We are also going to add a video node called 'Example Video'
        fancy_license = get_license(
            licenses.SPECIAL_PERMISSIONS,
            description="Special license for ricecooker fans only.",
            copyright_holder="The chef video makers",
        )
        examplevideo = ContentNode(
            title="Example Video",
            source_id="example-video",
            license=fancy_license,
            uri="https://archive.org/download/CM_National_Rice_Cooker_1982/CM_National_Rice_Cooker_1982.mp4",
        )
        # uri alone can't express subtitles - add them explicitly, language is required
        examplevideo.add_file(
            SubtitleFile(
                path="https://raw.githubusercontent.com/learningequality/ricecooker/main/examples/tutorial/captions.vtt",
                language="sw",
            )
        )
        # TODO: Create your video node here (use any url to a .mp4 file)

        # Finally, we are creating an audio node called 'Example Audio'
        exampleaudio = ContentNode(
            title="Example Audio",
            source_id="example-audio",
            license=get_license(licenses.PUBLIC_DOMAIN),
            uri="https://ia802508.us.archive.org/5/items/testmp3testfile/mpthreetest.mp3",
        )
        # TODO: Create your audio node here (use any url to a .mp3 file)

        # Now that we have our files, let's add them to our channel
        channel.add_child(examplepdf)  # Adding 'Example PDF' to your channel
        exampletopic.add_child(
            examplevideo
        )  # Adding 'Example Video' to 'Example Topic'
        examplesubtopic.add_child(
            exampleaudio
        )  # Adding 'Example Audio' to 'Example Subtopic'

        # TODO: Add your pdf file to your channel
        # TODO: Add your video file to your topic
        # TODO: Add your audio file to your subtopic

        # the `construct_channel` method returns a ChannelNode that will be
        # processed by the ricecooker framework
        return channel


if __name__ == "__main__":
    """
    This code will run when the sushi chef is called from the command line.
    """
    chef = TutorialChef()
    chef.main()
