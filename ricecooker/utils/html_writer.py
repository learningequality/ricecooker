import os
import zipfile
from ricecooker.utils.downloader import read

class HTMLWriter():
    """
        Class for writing zipfiles
    """

    zf = None               # Zip file to write to
    write_to_path = None    # Where to write zip file

    def __init__(self, write_to_path, mode="w"):
        """ Args: write_to_path: (str) where to write zip file """
        self.map = {}                       # Keeps track of content to write to csv
        self.write_to_path = write_to_path  # Where to write zip file
        self.mode = mode                    # What mode to open zipfile in

    def __enter__(self):
        """ Called when opening context (e.g. with HTMLWriter() as writer: ) """
        self.open()
        return self

    def __exit__(self, type, value, traceback):
        """ Called when closing context """
        self.close()

    def _write_to_zipfile(self, filename, content):
        if not self.contains(filename):
            info = zipfile.ZipInfo(filename, date_time=(2013, 3, 14, 1, 59, 26))
            info.comment = "HTML FILE".encode()
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 0
            self.zf.writestr(info, content)

    def _copy_to_zipfile(self, filepath, arcname=None):
        filename = arcname or filepath
        if not self.contains(filename):
            self.zf.write(filepath, arcname=arcname)

    """ USER-FACING METHODS """

    def open(self):
        """ open: Opens zipfile to write to
            Args: None
            Returns: None
        """
        self.zf = zipfile.ZipFile(self.write_to_path, self.mode)

    def close(self):
        """ close: Close zipfile when done
            Args: None
            Returns: None
        """
        index_present = self.contains('index.html')
        self.zf.close() # Make sure zipfile closes no matter what
        if not index_present:
            raise ReferenceError("Invalid Zip at {}: missing index.html file (use write_index_contents method)".format(self.write_to_path))

    def contains(self, filename):
        """ contains: Checks if filename is in the zipfile
            Args: filename: (str) name of file to check
            Returns: boolean indicating whether or not filename is in the zip
        """
        return filename in self.zf.namelist()

    def write_contents(self, filename, contents, directory=None):
        """ write_contents: Write contents to filename in zip
            Args:
                contents: (str) contents of file
                filename: (str) name of file in zip
                directory: (str) directory in zipfile to write file to (optional)
            Returns: path to file in zip
        """
        filepath = "{}/{}".format(directory.rstrip("/"), filename) if directory else filename
        self._write_to_zipfile(filepath, contents)
        return filepath

    def write_file(self, filepath, filename=None, directory=None):
        """ write_file: Write local file to zip
            Args:
                filepath: (str) location to local file
                directory: (str) directory in zipfile to write file to (optional)
            Returns: path to file in zip

            Note: filepath must be a relative path
        """
        arcname = None
        if filename or directory:
            directory = directory.rstrip("/") + "/" if directory else ""
            filename = filename or os.path.basename(filepath)
            arcname = "{}{}".format(directory, filename)
        self._copy_to_zipfile(filepath, arcname=arcname)
        return arcname or filepath

    def write_url(self, url, filename, directory=None):
        """ write_url: Write contents from url to filename in zip
            Args:
                url: (str) url to file to download
                filename: (str) name of file in zip
                directory: (str) directory in zipfile to write file to (optional)
            Returns: path to file in zip
        """
        return self.write_contents(filename, read(url), directory=directory)

    def write_index_contents(self, contents):
        """ write_index_contents: Write main index file to zip
            Args:
                contents: (str) contents of file
            Returns: path to file in zip
        """
        self._write_to_zipfile('index.html', contents)
