""" Tests for file downloading and processing """

import pytest
import os.path
import uuid
import tempfile
from le_utils.constants import content_kinds, languages
from ricecooker.classes.nodes import *
from ricecooker.classes.files import *
from ricecooker import config


""" *********** CHANNEL FIXTURES *********** """
@pytest.fixture
def document_file():
    if not os.path.exists("tests/testcontent/testdocument.pdf"):
        with open("tests/testcontent/testdocument.pdf", 'wb') as docfile:
            docfile.write(b'testing')
    return DocumentFile("tests/testcontent/testdocument.pdf")

@pytest.fixture
def document_filename():
    return 'ae2b1fca515949e5d54fb22b8ed95575.pdf'

@pytest.fixture
def audio_file():
    if not os.path.exists("tests/testcontent/testaudio.mp3"):
        with open("tests/testcontent/testaudio.mp3", 'wb') as audiofile:
            audiofile.write(b'testing')
    return AudioFile("tests/testcontent/testaudio.mp3")

@pytest.fixture
def audio_filename():
    return 'ae2b1fca515949e5d54fb22b8ed95575.mp3'

@pytest.fixture
def video_file():
    if not os.path.exists("tests/testcontent/testvideo.mp4"):
        with open("tests/testcontent/testvideo.mp4", 'wb') as videofile:
            videofile.write(b'testing')
    return VideoFile("tests/testcontent/testvideo.mp4")

@pytest.fixture
def video_filename():
    return 'ae2b1fca515949e5d54fb22b8ed95575.mp4'

@pytest.fixture
def thumbnail_file():
    if not os.path.exists("tests/testcontent/testimage.png"):
        with open("tests/testcontent/testimage.png", 'wb') as imgfile:
            imgfile.write(b'testing')
    return ThumbnailFile("tests/testcontent/testimage.png")

@pytest.fixture
def thumbnail_filename():
    return 'ae2b1fca515949e5d54fb22b8ed95575.png'

@pytest.fixture
def subtitle_file():
    if not os.path.exists("tests/testcontent/testsubtitles.vtt"):
        with open("tests/testcontent/testsubtitles.vtt", 'wb') as subtitlefile:
            subtitlefile.write(b'testing')
    return SubtitleFile("tests/testcontent/testsubtitles.vtt", language='en')

@pytest.fixture
def subtitle_filename():
    return 'ae2b1fca515949e5d54fb22b8ed95575.vtt'

@pytest.fixture
def html_file():
    if not os.path.exists("tests/testcontent/testhtml.zip"):
        with zipfile.ZipFile("tests/testcontent/testhtml.zip", 'w', zipfile.ZIP_DEFLATED) as archive:
            info = zipfile.ZipInfo('index.html', date_time=(2013, 3, 14, 1, 59, 26))
            info.comment = "test file".encode()
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 0
            archive.writestr(info, '<div></div>')
    return HTMLZipFile("tests/testcontent/testhtml.zip")

@pytest.fixture
def html_filename():
    return '3ce367dc18043e18429432677e19e7c2.zip'


# Process all of the files
def process_files(video_file, html_file, audio_file, document_file, thumbnail_file, subtitle_file):
    video_file.process_file()
    html_file.process_file()
    audio_file.process_file()
    document_file.process_file()
    thumbnail_file.process_file()
    subtitle_file.process_file()


""" *********** DOWNLOAD TESTS *********** """
def test_download(video_file, html_file, audio_file, document_file, thumbnail_file, subtitle_file):
    try:
        process_files(video_file, html_file, audio_file, document_file, thumbnail_file, subtitle_file)
        assert True
    except Exception:
        assert False, "One or more of the files failed to download"

def test_download_filenames(video_file, video_filename, html_file, html_filename, audio_file, audio_filename,
    document_file, document_filename, thumbnail_file, thumbnail_filename, subtitle_file, subtitle_filename):
    assert video_file.process_file() == video_filename, "Video file should have filename {}".format(video_filename)
    #assert html_file.process_file() == html_filename, "HTML file should have filename {}".format(html_filename)
    assert audio_file.process_file() == audio_filename, "Audio file should have filename {}".format(audio_filename)
    assert document_file.process_file() == document_filename, "Document file should have filename {}".format(document_filename)
    assert thumbnail_file.process_file() == thumbnail_filename, "Thumbnail file should have filename {}".format(thumbnail_filename)
    assert subtitle_file.process_file() == subtitle_filename, "Subtitle file should have filename {}".format(subtitle_filename)

def test_download_to_storage(video_file, video_filename, html_file, html_filename, audio_file, audio_filename,
    document_file, document_filename, thumbnail_file, thumbnail_filename, subtitle_file, subtitle_filename):
    process_files(video_file, html_file, audio_file, document_file, thumbnail_file, subtitle_file)
    video_path = config.get_storage_path(video_filename)
    html_path = config.get_storage_path(html_filename)
    audio_path = config.get_storage_path(audio_filename)
    document_path = config.get_storage_path(document_filename)
    thumbnail_path = config.get_storage_path(thumbnail_filename)
    subtitle_path = config.get_storage_path(subtitle_filename)

    assert os.path.isfile(video_path), "Video should be stored at {}".format(video_path)
    # assert os.path.isfile(html_path), "HTML should be stored at {}".format(html_path)
    assert os.path.isfile(audio_path), "Audio should be stored at {}".format(audio_path)
    assert os.path.isfile(document_path), "Document should be stored at {}".format(document_path)
    assert os.path.isfile(thumbnail_path), "Thumbnail should be stored at {}".format(thumbnail_path)
    assert os.path.isfile(subtitle_path), "Subtitle should be stored at {}".format(subtitle_path)

def test_set_language():
    sub1 = SubtitleFile('path', language='en')
    sub2 = SubtitleFile('path', language=languages.getlang('es'))
    assert isinstance(sub1.language, str), "Subtitles must be converted to Language class"
    assert isinstance(sub2.language, str), "Subtitles can be passed as Langauge models"
    assert sub1.language == 'en', "Subtitles must have a language"
    assert sub2.language == 'es', "Subtitles must have a language"
    pytest.raises(TypeError, SubtitleFile, 'path', language='notalanguage')

def test_presets():
    assert True

def test_validate():
    assert True

def test_to_dict():
    assert True

""" *********** DOWNLOADFILE TESTS *********** """
def test_downloadfile_validate():
    assert True

def test_downloadfile_process_file():
    assert True


""" *********** THUMBNAILFILE TESTS *********** """
def test_thumbnailfile_validate():
    assert True

def test_thumbnailfile_to_dict():
    assert True

def test_languages():
    assert True


""" *********** DOCUMENTFILE TESTS *********** """
def test_documentfile_validate():
    assert True

def test_documentfile_to_dict():
    assert True


""" *********** HTMLZIPFILE TESTS *********** """
def test_htmlfile_validate():
    assert True

def test_htmlfile_to_dict():
    assert True


""" *********** EXTRACTEDVIDEOTHUMBNAILFILE TESTS *********** """
def test_extractedvideothumbnail_process_file():
    assert True

def test_extractedvideothumbnail_validate():
    assert True

def test_extractedvideothumbnail_to_dict():
    assert True

def test_extractedvideothumbnail_derive_thumbnail():
    assert True

""" *********** VIDEOFILE TESTS *********** """
def test_video_validate():
    assert True

def test_video_to_dict():
    assert True


""" *********** WEBVIDEOFILE TESTS *********** """
def test_webvideo_process_file():
    assert True

def test_webvideo_validate():
    assert True

def test_webvideo_to_dict():
    assert True


""" *********** YOUTUBEVIDEOFILE TESTS *********** """
def test_youtubevideo_process_file():
    assert True

def test_youtubevideo_validate():
    assert True

def test_youtubevideo_to_dict():
    assert True


""" *********** YOUTUBESUBTITLEFILE TESTS *********** """
def test_youtubesubtitle_process_file():
    assert True

def test_youtubesubtitle_validate():
    assert True

def test_youtubesubtitle_to_dict():
    assert True


""" *********** SUBTITLEFILE TESTS *********** """
def test_subtitle_validate():
    assert True

def test_subtitle_to_dict():
    assert True
