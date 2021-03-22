""" Tests for file downloading and processing """
import os.path
import pytest
from shutil import copyfile
import tempfile

from le_utils.constants import languages
from ricecooker.classes.files import YouTubeVideoFile
from ricecooker.classes.files import YouTubeSubtitleFile
from ricecooker.classes.files import SubtitleFile
from ricecooker.classes.files import is_youtube_subtitle_file_supported_language
from ricecooker.classes.files import _get_language_with_alpha2_fallback
from ricecooker.utils.zip import create_predictable_zip
from ricecooker import config

from test_pdfutils import _save_file_url_to_path


# Process all of the files
def process_files(video_file, html_file, audio_file, document_file, epub_file, thumbnail_file, subtitle_file):
    video_file.process_file()
    html_file.process_file()
    audio_file.process_file()
    document_file.process_file()
    epub_file.process_file()
    thumbnail_file.process_file()
    subtitle_file.process_file()


""" *********** DOWNLOAD TESTS *********** """
def test_download(video_file, html_file, audio_file, document_file, epub_file, thumbnail_file, subtitle_file):
    try:
        process_files(video_file, html_file, audio_file, document_file, epub_file, thumbnail_file, subtitle_file)
        assert True
    except Exception:
        assert False, "One or more of the files failed to download"

def test_download_filenames(video_file, video_filename, html_file, html_filename, audio_file, audio_filename,
    document_file, document_filename, epub_file, epub_filename, thumbnail_file, thumbnail_filename, subtitle_file, subtitle_filename):
    assert video_file.process_file() == video_filename, "Video file should have filename {}".format(video_filename)
    assert html_file.process_file() == html_filename, "HTML file should have filename {}".format(html_filename)
    assert audio_file.process_file() == audio_filename, "Audio file should have filename {}".format(audio_filename)
    assert document_file.process_file() == document_filename, "PDF document file should have filename {}".format(document_filename)
    assert epub_file.process_file() == epub_filename, "ePub document file should have filename {}".format(epub_filename)
    assert thumbnail_file.process_file() == thumbnail_filename, "Thumbnail file should have filename {}".format(thumbnail_filename)
    assert subtitle_file.process_file() == subtitle_filename, "Subtitle file should have filename {}".format(subtitle_filename)

def test_download_to_storage(video_file, video_filename, html_file, html_filename, audio_file, audio_filename,
    document_file, document_filename, epub_file, epub_filename, thumbnail_file, thumbnail_filename, subtitle_file, subtitle_filename):
    process_files(video_file, html_file, audio_file, document_file, epub_file, thumbnail_file, subtitle_file)
    video_path = config.get_storage_path(video_filename)
    html_path = config.get_storage_path(html_filename)
    audio_path = config.get_storage_path(audio_filename)
    document_path = config.get_storage_path(document_filename)
    epub_path = config.get_storage_path(epub_filename)
    thumbnail_path = config.get_storage_path(thumbnail_filename)
    subtitle_path = config.get_storage_path(subtitle_filename)

    assert os.path.isfile(video_path), "Video should be stored at {}".format(video_path)
    assert os.path.isfile(html_path), "HTML should be stored at {}".format(html_path)
    assert os.path.isfile(audio_path), "Audio should be stored at {}".format(audio_path)
    assert os.path.isfile(document_path), "PDF document should be stored at {}".format(document_path)
    assert os.path.isfile(epub_path), "ePub document should be stored at {}".format(epub_path)
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

@pytest.mark.skipif(True, reason="Requires connecting to youtube.")
def test_youtubevideo_process_file(youtube_video_dict):
    video_file = YouTubeVideoFile(youtube_id=youtube_video_dict['youtube_id'])
    filename = video_file.process_file()
    assert filename is not None, 'Processing YouTubeVideoFile file failed'
    assert filename.endswith('.mp4'), 'Wrong extenstion for video'

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

@pytest.mark.skipif(True, reason="Requires connecting to youtube.")
def test_youtubesubtitle_process_file(youtube_video_with_subs_dict):
    youtube_id = youtube_video_with_subs_dict['youtube_id']
    lang = youtube_video_with_subs_dict['subtitles_langs'][0]
    sub_file = YouTubeSubtitleFile(youtube_id=youtube_id, language=lang)
    filename = sub_file.process_file()
    assert filename is not None, 'Processing YouTubeSubtitleFile file failed'
    assert filename.endswith('.vtt'), 'Wrong extenstion for video subtitles'
    assert not filename.endswith('.' + lang + '.vtt'), 'Lang code in extension'

def test_youtubesubtitle_validate():
    assert True

def test_youtubesubtitle_to_dict():
    assert True




""" *********** SUBTITLEFILE TESTS *********** """

def test_convertible_substitles_ar_srt():
    """
    Basic check that srt --> vtt conversion works.
    """
    local_path = os.path.join("tests", "testcontent", "samples", "testsubtitles_ar.srt")
    assert os.path.exists(local_path)
    subtitle_file = SubtitleFile(local_path, language='ar')
    filename = subtitle_file.process_file()
    assert filename, 'converted filename must exist'
    assert filename.endswith('.vtt'), 'converted filename must have .vtt extension'
    storage_path = config.get_storage_path(filename)
    with open(storage_path, encoding="utf-8") as converted_vtt:
        filecontents = converted_vtt.read()
        check_words = 'لناس على'
        assert check_words in filecontents, 'missing check word in converted subs'


@pytest.fixture
def bad_subtitles_file():
    local_path = os.path.join("tests", "testcontent", "generated", "unconvetible.sub")
    if not os.path.exists(local_path):
        with open(local_path, 'wb') as f:
            f.write(b'this is an invalid subtitle file that cant be converted.')
            f.flush()
    else:
        f = open(local_path, 'rb')
        f.close()
    return f  # returns a closed file descriptor which we use for name attribute


def test_bad_subtitles_raises(bad_subtitles_file):
    subs_file = SubtitleFile(bad_subtitles_file.name, language='en')
    pytest.raises(ValueError, subs_file.process_file)




PRESSURECOOKER_REPO_URL = "https://raw.githubusercontent.com/bjester/pressurecooker/"
PRESSURECOOKER_FILES_URL_BASE = PRESSURECOOKER_REPO_URL + "pycaption/tests/files/subtitles/"
PRESSURECOOKER_SUBS_FIXTURES = [
    {
      'srcfilename': 'basic.srt',
      'subtitlesformat': 'srt',
      'language': languages.getlang('ar'),
      'check_words': 'البعض أكثر'
    },
    {
      'srcfilename': 'encapsulated.sami',
      'subtitlesformat': 'sami',
      'language': 'en',
      'check_words': 'we have this vision of Einstein',
    },
    {
      'srcfilename': 'basic.vtt',
      'subtitlesformat': 'vtt',
      'language': 'ar',
      'check_words': 'البعض أكثر'
    },
    {
      'srcfilename': 'encapsulated.vtt',
      'subtitlesformat': 'vtt',
      'language': 'en',
      'check_words': 'we have this vision of Einstein'
    },
]


def download_fixture_files(fixtures_list):
    """
    Downloads all the subtitles test files and return as list of fixutes dicts.
    """
    fixtures = []
    for fixture in fixtures_list:
        srcfilename = fixture['srcfilename']
        localpath = os.path.join('tests', 'testcontent', 'downloaded', srcfilename)
        if not os.path.exists(localpath):
            url = fixture['url'] if 'url' in fixture.keys() \
                else PRESSURECOOKER_FILES_URL_BASE + srcfilename
            print(url)
            _save_file_url_to_path(url, localpath)
            assert os.path.exists(localpath), 'Error mising local test file ' + localpath
        fixture['localpath'] = localpath
        fixtures.append(fixture)
    return fixtures


@pytest.fixture
def pressurcooker_test_files():
    """
    Downloads all the subtitles test files and return as list of fixutes dicts.
    """
    return download_fixture_files(PRESSURECOOKER_SUBS_FIXTURES)

@pytest.fixture
def youtube_test_file():
    return download_fixture_files([
        {
          'srcfilename': 'testsubtitles_ar.ttml',
          'subtitlesformat': 'ttml',
          'language': 'ar',
          'check_words': 'Mohammed Liyaudheen wafy',
          'url': 'https://www.youtube.com/api/timedtext?lang=ar&v=C_9f7Qq4YZc&fmt=ttml&name='
        },
    ])


def test_convertible_substitles_from_pressurcooker(pressurcooker_test_files):
    """
    Try to load all the test files used in pressurecooker as riceccooker `SubtitleFile`s.
    All subs have the appropriate extension so no need to specify `subtitlesformat`.
    """
    for fixture in pressurcooker_test_files:
        localpath = fixture['localpath']
        assert os.path.exists(localpath), 'Error mising local test file ' + localpath
        subtitle_file =  SubtitleFile(localpath, language=fixture['language'])
        filename = subtitle_file.process_file()
        assert filename, 'conferted filename must exit'
        assert filename.endswith('.vtt'), 'conferted filename must have .vtt extension'
        storage_path = config.get_storage_path(filename)
        with open(storage_path, encoding="utf-8") as converted_vtt:
            filecontents = converted_vtt.read()
            assert fixture['check_words'] in filecontents, 'missing check_words in converted subs'


def test_convertible_substitles_ar_ttml(youtube_test_file):
    """
    Regression test to make sure correct lang_code is detected from .ttml data.
    """
    local_path = os.path.join("tests", "testcontent", "downloaded", "testsubtitles_ar.ttml")
    assert os.path.exists(local_path)
    subtitle_file = SubtitleFile(local_path, language='ar')
    filename = subtitle_file.process_file()
    assert filename, 'conferted filename must exit'
    assert filename.endswith('.vtt'), 'conferted filename must have .vtt extension'


def test_convertible_substitles_noext_subtitlesformat():
    """
    Check that we handle correctly cases when path doesn't contain extenstion.
    """
    local_path = os.path.join("tests", "testcontent", "downloaded", "testsubtitles_ar.ttml")
    assert os.path.exists(local_path)
    local_path_no_ext = local_path.replace('.ttml', '')
    copyfile(local_path, local_path_no_ext)
    assert os.path.exists(local_path_no_ext)
    subtitle_file = SubtitleFile(
        local_path_no_ext,
        language='ar',
        subtitlesformat='ttml'          # settting subtitlesformat becaue no ext
    )
    filename = subtitle_file.process_file()
    assert filename, 'conferted filename must exit'
    assert filename.endswith('.vtt'), 'conferted filename must have .vtt extension'


def test_convertible_substitles_weirdext_subtitlesformat():
    """
    Check that we handle cases when ext cannot be guessed from URL or localpath.
    Passing `subtitlesformat` allows chef authors to manually specify subs format.
    """
    subs_url = 'https://commons.wikimedia.org/w/api.php?' \
        + 'action=timedtext&title=File%3AA_Is_for_Atom_1953.webm&lang=es&trackformat=srt'
    subtitle_file = SubtitleFile(
        subs_url,
        language='es',
        subtitlesformat='srt'  # set subtitlesformat when can't inferr ext form url
    )
    filename = subtitle_file.process_file()
    assert filename, 'conferted filename must exit'
    assert filename.endswith('.vtt'), 'conferted filename must have .vtt extension'
    storage_path = config.get_storage_path(filename)
    with open(storage_path, encoding="utf-8") as converted_vtt:
        filecontents = converted_vtt.read()
        assert 'El total de los protones y neutrones de un átomo' in filecontents, \
            'missing check words in converted subs'
