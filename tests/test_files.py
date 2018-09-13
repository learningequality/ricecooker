""" Tests for file downloading and processing """
import pytest
import os.path
import tempfile

from le_utils.constants import content_kinds, languages
from ricecooker.classes.files import *
from ricecooker.classes.files import _get_language_with_alpha2_fallback
from ricecooker.utils.zip import create_predictable_zip
from ricecooker import config

IS_TRAVIS_TESTING = "TRAVIS" in os.environ and os.environ["TRAVIS"] == "true"

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

@pytest.mark.skip('Skipping one-off create_predictable_zip stress test because long running...')
def test_create_many_predictable_zip_files(ndirs=8193):
    """
    Regression test for `OSError: [Errno 24] Too many open files` when using
    ricecooker.utils.zip.create_predictable_zip helper method:
    https://github.com/learningequality/ricecooker/issues/185
    Run `ulimit -a` to see the limits for # open files on your system and set ndirs
    to higher number to use this test. Also comment out the @pytest.mark.skip
    """
    zip_paths = []
    for _ in range(0, ndirs):
        inputdir = tempfile.mkdtemp()
        with open(os.path.join(inputdir,'index.html'), 'w') as testf:
            testf.write('something something')
        zip_path = create_predictable_zip(inputdir)
        zip_paths.append(zip_path)
    assert len(zip_paths) == ndirs, 'wrong number of zip files created'


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

@pytest.fixture
def subtitles_langs_internal():
    return ['en', 'es', 'pt-BR']

@pytest.fixture
def subtitles_langs_pycountry_mappable():
    return ['zu']

@pytest.fixture
def subtitles_langs_youtube_custom():
    return ['iw', 'zh-Hans', 'pt-BR']

@pytest.fixture
def subtitles_langs_ubsupported():
    return ['sgn', 'zzzza', 'ab-dab', 'bbb-qqq']

def test_is_youtube_subtitle_file_supported_language(subtitles_langs_internal,
                                                     subtitles_langs_pycountry_mappable,
                                                     subtitles_langs_youtube_custom):
    for lang in subtitles_langs_internal:
        assert is_youtube_subtitle_file_supported_language(lang), 'should be supported'
        lang_obj = _get_language_with_alpha2_fallback(lang)
        assert lang_obj is not None, 'lookup should return Language object'
    for lang in subtitles_langs_pycountry_mappable:
        assert is_youtube_subtitle_file_supported_language(lang), 'should be supported'
        lang_obj = _get_language_with_alpha2_fallback(lang)
        assert lang_obj is not None, 'lookup should return Language object'
    for lang in subtitles_langs_youtube_custom:
        assert is_youtube_subtitle_file_supported_language(lang), 'should be supported'
        lang_obj = _get_language_with_alpha2_fallback(lang)
        assert lang_obj is not None, 'lookup should return Language object'

def test_is_youtube_subtitle_file_unsupported_language(subtitles_langs_ubsupported):
    for lang in subtitles_langs_ubsupported:
        assert not is_youtube_subtitle_file_supported_language(lang), 'should not be supported'
        lang_obj = _get_language_with_alpha2_fallback(lang)
        assert lang_obj is None, 'lookup should fail'

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
