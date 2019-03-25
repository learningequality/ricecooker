import requests

from ricecooker.classes.nodes import DocumentNode, VideoNode, TopicNode, AudioNode, HTML5AppNode
from ricecooker.classes.files import HTMLZipFile, VideoFile, SubtitleFile, DownloadFile, AudioFile, DocumentFile, ThumbnailFile, WebVideoFile, Base64ImageFile, YouTubeSubtitleFile, YouTubeVideoFile
from le_utils.constants import licenses

from urllib.parse import urlsplit
import hashlib
import os
from ricecooker.utils.transcode import transcode_video, transcode_audio

class UnidentifiedFileType(Exception):
    pass

class TranscodeVideo(object):
    "Placeholder filetype for videos that require transcoding"

class TranscodeAudio(object):
    "Placeholder filetype for audio that requires transcoding"

DOWNLOAD_FOLDER = "__downloads"  # this generates completed files
metadata = {}
have_setup = False

def setup_directory():
    global have_setup
    if have_setup: return
    have_setup = True
    try:
        os.mkdir(DOWNLOAD_FOLDER)
    except FileExistsError:
        pass


node_dict = {VideoFile: VideoNode,
             AudioFile: AudioNode,
             HTMLZipFile: HTML5AppNode,
             DocumentFile: DocumentNode}

# Long-Range TODOs
# -- package up images as zip files (using build_carousel)

def guess_extension(url):
    "Return the extension of a URL, i.e. the bit after the ."
    if not url:
        return ""
    filename = urlsplit(url).path
    if "." not in filename[-8:]: # arbitarily chosen
        return ""
    ext = "." + filename.split(".")[-1].lower()
    if "/" in ext:  # dot isn't in last part of path
        return ""
    return ext

def create_filename(url):
    return hashlib.sha1(url.encode('utf-8')).hexdigest() + guess_extension(url)

def download_file(url):
    """
    Download file to the DOWNLOAD_FOLDER with a content-generated filename.
    Return that filename and the mime type the server told us the file was
    """

    # url must be fully specified!
    response = requests.get(url, stream=True)
    setup_directory()
    filename = DOWNLOAD_FOLDER + "/" + create_filename(url)
    if not os.path.exists(filename):
        #print ("Downloading to {}".format(filename))
        #print ("{} bytes".format(response.headers.get("content-length")))
        try:
            with open(filename, "wb") as f:
                # https://www.reddit.com/r/learnpython/comments/27ba7t/requests_library_doesnt_download_directly_to_disk/
                for chunk in response.iter_content( chunk_size = 1024 ):
                    if chunk: # filter out keep-alive new chunks
                        f.write(chunk)
        except:  # Explicitly, we also want to catch CTRL-C here.
            print("Catching & deleting bad zip created by quitting")
            try:
                os.remove(filename)
            except FileNotFoundError:
                pass
            raise

    else:
        print ("Already exists in cache")
    # get the bit before the ; in the content-type, if there is one
    content_type = response.headers.get('Content-Type', "").split(";")[0].strip()
    return filename, content_type

def create_node(file_class=None, url=None, filename=None, title=None, license=None, copyright_holder=None, description=""):
    """
    Create a content node from either a URL or filename.
    Which content node is determined by:
    * the 'file_class' explicitly passed (e.g. VideoFile)
    * guessing from downloaded mimetype, file extension or magic bytes
    (see guess_type function)

    Use metadata to automatically fille in licence and copyright_holder details --
    if they're not provided correctly, things will break downstream
    """

    mime = None
    if filename is None:
        assert url, "Neither URL nor filename provided to create_node"
        filename, mime = download_file(url)

    if file_class is None:
        with open(filename, "rb") as f:
            magic_bytes = f.read(8)[:8]  # increase if we use python_magic
        file_class = guess_type(mime_type=mime,
                                extension=guess_extension(url or filename),
                                magic=magic_bytes)
        # there is a reasonable chance that the file isn't actually a suitable filetype
        # and that guess_type will raise an UnidentifiedFileType error.
    assert file_class
    print (file_class)

    # Transcode video if necessary
    if file_class == TranscodeVideo:
        file_class = VideoFile
        filename = transcode_video(filename)

    if file_class == TranscodeAudio:
        file_class = AudioFile
        filename = transcode_audio(filename)

    # TODO - consider non-MP3 audio files

    # Ensure file has correct extension for the type of file we think it is:
    # this is a requirement from sushichef.
    extensions = {VideoFile: ".mp4",
                  AudioFile: ".mp3",
                  DocumentFile: ".pdf",
                  HTMLZipFile: ".zip",}
    extension = extensions[file_class]
    if not filename.endswith(extension):
        new_filename = filename + extension
        os.rename(filename, new_filename)
        filename = new_filename

    # print (filename, os.path.getsize(filename))

    # Do not permit zero-byte files
    assert(os.path.getsize(filename))

    kwargs = {VideoFile: {"ffmpeg_settings": {"max_width": 480, "crf": 28}},
              AudioFile: {},
              DocumentFile: {},
              HTMLZipFile: {}}
    file_instance = file_class(filename, **kwargs[file_class])

    node_class = node_dict[file_class]

    return node_class(source_id=filename,  # unique due to content-hash
                      title=title,
                      license=license or metadata['license'],
                      copyright_holder=copyright_holder or metadata['copyright_holder'],
                      files=[file_instance],
                      description=description,
                      )

def guess_type(mime_type="",
               extension="",
               magic=b""):

    content_mapping = {"audio/mp3": AudioFile,
                       "video/mp4": VideoFile,
                       "audio/mp4": VideoFile,
                       "video/webm": TranscodeVideo,
                       "application/pdf": DocumentFile,
                       }

    if mime_type in content_mapping:
        return content_mapping[mime_type]

    extension_mapping = {".mp3": AudioFile,
                         ".mp4": VideoFile,
                         ".webm": TranscodeVideo,
                         ".m4v": TranscodeVideo,
                         ".pdf": DocumentFile,
                         # "zip": HTMLZipFile,  # primarily for carousels
                         }

    if extension in extension_mapping:
        return extension_mapping[extension]

    magic_mapping = {b"\xFF\xFB": AudioFile,
                     b"ID3": AudioFile,
                     b"%PDF": DocumentFile,
                     b"\x1A\x45\xDF\xA3": TranscodeVideo,
                     # b"PK": HTMLZipFile,
                     }

    for mapping in magic_mapping:
        if magic.startswith(mapping):
            return magic_mapping[mapping]

    # TODO -- consider using python_magic library

    raise UnidentifiedFileType(str([mime_type, extension]))

if __name__ == "__main__":
    print(create_node(DocumentFile, "http://www.pdf995.com/samples/pdf.pdf", license=licenses.CC_BY_NC_ND, copyright_holder="foo"))
