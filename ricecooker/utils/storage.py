import hashlib
import shutil

from ricecooker import config
from ricecooker.utils.paths import extract_path_ext


def get_hash(filepath):
    file_hash = hashlib.md5()
    with open(filepath, "rb") as fobj:
        for chunk in iter(lambda: fobj.read(2097152), b""):
            file_hash.update(chunk)
    return file_hash.hexdigest()


def copy_file_to_storage(srcfilename, ext=None):
    """
    Copy `srcfilename` (filepath) to destination.
    :rtype: None
    """
    if ext is None:
        ext = extract_path_ext(srcfilename)

    hash = get_hash(srcfilename)
    filename = "{}.{}".format(hash, ext)
    try:
        shutil.copy(srcfilename, config.get_storage_path(filename))
    except shutil.SameFileError:
        return filename

    return filename
