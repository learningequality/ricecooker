import base64
import hashlib
import mimetypes
import os
import re
import tempfile
from dataclasses import field
from sys import platform
from typing import Dict
from typing import Optional
from urllib.parse import unquote
from urllib.parse import urlparse

import yt_dlp
from le_utils.constants import file_formats
from requests.exceptions import ConnectionError
from requests.exceptions import HTTPError
from requests.exceptions import InvalidSchema
from requests.exceptions import InvalidURL
from requests.exceptions import Timeout

from .context import ContextMetadata
from .context import FileMetadata
from .file_handler import FileHandler
from .file_handler import StageHandler
from ricecooker import config
from ricecooker.utils.caching import generate_key
from ricecooker.utils.encodings import get_base64_encoding
from ricecooker.utils.pipeline.exceptions import InvalidFileException
from ricecooker.utils.utils import extract_path_ext
from ricecooker.utils.utils import get_hash
from ricecooker.utils.youtube import get_language_with_alpha2_fallback
from ricecooker.utils.youtube import YouTubeResource


class GenericFileContextMetadata(ContextMetadata):
    default_ext: Optional[str] = None


class DiskResourceHandler(FileHandler):

    CONTEXT_CLASS = GenericFileContextMetadata

    HANDLED_EXCEPTIONS = [IOError, FileNotFoundError]

    def _normalize_path(self, path):
        """Convert file:// URLs to local file paths."""
        parsed = urlparse(path)
        if parsed.scheme == "file":

            # Normalise & platform-adapt
            path = os.path.normpath(unquote(parsed.path))

            if platform == "win32":
                # Path already uses back-slashes after normpath; just ensure a
                # drive-letter path is not prefixed with an extra separator.
                if (
                    path.startswith("\\")
                    and len(path) > 2
                    and path[1].isalpha()
                    and path[2] == ":"
                ):
                    path = path.lstrip("\\")

        return path

    def should_handle(self, path):
        return os.path.exists(self._normalize_path(path))

    def cached_file_outdated(self, filename):
        path = config.get_storage_path(filename)
        if not os.path.exists(config.get_storage_path(filename)):
            return True
        hash = get_hash(path)
        return not hash or not filename.startswith(hash)

    def handle_file(self, path, default_ext=None):
        path = self._normalize_path(path)
        ext = extract_path_ext(path, default_ext=default_ext)
        with self.write_file(ext) as fh:
            with open(path, "rb") as fobj:
                for chunk in iter(lambda: fobj.read(2097152), b""):
                    fh.write(chunk)
        return FileMetadata(original_filename=os.path.basename(path))


class WebResourceHandler(FileHandler):
    """Base class for handling web URLs"""

    PATTERNS = []

    def should_handle(self, url):
        """Check if this handler should handle the given URL"""
        try:
            parsed = urlparse(url)
            if parsed.scheme == "" or parsed.netloc == "":
                return False
            return any(pattern in parsed.netloc for pattern in self.PATTERNS)
        except ValueError:
            return False

    def cached_file_outdated(self, filename):
        return not os.path.exists(config.get_storage_path(filename))


CONTENT_DISPOSITION_FILENAME_STAR_RE = re.compile(
    r"filename\*=(?:([^\'\"]*)\'\')?([^;]+)"
)

CONTENT_DISPOSITION_FILENAME_RE = re.compile(r'filename=["\']?([^"\';]+)["\']?')


def get_filename_from_content_disposition_header(content_disposition):
    match = CONTENT_DISPOSITION_FILENAME_STAR_RE.search(content_disposition)
    if match:
        _, encoded_filename = match.groups()
        filename = unquote(encoded_filename)
        return filename

    # Fallback to 'filename' parameter if 'filename*' is not present
    match = CONTENT_DISPOSITION_FILENAME_RE.search(content_disposition)
    if match:
        return match.group(1)
    return None


def extract_filename_from_request(path, res):
    content_dis = res.headers.get("content-disposition")
    filename = None
    if content_dis:
        filename = get_filename_from_content_disposition_header(content_dis)
    if not filename:
        parsed_url = urlparse(path)
        filename = os.path.basename(parsed_url.path)
    return filename


class CatchAllWebResourceDownloadHandler(WebResourceHandler):
    CONTEXT_CLASS = GenericFileContextMetadata

    PATTERNS = [""]

    HANDLED_EXCEPTIONS = [
        HTTPError,
        ConnectionError,
        InvalidURL,
        InvalidSchema,
        Timeout,
    ]

    def handle_file(self, path, default_ext=None):
        # Use explicit timeout to prevent hanging downloads
        # (connection_timeout, read_timeout) - connection timeout for establishing connection,
        # read timeout for time between receiving data chunks (prevents stuck downloads)
        r = config.DOWNLOAD_SESSION.get(path, stream=True, timeout=(30, 60))
        original_filename = extract_filename_from_request(path, r)
        default_ext = extract_path_ext(original_filename, default_ext=default_ext)
        r.raise_for_status()
        with self.write_file(default_ext) as fh:
            for chunk in r.iter_content(chunk_size=8192):
                fh.write(chunk)
        return FileMetadata(original_filename=original_filename)


class YouTubeContextMetadata(ContextMetadata):
    download_video: bool = True
    high_resolution: bool = False
    max_height: int = 0
    subtitle_languages: list[str] = field(default_factory=list)
    yt_dlp_settings: dict = field(default_factory=dict)


class YoutubeDownloadHandler(WebResourceHandler):
    CONTEXT_CLASS = YouTubeContextMetadata

    PATTERNS = ["youtube.com", "youtu.be"]

    def get_cache_key(self, path, **kwargs) -> str:
        return generate_key("DOWNLOADED", path, settings=kwargs["yt_dlp_settings"])

    def get_file_kwargs(self, context: YouTubeContextMetadata) -> list[dict]:
        file_kwargs = []
        if context.download_video:
            max_height = context.max_height or (720 if context.high_resolution else 480)
            yt_dlp_settings = context.yt_dlp_settings or {
                "format": f"bestvideo[height<={max_height}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={max_height}][ext=webm]+bestaudio[ext=webm]/best[height<={max_height}][ext=mp4]",  # noqa: E501
            }
            file_kwargs.append(
                {
                    "yt_dlp_settings": yt_dlp_settings,
                }
            )
        for lang in context.subtitle_languages:
            file_kwargs.append(
                {
                    "yt_dlp_settings": {
                        "skip_download": True,
                        "writesubtitles": True,
                        "subtitleslangs": [lang],
                        "subtitlesformat": "best[ext={}]".format(file_formats.VTT),
                        "quiet": True,
                        "no_warnings": True,
                    },
                }
            )
        return file_kwargs

    def _fetch_from_youtube(self, path, yt_dlp_settings, file_format, destination_path):
        # Download the web_url which can be either a video or subtitles
        if not config.USEPROXY:
            # Connect to YouTube directly
            with yt_dlp.YoutubeDL(yt_dlp_settings) as ydl:
                ydl.download([path])
                if not os.path.exists(destination_path):
                    raise yt_dlp.utils.DownloadError("Failed to download " + path)
        else:
            # Connect to YouTube via an HTTP proxy
            yt_resource = YouTubeResource(path, useproxy=True, options=yt_dlp_settings)
            result1 = yt_resource.get_resource_info()
            if result1 is None:
                raise yt_dlp.utils.DownloadError("Failed to get resource info")
            yt_dlp_settings["writethumbnail"] = False  # overwrite default behaviour
            if file_format == file_formats.VTT:
                # We need to use the proxy when downloading subtitles
                result2 = yt_resource.download(options=yt_dlp_settings, useproxy=True)
            else:
                # For video files we can skip the proxy for faster download speed
                result2 = yt_resource.download(options=yt_dlp_settings)
            if result2 is None or not os.path.exists(destination_path):
                raise yt_dlp.utils.DownloadError("Failed to download resource " + path)

    def handle_file(self, path, yt_dlp_settings=None):
        # By default assume we are downloading a video file
        if yt_dlp_settings is None:
            raise ValueError("yt_dlp_settings must be provided")
        youtube_language = None
        if "subtitleslangs" in yt_dlp_settings:
            file_format = file_formats.VTT
            youtube_language = yt_dlp_settings["subtitleslangs"][0]
            download_ext = ext = ".{lang}.{ext}".format(
                lang=youtube_language, ext=file_formats.VTT
            )
        else:
            download_ext = ""
            ext = ".mp4"
            file_format = file_formats.MP4

        # Get hash of web_url to act as temporary storage name
        url_hash = hashlib.md5()
        url_hash.update(path.encode("utf-8"))
        tempfilename = "{}{ext}".format(url_hash.hexdigest(), ext=ext)
        outtmpl_path = os.path.join(tempfile.gettempdir(), tempfilename)
        yt_dlp_settings["outtmpl"] = outtmpl_path
        destination_path = outtmpl_path + download_ext  # file dest. after download

        # Delete files in case previously downloaded
        if os.path.exists(outtmpl_path):
            os.remove(outtmpl_path)
        if os.path.exists(destination_path):
            os.remove(destination_path)

        # Download the file from YouTube
        self._fetch_from_youtube(path, yt_dlp_settings, file_format, destination_path)

        with self.write_file(file_format) as fh:
            with open(destination_path, "rb") as fobj:
                for chunk in iter(lambda: fobj.read(2097152), b""):
                    fh.write(chunk)
        if youtube_language is not None:
            language_obj = get_language_with_alpha2_fallback(youtube_language)
            return FileMetadata(language=language_obj.code)


instructions = "Please install ricecooker using `pip install ricecooker[google_drive]` to include required dependencies"


class GoogleDriveHandler(WebResourceHandler):
    """Handles downloading from Google Drive share URLs"""

    PATTERNS = ["drive.google.com", "docs.google.com"]

    # Mapping of Google Workspace MIME types to export formats
    GOOGLE_WORKSPACE_FORMATS = {
        "application/vnd.google-apps.document": "application/pdf",
        "application/vnd.google-apps.spreadsheet": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.google-apps.presentation": "application/pdf",
        "application/vnd.google-apps.drawing": "image/png",
    }

    def __init__(self):
        super().__init__()
        self._drive_service = None

    @property
    def HANDLED_EXCEPTIONS(self):
        from googleapiclient.errors import HttpError as GoogleHttpError

        return [GoogleHttpError]

    @property
    def drive_service(self):
        try:
            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build
        except ImportError:
            raise RuntimeError(
                "Google Drive downloads require google-auth and google-api-python-client libraries\n"
                + instructions
            )

        if self._drive_service is None:
            if not config.GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH:
                raise RuntimeError(
                    "Google Drive downloads require service account credentials.\n"
                    "Please set GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH environment variable."
                )
            credentials = Credentials.from_service_account_file(
                config.GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_PATH,
                scopes=["https://www.googleapis.com/auth/drive.readonly"],
            )
            self._drive_service = build(
                "drive", "v3", credentials=credentials, cache_discovery=False
            )
        return self._drive_service

    def _get_file_id(self, url):
        """Extract file ID from Google Drive URL"""
        FILE_ID_PATTERNS = [
            r"drive\.google\.com/file/d/([^/]+)",  # /file/d/{fileid}/view
            r"drive\.google\.com/open\?id=([^/]+)",  # /open?id={fileid}
            r"docs\.google\.com/\w+/d/([^/]+)",  # docs/sheets/etc
        ]

        for pattern in FILE_ID_PATTERNS:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        raise ValueError(f"Could not extract file ID from URL: {url}")

    def _is_google_workspace_file(self, mime_type: str) -> bool:
        """Check if file is a Google Workspace native format"""
        return mime_type.startswith("application/vnd.google-apps.")

    def _get_export_mime_type(self, mime_type: str) -> str:
        """Get the export MIME type for a Google Workspace file"""
        export_type = self.GOOGLE_WORKSPACE_FORMATS.get(mime_type)
        if not export_type:
            # Default to PDF for unknown Google Workspace types
            export_type = "application/pdf"
        return export_type

    def handle_file(self, path: str):
        try:
            from googleapiclient.http import MediaIoBaseDownload
        except ImportError:
            raise RuntimeError(
                "Google Drive downloads require google-api-python-client library\n"
                + instructions
            )
        file_id = self._get_file_id(path)

        # Get file metadata to determine extension
        file = (
            self.drive_service.files()
            .get(fileId=file_id, fields="name, mimeType")
            .execute()
        )

        mime_type = file["mimeType"]
        is_workspace_file = self._is_google_workspace_file(mime_type)

        if is_workspace_file:
            # Handle Google Workspace files using export
            export_mime_type = self._get_export_mime_type(mime_type)
            request = self.drive_service.files().export_media(
                fileId=file_id, mimeType=export_mime_type
            )
            # Update extension based on export format
            ext = mimetypes.guess_extension(export_mime_type) or ""
        else:
            # Handle regular binary files
            request = self.drive_service.files().get_media(fileId=file_id)
            # Get extension from original filename or mimetype
            _, ext = os.path.splitext(file["name"])
            if not ext and mime_type:
                ext = mimetypes.guess_extension(mime_type) or ""

        with self.write_file(ext.lstrip(".")) as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

        return FileMetadata(
            original_filename=file["name"],
        )


class Base64FileHandler(FileHandler):
    def should_handle(self, path: str) -> bool:
        return bool(get_base64_encoding(path))

    def get_cache_key(self, path: str) -> str:
        hashed_content = hashlib.md5()
        hashed_content.update(path.encode("utf-8"))
        return "ENCODED: {} (base64 encoded)".format(hashed_content.hexdigest())

    def handle_file(self, path: str):
        encoding_match = get_base64_encoding(path)
        extension = encoding_match.group(1)
        # Prefer JPG over JPEG as a file extension
        if extension == file_formats.JPEG:
            extension = file_formats.JPG
        with self.write_file(extension) as fh:
            fh.write(base64.decodebytes(encoding_match.group(2).encode("utf-8")))


class DownloadStageHandler(StageHandler):
    STAGE = "DOWNLOAD"
    DEFAULT_CHILDREN = [
        YoutubeDownloadHandler,
        GoogleDriveHandler,
        CatchAllWebResourceDownloadHandler,
        DiskResourceHandler,
        Base64FileHandler,
    ]

    def should_handle(self, path: str) -> bool:
        should_handle = super().should_handle(path)
        if not should_handle:
            # If we can't handle the specified path, we raise an error
            # to prevent further processing
            raise InvalidFileException(f"Could not handle download from {path}")
        return should_handle

    def execute(
        self,
        path: str,
        context: Optional[Dict] = None,
        skip_cache: Optional[bool] = False,
    ) -> list[FileMetadata]:
        metadata_list = super().execute(path, context=context, skip_cache=skip_cache)
        if not metadata_list:
            # The download stage is special, as we expect it to always return a file
            # if it does not, we raise an exception to prevent further processing
            raise InvalidFileException(f"No file could be downloaded from {path}")

        # Ensure all downloaded files are actually in storage
        for metadata in metadata_list:
            if not metadata.path.startswith(os.path.abspath(config.STORAGE_DIRECTORY)):
                raise InvalidFileException(f"{path} failed to transfer to storage")

        return metadata_list
