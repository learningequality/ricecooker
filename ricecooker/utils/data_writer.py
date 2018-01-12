import csv
import os
import zipfile
from io import StringIO
from ricecooker.utils.downloader import read
from le_utils.constants import licenses

DEFAULT_WRITE_TO_PATH = "Channel.zip"
NO_COPYRIGHT_HOLDER_REQUIRED = [licenses.PUBLIC_DOMAIN]

class DataWriter():
    """
        Class for writing topic tree to standardized folder/csv structure
    """

    zf = None               # Zip file to write to
    write_to_path = None    # Where to write zip file

    def __init__(self, write_to_path=DEFAULT_WRITE_TO_PATH):
        """ Args: write_to_path: (str) where to write zip file (optional) """
        self.map = {}                       # Keeps track of content to write to csv
        self.write_to_path = write_to_path  # Where to write zip file

    def __enter__(self):
        """ Called when opening context (e.g. with DataWriter() as writer: ) """
        self.open()
        return self

    def __exit__(self, type, value, traceback):
        """ Called when closing context """
        self.close()

    def _write_to_zip(self, path, contents):
        """ _write_to_zip: Write file to zip
            Args:
                path: (str) where in zip to write file
                contents: (str) contents of file to write
            Returns: None
        """
        if isinstance(path, list):
            path = os.path.sep.join(path)
        self.zf.writestr(path, contents)

    def _commit(self, path, title, source_id=None, description=None, author=None, language=None, license=None, copyright_holder=None, license_description=None, thumbnail=None):
        """ _commit: Adds folder/file to map
            Args:
                path: (str) where in zip to write file
                title: (str) content's title
                source_id: (str) content's original id (optional)
                description: (str) description of content (optional)
                author (str): who created the content (optional)
                language (str): language of content (optional)
                license: (str) content's license (optional)
                copyright_holder (str): holder of content's license (optional)
                license_description (str): description of content's license (optional)
                thumbnail (str):  path to thumbnail in zip (optional)
            Returns: None
        """
        node = self.map.get(path)
        self.map.update({path: {
            'title': title or node and node.get('path'),
            'source_id': source_id or node and node.get('source_id'),
            'description': description or node and node.get('description'),
            'author': author or node and node.get('author'),
            'language': language or node and node.get('language'),
            'license': license or node and node.get('license'),
            'copyright_holder': copyright_holder or node and node.get('copyright_holder'),
            'license_description': license_description or node and node.get('license_description'),
            'thumbnail': thumbnail or node and node.get('thumbnail'),
        }})

    def _parse_path(self, path):
        """ _parse_path: Go through path and make sure topics exist in map
            Args: path: (str) path to file in zip
            Returns: None
        """
        paths = path.split('/')
        current_path = paths[0]
        for p in paths[1:]:
            current_path = "{}/{}".format(current_path, p)
            if not self.map.get(current_path): # Create any folders that might not exist yet
                self._commit(current_path, p)

    def _write_metadata(self):
        """ _write_metadata: Writes node metadata to csv file
            Args: None
            Returns: None
        """
        string_buffer = StringIO()
        writer = csv.writer(string_buffer, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(['Path *', 'Title *', 'Source ID', 'Description', 'Author', 'Language', 'License ID *', 'License Description', 'Copyright Holder', 'Thumbnail'])
        for k in self.map:
            node = self.map[k]
            writer.writerow([k, node['title'], node['source_id'], node['description'], node['author'], node['language'], node['license'], node['license_description'], node['copyright_holder'], node['thumbnail']])

        self.zf.writestr('Content.csv', string_buffer.getvalue())


    """ USER-FACING METHODS """

    def open(self):
        """ open: Opens zipfile to write to
            Args: None
            Returns: None
        """
        self.zf = zipfile.ZipFile(self.write_to_path, "w")

    def close(self):
        """ close: Close zipfile when done
            Args: None
            Returns: None
        """
        self._write_metadata()
        self.zf.close()

    def add_channel(self, title, source_id, domain, language, description=None, thumbnail=None):
        """ add_channel: Creates channel metadata
            Args:
                source_id: (str) channel's unique id
                domain: (str) who is providing the content (e.g. learningequality.org)
                title: (str): name of channel
                language: (str): language code for channel (e.g. 'en')
                description: (str) description of the channel (optional)
                thumbnail: (str) path to thumbnail in zip (optional)
            Returns: None
        """
        string_buffer = StringIO()
        writer = csv.writer(string_buffer, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(['Title', 'Description', 'Domain', 'Source ID', 'Language', 'Thumbnail'])
        writer.writerow([title, description, domain, source_id, language, thumbnail])
        self.zf.writestr('Channel.csv', string_buffer.getvalue())

    def add_folder(self, path, title, description=None, language=None, thumbnail=None, source_id=None, **node_data):
        """ add_folder: Creates folder in csv
            Args:
                path: (str) where in zip to write folder
                title: (str) content's title
                source_id: (str) content's original id (optional)
                description: (str) description of content (optional)
                language (str): language of content (optional)
                thumbnail (str):  path to thumbnail in zip (optional)
            Returns: None
        """
        self._parse_path(path)
        path = path if path.endswith(title) else "{}/{}".format(path, title)
        self._commit(path, title, description=description, language=language, thumbnail=thumbnail, source_id=source_id)

    def add_file(self, path, title, download_url, write_data=True, ext=None, license=None, copyright_holder=None, **node_data):
        """ add_file: Creates file in csv and writes file to zip
            Args:
                path: (str) where in zip to write file
                title: (str) content's title
                download_url: (str) url or local path to download from
                write_data: (boolean) indicates whether to add as a csv entry (optional)
                ext: (str) extension to use for file
                license (str): content's license
                copyright_holder (str): holder of content's license (required except for PUBLIC_DOMAIN)
                license_description (str): description of content's license (optional)
                source_id: (str) content's original id (optional)
                description: (str) description of content (optional)
                author (str): who created the content (optional)
                language (str): language of content (optional)
                thumbnail (str):  path to thumbnail in zip (optional)
            Returns: path to file in zip
        """
        if write_data:
            assert license, "Files must have a license"
            copyright_holder = None if not copyright_holder or copyright_holder.strip() == '' else copyright_holder
            assert license in NO_COPYRIGHT_HOLDER_REQUIRED or copyright_holder, "Licenses must have a copyright holder if they are not public domain"

        self._parse_path(path)
        if not ext:
            _name, ext = os.path.splitext(download_url or "")
            ext = ext.lower()  # normalize to lowercase extensions inside zip archive
        filepath = "{}/{}{}".format(path, title, ext)
        if download_url and filepath:
            self._write_to_zip(filepath, read(download_url))
            if write_data:
                self._commit(filepath, title, license=license, copyright_holder=copyright_holder, **node_data)
            return filepath
