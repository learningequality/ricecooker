""" invoke with 'pytest' """

from ricecooker.utils.add_file import create_node, TranscodeAudio
from ricecooker.classes.nodes import AudioNode

def test_create_node_extension():
    """Detect by filename working correctly -- is not a valid MP3 file"""
    node = create_node(filename="tests/testcontent/fake.mp3",
                       license="Public Domain",
                       copyright_holder="X")
    assert isinstance(node, AudioNode)

@pytest.mark.skipif(IS_TRAVIS_TESTING, reason="Skipping ffmpeg tests on Travis.")
def test_webm():
    """Confirm we're automatically transcoding webm content"""
    node = create_node(filename="tests/testcontent/bigbuck_webm",
                       license="Public Domain",
                       copyright_holder="X")
    filename = str(node.files[0])
    with open(filename, "rb") as f:
        assert b"mp4" in f.read(40)[:40]

@pytest.mark.skipif(IS_TRAVIS_TESTING, reason="Skipping ffmpeg tests on Travis.")
def test_mp3():
    """Confirm forced conversion to MP3 works correctly"""
    node = create_node(filename="tests/testcontent/bigbuck_webm",
                       file_class = TranscodeAudio,
                       license="Public Domain",
                       copyright_holder="X")
    filename = str(node.files[0])
    print (filename)
    with open(filename, "rb") as f:
        assert b"ID3" in f.read(3)[:3]

