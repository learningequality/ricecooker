import base64
import copy
import io
import json
import mimetypes
import os
import sys
import tempfile
import tracemalloc
import urllib.parse
import zipfile
from contextlib import contextmanager
from contextlib import ExitStack
from sys import platform
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
import requests
import urllib3
import yt_dlp
from fake_session import fake_download_session
from le_utils.constants import format_presets
from le_utils.constants import licenses
from vcr_config import my_vcr

from ricecooker import config
from ricecooker.classes.licenses import get_license
from ricecooker.classes.nodes import ContentNode
from ricecooker.exceptions import InvalidNodeException
from ricecooker.utils.caching import generate_key
from ricecooker.utils.caching import set_cache_data
from ricecooker.utils.pipeline import FilePipeline
from ricecooker.utils.pipeline.context import FileMetadata
from ricecooker.utils.pipeline.exceptions import ExpectedFileException
from ricecooker.utils.pipeline.exceptions import InvalidFileException
from ricecooker.utils.pipeline.file_handler import FileHandler
from ricecooker.utils.pipeline.transfer import Base64FileHandler
from ricecooker.utils.pipeline.transfer import CatchAllWebResourceDownloadHandler
from ricecooker.utils.pipeline.transfer import DiskResourceHandler
from ricecooker.utils.pipeline.transfer import DownloadStageHandler
from ricecooker.utils.pipeline.transfer import (
    get_filename_from_content_disposition_header,
)
from ricecooker.utils.pipeline.transfer import GoogleDriveHandler
from ricecooker.utils.pipeline.transfer import read
from ricecooker.utils.pipeline.transfer import SingleFileRenderHandler
from ricecooker.utils.pipeline.transfer import YouTubeContextMetadata
from ricecooker.utils.pipeline.transfer import YoutubeDownloadHandler

from .helpers import _PNG_1x1
from .helpers import fake_render_page

content_disposition_filename_cases = [
    ('Content-Disposition: attachment; filename="example.jpg"', "example.jpg"),
    (
        "Content-Disposition: attachment; filename*=UTF-8''%E4%BE%8B%E5%AD%90.jpg",
        "例子.jpg",
    ),
    ('Content-Disposition: inline; filename="document.pdf"', "document.pdf"),
    ("Content-Disposition: attachment; filename=plainfile.txt", "plainfile.txt"),
    (
        "Content-Disposition: attachment; filename*=UTF-8''%C3%A9l%C3%A9phant.jpg",
        "éléphant.jpg",
    ),
    ("Content-Disposition: attachment", None),
    (
        "Content-Disposition: attachment; filename=\"\"; filename*=UTF-8''%F0%9F%98%82.jpg",
        "😂.jpg",
    ),
    (
        "Content-Disposition: attachment; filename=\"EURO rates\"; filename*=utf-8''%E2%82%AC%20rates.txt",
        "€ rates.txt",
    ),
]


@pytest.mark.parametrize(
    "content_disposition, expected", content_disposition_filename_cases
)
def test_get_filename_from_content_disposition_header(content_disposition, expected):
    result = get_filename_from_content_disposition_header(content_disposition)
    assert result == expected, (
        f"Failed on {content_disposition}: expected {expected}, got {result}"
    )


# Google Drive handler integration tests


def generate_test_private_key():
    """Function to generate fresh test keys if needed.

    Note: This is only included for reference/regeneration. Tests use the static MOCK_PRIVATE_KEY.
    """
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
    except ImportError:
        return None

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    return pem.decode("utf-8")


MOCK_PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDfRVanH20ggRRz
/11XCdZyv5LldFXoePAxnzEUHSBap9enz9sroBQ9A0DFDc84Hm9yT+puXIt9WG8q
p/6xlYuy/yTeDxEf3SMhWz78iCHz0vd2LNP781Ht0LHLsGx6IqJmTwNz49N35QqM
4R5PGg8zPglZyYPVQMliivbYAKaiXeHvlEn8RykVe27r9HvvxVmrQHDNRLla4CES
yR0w/w4WLgr4sWWMjpwrADFpFP3POGF9t18eoi8XLRdgVuhDn1fNBK1Fz8zAZpjy
c4hwL09vcuYl09RtnxmCV3CdtJpvDZaM8cPMwoFrgikCD6JI5OgzTfqq7OV4wr9g
v+QdFNbzAgMBAAECggEAPm7POlBpXYt6wq0H1szjcJbtZshPNYCL+fQ/7xXt9Cu2
/C/9Y4eR4TXFqNShu1mXZGnAbjfmsZhHDbCIYfQlalo6XvXrnfNiXXN8e3U9uUam
+B608GEr6cpPzVt6GfURYHZ7yq5MddxQRPC2Xvw0f+m7B6Z3/Ovu5GVjfSdBcWk1
XRwn6hT3mYsTD7Rox37UhCUaF/CY2KvEinFTZyBax91Bh7XBrAIWEbwRQhUFe+lN
qCw/25qYvgCZCUrnfVt9XTIvKlkrdlZECGZGbVoT38r2niT73O/eXcQKkLbGENzp
NWXyWpiKHJ6NCqShd+ArYsGPOjz65PTd4EDACaYzUQKBgQD8Jz7a1hJWDzv1L+Zc
1O6eBn+J666PeOG74AvPtFmKU+/PCrKYeKjWFPCDJ1FuUsnOU15JaXz+nDFk8hOF
FJ33yhglskytEyc9RPsqwlkgMyzjX+nE30se+7MUHjliDbdOJjDzlJE4Khr5/ZR+
3QNpeTkeX9Q3FK53cUT1+YlH5wKBgQDirUvH9lXhRBD6PZXP0R1ceLpVQF9A6g8y
g9GWkUvjskMFIP4x8FXVdG93vzQhbGmGJ0asRRsSIYFsgJd4ov38AphRbI+y3Qaq
dGpimfcif1Bl8GoL8/jMGOwL+ARb83EE14ZJKE+eD3fBgpJhsGs97Lh/CaI7+99F
J2d7I3xnFQKBgQDIqobX6sL+3/LMRklimUYoVm2LGhd6MC4csMlVi2YysmfG8fF9
a5CZhmJ9TX39eT8GxsvjSmLh0PVyK0AjiWvJdXhQD5v7pKF2nf3wYmhBOti/PmYw
ea8zwgUavo7WHKpDNBuCzTngY4nCZu6VI1gCySkOph6hkwDhJzBFPEfnAwKBgFhk
Y2yyboLNXCF46naDgQOSQHcGBx71Jr/4Dz67ofBEj0Xsu7MVmSMHqH/1m4p9EBk0
L6b1u7yyPBnneymbxZcEHAmEX/TLo9HMW7/fcjONmfhma7QFiztrbICuUmTY5XWR
5deZVJK6TWS0WgimFuuq57cCNrVVXpdE6mFmURiRAoGAJyYYtdgT0XqHi1PrTZty
15tVfl5pbHPS1JAVz5aLow+Kc/O4lxd2RVteCI7ivl8MbC3sS8WzwfnDCdlfbOnz
OXxXNQ+TipVqG2xCyghu2ZiA/7hJmHKso843cqyRskIGpDYrdzimjxiJ34O7Rr7O
9B8SctgvCfZ5FT83MSkDtIA=
-----END PRIVATE KEY-----
"""


@pytest.fixture
def mock_google_creds(monkeypatch):
    """Fixture that provides mock Google credentials if real ones aren't configured.

    If config.GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH is set, this is a no-op.
    Otherwise, creates a temporary mock credentials file and patches the config path.
    """
    # If real credentials exist, use those
    if os.environ.get("GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH"):
        yield
        return

    # Create minimal mock service account credentials
    mock_credentials = {
        "type": "service_account",
        "project_id": "mock-project",
        "private_key_id": "mock_key_id",
        "private_key": MOCK_PRIVATE_KEY,
        "client_email": "mock@mock-project.iam.gserviceaccount.com",
        "client_id": "123456789",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/mock%40mock-project.iam.gserviceaccount.com",
    }

    # Create temporary credentials file
    temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(mock_credentials, temp_file)
    temp_file.close()

    # Patch config to use our temporary file
    monkeypatch.setattr(
        "ricecooker.config.GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH", temp_file.name
    )

    yield

    # Clean up temporary file
    if os.path.exists(temp_file.name):
        os.unlink(temp_file.name)


# All these files are in this Google Drive folder on the Learning Equality Google Drive:
# https://drive.google.com/drive/folders/1o15rBViWv-evjN-CkV1WDEpWeTGyUAf2
# in case they ever need to be updated or changed.
# If they are updated, the relevant cassettes for these tests should be deleted and recreated by running
# the test suite with a Google service account with read permissions to this folder.
# If additional file types should be tested, they can be added to this folder and explicitly referenced below.
slide_show_link = "https://docs.google.com/presentation/d/1o8BJz3RJkhjFSitjOLNb7DNkpNwpXXWs2n2TpeMdO2w/edit?usp=drive_link"
doc_link = "https://docs.google.com/document/d/1T9dM1gbOc_aOXwvs8H1bkqSfJhcnLG11yZQ9RPEJI6Y/edit?usp=drive_link"
video_link = "https://drive.google.com/file/d/1ls8sGsz8QMSx7fOQYNXIuY0FMyB30OaR/view?usp=drive_link"
pdf_link = "https://drive.google.com/file/d/1xhU-khyG_n1AEGQX-M4p3jDu9fmZ6JDT/view?usp=drive_link"
vtt_link = "https://drive.google.com/file/d/1wLoTx5ZjmsN9E7q6FXz6fz9qWjTnpYED/view?usp=drive_link"
audio_link = "https://drive.google.com/file/d/1XGeJ7ySmMLcJkQjPJoBy2JX_WJcILbXU/view?usp=drive_link"
channel_spreadsheet_link = "https://docs.google.com/spreadsheets/d/1-IReWbsN4YYhojA1cqyOC2PciKsv-j4HFBpihszxW5A/edit?usp=drive_link"


def test_gdrive_should_handle():
    handler = GoogleDriveHandler()
    assert handler.should_handle(slide_show_link)
    assert handler.should_handle(doc_link)
    assert handler.should_handle(video_link)
    assert handler.should_handle(pdf_link)
    assert handler.should_handle(vtt_link)
    assert handler.should_handle(audio_link)
    assert handler.should_handle(channel_spreadsheet_link)


def test_gdrive_forwards_init_context_to_super():
    # No-arg construction is unchanged and init context defaults to empty.
    handler = GoogleDriveHandler()
    assert handler._init_context == {}
    assert handler._drive_service is None


def test_gdrive_init_context_validated_via_super():
    # GoogleDriveHandler's CONTEXT_CLASS (base ContextMetadata) has no fields,
    # so any init context is rejected -- but by super's validation, proving the
    # custom __init__ forwards **context rather than swallowing it.
    with pytest.raises(TypeError, match="unexpected context field"):
        GoogleDriveHandler(default_ext="pdf")


def test_gdrive_without_extra_reports_missing_library():
    blocked = dict.fromkeys(
        ["googleapiclient", "googleapiclient.errors", "googleapiclient.http"]
    )
    with patch.dict(sys.modules, blocked):
        with pytest.raises(RuntimeError, match="google-api-python-client"):
            GoogleDriveHandler().execute(pdf_link, skip_cache=True)


@my_vcr.use_cassette
def test_gdrive_slideshow(mock_google_creds):
    """
    At the moment we are exporting Google Slides as PDFs
    If we ever decide to update this, this test will need to be updated.
    """
    handler = GoogleDriveHandler()
    assert handler.should_handle(slide_show_link)
    file_metadata = handler.execute(slide_show_link)
    assert file_metadata is not None
    assert file_metadata[0].filename.endswith("pdf")
    assert file_metadata[0].original_filename == "Slip sliding away"


@my_vcr.use_cassette
def test_gdrive_doc(mock_google_creds):
    """
    We export Google Docs as .docx so they flow through the pandoc-based
    DocumentConversionHandler and become KPUB.
    """
    handler = GoogleDriveHandler()
    assert handler.should_handle(doc_link)
    file_metadata = handler.execute(doc_link)
    assert file_metadata is not None
    assert file_metadata[0].filename.endswith("docx")
    assert file_metadata[0].original_filename == "This is a sample document"


@my_vcr.use_cassette
def test_gdrive_video(mock_google_creds):
    handler = GoogleDriveHandler()
    assert handler.should_handle(video_link)
    file_metadata = handler.execute(video_link)
    assert file_metadata is not None
    assert file_metadata[0].filename.endswith("ogv")
    assert file_metadata[0].original_filename == "low_res_ogv_video.ogv"


@my_vcr.use_cassette
def test_gdrive_pdf(mock_google_creds):
    handler = GoogleDriveHandler()
    assert handler.should_handle(pdf_link)
    file_metadata = handler.execute(pdf_link)
    assert file_metadata is not None
    assert file_metadata[0].filename.endswith("pdf")
    assert file_metadata[0].original_filename == "41568-pdf.pdf"


@my_vcr.use_cassette
def test_gdrive_vtt(mock_google_creds):
    handler = GoogleDriveHandler()
    assert handler.should_handle(vtt_link)
    file_metadata = handler.execute(vtt_link)
    assert file_metadata is not None
    assert file_metadata[0].filename.endswith("vtt")
    assert file_metadata[0].original_filename == "encapsulated.vtt"


@my_vcr.use_cassette
def test_gdrive_audio(mock_google_creds):
    handler = GoogleDriveHandler()
    assert handler.should_handle(audio_link)
    file_metadata = handler.execute(audio_link)
    assert file_metadata is not None
    assert file_metadata[0].filename.endswith("mp3")
    assert file_metadata[0].original_filename == "audio_media_test.mp3"


@my_vcr.use_cassette
def test_gdrive_channel_spreadsheet(mock_google_creds):
    handler = GoogleDriveHandler()
    assert handler.should_handle(channel_spreadsheet_link)
    file_metadata = handler.execute(channel_spreadsheet_link)
    assert file_metadata is not None
    assert file_metadata[0].filename.endswith("xlsx")
    assert file_metadata[0].original_filename == "Channel spreadsheet"


@pytest.mark.parametrize(
    "url,claimed",
    [
        ("https://vimeo.com/76979871", True),
        ("https://youtu.be/abc123def45", True),
        # Claimed by the playlist-only KhanAcademyUnit extractor
        (
            "https://www.khanacademy.org/math/algebra/x2f8bb11595b61c86:foundation-algebra",
            True,
        ),
        # Only yt-dlp's Generic extractor claims a plain file URL
        ("https://example.com/video.mp4", False),
        ("/home/user/video.mp4", False),
        # Claimed by yt-dlp's Imgur, Dropbox, Wikimedia and NYTimesArticle extractors
        ("https://i.imgur.com/abcdefg.png", False),
        ("https://www.dropbox.com/s/abc123/doc.pdf?dl=1", False),
        ("https://commons.wikimedia.org/wiki/File:Example.jpg", False),
        ("https://www.nytimes.com/2024/01/01/world/story.html", False),
    ],
)
def test_yt_dlp_should_handle(url, claimed):
    assert YoutubeDownloadHandler().should_handle(url) is claimed


def test_yt_dlp_default_format_selects_split_mp4_streams():
    # Vimeo's shape: no progressive mp4, and its audio-only formats report ext=mp4
    formats = [
        {
            "format_id": "video",
            "ext": "mp4",
            "vcodec": "avc1",
            "acodec": "none",
            "height": 360,
        },
        {"format_id": "audio", "ext": "mp4", "vcodec": "none", "acodec": "mp4a"},
    ]
    for f in formats:
        f.update(url="https://example.com/" + f["format_id"], protocol="https")
    [kwargs] = YoutubeDownloadHandler().get_file_kwargs(YouTubeContextMetadata())
    select = yt_dlp.YoutubeDL().build_format_selector(
        kwargs["yt_dlp_settings"]["format"] + kwargs["format_fallback"]
    )
    selected = list(
        select(
            {
                "formats": formats,
                "has_merged_format": False,
                "incomplete_formats": False,
            }
        )
    )
    assert [f["format_id"] for f in selected] == ["video+audio"]


@my_vcr.use_cassette("test_gdrive_video")
def test_download_stage_sends_gdrive_links_to_drive_handler(mock_google_creds):
    result = DownloadStageHandler().execute(video_link)
    assert result[0].original_filename == "low_res_ogv_video.ogv"


def test_yt_dlp_default_cache_key_is_unchanged():
    url = "http://www.youtube.com/watch?v=abc123def45"
    [kwargs] = YoutubeDownloadHandler().get_file_kwargs(YouTubeContextMetadata())
    legacy_format = "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480][ext=webm]+bestaudio[ext=webm]/best[height<=480][ext=mp4]"  # noqa: E501
    assert YoutubeDownloadHandler().get_cache_key(url, **kwargs) == generate_key(
        "DOWNLOADED", url, settings={"format": legacy_format}
    )


BBC_ARTICLE = "https://www.bbc.com/news/articles/cvp8d0nezkeko"
VIMEO_EMBED = {
    "_type": "url_transparent",
    "url": "https://vimeo.com/76979871",
    "ie_key": "Vimeo",
    "title": "t",
}
MP3_ONLY = {
    "id": "a1",
    "title": "audio",
    "formats": [
        {
            "url": "https://media.invalid/a.mp3",
            "ext": "mp3",
            "vcodec": "none",
            "acodec": "mp3",
        }
    ],
}
MP4_ONLY = [
    {
        "format_id": "18",
        "url": "https://media.invalid/v.mp4",
        "protocol": "https",
        "ext": "mp4",
        "height": 360,
        "vcodec": "avc1",
        "acodec": "mp4a",
    }
]
FLV_ONLY = [{**MP4_ONLY[0], "url": "https://media.invalid/v.flv", "ext": "flv"}]
VIDEO = {"id": "v1", "title": "video", "formats": MP4_ONLY}


def _video_info(url, subtitle_lang):
    return {
        **VIDEO,
        "webpage_url": url,
        "subtitles": {
            subtitle_lang: [{"url": "https://media.invalid/s.vtt", "ext": "vtt"}]
        },
    }


def _fake_yt_dlp_download(self, name, info, subtitle=False, test=False):
    with open(name, "wb") as fh:
        fh.write(b"WEBVTT\n" if subtitle else b"mp4 bytes")
    return True, True


@contextmanager
def fake_extractors(results):
    with ExitStack() as stack:
        for extractor, result in results.items():
            side_effect = (
                result
                if isinstance(result, Exception)
                else lambda u, r=result: copy.deepcopy(r)
            )
            stack.enter_context(
                patch.object(extractor, "_real_extract", side_effect=side_effect)
            )
        yield


@contextmanager
def html_page(url, render_page=None):
    with (
        patch.object(
            config.DOWNLOAD_SESSION,
            "head",
            side_effect=_fake_head({url: "text/html"}),
        ) as head,
        patch(
            "ricecooker.utils.pipeline.transfer.render_page",
            side_effect=render_page or AssertionError("rendered the page"),
        ),
    ):
        yield head


@pytest.fixture
def renders_page():
    def render(url, context=None):
        with html_page(url, fake_render_page()) as head:
            result = DownloadStageHandler().execute(
                url, context=context, skip_cache=True
            )
        assert result[0].filename.endswith(".zip")
        assert head.call_count == 1

    return render


BBCIE = yt_dlp.extractor.bbc.BBCIE
VimeoIE = yt_dlp.extractor.vimeo.VimeoIE


@pytest.mark.parametrize(
    "url,results",
    [
        (
            BBC_ARTICLE,
            {BBCIE: yt_dlp.utils.ExtractorError("Unable to extract playlist data")},
        ),
        (BBC_ARTICLE, {BBCIE: TypeError("bug")}),
        (BBC_ARTICLE, {BBCIE: {"_type": "playlist", "entries": []}}),
        (
            BBC_ARTICLE,
            {BBCIE: {"_type": "playlist", "entries": [{"url": "https://a.b/1"}]}},
        ),
        (
            BBC_ARTICLE,
            {
                BBCIE: VIMEO_EMBED,
                VimeoIE: yt_dlp.utils.ExtractorError("Unable to extract video data"),
            },
        ),
        (
            "https://www.mixcloud.com/dholbach/cryptocurrency-a-conversation/",
            {yt_dlp.extractor.mixcloud.MixcloudIE: MP3_ONLY},
        ),
        (
            "https://blazo.bandcamp.com/track/jazz-rock-mix",
            {yt_dlp.extractor.bandcamp.BandcampIE: MP3_ONLY},
        ),
        (
            "https://podcasts.apple.com/us/podcast/ferreck-dawn/id1625658232?i=1000665010654",
            {yt_dlp.extractor.applepodcasts.ApplePodcastsIE: MP3_ONLY},
        ),
        (
            "https://audioboom.com/posts/7398103-asim-chaudhry",
            {
                yt_dlp.extractor.audioboom.AudioBoomIE: {
                    "id": "7398103",
                    "url": "https://audioboom.com/posts/7398103.mp3",
                }
            },
        ),
        (
            "https://www.spreaker.com/episode/12534508",
            {
                yt_dlp.extractor.spreaker.SpreakerIE: {
                    "id": "12534508",
                    "url": "https://api.spreaker.com/download/episode/12534508/x.mp3",
                    "ext": "mp3",
                }
            },
        ),
        (BBC_ARTICLE, {BBCIE: {**VIDEO, "is_live": True}}),
        (BBC_ARTICLE, {BBCIE: {**VIDEO, "live_status": "is_live"}}),
        (
            "https://www.ted.com/talks/some_talk?ref=youtube.com",
            {
                yt_dlp.extractor.ted.TedTalkIE: yt_dlp.utils.ExtractorError(
                    "Unable to extract talk"
                )
            },
        ),
    ],
    ids=[
        "extraction_error",
        "extractor_bug",
        "empty_playlist",
        "playlist",
        "embed_error",
        "mixcloud_audio",
        "bandcamp_audio",
        "apple_podcasts_audio",
        "audioboom_audio_no_codecs",
        "spreaker_audio_no_codecs",
        "live_stream",
        "live_status_only",
        "youtube_in_query",
    ],
)
def test_download_stage_renders_page_when_yt_dlp_finds_no_video(
    url, results, renders_page, capfd
):
    with fake_extractors(results):
        renders_page(url)
    assert "ERROR:" not in capfd.readouterr().err


def test_download_stage_renders_page_with_several_videos(renders_page):
    videos = [
        {"videoData": {"pid": "p0lead00", "vpid": "p0lead01", "isLead": True}},
        {"videoData": {"pid": "p0secn00", "vpid": "p0secn01"}},
    ]
    payload = {"body": {"content": {"article": {"body": json.dumps(videos)}}}}
    page = f"<script>Morph.setPayload('/data/x', {json.dumps(payload)});</script>"

    def urlopen(self, req):
        return yt_dlp.networking.Response(
            io.BytesIO(page.encode()), req.url, {"Content-Type": "text/html"}, 200
        )

    with (
        patch.object(yt_dlp.YoutubeDL, "urlopen", urlopen),
        patch.object(
            yt_dlp.extractor.bbc.BBCCoUkIE,
            "_download_media_selector",
            side_effect=lambda pid: (copy.deepcopy(MP4_ONLY), {}),
        ),
        patch.object(yt_dlp.YoutubeDL, "dl", _fake_yt_dlp_download),
    ):
        renders_page("https://www.bbc.co.uk/news/uk-12345678")


@pytest.mark.parametrize("default_ext", ["zip", "pdf", "png", "mp3"])
def test_download_stage_renders_video_page_for_non_video_default_ext(
    default_ext, renders_page
):
    with (
        fake_extractors({BBCIE: VIDEO}),
        patch.object(yt_dlp.YoutubeDL, "dl", _fake_yt_dlp_download),
    ):
        renders_page(BBC_ARTICLE, context={"default_ext": default_ext})


def test_download_stage_downloads_subtitle_endpoint_serving_html():
    url = "https://amara.org/api/videos/abc/languages/en/subtitles/?format=vtt"
    with (
        fake_extractors({yt_dlp.extractor.amara.AmaraIE: VIDEO}),
        patch.object(yt_dlp.YoutubeDL, "dl", _fake_yt_dlp_download),
        fake_download_session({url: b"WEBVTT\n"}),
        html_page(url),
    ):
        result = DownloadStageHandler().execute(
            url, context={"ext": "vtt", "render_html": False}, skip_cache=True
        )
    assert result[0].filename.endswith(".vtt")


def test_download_stage_renders_page_after_caching_its_video():
    with (
        fake_extractors({BBCIE: VIDEO}),
        patch.object(yt_dlp.YoutubeDL, "dl", _fake_yt_dlp_download),
        html_page(BBC_ARTICLE, fake_render_page()),
    ):
        video_file = DownloadStageHandler().execute(BBC_ARTICLE, skip_cache=True)
        page = DownloadStageHandler().execute(
            BBC_ARTICLE, context={"default_ext": "zip"}
        )
    assert video_file[0].filename.endswith(".mp4")
    assert page[0].filename.endswith(".zip")


def _forbidden_download(self, name, info, subtitle=False, test=False):
    raise yt_dlp.utils.DownloadError("HTTP Error 403: Forbidden")


@pytest.mark.parametrize("embedded", [False, True], ids=["video", "embedded_video"])
@pytest.mark.parametrize(
    "formats,dl,error",
    [
        (FLV_ONLY, _fake_yt_dlp_download, "Requested format is not available"),
        (MP4_ONLY, _forbidden_download, "HTTP Error 403: Forbidden"),
    ],
    ids=["format_error", "download_error"],
)
def test_download_stage_fails_page_whose_video_does_not_download(
    embedded, formats, dl, error
):
    video = {**VIDEO, "formats": formats}
    results = {BBCIE: VIMEO_EMBED, VimeoIE: video} if embedded else {BBCIE: video}
    with (
        fake_extractors(results),
        patch.object(yt_dlp.YoutubeDL, "dl", dl),
        html_page(BBC_ARTICLE),
        pytest.raises(ExpectedFileException, match=error),
    ):
        DownloadStageHandler().execute(BBC_ARTICLE, skip_cache=True)


def test_download_stage_downloads_watch_url_video_not_its_playlist():
    url = "https://www.youtube.com/watch?v=aaaaaaaaaaa&list=PL472BC6F4F2C3ABEF"
    resolved = []
    with (
        patch.object(
            yt_dlp.YoutubeDL, "urlopen", side_effect=ConnectionError("offline")
        ),
        patch.object(
            yt_dlp.extractor.youtube.YoutubeIE,
            "_real_extract",
            side_effect=lambda u: resolved.append(u) or copy.deepcopy(VIDEO),
        ),
        patch.object(yt_dlp.YoutubeDL, "dl", _fake_yt_dlp_download),
    ):
        result = DownloadStageHandler().execute(url, skip_cache=True)
    assert result[0].filename.endswith(".mp4")
    assert resolved == ["https://www.youtube.com/watch?v=aaaaaaaaaaa"]


def test_download_stage_fails_video_url_without_formats():
    url = "https://vimeo.com/76979899"
    with (
        fake_extractors({VimeoIE: {**VIDEO, "formats": []}}),
        html_page(url),
        pytest.raises(ExpectedFileException, match="No video formats found"),
    ):
        DownloadStageHandler().execute(
            url, context={"default_ext": "mp4"}, skip_cache=True
        )


@pytest.mark.parametrize(
    "live",
    [{"is_live": True}, {"live_status": "is_live"}],
    ids=["is_live", "live_status"],
)
def test_download_stage_fails_live_video(live):
    url = "https://vimeo.com/76979883"
    with (
        fake_extractors({VimeoIE: {**VIDEO, **live}}),
        patch.object(yt_dlp.YoutubeDL, "dl", side_effect=AssertionError("recorded")),
        html_page(url),
        pytest.raises(InvalidFileException, match="live stream"),
    ):
        DownloadStageHandler().execute(
            url, context={"default_ext": "mp4"}, skip_cache=True
        )


def test_yt_dlp_should_handle_does_not_retain_data_uris():
    handler = YoutubeDownloadHandler()
    tracemalloc.start()
    try:
        before = tracemalloc.get_traced_memory()[0]
        for i in range(5):
            data_uri = (
                "data:image/png;base64," + base64.b64encode(bytes([i]) * 2**20).decode()
            )
            assert not handler.should_handle(data_uri)
            del data_uri
        # Python <= 3.13 caches urlsplit results.
        urllib.parse.clear_cache()
        retained = tracemalloc.get_traced_memory()[0] - before
    finally:
        tracemalloc.stop()
    assert retained < 2**20


def test_download_stage_downloads_video_file_without_yt_dlp():
    url = "https://www.dropbox.com/s/abc123/lesson.mp4?dl=1"
    with (
        patch.object(
            yt_dlp.YoutubeDL,
            "urlopen",
            side_effect=AssertionError("yt-dlp fetched the file"),
        ),
        fake_download_session({url: b"mp4 bytes"}),
    ):
        result = DownloadStageHandler().execute(
            url, context={"default_ext": "mp4"}, skip_cache=True
        )
    assert result[0].filename.endswith(".mp4")


@pytest.fixture
def fake_video_site():
    def download(url, extractor, subtitle_lang="en"):
        with (
            fake_extractors({extractor: _video_info(url, subtitle_lang)}),
            patch.object(yt_dlp.YoutubeDL, "dl", _fake_yt_dlp_download),
            html_page(url, fake_render_page()),
        ):
            return DownloadStageHandler().execute(
                url, context={"subtitle_languages": ["en"]}, skip_cache=True
            )

    return download


@pytest.mark.parametrize(
    "url,extractor",
    [
        (
            "https://www.youtube.com/watch?v=abcdefghijk",
            yt_dlp.extractor.youtube.YoutubeIE,
        ),
        ("https://vimeo.com/76979881", VimeoIE),
    ],
)
def test_download_stage_downloads_video_and_subtitles(fake_video_site, url, extractor):
    result = fake_video_site(url, extractor)
    assert [os.path.splitext(f.filename)[1] for f in result] == [".mp4", ".vtt"]


def test_download_stage_fails_video_missing_subtitle_language(fake_video_site):
    with pytest.raises(ExpectedFileException, match="Failed to download"):
        fake_video_site(
            "https://vimeo.com/76979882",
            VimeoIE,
            subtitle_lang="fr",
        )


def test_disk_transfer_file_protocol():
    file_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "..", "testcontent", "samples", "thumbnail.png"
        )
    )

    # Convert to proper file:// URL format based on platform
    if platform == "win32":
        # Windows needs file:/// followed by the path (e.g., file:///C:/path/to/file)
        file_path_with_protocol = "file:///" + file_path.replace("\\", "/")
    else:
        # Unix-like systems should use file:// followed by the path (e.g., file:///path/to/file)
        file_path_with_protocol = "file://" + file_path

    handler = DiskResourceHandler()
    assert handler.should_handle(file_path_with_protocol), (
        f"Handler should handle {file_path_with_protocol}"
    )

    file_metadata = handler.execute(file_path_with_protocol)
    assert file_metadata is not None, "File metadata should not be None"
    assert file_metadata[0].filename.endswith("png"), (
        "File extension should be preserved"
    )


def test_disk_transfer_rejects_extensionless_path(tmp_path):
    source = tmp_path / "diagram"
    source.write_bytes(b"data")
    with pytest.raises(InvalidFileException, match="No extension"):
        DiskResourceHandler().execute(str(source), skip_cache=True)


def test_disk_transfer_recopies_edited_file(tmp_path):
    source = tmp_path / "notes.txt"
    handler = DownloadStageHandler()

    source.write_text("first draft")
    handler.execute(str(source))
    source.write_text("second draft")
    result = handler.execute(str(source))[0]

    with open(result.path) as fh:
        assert fh.read() == "second draft"


def test_disk_transfer_reuses_unchanged_file(tmp_path):
    source = tmp_path / "notes.txt"
    source.write_text("first draft")
    handler = DiskResourceHandler()

    first = handler.execute(str(source))[0]
    # Backdate the stored copy so a re-copy would show up as a new mtime
    os.utime(first.path, (0, 0))
    second = handler.execute(str(source))[0]

    assert second.path == first.path
    assert os.path.getmtime(second.path) == 0


def test_disk_transfer_declared_ext_is_fallback_for_unknown_ext(tmp_path):
    source = tmp_path / "subs.txt"
    source.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n")
    handler = DiskResourceHandler()

    handler.execute(str(source))
    result = handler.execute(str(source), context={"ext": "srt"})[0]

    assert result.filename.endswith(".srt")


def test_disk_transfer_known_ext_beats_declared_ext(tmp_path):
    source = tmp_path / "subs.vtt"
    source.write_text("WEBVTT\n\n00:01.000 --> 00:02.000\nHello\n")

    result = DiskResourceHandler().execute(str(source), context={"ext": "srt"})[0]

    assert result.filename.endswith(".vtt")


def test_disk_transfer_non_file_protocol():
    """Test that non-file protocols are left unchanged."""
    path = "http://example.com/path/to/file.jpg"
    handler = DiskResourceHandler()

    # The handler should not process non-file URLs
    normalized_path = handler._normalize_path(path)
    assert normalized_path == path, "Non-file URL should be left unchanged"

    # The handler should not handle non-file URLs
    with patch(
        "os.path.exists", return_value=False
    ):  # Ensure it doesn't try to check a web URL
        assert not handler.should_handle(path), "Handler should not handle HTTP URLs"


class DummyPassthroughHandler(FileHandler):
    """A dummy handler that passes through the original path without transferring to storage.

    This simulates the bug where a download handler fails to actually download/transfer
    the file but returns the original URL as the path.
    """

    def should_handle(self, path: str) -> bool:
        return path.startswith("http://dummy-test-url.com")

    def handle_file(self, path, **kwargs):
        # Intentionally don't use write_file context manager
        # This simulates a handler that fails to transfer the file to storage
        return FileMetadata(original_filename="test.txt")


def test_download_stage_handler_catches_failed_transfer():
    """Test that DownloadStageHandler catches when files aren't transferred to storage.

    This is a regression test for the issue where download handlers would sometimes
    log "saved to [original URL]" instead of the actual storage path, indicating
    that the file wasn't actually transferred to storage.
    """
    # Create a DownloadStageHandler with our dummy passthrough handler
    download_handler = DownloadStageHandler(children=[DummyPassthroughHandler()])

    dummy_url = "http://dummy-test-url.com/test.txt"

    # The handler should raise an InvalidFileException when the file isn't transferred to storage
    with pytest.raises(InvalidFileException, match="failed to transfer to storage"):
        download_handler.execute(dummy_url)


def test_base64_should_handle():
    handler = Base64FileHandler()
    assert handler.should_handle("data:font/woff2;base64,AAAA") is True
    assert handler.should_handle("https://x/a.png") is False


@pytest.mark.parametrize(
    "data_uri,suffix",
    [
        ("data:font/woff2;base64,AAAA", ".woff2"),
        ("data:image/gif;base64,AAAA", ".gif"),
        # image/jpeg maps to .jpg, not .jpeg.
        ("data:image/jpeg;base64,AAAA", ".jpg"),
    ],
)
def test_base64_decodes_data_uri_extension(data_uri, suffix):
    result = Base64FileHandler().execute(data_uri)
    assert result[0].filename.endswith(suffix)


def test_base64_malformed_payload_raises_invalidfileexception():
    # The loose data-URI regex matches non-base64 payloads; decoding must
    # degrade to InvalidFileException (caught upstream), not a raw binascii.Error.
    handler = Base64FileHandler()
    with pytest.raises(InvalidFileException, match="Malformed base64"):
        handler.execute("data:image/png;base64,AAA")


def test_render_page_writes_index_and_passes_crawl_flags():
    import ricecooker.utils.singlefile as singlefile

    with tempfile.TemporaryDirectory() as tmpdir:
        recorded = {}

        def check_output(command, *args, **kwargs):
            recorded["command"] = command
            with open(os.path.join(tmpdir, "index.html"), "w") as f:
                f.write("<html><body>hi</body></html>")
            return b""

        with patch.object(
            singlefile.subprocess, "check_output", side_effect=check_output
        ):
            result = singlefile.render_page(
                "https://spa.example/",
                tmpdir,
                crawl_max_depth=2,
                crawl_inner_links_only=True,
            )
        assert result == os.path.join(tmpdir, "index.html")
        assert os.path.exists(result)
        command = recorded["command"]
        assert "--crawl-links=true" in command
        assert "--crawl-max-depth=2" in command
        assert "--crawl-inner-links-only=true" in command


def test_render_page_passes_auth_flags():
    import ricecooker.utils.singlefile as singlefile

    with tempfile.TemporaryDirectory() as tmpdir:
        recorded = {}

        def check_output(command, *args, **kwargs):
            recorded["command"] = command
            with open(os.path.join(tmpdir, "index.html"), "w") as f:
                f.write("<html><body>hi</body></html>")
            return b""

        with patch.object(
            singlefile.subprocess, "check_output", side_effect=check_output
        ):
            singlefile.render_page(
                "https://locked.example/",
                tmpdir,
                browser_cookies_file="/tmp/cookies.txt",
                http_headers={"Authorization": "Bearer tok"},
            )
        command = recorded["command"]
        assert "--browser-cookies-file=/tmp/cookies.txt" in command
        assert "--http-header=Authorization: Bearer tok" in command


def test_render_page_missing_binary_raises_singlefilerendererror():
    import ricecooker.utils.singlefile as singlefile

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(
            singlefile.subprocess, "check_output", side_effect=FileNotFoundError()
        ):
            with pytest.raises(singlefile.SingleFileRenderError, match="single-file"):
                singlefile.render_page("https://spa.example/", tmpdir)


class _FakeHeadResponse:
    def __init__(self, content_type):
        self.ok = True
        self.headers = {"content-type": content_type}


def _fake_head(content_types_by_url):
    """A DOWNLOAD_SESSION.head stand-in returning a canned content-type per URL."""

    def head(url, **kwargs):
        return _FakeHeadResponse(content_types_by_url.get(url, ""))

    return head


class _FakeGetResponse(_FakeHeadResponse):
    def __init__(self, content, content_type):
        super().__init__(content_type)
        self.content = content

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size=8192):
        yield self.content


@pytest.mark.parametrize(
    "url,content_type,content,default_ext,suffix",
    [
        (
            "https://site.example/thumb.php?id=1",
            "image/jpeg",
            b"\xff\xd8\xff\xe0jpeg",
            "png",
            ".jpg",
        ),
        (
            "https://fonts.googleapis.com/css?family=Roboto",
            "text/css; charset=utf-8",
            b"@font-face{}",
            None,
            ".css",
        ),
        (
            "https://site.example/file?id=2",
            "application/octet-stream",
            _PNG_1x1,
            None,
            ".png",
        ),
        (
            "https://site.example/pkg.h5p",
            "application/zip",
            b"PK\x03\x04",
            None,
            ".h5p",
        ),
        (
            "https://site.example/pkg?id=3",
            "application/zip",
            b"PK\x03\x04",
            "h5p",
            ".h5p",
        ),
        (
            "https://site.example/data.xml",
            "application/xml",
            b"<data/>",
            None,
            ".xml",
        ),
        (
            "https://cdn.example/script?v=1",
            "application/javascript",
            b"var x;",
            None,
            ".js",
        ),
        (
            "https://site.example/page.htm",
            "text/html; charset=utf-8",
            b"<html></html>",
            None,
            ".htm",
        ),
        (
            "https://site.example/video.m3u8",
            "application/vnd.apple.mpegurl",
            b"#EXTM3U",
            None,
            ".m3u8",
        ),
        (
            "https://site.example/app.ggb",
            "application/octet-stream",
            b"PK\x03\x04",
            None,
            ".ggb",
        ),
        (
            "https://site.example/app.sb3",
            "application/zip",
            b"PK\x03\x04",
            None,
            ".sb3",
        ),
        (
            "https://maps.googleapis.com/maps/api/js?key=K",
            "text/javascript",
            b"var x;",
            None,
            ".js",
        ),
        ("https://site.example/app.js", "application/json", b"var x;", None, ".js"),
        (
            "https://site.example/lib.min.js.map",
            "application/json",
            b"{}",
            None,
            ".map",
        ),
        (
            "https://site.example/data.csv",
            "application/vnd.ms-excel",
            b"a,b",
            None,
            ".csv",
        ),
        (
            "https://site.example/feed.xml",
            "application/rss+xml",
            b"<rss/>",
            None,
            ".xml",
        ),
        (
            "https://site.example/page.js",
            "text/html",
            b"<html></html>",
            None,
            ".html",
        ),
        (
            "https://s.example/icon.svg",
            "text/html",
            b"<svg xmlns='http://www.w3.org/2000/svg' width='1' height='1'/>",
            None,
            ".svg",
        ),
        (
            "https://s.example/download.php?id=1",
            "application/zip",
            b"PK\x03\x04",
            "zip",
            ".zip",
        ),
        (
            "https://s.example/getsub.php?id=5",
            "application/zip",
            b"PK\x03\x04",
            "vtt",
            ".php",
        ),
        ("https://s.example/stream.php?id=1", "audio/ogg", b"OggS", None, ".ogg"),
        ("https://s.example/feed.xml", "text/html", b"<data>1</data>", None, ".xml"),
        (
            "https://s.example/logo.svg",
            "text/html",
            b"<!-- Generator --><svg xmlns='http://www.w3.org/2000/svg'/>",
            None,
            ".svg",
        ),
        (
            "https://s.example/app2.js",
            "text/html",
            b"<!-- hide\nvar x;\n// -->",
            None,
            ".js",
        ),
        ("https://s.example/site.css", "text/html", b"<!-- body{} -->", None, ".css"),
        (
            "https://s.example/page2.js",
            "text/html",
            b"<?xml version='1.0'?>\n<!-- 404 -->\n<!DOCTYPE html><html/>",
            None,
            ".html",
        ),
    ],
    ids=[
        "unknown-name-ext",
        "no-name-ext",
        "sniffed",
        "known-name-ext",
        "declared-default",
        "xml-not-xsl",
        "js",
        "matching-name-ext-htm",
        "matching-name-ext-m3u8",
        "sniffed-zip-keeps-name-ext",
        "zip-type-keeps-name-ext",
        "text-javascript",
        "asset-ext-beats-json-type",
        "source-map",
        "csv-not-xls",
        "xml-not-rss",
        "page-at-asset-ext",
        "svg-served-as-html",
        "container-type-takes-default-ext",
        "container-type-ignores-non-archive-default-ext",
        "ogg-not-oga",
        "xml-served-as-html",
        "comment-first-svg-served-as-html",
        "comment-first-js-served-as-html",
        "comment-only-css-served-as-html",
        "xhtml-page-at-asset-ext",
    ],
)
def test_catchall_names_file_from_response(
    url, content_type, content, default_ext, suffix
):
    with patch.object(
        config.DOWNLOAD_SESSION,
        "get",
        return_value=_FakeGetResponse(content, content_type),
    ):
        result = CatchAllWebResourceDownloadHandler().execute(
            url, context={"default_ext": default_ext}, skip_cache=True
        )
    assert result[0].filename.endswith(suffix)


@pytest.mark.parametrize(
    "url,content_type,suffix",
    [
        ("https://s.example/subs.php?id=1", "text/vtt", ".vtt"),
        ("https://s.example/subs.php?id=2", "application/ttml+xml", ".ttml"),
        ("https://s.example/subs.php?id=3", "application/x-subrip", ".srt"),
        ("https://s.example/thumb.php?id=4", "image/webp", ".webp"),
        ("https://s.example/page.htm", "text/html", ".htm"),
    ],
)
def test_catchall_naming_ignores_host_mimetypes_db(
    monkeypatch, url, content_type, suffix
):
    empty_db = mimetypes.MimeTypes()
    empty_db.types_map = ({}, {})
    empty_db.types_map_inv = ({}, {})
    monkeypatch.setattr(mimetypes, "_db", empty_db)
    monkeypatch.setattr(mimetypes, "inited", True)
    with patch.object(
        config.DOWNLOAD_SESSION,
        "get",
        return_value=_FakeGetResponse(b"x", content_type),
    ):
        result = CatchAllWebResourceDownloadHandler().execute(url, skip_cache=True)
    assert result[0].filename.endswith(suffix)


@pytest.mark.parametrize(
    "url,cached,refetched",
    [
        ("https://site.example/stale-cache.php", "stale.php", True),
        ("https://site.example/kept-cache.png", "kept.png", False),
    ],
    ids=["renamed-ext-refetched", "kept-ext-reused"],
)
def test_catchall_download_cached_by_earlier_release(url, cached, refetched):
    with open(config.get_storage_path(cached), "wb") as fh:
        fh.write(_PNG_1x1)
    set_cache_data(f"DOWNLOAD:{url}", {"filename": cached})
    with patch.object(
        config.DOWNLOAD_SESSION,
        "get",
        return_value=_FakeGetResponse(_PNG_1x1, "image/png"),
    ) as get:
        handler = CatchAllWebResourceDownloadHandler()
        handler.parent = DownloadStageHandler()
        result = handler.execute(url, context={})
    assert get.called == refetched
    assert (result[0].filename == cached) != refetched


def test_catchall_node_file_and_archive_ref_share_one_download():
    url = "https://site.example/shared-logo.png"
    with patch.object(
        config.DOWNLOAD_SESSION,
        "get",
        return_value=_FakeGetResponse(_PNG_1x1, "image/png"),
    ) as get:
        handler = CatchAllWebResourceDownloadHandler()
        handler.parent = DownloadStageHandler()
        handler.execute(url, context={})
        handler.execute(url, context={"asset_ref": True})
    assert get.call_count == 1


def test_catchall_rejects_undeterminable_type():
    with patch.object(
        config.DOWNLOAD_SESSION,
        "get",
        return_value=_FakeGetResponse(b"hello", "text/plain"),
    ):
        with pytest.raises(
            InvalidFileException, match="Could not determine the file type"
        ):
            CatchAllWebResourceDownloadHandler().execute(
                "https://site.example/blob?id=4", context={}, skip_cache=True
            )


def test_singlefile_render_handler_should_handle_detects_html():
    # No marker: the handler claims a URL only when a HEAD says it serves HTML,
    # so it can sit before the catch-all and render only HTML pages.
    handler = SingleFileRenderHandler()
    content_types = {
        "https://spa.example/": "text/html; charset=utf-8",
        "https://spa.example/report.pdf": "application/pdf",
    }
    with patch.object(
        config.DOWNLOAD_SESSION, "head", side_effect=_fake_head(content_types)
    ):
        assert handler.should_handle("https://spa.example/") is True
        # A non-HTML resource falls through to the catch-all download handler.
        assert handler.should_handle("https://spa.example/report.pdf") is False
    # Non-http(s) URIs never trigger a HEAD request.
    assert handler.should_handle("ftp://x/") is False
    assert handler.should_handle("data:image/png;base64,AA") is False


def test_singlefile_render_handler_head_is_cached():
    # should_handle is called repeatedly (composite probe + dispatch); the HEAD
    # request must fire at most once per URL.
    handler = SingleFileRenderHandler()
    head = MagicMock(return_value=_FakeHeadResponse("text/html"))
    with patch.object(config.DOWNLOAD_SESSION, "head", head):
        assert handler.should_handle("https://spa.example/") is True
        assert handler.should_handle("https://spa.example/") is True
    assert head.call_count == 1


def test_singlefile_render_handler_produces_zip():
    handler = SingleFileRenderHandler()
    with patch(
        "ricecooker.utils.pipeline.transfer.render_page",
        side_effect=fake_render_page(),
    ):
        result = handler.execute("https://spa.example/")
    assert result[0].filename.endswith(".zip")
    with zipfile.ZipFile(result[0].path) as zf:
        index = zf.read("index.html").decode()
    # The raw render (pre-CONVERT) still has the inlined data: URI.
    assert "data:image/png" in index


def test_singlefile_render_handler_neutralizes_external_navigation():
    # An offline archive must not phone home: external <a>/<iframe> are made inert
    # before the archive is sealed. Relative in-archive refs are preserved.
    body = (
        '<a href="https://external.example/page">out</a>'
        '<a href="page2.html">sibling</a>'
        '<iframe src="https://cross.example/frame"></iframe>'
    )

    def render_page(url, output_dir, **kwargs):
        with open(os.path.join(output_dir, "index.html"), "w") as fh:
            fh.write("<html><body>{}</body></html>".format(body))
        return os.path.join(output_dir, "index.html")

    with patch(
        "ricecooker.utils.pipeline.transfer.render_page", side_effect=render_page
    ):
        # Distinct URL so this render is not served from another test's cache.
        result = SingleFileRenderHandler().execute("https://nav.example/")
    with zipfile.ZipFile(result[0].path) as zf:
        index = zf.read("index.html").decode()
    assert "https://external.example/page" not in index
    assert "https://cross.example/frame" not in index
    assert 'href="#"' in index
    assert 'src="about:blank"' in index
    # The captured sibling page is still linked.
    assert 'href="page2.html"' in index


def test_singlefile_render_handler_forwards_crawl_context():
    # Crawl depth/scope reach the handler only through CONTEXT_CLASS; without it
    # every field silently defaults and the depth/scope config AC is a no-op.
    # fake_render_page asserts the kwargs render_page actually received.
    handler = SingleFileRenderHandler()
    with patch(
        "ricecooker.utils.pipeline.transfer.render_page",
        side_effect=fake_render_page(crawl_max_depth=3, crawl_inner_links_only=False),
    ):
        result = handler.execute(
            "https://spa.example/",
            context={"crawl_max_depth": 3, "crawl_inner_links_only": False},
        )
    assert result[0].filename.endswith(".zip")


def test_singlefile_render_handler_forwards_auth_context():
    # Login-wall auth reaches the render the same way crawl options do: through
    # CONTEXT_CLASS. fake_render_page asserts render_page got the auth kwargs.
    handler = SingleFileRenderHandler()
    with patch(
        "ricecooker.utils.pipeline.transfer.render_page",
        side_effect=fake_render_page(
            browser_cookies_file="/tmp/cookies.txt",
            http_headers={"Authorization": "Bearer tok"},
        ),
    ):
        result = handler.execute(
            "https://locked.example/",
            context={
                "browser_cookies_file": "/tmp/cookies.txt",
                "http_headers": {"Authorization": "Bearer tok"},
            },
        )
    assert result[0].filename.endswith(".zip")


def test_singlefile_render_end_to_end_explosion():
    # The render handler is a default DOWNLOAD child, so the stock pipeline
    # renders HTML-page URLs and explodes their inlined data: assets.
    pipeline = FilePipeline()
    with (
        patch(
            "ricecooker.utils.pipeline.transfer.render_page",
            side_effect=fake_render_page(),
        ),
        patch.object(
            config.DOWNLOAD_SESSION,
            "head",
            side_effect=_fake_head({"https://spa.example/": "text/html"}),
        ),
    ):
        result = pipeline.execute("https://spa.example/")

    # The rendered page has no scripts, so the HTML5 handler promotes it to a KPUB.
    assert result[0].preset == format_presets.KPUB_ZIP
    with zipfile.ZipFile(result[0].path) as zf:
        names = zf.namelist()
        index = zf.read("index.html").decode()
    # The inlined asset is exploded into a real file and the ref rewritten.
    assert "data:image/png" not in index
    pngs = [n for n in names if n.endswith(".png")]
    assert len(pngs) == 1
    assert 'src="{}"'.format(pngs[0]) in index


@pytest.mark.parametrize(
    "url",
    [
        "https://en.wikipedia.org/wiki/Node.js",
        "https://commons.wikimedia.org/wiki/File:Example.svg",
        "https://github.com/nodejs/node/blob/main/package.json",
    ],
)
def test_page_at_asset_extension_url_renders(url):
    with (
        patch(
            "ricecooker.utils.pipeline.transfer.render_page",
            side_effect=fake_render_page(),
        ),
        patch.object(
            config.DOWNLOAD_SESSION, "head", side_effect=_fake_head({url: "text/html"})
        ),
    ):
        result = FilePipeline().execute(url)
    assert result[0].preset == format_presets.KPUB_ZIP


def test_default_pipeline_renders_html_and_downloads_other_sources():
    # The render handler ships in the default DOWNLOAD children and auto-detects
    # HTML pages via HEAD — no marker, no custom pipeline construction.
    pipeline = FilePipeline()
    content_types = {
        "https://spa.example/": "text/html",
        "https://example.com/x.pdf": "application/pdf",
    }
    with patch.object(
        config.DOWNLOAD_SESSION, "head", side_effect=_fake_head(content_types)
    ):
        # An HTML page is claimed by the render handler.
        assert pipeline.should_handle("https://spa.example/") is True
        # A non-HTML resource still routes to a default download handler.
        assert pipeline.should_handle("https://example.com/x.pdf") is True


@pytest.mark.parametrize(
    "url",
    ["https://nohead405.example/report.pdf", "https://nohead501.example/report.pdf"],
)
@my_vcr.use_cassette
def test_rejected_head_downloads_via_get(url):
    result = DownloadStageHandler().execute(url, skip_cache=True)
    assert result[0].filename.endswith(".pdf")
    with open(result[0].path, "rb") as fh:
        assert fh.read() == b"%PDF-1.4\n"


def test_http_error_fails_download():
    with my_vcr.use_cassette("test_http_error_fails_download") as cassette:
        with pytest.raises(ExpectedFileException, match="404"):
            DownloadStageHandler().execute(
                "https://gone.example/missing.pdf", skip_cache=True
            )
    assert cassette.play_count == 2


def _fresh_download_session(monkeypatch):
    session = requests.Session()
    session.trust_env = False
    monkeypatch.setattr(config, "DOWNLOAD_SESSION", session)
    config.set_download_attempts(1)


def test_failed_get_probe_is_not_retried_again(monkeypatch):
    _fresh_download_session(monkeypatch)
    with my_vcr.use_cassette("test_failed_get_probe_is_not_retried_again") as cassette:
        with pytest.raises(ExpectedFileException, match="503"):
            DownloadStageHandler().execute("https://down.example/page", skip_cache=True)
    assert cassette.play_count == 3


def _fake_http(monkeypatch, respond):
    _fresh_download_session(monkeypatch)
    methods = []

    def make_request(pool, conn, method, url, headers=None, **kwargs):
        methods.append(method)
        return respond(pool, method, url, headers or {})

    monkeypatch.setattr(
        urllib3.connectionpool.HTTPConnectionPool, "_make_request", make_request
    )
    return methods


def _response(status, content_type="", body=b"", **headers):
    return urllib3.HTTPResponse(
        body=io.BytesIO(body),
        status=status,
        headers={"Content-Type": content_type, **headers},
        preload_content=False,
    )


def test_raising_get_probe_is_not_retried_again(monkeypatch):
    def respond(pool, method, url, headers):
        if method == "HEAD":
            return _response(405)
        raise urllib3.exceptions.ReadTimeoutError(pool, url, "read timed out")

    methods = _fake_http(monkeypatch, respond)
    with pytest.raises(ExpectedFileException, match="timed out"):
        DownloadStageHandler().execute("https://slow.example/page", skip_cache=True)
    assert methods == ["HEAD", "GET", "GET"]


@pytest.mark.parametrize(
    "url", ["https://site.example/lesson", "https://site.example/lesson.html"]
)
def test_raising_head_html_page_is_rendered(monkeypatch, url):
    def respond(pool, method, url, headers):
        if method == "HEAD":
            raise urllib3.exceptions.ReadTimeoutError(pool, url, "read timed out")
        return _response(200, "text/html", b"<html></html>")

    methods = _fake_http(monkeypatch, respond)
    with patch(
        "ricecooker.utils.pipeline.transfer.render_page",
        side_effect=fake_render_page(),
    ):
        result = DownloadStageHandler().execute(url, skip_cache=True)
    assert result[0].filename.endswith(".zip")
    assert methods == ["HEAD", "GET"]


def test_probe_omits_context_http_headers(monkeypatch):
    sent = []

    def respond(pool, method, url, headers):
        sent.append((pool.host, dict(headers)))
        if pool.host == "locked.example":
            return _response(302, Location="https://s3.example/doc.pdf?sig=1")
        return _response(200, "application/pdf", b"%PDF-1.4\n")

    _fake_http(monkeypatch, respond)
    DownloadStageHandler().execute(
        "https://locked.example/doc.pdf",
        context={"http_headers": {"X-Api-Key": "k"}},
        skip_cache=True,
    )
    assert {host for host, _ in sent} == {"locked.example", "s3.example"}
    assert not [headers for _, headers in sent if "X-Api-Key" in headers]


def test_failed_download_is_retried_after_recovery(monkeypatch):
    _fresh_download_session(monkeypatch)
    url = "https://recovering.example/report.pdf"
    stage = DownloadStageHandler()
    with my_vcr.use_cassette(
        "test_failed_download_is_retried_after_recovery"
    ) as cassette:
        assert stage.should_handle(url) is True
        with pytest.raises(ExpectedFileException, match="503"):
            stage.execute(url, skip_cache=True)
        result = stage.execute(url, skip_cache=True)
    with open(result[0].path, "rb") as fh:
        assert fh.read() == b"%PDF-1.4\n"
    assert cassette.play_count == 5


def test_cached_render_survives_failing_source(monkeypatch):
    _fresh_download_session(monkeypatch)
    url = "https://site.example/lesson"
    with my_vcr.use_cassette("test_cached_render_survives_failing_source") as cassette:
        with patch(
            "ricecooker.utils.pipeline.transfer.render_page",
            side_effect=fake_render_page(),
        ):
            first = DownloadStageHandler().execute(url, skip_cache=True)
        second = DownloadStageHandler().execute(url)
        with pytest.raises(ExpectedFileException, match="503"):
            DownloadStageHandler().execute(url, skip_cache=True)
    assert second[0].path == first[0].path
    assert cassette.play_count == 4


@pytest.mark.parametrize(
    "url", ["https://nohead.example/page", "https://busy.example/page"]
)
@my_vcr.use_cassette
def test_rejected_head_html_page_is_rendered(url):
    with patch(
        "ricecooker.utils.pipeline.transfer.render_page",
        side_effect=fake_render_page(),
    ):
        result = DownloadStageHandler().execute(url, skip_cache=True)
    assert result[0].filename.endswith(".zip")


def test_failed_probe_serves_cached_download(monkeypatch):
    _fresh_download_session(monkeypatch)
    url = "https://flaky.example/cached-report.pdf"
    with my_vcr.use_cassette("test_failed_probe_serves_cached_download") as cassette:
        first = DownloadStageHandler().execute(url, skip_cache=True)
        second = DownloadStageHandler().execute(url)
        with pytest.raises(ExpectedFileException, match="503"):
            DownloadStageHandler().execute(url, skip_cache=True)
    assert second[0].path == first[0].path
    assert cassette.play_count == 8


def test_cached_download_of_html_page_is_rendered(monkeypatch):
    methods = _fake_http(
        monkeypatch,
        lambda pool, method, url, headers: _response(
            200, "text/html", b"<html></html>"
        ),
    )
    url = "https://v080.example/lesson.html"
    DownloadStageHandler(children=[CatchAllWebResourceDownloadHandler()]).execute(url)
    with patch(
        "ricecooker.utils.pipeline.transfer.render_page",
        side_effect=fake_render_page(),
    ):
        result = DownloadStageHandler().execute(url)
    assert result[0].filename.endswith(".zip")
    assert methods == ["GET", "HEAD"]


def _failing_source(status):
    def respond(pool, method, url, headers):
        if status is None:
            raise urllib3.exceptions.NewConnectionError(pool, "connection refused")
        return _response(status, "text/html")

    return respond


def _render_disk_pipeline():
    return FilePipeline(
        children=[
            DownloadStageHandler(
                children=[SingleFileRenderHandler(), DiskResourceHandler()]
            )
        ]
    )


@pytest.mark.parametrize("status", [None, 404])
def test_failed_probe_without_catch_all_invalidates_node(monkeypatch, status):
    _fake_http(monkeypatch, _failing_source(status))
    node = ContentNode(
        source_id="lesson",
        title="Lesson",
        license=get_license(licenses.CC_BY, copyright_holder="Holder"),
        uri="https://down.example/lesson",
        pipeline=_render_disk_pipeline(),
    )
    with pytest.raises(InvalidNodeException, match="cannot handle uri"):
        node.validate()


@pytest.mark.parametrize("status", [None, 404, 503])
def test_failed_probe_without_catch_all_serves_cached_render(monkeypatch, status):
    url = "https://site.example/lesson"
    _fake_http(monkeypatch, lambda *args: _response(200, "text/html"))
    with patch(
        "ricecooker.utils.pipeline.transfer.render_page",
        side_effect=fake_render_page(),
    ):
        first = _render_disk_pipeline().execute(url, skip_cache=True)
    methods = _fake_http(monkeypatch, _failing_source(status))
    pipeline = _render_disk_pipeline()
    assert pipeline.should_handle(url)
    second = pipeline.execute(url)
    assert second[0].path == first[0].path
    assert methods == []


@my_vcr.use_cassette
def test_read_refetches_under_update():
    url = "https://changing.example/data.txt"
    with patch.object(config, "UPDATE", True):
        assert read(url) == b"first"
        assert read(url) == b"second"
