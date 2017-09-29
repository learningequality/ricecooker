import csv
import os

from ricecooker.config import LOGGER


# CONSTANTS
################################################################################

DEFAULT_CHANNEL_INFO_FILENAME = 'Channel.csv'
CHANNEL_TITLE_KEY = 'Title'
CHANNEL_DESCRIPTION_KEY = 'Description'
CHANNEL_DOMAIN_KEY = 'Domain'
CHANNEL_SOURCEID_KEY = 'Source ID'
CHANNEL_LANGUAGE_KEY = 'Language'
CHANNEL_THUMBNAIL_KEY = 'Thumbnail'
CHANNEL_INFO_HEADER = [
    CHANNEL_TITLE_KEY,
    CHANNEL_DESCRIPTION_KEY,
    CHANNEL_DOMAIN_KEY,
    CHANNEL_SOURCEID_KEY,
    CHANNEL_LANGUAGE_KEY,
    CHANNEL_THUMBNAIL_KEY
]

DEFAULT_CONTENT_INFO_FILENAME = 'Content.csv'
CONTENT_PATH_KEY = 'Path *'
CONTENT_TITLE_KEY = 'Title *'
CONTENT_SOURCEID_KEY = 'Source ID'
CONTENT_DESCRIPTION_KEY = 'Description'
CONTENT_AUTHOR_KEY = 'Author'
CONTENT_LANGUAGE_KEY = 'Language'
CONTENT_LICENSE_ID_KEY = 'License ID *'
CONTENT_LICENSE_DESCRIPTION_KEY = 'License Description'
CONTENT_LICENSE_COPYRIGHT_HOLDER_KEY = 'Copyright Holder'
CONTENT_THUMBNAIL_KEY = 'Thumbnail'
CONTENT_INFO_HEADER = [
    CONTENT_PATH_KEY,
    CONTENT_TITLE_KEY,
    CONTENT_SOURCEID_KEY,
    CONTENT_DESCRIPTION_KEY,
    CONTENT_AUTHOR_KEY,
    CONTENT_LANGUAGE_KEY,
    CONTENT_LICENSE_ID_KEY,
    CONTENT_LICENSE_DESCRIPTION_KEY,
    CONTENT_LICENSE_COPYRIGHT_HOLDER_KEY,
    CONTENT_THUMBNAIL_KEY
]



# HELPER FUNCTIONS
################################################################################

def path_to_tuple(path, windows=False):
    """
    Used to split a `chan_path`
    """
    if windows:
        path_tup = tuple(path.split('\\'))
    else:
        path_tup = tuple(path.split('/'))
    return path_tup

def get_metadata_file_path(channeldir, filename):
    """
    Return the path to the metadata file named `filename` that is a sibling of `channeldir`.
    """
    channelparentdir, channeldirname = os.path.split(channeldir)
    return os.path.join(channelparentdir, filename)



# METADATA PROVIDERS
################################################################################

class MetadataProvider(object):

    def validate(self):
        """
        Do a dry-run to check if metadata provided is valid.
        """
        pass

    def generate(self):
        raise NotImplementedError('Subclasses should implement generate method.')


def _read_csv_lines(path):
    """
    Opens CSV file `path` and returns list of rows.
    Pass output of this function to `csv.DictReader` for reading data.
    """
    csv_file = open(path, 'r')
    csv_lines_raw = csv_file.readlines()
    csv_lines_clean = [line for line in csv_lines_raw if len(line.strip()) > 0]
    return csv_lines_clean

def _clean_dict(row):
    """
    Transform empty strings values of dict `row` to None.
    """
    row_cleaned = {}
    for key, val in row.items():
        if val is None or val == '':
            row_cleaned[key] = None
        else:
            row_cleaned[key] = val
    return row_cleaned


class CsvMetadataProvider(MetadataProvider):

    def __init__(self, channeldir, channelinfo=DEFAULT_CHANNEL_INFO_FILENAME,
                 contentinfo=DEFAULT_CONTENT_INFO_FILENAME):
        """
        Load the metadata from CSV files `channelinfo` and `contentinfo`.
        """
        self.channeldir = channeldir
        self.channelinfo = channelinfo
        self.contentinfo = contentinfo
        self.cache = {}           # {  ('chan', 'path','as','tuple's) --> node metadata dict
        self.validate_format()
        self.winpaths = False  # paths separator in .csv is windows '\'  # TODO: make this configurable
        self.cache_contentinfo()  # read and parse CSV main lookup table


    def validate_format(self):
        """
        Check if CSV metadata files have the right format.
        """
        super().validate()
        # content metadata headers
        expected = set(CONTENT_INFO_HEADER)
        csv_filename = get_metadata_file_path(channeldir=self.channeldir, filename=self.contentinfo)
        csv_lines = _read_csv_lines(csv_filename)
        dict_reader = csv.DictReader(csv_lines)
        actual = set(list(dict_reader)[0].keys())
        if not actual == expected:
            raise ValueError('Unexpected CSV file header for ' + csv_filename)
        # channel metadata headers
        expected = set(CHANNEL_INFO_HEADER)
        csv_filename = get_metadata_file_path(channeldir=self.channeldir, filename=self.channelinfo)
        csv_lines = _read_csv_lines(csv_filename)
        dict_reader = csv.DictReader(csv_lines)
        actual = set(list(dict_reader)[0].keys())
        if not actual == expected:
            raise ValueError('Unexpected CSV file header for ' + csv_filename)


    def _map_content_row_to_dict(self, row):
        """
        Convert dictionary keys from raw csv format (see CONTENT_INFO_HEADER),
        to ricecooker-like keys, e.g., 'Title *' --> 'title'
        """
        row_cleaned = _clean_dict(row)
        license_id = row_cleaned[CONTENT_LICENSE_ID_KEY]
        if license_id:
            license_dict = dict(
                license_id=row_cleaned[CONTENT_LICENSE_ID_KEY],
                description=row_cleaned.get(CONTENT_LICENSE_DESCRIPTION_KEY, None),
                copyright_holder=row_cleaned.get(CONTENT_LICENSE_COPYRIGHT_HOLDER_KEY, None)
            )
        else:
            license_dict = None
        row_dict = dict(
            chan_path=row_cleaned[CONTENT_PATH_KEY],
            title=row_cleaned[CONTENT_TITLE_KEY],
            source_id=row_cleaned.get(CONTENT_SOURCEID_KEY, None),
            description=row_cleaned.get(CONTENT_DESCRIPTION_KEY, None),
            author=row_cleaned.get(CONTENT_AUTHOR_KEY, None),
            language=row_cleaned.get(CONTENT_LANGUAGE_KEY, None),
            license=license_dict,
            thumbnail_chan_path=row_cleaned.get(CONTENT_THUMBNAIL_KEY, None)
        )
        return row_dict

    def cache_contentinfo(self):
        csv_filename = get_metadata_file_path(channeldir=self.channeldir, filename=self.contentinfo)
        csv_lines = _read_csv_lines(csv_filename)
        dict_reader = csv.DictReader(csv_lines)
        for row in dict_reader:
            row_dict = self._map_content_row_to_dict(row)
            path_tuple = path_to_tuple(row_dict['chan_path'], windows=self.winpaths)
            self.cache[path_tuple] = row_dict


    def _map_channel_row_to_dict(self, row):
        """
        Convert dictionary keys from raw csv format (see CHANNEL_INFO_HEADER),
        to ricecooker-like keys, e.g., ''Source ID' --> 'source_id'
        """
        channel_cleaned = _clean_dict(row)
        channel_dict = dict(
            title=channel_cleaned[CHANNEL_TITLE_KEY],
            description=channel_cleaned[CHANNEL_DESCRIPTION_KEY],
            source_domain=channel_cleaned[CHANNEL_DOMAIN_KEY],
            source_id=channel_cleaned[CHANNEL_SOURCEID_KEY],
            language=channel_cleaned[CHANNEL_LANGUAGE_KEY],
            thumbnail_chan_path=channel_cleaned[CHANNEL_THUMBNAIL_KEY]
        )
        return channel_dict

    def get_channel_info(self):
        csv_filename = get_metadata_file_path(channeldir=self.channeldir, filename=self.channelinfo)
        csv_lines = _read_csv_lines(csv_filename)
        dict_reader = csv.DictReader(csv_lines)
        channel_csvs_list =  list(dict_reader)
        channel_csv = channel_csvs_list[0]
        if len(channel_csvs_list) > 1:
            raise ValueError('Found multiple channel rows in ' + self.channelinfo)
        channel_cleaned = _clean_dict(channel_csv)
        channel_info = self._map_channel_row_to_dict(channel_cleaned)
        return channel_info


    def get(self, path_tuple):
        """
        Returns metadata dict for path in `path_tuple`.
        """
        if path_tuple in self.cache:
            metadata = self.cache[path_tuple]
        else:
            # TODO: make chef robust to missing metadata
            # LOGGER.error(
            print('No metadata found for path_tuple ' + str(path_tuple))
            metadata = dict(
                filepath=os.path.sep.join(path_tuple),
                title=os.path.sep.join(path_tuple)
            )
        return metadata


    def get_thumbnail_paths(self):
        """
        Helper function used to avoid processing thumbnail files during `os.walk`.
        """
        thumbnail_path_tuples = []
        # content thumbnails
        for content_file_path_tuple, row in self.cache.items():
            thumbnail_path = row.get('thumbnail_chan_path', None)
            if thumbnail_path:
                thumbnail_path_tuple = path_to_tuple(thumbnail_path, windows=self.winpaths)
                thumbnail_path_tuples.append(thumbnail_path_tuple)
        # channel thumbnail
        channel_info = self.get_channel_info()
        thumbnail_path = channel_info.get('thumbnail_chan_path', None)
        if thumbnail_path:
            thumbnail_path_tuple = path_to_tuple(thumbnail_path, windows=self.winpaths)
            thumbnail_path_tuples.append(thumbnail_path_tuple)
        return thumbnail_path_tuples


    def validate(self):
        """
        Checks if provided .csv is valid as a whole.
        """
        pass

    def generate(self, channeldir, channelinfo=DEFAULT_CHANNEL_INFO_FILENAME,
                 contentinfo=DEFAULT_CONTENT_INFO_FILENAME):
        """
        Create empty .csv files `channelinfo` and `contentinfo` with the right header.
        Will place files as siblings of directory `channeldir`.
        """
        pass


class ExcelMetadataProvider(MetadataProvider):
    # LIBRARIES COULD USE
    # https://github.com/jmcnamara/XlsxWriter/blob/95334f999d3a5fb58d8da3197260e920be357638/dev/docs/source/alternatives.rst

    def validate(self):
        """
        Checks if provided .xlsx/.xls is valid as a whole.
        """
        pass

