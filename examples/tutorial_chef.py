from ricecooker.classes.nodes import ChannelNode, HTML5AppNode, TopicNode, VideoNode, DocumentNode, AudioNode
from ricecooker.classes.files import DocumentFile, VideoFile, AudioFile
from le_utils.constants import licenses

def construct_channel(*args, **kwargs):

    """ Start by creating your channel """
    # Let's start by creating your own channel (replace <placeholders> with your own values)
    channel = ChannelNode(
        source_domain = "<yourdomain.org>",     # (e.g. "jamiealexandre.com")
        source_id = "<yourid>",                 # (e.g. "my-sushi-chef")
        title = "Tutorial channel",             # (e.g. "My Sushi Chef Channel")
    )

    """ Create topics to add to your channel """
    # Here we are creating a topic named 'Example Topic'
    exampletopic = TopicNode(source_id="topic-1", title="Example Topic")
    # TODO: Create your topic here

    # Now we are adding 'Example Topic' to our channel
    channel.add_child(exampletopic)
    # TODO: Add your topic to channel here


    """ You can also add subtopics to topics """
    # Here we are creating a subtopic named 'Example Subtopic'
    examplesubtopic = TopicNode(source_id="topic-1a", title="Example Subtopic")
    # TODO: Create your subtopic here

    # Now we are adding 'Example Subtopic' to our 'Example Topic'
    exampletopic.add_child(examplesubtopic)
    # TODO: Add your subtopic to your topic here


    """ You can also add pdfs, videos, and audio files to your channel """
    # Next, let's create a document file called 'Example PDF'
    examplepdf = DocumentNode(title="Example PDF", source_id="example-pdf", files=[DocumentFile(path="http://www.pdf995.com/samples/pdf.pdf")], license=licenses.CC_BY_SA)
    # TODO: Create your pdf file here (use any url to a .pdf file)

    # We are also going to add a video file called 'Example Video'
    examplevideo = VideoNode(title="Example Video", source_id="example-video", files=[VideoFile(path="https://ia600209.us.archive.org/27/items/RiceChef/Rice Chef.mp4")], license=licenses.CC_BY_SA)
    # TODO: Create your video file here (use any url to a .mp4 file)

    # Finally, we are creating an audio file called 'Example Audio'
    exampleaudio = AudioNode(title="Example Audio", source_id="example-audio", files=[AudioFile(path="https://ia802508.us.archive.org/5/items/testmp3testfile/mpthreetest.mp3")], license=licenses.CC_BY_SA)
    # TODO: Create your audio file here (use any url to a .mp3 file)

    # Now that we have our files, let's add them to our channel
    channel.add_child(examplepdf) # Adding 'Example PDF' to your channel
    exampletopic.add_child(examplevideo) # Adding 'Example Video' to 'Example Topic'
    examplesubtopic.add_child(exampleaudio) # Adding 'Example Audio' to 'Example Subtopic'

    # TODO: Add your pdf file to your channel
    # TODO: Add your video file to your topic
    # TODO: Add your audio file to your subtopic

    return channel

