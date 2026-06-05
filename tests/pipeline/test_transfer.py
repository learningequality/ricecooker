import json
import os
import tempfile
from sys import platform
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
import requests_cache
from vcr_config import box_vcr
from vcr_config import my_vcr

from ricecooker.utils.pipeline.context import FileMetadata
from ricecooker.utils.pipeline.exceptions import InvalidFileException
from ricecooker.utils.pipeline.file_handler import FileHandler
from ricecooker.utils.pipeline.transfer import BoxHandler
from ricecooker.utils.pipeline.transfer import DiskResourceHandler
from ricecooker.utils.pipeline.transfer import DownloadStageHandler
from ricecooker.utils.pipeline.transfer import (
    get_filename_from_content_disposition_header,
)
from ricecooker.utils.pipeline.transfer import GoogleDriveHandler

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
    At the moment we are exporting Google Docs as PDFs
    If we ever decide to update this, this test will need to be updated.
    """
    handler = GoogleDriveHandler()
    assert handler.should_handle(doc_link)
    file_metadata = handler.execute(doc_link)
    assert file_metadata is not None
    assert file_metadata[0].filename.endswith("pdf")
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


# All these files are in this Box folder on the Learning Equality Box account:
# https://app.box.com/s/d7wax7wg6bborzk8l0cjz9anws1ghsf6
# in case they ever need to be updated or changed.
# If they are updated, the relevant cassettes for these tests should be deleted
# and recreated by running the test suite with real Box client credentials
# grant values in the BOX_CLIENT_ID, BOX_CLIENT_SECRET, and BOX_ENTERPRISE_ID
# environment variables.
box_pdf_link = "https://app.box.com/s/g8ibjz3jd1m5xu943i5al0bh8k99rqtu"
box_video_link = "https://app.box.com/s/5iunzudtzdrgkag35m7xptc52nbv033i"
box_vtt_link = "https://app.box.com/s/2z5rwa70suvtmocwdmv0pedaax539poa"
box_audio_link = "https://app.box.com/s/8nkrjotu27q6ol6ouaqb901dfdnbspym"

BOX_CASSETTES_DIR = os.path.join(os.path.dirname(__file__), "..", "cassettes")
BOX_SKIP_REASON = (
    "Box cassette not recorded yet; run with real BOX_* env vars to record"
)


def box_cassette_missing(cassette_name):
    """skipif condition: this test's cassette is unrecorded and no real creds are set."""
    return not os.path.exists(
        os.path.join(BOX_CASSETTES_DIR, cassette_name)
    ) and not os.environ.get("BOX_CLIENT_ID")


@pytest.fixture
def mock_box_creds(monkeypatch):
    """Fixture that provides mock Box credentials if real ones aren't configured.

    If the BOX_* environment variables are set, this is a no-op (allowing
    cassettes to be recorded). Otherwise, patches mock values into config so
    the client can be constructed while VCR replays the recorded responses.
    """
    if os.environ.get("BOX_CLIENT_ID"):
        yield
        return

    monkeypatch.setattr("ricecooker.config.BOX_CLIENT_ID", "mock-client-id")
    monkeypatch.setattr("ricecooker.config.BOX_CLIENT_SECRET", "mock-client-secret")
    monkeypatch.setattr("ricecooker.config.BOX_ENTERPRISE_ID", "123456789")
    yield


@pytest.fixture
def no_requests_cache():
    """Make Box tests immune to globally installed requests_cache.

    tests/media_utils modules call requests_cache.install_cache() at import
    time, globally patching requests.Session; the patched session cannot wrap
    VCR's fake response objects, so restore the plain session for these tests.
    """
    with requests_cache.disabled():
        yield


def test_box_should_handle():
    handler = BoxHandler()
    assert handler.should_handle(box_pdf_link)
    assert handler.should_handle(box_video_link)
    assert handler.should_handle(box_vtt_link)
    assert handler.should_handle(box_audio_link)
    assert handler.should_handle("https://acme.app.box.com/s/abc123def")
    assert not handler.should_handle("https://example.com/file.pdf")
    assert not handler.should_handle("not-a-url")


@pytest.mark.skipif(box_cassette_missing("test_box_pdf.yaml"), reason=BOX_SKIP_REASON)
@box_vcr.use_cassette
def test_box_pdf(mock_box_creds, no_requests_cache):
    pytest.importorskip("box_sdk_gen")
    handler = BoxHandler()
    assert handler.should_handle(box_pdf_link)
    file_metadata = handler.execute(box_pdf_link, skip_cache=True)
    assert file_metadata is not None
    assert file_metadata[0].filename.endswith("pdf")
    assert file_metadata[0].original_filename == "41568-pdf.pdf"


@pytest.mark.skipif(box_cassette_missing("test_box_video.yaml"), reason=BOX_SKIP_REASON)
@box_vcr.use_cassette
def test_box_video(mock_box_creds, no_requests_cache):
    pytest.importorskip("box_sdk_gen")
    handler = BoxHandler()
    assert handler.should_handle(box_video_link)
    file_metadata = handler.execute(box_video_link, skip_cache=True)
    assert file_metadata is not None
    assert file_metadata[0].filename.endswith("ogv")
    assert file_metadata[0].original_filename == "low_res_ogv_video.ogv"


@pytest.mark.skipif(box_cassette_missing("test_box_vtt.yaml"), reason=BOX_SKIP_REASON)
@box_vcr.use_cassette
def test_box_vtt(mock_box_creds, no_requests_cache):
    pytest.importorskip("box_sdk_gen")
    handler = BoxHandler()
    assert handler.should_handle(box_vtt_link)
    file_metadata = handler.execute(box_vtt_link, skip_cache=True)
    assert file_metadata is not None
    assert file_metadata[0].filename.endswith("vtt")
    assert file_metadata[0].original_filename == "encapsulated.vtt"


@pytest.mark.skipif(box_cassette_missing("test_box_audio.yaml"), reason=BOX_SKIP_REASON)
@box_vcr.use_cassette
def test_box_audio(mock_box_creds, no_requests_cache):
    pytest.importorskip("box_sdk_gen")
    handler = BoxHandler()
    assert handler.should_handle(box_audio_link)
    file_metadata = handler.execute(box_audio_link, skip_cache=True)
    assert file_metadata is not None
    assert file_metadata[0].filename.endswith("mp3")
    assert file_metadata[0].original_filename == "audio_media_test.mp3"


def test_box_handle_file_uses_shared_link_header():
    """Unit test for the shared-link plumbing, independent of the Box SDK."""
    handler = BoxHandler()
    mock_client = MagicMock()
    file_info = mock_client.shared_links_files.find_file_for_shared_link.return_value
    file_info.name = "sample.pdf"
    file_info.id = "12345"
    file_info.type = "file"

    def fake_download(file_id, output_stream, boxapi):
        output_stream.write(b"%PDF-1.4 test bytes")

    mock_client.downloads.download_file_to_output_stream.side_effect = fake_download
    handler._box_client = mock_client

    url = "https://app.box.com/s/abc123def"
    file_metadata = handler.execute(url, skip_cache=True)

    assert file_metadata[0].original_filename == "sample.pdf"
    assert file_metadata[0].filename.endswith(".pdf")
    expected_boxapi = f"shared_link={url}"
    find_call = mock_client.shared_links_files.find_file_for_shared_link.call_args
    assert find_call.kwargs["boxapi"] == expected_boxapi
    download_call = mock_client.downloads.download_file_to_output_stream.call_args
    assert download_call.kwargs["file_id"] == "12345"
    assert download_call.kwargs["boxapi"] == expected_boxapi


def test_box_client_requires_credentials():
    pytest.importorskip("box_sdk_gen")
    handler = BoxHandler()
    with (
        patch("ricecooker.config.BOX_CLIENT_ID", None),
        patch("ricecooker.config.BOX_CLIENT_SECRET", None),
    ):
        with pytest.raises(RuntimeError, match="client credentials"):
            handler.box_client


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
