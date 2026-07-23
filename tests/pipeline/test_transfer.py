import base64
import json
import os
import tempfile
import zipfile
from sys import platform
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from le_utils.constants import format_presets
from vcr_config import my_vcr

from ricecooker import config
from ricecooker.utils.pipeline import FilePipeline
from ricecooker.utils.pipeline.context import FileMetadata
from ricecooker.utils.pipeline.exceptions import InvalidFileException
from ricecooker.utils.pipeline.file_handler import FileHandler
from ricecooker.utils.pipeline.transfer import Base64FileHandler
from ricecooker.utils.pipeline.transfer import DiskResourceHandler
from ricecooker.utils.pipeline.transfer import DownloadStageHandler
from ricecooker.utils.pipeline.transfer import (
    get_filename_from_content_disposition_header,
)
from ricecooker.utils.pipeline.transfer import GoogleDriveHandler
from ricecooker.utils.pipeline.transfer import SingleFileRenderHandler

# A valid 1x1 PNG — single-file inlines binary assets as base64 ``data:`` URIs,
# and the CONVERT stage needs a decodable image to explode.
_PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

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


def _fake_render_page(**expected_kwargs):
    """Return a render_page stand-in that emits an index.html with a data: img.

    The emitted body has real content (the <img>), which the CONVERT stage's
    index.html body validation requires.
    """
    data_uri = "data:image/png;base64," + base64.b64encode(_PNG_1x1).decode()

    def render_page(url, output_dir, **kwargs):
        for key, value in expected_kwargs.items():
            assert kwargs.get(key) == value
        index_path = os.path.join(output_dir, "index.html")
        with open(index_path, "w") as fh:
            fh.write('<html><body><img src="{}"></body></html>'.format(data_uri))
        return index_path

    return render_page


class _FakeHeadResponse:
    def __init__(self, content_type):
        self.headers = {"content-type": content_type}


def _fake_head(content_types_by_url):
    """A DOWNLOAD_SESSION.head stand-in returning a canned content-type per URL."""

    def head(url, **kwargs):
        return _FakeHeadResponse(content_types_by_url.get(url, ""))

    return head


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
        side_effect=_fake_render_page(),
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
    # _fake_render_page asserts the kwargs render_page actually received.
    handler = SingleFileRenderHandler()
    with patch(
        "ricecooker.utils.pipeline.transfer.render_page",
        side_effect=_fake_render_page(crawl_max_depth=3, crawl_inner_links_only=False),
    ):
        result = handler.execute(
            "https://spa.example/",
            context={"crawl_max_depth": 3, "crawl_inner_links_only": False},
        )
    assert result[0].filename.endswith(".zip")


def test_singlefile_render_handler_forwards_auth_context():
    # Login-wall auth reaches the render the same way crawl options do: through
    # CONTEXT_CLASS. _fake_render_page asserts render_page got the auth kwargs.
    handler = SingleFileRenderHandler()
    with patch(
        "ricecooker.utils.pipeline.transfer.render_page",
        side_effect=_fake_render_page(
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
            side_effect=_fake_render_page(),
        ),
        patch.object(
            config.DOWNLOAD_SESSION,
            "head",
            side_effect=_fake_head({"https://spa.example/": "text/html"}),
        ),
    ):
        result = pipeline.execute("https://spa.example/")

    assert result[0].preset == format_presets.HTML5_ZIP
    with zipfile.ZipFile(result[0].path) as zf:
        names = zf.namelist()
        index = zf.read("index.html").decode()
    # The inlined asset is exploded into a real file and the ref rewritten.
    assert "data:image/png" not in index
    pngs = [n for n in names if n.endswith(".png")]
    assert len(pngs) == 1
    assert 'src="{}"'.format(pngs[0]) in index


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
