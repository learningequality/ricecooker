import base64
import binascii
import functools
import hashlib
import mimetypes
import os
import re
import tempfile
from contextlib import contextmanager
from dataclasses import field
from sys import platform
from typing import Dict
from typing import Optional
from urllib.parse import unquote
from urllib.parse import urlparse

import filetype
import yt_dlp
from le_utils.constants import file_formats
from requests.exceptions import RequestException
from yt_dlp.extractor import gen_extractor_classes

from ricecooker import config
from ricecooker.utils.caching import generate_key
from ricecooker.utils.encodings import ext_from_content_type
from ricecooker.utils.encodings import ext_from_data_uri_mimetype
from ricecooker.utils.encodings import exts_from_mimetype
from ricecooker.utils.encodings import get_base64_data_uri
from ricecooker.utils.encodings import mimetype_from_content_type
from ricecooker.utils.paths import extract_path_ext
from ricecooker.utils.paths import resolve_path_ext
from ricecooker.utils.pipeline.exceptions import InvalidFileException
from ricecooker.utils.pipeline.exceptions import NotHandledException
from ricecooker.utils.pipeline.exceptions import ProbeError
from ricecooker.utils.references import neutralize_external_navigation
from ricecooker.utils.singlefile import render_page
from ricecooker.utils.singlefile import SingleFileRenderError
from ricecooker.utils.storage import get_hash
from ricecooker.utils.youtube import get_language_with_alpha2_fallback
from ricecooker.utils.youtube import is_youtube_url
from ricecooker.utils.youtube import YouTubeResource

from .context import ContextMetadata
from .context import FileMetadata
from .convert import _seal_directory_to_file
from .convert import ArchiveProcessingBaseHandler
from .convert import ConversionStageHandler
from .convert import VideoCompressionHandler
from .file_handler import FileHandler
from .file_handler import Handler
from .file_handler import StageHandler


class GenericFileContextMetadata(ContextMetadata):
    default_ext: Optional[str] = None
    ext: Optional[str] = None


class DeclaredExtMixin:
    CONTEXT_CLASS = GenericFileContextMetadata

    def get_cache_key(self, path, ext=None, **kwargs) -> str:
        key = super().get_cache_key(path, **kwargs)
        return f"{key}:{ext}" if ext else key


class DiskResourceHandler(DeclaredExtMixin, FileHandler):
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

    def cached_file_outdated(self, path, filename):
        if not os.path.exists(config.get_storage_path(filename)):
            return True
        # Cached by path, so a file edited in place must be copied again
        return not filename.startswith(get_hash(self._normalize_path(path)))

    def handle_file(self, path, default_ext=None, ext=None):
        path = self._normalize_path(path)
        try:
            ext = resolve_path_ext(path, declared_ext=ext, default_ext=default_ext)
        except ValueError as e:
            raise InvalidFileException(str(e)) from e
        with self.write_file(ext) as fh:
            with open(path, "rb") as fobj:
                for chunk in iter(lambda: fobj.read(2097152), b""):
                    fh.write(chunk)
        return FileMetadata(original_filename=os.path.basename(path))


class WebResourceHandler(FileHandler):
    """Base class for handling web URLs"""

    PATTERNS = []

    HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")

    def __init__(self, **context):
        super().__init__(**context)
        self._content_type_cache = {}

    def _content_type(self, url: str) -> str:
        if url not in self._content_type_cache:
            try:
                response = config.DOWNLOAD_SESSION.head(
                    url, allow_redirects=True, timeout=(30, 30)
                )
            except RequestException:
                response = None
            if response is None or not response.ok:
                try:
                    response = config.DOWNLOAD_SESSION.get(
                        url, stream=True, timeout=(30, 60)
                    )
                    response.close()
                    response.raise_for_status()
                except RequestException as e:
                    raise ProbeError(e) from e
            content_type = response.headers.get("content-type", "")
            self._content_type_cache[url] = (
                content_type.split(";", 1)[0].strip().lower()
            )
        return self._content_type_cache[url]

    def should_handle(self, url):
        """Check if this handler should handle the given URL"""
        try:
            parsed = urlparse(url)
            if parsed.scheme == "" or parsed.netloc == "":
                return False
            return any(pattern in parsed.netloc for pattern in self.PATTERNS)
        except ValueError:
            return False

    def cached_file_outdated(self, path, filename):
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


CONVERT_EXTENSIONS = frozenset(
    ext
    for handler in ConversionStageHandler.DEFAULT_CHILDREN
    for ext in handler.EXTENSIONS
)


def path_ext_or_none(path):
    try:
        return extract_path_ext(path)
    except ValueError:
        return None


# Not from mimetypes: its font types are absent before Python 3.14.
STATIC_ASSET_EXTENSIONS = frozenset(
    {
        "css",
        "csv",
        "eot",
        "js",
        file_formats.JSON,
        "map",
        "mjs",
        "otf",
        file_formats.SVG,
        "ttf",
        "woff",
        "woff2",
        "xml",
    }
)

NAME_KEPT_EXTENSIONS = CONVERT_EXTENSIONS | STATIC_ASSET_EXTENSIONS

_CONTAINER_EXTENSIONS = frozenset({"7z", "bz2", "gz", "rar", "tar", "xz", "zip"})

_ARCHIVE_EXTENSIONS = frozenset(
    ext
    for handler in ConversionStageHandler.DEFAULT_CHILDREN
    if issubclass(handler, ArchiveProcessingBaseHandler)
    for ext in handler.EXTENSIONS
)


_WHITESPACE = b" \t\r\n\f"


def _is_html(head):
    start = head.lstrip(b"\xef\xbb\xbf" + _WHITESPACE).lower()
    while start.startswith((b"<!--", b"<?")):
        close = b"-->" if start.startswith(b"<!--") else b"?>"
        end = start.find(close)
        if end == -1:
            return False
        start = start[end + len(close) :].lstrip(_WHITESPACE)
    return start.startswith((b"<!doctype html", b"<html", b"<head", b"<body"))


class WebDownloadContextMetadata(GenericFileContextMetadata):
    asset_ref: bool = False


class CatchAllWebResourceDownloadHandler(DeclaredExtMixin, WebResourceHandler):
    CONTEXT_CLASS = WebDownloadContextMetadata

    PATTERNS = [""]

    HANDLED_EXCEPTIONS = [RequestException]

    def get_cache_key(self, path, asset_ref=False, **kwargs) -> str:
        key = super().get_cache_key(path, **kwargs)
        name_ext = path_ext_or_none(path)
        if name_ext not in NAME_KEPT_EXTENSIONS:
            key += ":v2"
        if asset_ref and name_ext in STATIC_ASSET_EXTENSIONS:
            key += ":asset"
        return key

    def handle_file(self, path, default_ext=None, ext=None, asset_ref=False):
        # Use explicit timeout to prevent hanging downloads
        # (connection_timeout, read_timeout) - connection timeout for establishing connection,
        # read timeout for time between receiving data chunks (prevents stuck downloads)
        r = config.DOWNLOAD_SESSION.get(path, stream=True, timeout=(30, 60))
        r.raise_for_status()
        original_filename = extract_filename_from_request(path, r)
        chunks = r.iter_content(chunk_size=8192)
        head = b""
        for chunk in chunks:
            head += chunk
            if len(head) >= 512:
                break
        if ext:
            ext = resolve_path_ext(original_filename, declared_ext=ext)
        else:
            ext = self._resolve_ext(
                path,
                original_filename,
                r.headers.get("content-type"),
                head,
                default_ext,
                asset_ref=asset_ref,
            )
        with self.write_file(ext) as fh:
            fh.write(head)
            for chunk in chunks:
                fh.write(chunk)
        return FileMetadata(original_filename=original_filename)

    def _resolve_ext(self, path, filename, content_type, head, default_ext, asset_ref):
        name_ext = path_ext_or_none(filename)
        mimetype = mimetype_from_content_type(content_type)
        page = (
            name_ext in STATIC_ASSET_EXTENSIONS
            and mimetype == "text/html"
            and _is_html(head)
        )
        if page and asset_ref:
            raise InvalidFileException(
                f"{path} was answered with an HTML page, not a .{name_ext} file"
            )
        if not page and (
            name_ext in NAME_KEPT_EXTENSIONS or name_ext in exts_from_mimetype(mimetype)
        ):
            return name_ext
        if name_ext is None and default_ext:
            return default_ext
        ext = ext_from_content_type(content_type)
        if not ext or mimetype == "text/html":
            ext = getattr(filetype.guess(head), "extension", None) or ext
        # Many formats (.ggb, .sb3, .jar) are containers under their own extension.
        if name_ext and ext in _CONTAINER_EXTENSIONS:
            ext = default_ext if default_ext in _ARCHIVE_EXTENSIONS else name_ext
        ext = ext or name_ext
        if not ext:
            raise InvalidFileException(f"Could not determine the file type of {path}")
        return ext


class YouTubeContextMetadata(ContextMetadata):
    download_video: bool = True
    high_resolution: bool = False
    max_height: int = 0
    subtitle_languages: list[str] = field(default_factory=list)
    yt_dlp_settings: dict = field(default_factory=dict)
    default_ext: Optional[str] = None
    ext: Optional[str] = None


@functools.cache
def _yt_dlp_extractors():
    # yt-dlp's Generic extractor claims every URL.
    return [ie for ie in gen_extractor_classes() if ie.ie_key() != "Generic"]


class _QuietLogger:
    def debug(self, msg):
        config.LOGGER.debug(msg)

    info = warning = error = debug


class YoutubeDownloadHandler(WebResourceHandler):
    CONTEXT_CLASS = YouTubeContextMetadata

    PATTERNS = [""]

    HANDLED_EXCEPTIONS = [yt_dlp.utils.YoutubeDLError]

    def __init__(self, **context):
        super().__init__(**context)
        self._should_handle_cache = {}

    def _has_non_video_ext(self, url):
        try:
            ext = extract_path_ext(url)
        except ValueError:
            return False
        return ext not in VideoCompressionHandler.EXTENSIONS

    def should_handle(self, url):
        if not super().should_handle(url) or self._has_non_video_ext(url):
            return False
        if url not in self._should_handle_cache:
            self._should_handle_cache[url] = any(
                ie.suitable(url) for ie in _yt_dlp_extractors()
            )
        return self._should_handle_cache[url]

    def get_cache_key(self, path, **kwargs) -> str:
        return generate_key("DOWNLOADED", path, settings=kwargs["yt_dlp_settings"])

    def get_file_kwargs(self, context: YouTubeContextMetadata) -> list[dict]:
        for ext in (context.default_ext, context.ext):
            if ext and ext not in VideoCompressionHandler.EXTENSIONS:
                raise NotHandledException(ext)
        file_kwargs = []
        if context.download_video:
            max_height = context.max_height or (720 if context.high_resolution else 480)
            yt_dlp_settings = {
                "format": f"bestvideo[height<={max_height}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={max_height}][ext=webm]+bestaudio[ext=webm]/best[height<={max_height}][ext=mp4]",  # noqa: E501
                **context.yt_dlp_settings,
            }
            format_fallback = (
                ""
                if "format" in context.yt_dlp_settings
                else f"/bestvideo[height<={max_height}][ext=mp4]+bestaudio[ext=mp4]"
            )
            file_kwargs.append(
                {
                    "yt_dlp_settings": yt_dlp_settings,
                    "format_fallback": format_fallback,
                    "default_ext": context.default_ext,
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

    def _reject_playlist(self, path, info):
        if info.get("_type") in ("playlist", "multi_video"):
            raise InvalidFileException(f"{path} is a playlist, not a single video")

    def _no_video(self, path, reason):
        config.LOGGER.warning(f"\tyt-dlp found no video at {path}: {reason}")
        return NotHandledException(path)

    @contextmanager
    def _video_errors(self, path, fall_through):
        try:
            yield
        except Exception as e:
            if fall_through:
                raise self._no_video(path, e)
            if isinstance(e, yt_dlp.utils.YoutubeDLError):
                raise
            # yt-dlp re-raises extractor bugs as-is.
            raise yt_dlp.utils.DownloadError(str(e)) from e

    def _follow_url(self, ydl, info):
        inner = ydl.extract_info(
            info["url"], download=False, process=False, ie_key=info.get("ie_key")
        )
        if info["_type"] == "url":
            return inner
        # Mirrors yt-dlp's url_transparent merge in YoutubeDL.process_ie_result.
        exempted = {"_type", "url", "ie_key"}
        if not info.get("section_end") and info.get("section_start") is None:
            exempted |= {"id", "extractor", "extractor_key"}
        merged = {
            **inner,
            **{k: v for k, v in info.items() if v is not None and k not in exempted},
        }
        if merged.get("_type") == "url":
            merged["_type"] = "url_transparent"
        return merged

    def _is_audio_only(self, fmt):
        if fmt.get("vcodec") is not None:
            return fmt["vcodec"] == "none"
        # Extractors leave vcodec unset on bare audio URLs (e.g. AudioBoom).
        ext = fmt.get("ext") or yt_dlp.utils.determine_ext(fmt.get("url", ""))
        return ext in yt_dlp.utils.MEDIA_EXTENSIONS.audio

    def _extract_single(self, ydl, path, wants_video):
        if not is_youtube_url(path):
            try:
                content_type = self._content_type(path)
            except ProbeError:
                content_type = ""
            if content_type and content_type not in self.HTML_CONTENT_TYPES:
                raise self._no_video(path, content_type)
        with self._video_errors(path, fall_through=not wants_video):
            info = ydl.extract_info(path, download=False, process=False)
            while info.get("_type") in ("url", "url_transparent"):
                info = self._follow_url(ydl, info)
        # yt-dlp derives is_live from live_status only after this point.
        is_live = info.get("is_live") or info.get("live_status") == "is_live"
        if wants_video:
            self._reject_playlist(path, info)
            if is_live:
                raise InvalidFileException(f"{path} is a live stream")
        else:
            formats = info.get("formats") or ([info] if info.get("url") else [])
            if all(self._is_audio_only(f) for f in formats):
                raise self._no_video(path, "no video formats")
            if is_live:
                raise self._no_video(path, "live stream")
        return info

    def _fetch_from_youtube(
        self, path, yt_dlp_settings, file_format, destination_path, wants_video
    ):
        if not config.USEPROXY or not is_youtube_url(path):
            with yt_dlp.YoutubeDL(yt_dlp_settings) as ydl:
                info = self._extract_single(ydl, path, wants_video)
                with self._video_errors(path, fall_through=False):
                    ydl.process_ie_result(info, download=True)
                    if not os.path.exists(destination_path):
                        raise yt_dlp.utils.DownloadError("Failed to download " + path)
        else:
            # Connect to YouTube via an HTTP proxy
            yt_resource = YouTubeResource(path, useproxy=True, options=yt_dlp_settings)
            result1 = yt_resource.get_resource_info(
                options={"extract_flat": "in_playlist"}
            )
            if result1 is None:
                raise yt_dlp.utils.DownloadError("Failed to get resource info")
            self._reject_playlist(path, yt_resource.info)
            yt_dlp_settings["writethumbnail"] = False  # overwrite default behaviour
            if file_format == file_formats.VTT:
                # We need to use the proxy when downloading subtitles
                result2 = yt_resource.download(options=yt_dlp_settings, useproxy=True)
            else:
                # For video files we can skip the proxy for faster download speed
                result2 = yt_resource.download(options=yt_dlp_settings)
            if result2 is None or not os.path.exists(destination_path):
                raise yt_dlp.utils.DownloadError("Failed to download resource " + path)

    def handle_file(
        self, path, yt_dlp_settings=None, format_fallback="", default_ext=None
    ):
        # By default assume we are downloading a video file
        if yt_dlp_settings is None:
            raise ValueError("yt_dlp_settings must be provided")
        if format_fallback:
            yt_dlp_settings = {
                **yt_dlp_settings,
                "format": yt_dlp_settings["format"] + format_fallback,
            }
        is_subtitle = "subtitleslangs" in yt_dlp_settings
        wants_video = is_youtube_url(path) or is_subtitle or default_ext is not None
        if wants_video:
            yt_dlp_settings = {"noplaylist": True, **yt_dlp_settings}
        else:
            yt_dlp_settings = {"logger": _QuietLogger(), **yt_dlp_settings}
        youtube_language = None
        if is_subtitle:
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
        self._fetch_from_youtube(
            path, yt_dlp_settings, file_format, destination_path, wants_video
        )

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
        "application/vnd.google-apps.document": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.google-apps.spreadsheet": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.google-apps.presentation": "application/pdf",
        "application/vnd.google-apps.drawing": "image/png",
    }

    def __init__(self, **context):
        super().__init__(**context)
        self._drive_service = None

    @property
    def HANDLED_EXCEPTIONS(self):
        try:
            from googleapiclient.errors import HttpError as GoogleHttpError
        except ImportError:
            return []
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
        return bool(get_base64_data_uri(path))

    def get_cache_key(self, path: str) -> str:
        hashed_content = hashlib.md5()
        hashed_content.update(path.encode("utf-8"))
        return "ENCODED: {} (base64 encoded)".format(hashed_content.hexdigest())

    def handle_file(self, path: str):
        encoding_match = get_base64_data_uri(path)
        extension = ext_from_data_uri_mimetype(encoding_match.group(1))
        if extension is None:
            raise InvalidFileException(
                f"Unsupported base64 data URI mimetype: {encoding_match.group(1)}"
            )
        try:
            decoded = base64.decodebytes(encoding_match.group(2).encode("utf-8"))
        except binascii.Error as e:
            raise InvalidFileException(f"Malformed base64 data URI: {e}")
        with self.write_file(extension) as fh:
            fh.write(decoded)


class SingleFileRenderContextMetadata(ContextMetadata):
    crawl_max_depth: int = 1
    crawl_inner_links_only: bool = True
    crawl_rewrite_rule: Optional[str] = None
    browser_executable_path: Optional[str] = None
    # Auth for login-walled targets, forwarded to single-file's
    # --browser-cookies-file / --http-header. The probe in should_handle has
    # no per-URL context, so it authenticates separately via config.DOWNLOAD_SESSION.
    browser_cookies_file: Optional[str] = None
    http_headers: Optional[Dict[str, str]] = None


class SingleFileRenderHandler(WebResourceHandler):
    """Render a URL that serves an HTML page into an HTML5 zip via single-file-cli.

    ``should_handle`` does a cached HEAD request, or a streamed GET when HEAD
    fails, and claims a URL when a successful response reports HTML. No pip
    dependency is added — the ``single-file``/Chromium binaries are shelled out
    to lazily and only for HTML URLs. For login-walled targets see
    :class:`SingleFileRenderContextMetadata`.
    """

    CONTEXT_CLASS = SingleFileRenderContextMetadata

    HANDLED_EXCEPTIONS = [SingleFileRenderError]

    REMOTE_PROBE = True

    def should_handle(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
        except ValueError:
            return False
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return False
        return self._content_type(url) in self.HTML_CONTENT_TYPES

    def get_cache_key(self, path, **kwargs) -> str:
        # Include the crawl settings so two depths/scopes of the same URL do
        # not collide (mirrors MediaCompressionHandler.get_cache_key).
        return generate_key("SINGLEFILE", self.normalize_path(path), settings=kwargs)

    def handle_file(self, path, **context):
        with tempfile.TemporaryDirectory() as temp_dir:
            render_page(path, temp_dir, **context)
            self._neutralize_navigation(temp_dir)
            _seal_directory_to_file(self, temp_dir, file_formats.HTML5)

    def _neutralize_navigation(self, directory):
        """Apply neutralize_external_navigation to every rendered HTML page."""
        for root, _dirs, files in os.walk(directory):
            for name in files:
                if not name.lower().endswith((".html", ".htm", ".xhtml")):
                    continue
                file_path = os.path.join(root, name)
                with open(file_path, encoding="utf-8") as fh:
                    html = fh.read()
                rewritten = neutralize_external_navigation(html)
                if rewritten != html:
                    with open(file_path, "w", encoding="utf-8") as fh:
                        fh.write(rewritten)


class DownloadStageHandler(StageHandler):
    STAGE = "DOWNLOAD"
    DEFAULT_CHILDREN = [
        # Before yt-dlp, whose GoogleDrive extractor also claims Drive file links.
        GoogleDriveHandler,
        YoutubeDownloadHandler,
        # After the site-specific handlers and before the catch-all: HTML pages
        # render, everything else falls through to a static download.
        SingleFileRenderHandler,
        CatchAllWebResourceDownloadHandler,
        DiskResourceHandler,
        Base64FileHandler,
    ]

    def __init__(self, children=None):
        super().__init__(children=children)
        content_type_cache = {}
        for child in self._children:
            if isinstance(child, WebResourceHandler):
                child._content_type_cache = content_type_cache

    @staticmethod
    def _claims(handler, path):
        if handler.REMOTE_PROBE and handler.get_cached(path):
            return True
        try:
            return handler.should_handle(path)
        except ProbeError:
            return False

    def should_handle(self, path: str) -> bool:
        should_handle = any(
            self._claims(handler, path)
            for handler in sorted(self._children, key=lambda h: h.REMOTE_PROBE)
        )
        if not should_handle:
            # If we can't handle the specified path, we raise an error
            # to prevent further processing
            raise InvalidFileException(f"Could not handle download from {path}")
        return should_handle

    def get_handlers(self, context: Optional[Dict] = None) -> list[Handler]:
        if (context or {}).get("render_html", True):
            return self._children
        return [h for h in self._children if not isinstance(h, SingleFileRenderHandler)]

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


_download_stage = None


def read(path):
    """Fetch a URL or local path through the download stage; return its bytes.

    Replaces the old ``downloader.read``. The old ``loadjs`` selenium/pyppeteer
    render path is dropped (headless JS-render is a follow-up); the remaining
    callers only fetched static bytes. Raises ``InvalidFileException`` if the
    source cannot be fetched.
    """
    global _download_stage
    if _download_stage is None:
        _download_stage = DownloadStageHandler()
    results = _download_stage.execute(path, skip_cache=config.UPDATE)
    with open(results[0].path, "rb") as fh:
        return fh.read()
