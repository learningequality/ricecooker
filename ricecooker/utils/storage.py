import hashlib
import os
import shutil
import tempfile

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
    dest = config.get_storage_path(filename)
    # The name is the content hash, so an existing file is already right;
    # replacing one another thread holds open fails on Windows.
    if os.path.exists(dest):
        return filename
    # Write-then-rename: chefs sharing storage may read a file while another stores it.
    fd, tmp = tempfile.mkstemp(
        dir=os.path.dirname(dest), prefix=filename, suffix=".tmp"
    )
    os.close(fd)
    try:
        shutil.copy(srcfilename, tmp)
        os.replace(tmp, dest)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return filename
