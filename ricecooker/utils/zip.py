import os
import tempfile
import zipfile


def _read_file(path):
    with open(path, "rb") as f:
        return f.read()


def create_predictable_zip(path, entrypoint=None, file_converter=None):
    """
    Create a zip file with predictable sort order and metadata so that MD5 will
    stay consistent if zipping the same content twice.
    Args:
        path (str): absolute path either to a directory to zip up, or an existing zip file to convert.
        entrypoint (str or None): if specified, a relative file path in the zip to serve as the first page to load
    Returns: path (str) to the output zip file
    """
    extension = "zip"
    # if path is a directory, recursively enumerate all the files under the directory
    if os.path.isdir(path):
        paths = []

        for root, directories, filenames in os.walk(path):
            paths += [
                os.path.join(root, filename)[len(path) + 1 :] for filename in filenames
            ]

        def reader(x):
            return _read_file(os.path.join(path, x))

    # otherwise, if it's a zip file, open it up and pull out the list of names
    elif os.path.isfile(path):
        extension = os.path.splitext(path)[1]
        inputzip = zipfile.ZipFile(path)
        paths = inputzip.namelist()

        def reader(x):
            return inputzip.read(x)

    # create a temporary zip file path to write the output into
    zippathfd, zippath = tempfile.mkstemp(suffix=".{}".format(extension))

    with zipfile.ZipFile(zippath, "w", compression=zipfile.ZIP_DEFLATED) as outputzip:
        # loop over the file paths in sorted order, to ensure a predictable zip
        for filepath in sorted(paths):
            write_file_to_zip_with_neutral_metadata(
                outputzip,
                filepath,
                file_converter(filepath, reader)
                if file_converter
                else reader(filepath),
            )
        os.fdopen(zippathfd).close()
    return zippath


def write_file_to_zip_with_neutral_metadata(zfile, filepath, content):
    """
    Write the string `content` to `filepath` in the open ZipFile `zfile`.
    Args:
        zfile (ZipFile): open ZipFile to write the content into
        filepath (str): the file path within the zip file to write into
        content (str): the content to write into the zip
    Returns: None
    """
    # Convert any windows file separators to unix style for consistent
    # file paths in the zip file
    filepath = filepath.replace("\\", "/")
    info = zipfile.ZipInfo(filepath, date_time=(2015, 10, 21, 7, 28, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.comment = "".encode()
    info.create_system = 0
    zfile.writestr(info, content)
