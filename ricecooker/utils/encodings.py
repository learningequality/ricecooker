import base64
import codecs
import re

import chardet
from le_utils.constants import file_formats

BASE64_REGEX_STR = r"data:image\/([A-Za-z]*);base64,((?:[A-Za-z0-9+\/]{4})*(?:[A-Za-z0-9+\/]{2}==|[A-Za-z0-9+\/]{3}=)*)"
BASE64_REGEX = re.compile(BASE64_REGEX_STR, flags=re.IGNORECASE)

DATA_URI_BASE64_REGEX = re.compile(
    r"^data:([\w.+-]+/[\w.+-]+)?(?:;[\w-]+=[^;,]+)*;base64,([A-Za-z0-9+/=\s]+)$",
    flags=re.IGNORECASE,
)

# Not from mimetypes: its table differs by OS and Python version.
_MIMETYPE_EXTENSIONS = {
    file_formats.BLOOMPUB_MIMETYPE: ("bloompub",),
    file_formats.EPUB_MIMETYPE: ("epub",),
    file_formats.GIF_MIMETYPE: ("gif",),
    file_formats.HTML5_ARTICLE_MIMETYPE: ("kpub",),
    file_formats.JPG_MIMETYPE: ("jpg", "jpeg", "jpe", "jfif"),
    file_formats.JSON_MIMETYPE: ("json",),
    file_formats.MP4_MIMETYPE: ("mp4", "m4v"),
    file_formats.PDF_MIMETYPE: ("pdf",),
    file_formats.PERSEUS_MIMETYPE: ("perseus",),
    file_formats.PNG_MIMETYPE: ("png",),
    file_formats.SVG_MIMETYPE: ("svg",),
    file_formats.WEBM_MIMETYPE: ("webm",),
    "application/zip": ("zip",),
    "audio/mpeg": ("mp3",),
    "audio/aac": ("aac",),
    "audio/mp4": ("m4a",),
    "audio/ogg": ("ogg", "oga"),
    "audio/wav": ("wav",),
    "audio/x-wav": ("wav",),
    "video/mpeg": ("mpg", "mpeg"),
    "video/ogg": ("ogv",),
    "video/quicktime": ("mov",),
    "video/x-flv": ("flv",),
    "video/x-matroska": ("mkv",),
    "video/x-ms-wmv": ("wmv",),
    "video/x-msvideo": ("avi",),
    "text/vtt": ("vtt",),
    "application/x-subrip": ("srt",),
    "text/srt": ("srt",),
    "application/ttml+xml": ("ttml", "dfxp"),
    "application/ttaf+xml": ("dfxp",),
    "application/x-sami": ("sami", "smi"),
    "text/x-scc": ("scc",),
    "application/rtf": ("rtf",),
    "application/vnd.oasis.opendocument.text": ("odt",),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (
        "docx",
    ),
    "text/markdown": ("md", "markdown"),
    "image/avif": ("avif",),
    "image/bmp": ("bmp",),
    "image/emf": ("emf",),
    "image/fits": ("fits", "fit", "fts"),
    "image/jp2": ("jp2", "jpg2"),
    "image/jpx": ("jpx", "jpf"),
    "image/pcx": ("pcx",),
    "image/svg+xml": ("svg",),
    "image/tiff": ("tiff", "tif"),
    "image/vnd.microsoft.icon": ("ico",),
    "image/vnd.mozilla.apng": ("apng",),
    "image/webp": ("webp",),
    "image/wmf": ("wmf",),
    "image/x-cmu-raster": ("ras",),
    "image/x-icon": ("ico",),
    "image/x-ms-bmp": ("bmp",),
    "image/x-photoshop": ("psd",),
    "image/x-portable-anymap": ("pnm",),
    "image/x-portable-bitmap": ("pbm",),
    "image/x-portable-graymap": ("pgm",),
    "image/x-portable-pixmap": ("ppm",),
    "image/x-rgb": ("rgb",),
    "image/x-targa": ("tga",),
    "image/x-xbitmap": ("xbm",),
    "image/x-xpixmap": ("xpm",),
    "font/collection": ("ttc",),
    "font/otf": ("otf",),
    "font/ttf": ("ttf",),
    "font/woff": ("woff",),
    "font/woff2": ("woff2",),
    "application/vnd.ms-fontobject": ("eot",),
    "application/javascript": ("js", "mjs"),
    "text/javascript": ("js", "mjs"),
    "application/xml": ("xml",),
    "text/xml": ("xml",),
    "text/css": ("css",),
    "text/csv": ("csv",),
    "text/html": ("html", "htm"),
    "application/xhtml+xml": ("xhtml",),
    "application/vnd.apple.mpegurl": ("m3u8",),
    "application/x-mpegurl": ("m3u8",),
}


def get_base64_encoding(text):
    """get_base64_encoding: Get the first base64 match or None
    Args:
        text (str): text to check for base64 encoding
    Returns: First match in text
    """
    return BASE64_REGEX.search(text)


def get_base64_data_uri(text):
    """Match a base64 ``data:`` URI of any mimetype (group 1 = mimetype, group 2 = data), or None."""
    return DATA_URI_BASE64_REGEX.match(text)


_FORMATLESS_TYPES = {"application/octet-stream", "binary/octet-stream", "text/plain"}


def mimetype_from_content_type(content_type):
    if not content_type:
        return None
    return content_type.split(";")[0].strip().lower()


def ext_from_content_type(content_type):
    mimetype = mimetype_from_content_type(content_type)
    if not mimetype or mimetype in _FORMATLESS_TYPES:
        return None
    return next(iter(exts_from_mimetype(mimetype)), None)


def exts_from_mimetype(mimetype):
    return _MIMETYPE_EXTENSIONS.get(mimetype, ())


def ext_from_data_uri_mimetype(mimetype):
    """Map a ``data:`` URI mimetype to a file extension (no dot), or None if undeterminable."""
    if not mimetype or not mimetype.lower().startswith(("image/", "font/")):
        return None
    return ext_from_content_type(mimetype)


_C1_BYTES = re.compile(rb"[\x80-\x9f]")


def decode_text(data):
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError as e:
        encoding = (
            chardet.detect(data[e.start : e.start + 4096])["encoding"] or "latin-1"
        )
        try:
            codec = codecs.lookup(encoding).name
        except LookupError:
            encoding, codec = "latin-1", "iso8859-1"
        # chardet names cp1252 only when the sampled bytes include 0x80-0x9F.
        if codec == "iso8859-1" and _C1_BYTES.search(data):
            encoding = "cp1252"
        try:
            return data.decode(encoding, errors="surrogateescape"), encoding
        except UnicodeDecodeError:
            # surrogateescape can't absorb a truncated UTF-16/32 code unit.
            return data.decode("latin-1"), "latin-1"


def encode_text(text, encoding):
    return text.encode(encoding, errors="surrogateescape")


def write_base64_to_file(encoding, fpath_out):
    """write_base64_to_file: Convert base64 image to file
    Args:
        encoding (str): base64 encoded string
        fpath_out (str): path to file to write
    Returns: None
    """

    encoding_match = get_base64_encoding(encoding)

    assert encoding_match, "Error writing to file: Invalid base64 encoding"

    with open(fpath_out, "wb") as target_file:
        target_file.write(base64.decodebytes(encoding_match.group(2).encode("utf-8")))


def encode_file_to_base64(fpath_in, prefix):
    """encode_file_to_base64: gets base64 encoding of file
    Args:
        fpath_in (str): path to file to encode
        prefix (str): file data for encoding (e.g. 'data:image/png;base64,')
    Returns: base64 encoding of file
    """
    with open(fpath_in, "rb") as file_obj:
        return prefix + base64.b64encode(file_obj.read()).decode("utf-8")
