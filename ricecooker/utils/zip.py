import os
import tempfile
import zipfile

def _read_file(path):
    with open(path, "rb") as f:
        return f.read()

def create_predictable_zip(path):
    """ create_predictable_zip: Create a zip file with predictable sort order and metadata, for MD5 consistency.
        Args:
            path (str): absolute path either to a directory to zip up, or an existing zip file to convert.
        Returns: path (str) to the output zip file
    """

    # if path is a directory, recursively enumerate all the files under the directory
    if os.path.isdir(path): 
        paths = []
        for root, directories, filenames in os.walk(path):
            paths += [os.path.join(root, filename)[len(path)+1:] for filename in filenames]
        reader = lambda x: _read_file(os.path.join(path, x))
    # otherwise, if it's a zip file, open it up and pull out the list of names
    elif os.path.isfile(path) and os.path.splitext(path)[1] == ".zip":
        inputzip = zipfile.ZipFile(path)
        paths = inputzip.namelist()
        reader = lambda x: inputzip.read(x)
    else:
        raise Exception("The `path` must either point to a directory or to a zip file.")

    # create a temporary zip file path to write the output into
    zippath = tempfile.mkstemp(suffix=".zip")[1]

    with zipfile.ZipFile(zippath, "w") as outputzip:
        # loop over the file paths in sorted order, to ensure a predictable zip
        for filepath in sorted(paths):
            write_file_to_zip_with_neutral_metadata(outputzip, filepath, reader(filepath))
    return zippath


def write_file_to_zip_with_neutral_metadata(zfile, filename, content):
    """ write_file_to_zip_with_neutral_metadata: Write a string into an open ZipFile with predictable metadata.
        Args:
            zfile (ZipFile): open ZipFile to write the content into
            filename (str): the file path within the zip file to write into
            content (str): the content to write into the zip
        Returns: None
    """

    info = zipfile.ZipInfo(filename, date_time=(2015, 10, 21, 7, 28, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.comment = "".encode()
    info.create_system = 0
    zfile.writestr(info, content)

