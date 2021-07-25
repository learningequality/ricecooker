import re
import base64

BASE64_REGEX_STR = r'data:image\/([A-Za-z]*);base64,((?:[A-Za-z0-9+\/]{4})*(?:[A-Za-z0-9+\/]{2}==|[A-Za-z0-9+\/]{3}=)*)'
BASE64_REGEX = re.compile(BASE64_REGEX_STR, flags=re.IGNORECASE)


def get_base64_encoding(text):
    """ get_base64_encoding: Get the first base64 match or None
        Args:
            text (str): text to check for base64 encoding
        Returns: First match in text
    """
    return BASE64_REGEX.search(text)

def write_base64_to_file(encoding, fpath_out):
    """ write_base64_to_file: Convert base64 image to file
        Args:
            encoding (str): base64 encoded string
            fpath_out (str): path to file to write
        Returns: None
    """

    encoding_match = get_base64_encoding(encoding)

    assert encoding_match, "Error writing to file: Invalid base64 encoding"

    with open(fpath_out, "wb") as target_file:
        target_file.write(base64.decodestring(encoding_match.group(2).encode('utf-8')))

def encode_file_to_base64(fpath_in, prefix):
    """ encode_file_to_base64: gets base64 encoding of file
        Args:
            fpath_in (str): path to file to encode
            prefix (str): file data for encoding (e.g. 'data:image/png;base64,')
        Returns: base64 encoding of file
    """
    with open(fpath_in, 'rb') as file_obj:
        return prefix + base64.b64encode(file_obj.read()).decode('utf-8')
