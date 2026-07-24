import base64
import mimetypes
import re

BASE64_REGEX_STR = r"data:image\/([A-Za-z]*);base64,((?:[A-Za-z0-9+\/]{4})*(?:[A-Za-z0-9+\/]{2}==|[A-Za-z0-9+\/]{3}=)*)"
BASE64_REGEX = re.compile(BASE64_REGEX_STR, flags=re.IGNORECASE)

DATA_URI_BASE64_REGEX = re.compile(
    r"^data:([\w.+-]+/[\w.+-]+)?(?:;[\w-]+=[^;,]+)*;base64,([A-Za-z0-9+/=\s]+)$",
    flags=re.IGNORECASE,
)

# Pin extensions for the types single-file-cli emits, so they resolve the same
# on every supported Python (e.g. image/webp is absent from stdlib mimetypes
# before 3.11) rather than depending on the interpreter's mimetypes DB.
_DATA_URI_EXTENSIONS = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/svg+xml": "svg",
    "image/webp": "webp",
    "font/woff2": "woff2",
    "font/woff": "woff",
    "font/ttf": "ttf",
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


def ext_from_data_uri_mimetype(mimetype):
    """Map a ``data:`` URI mimetype to a file extension (no dot), or None if undeterminable."""
    if not mimetype:
        return None
    mimetype = mimetype.lower()
    if mimetype in _DATA_URI_EXTENSIONS:
        return _DATA_URI_EXTENSIONS[mimetype]
    # Restrict the guess_extension fallback to image/font so a non-asset
    # mimetype (e.g. text/plain) is rejected, not decoded to a spurious file.
    if not mimetype.startswith(("image/", "font/")):
        return None
    guessed = mimetypes.guess_extension(mimetype)
    return guessed.lstrip(".") if guessed else None


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
