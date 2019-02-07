import csv
import os
import requests


# CORRECTIONS STRUCTURE v0.1
################################################################################
NODE_ID_KEY = 'Node ID'
SOURCE_ID_OR_CONTENT_ID_KEY = 'Source ID or Content ID'
PATH_KEY = 'Path'
CONTENT_KIND_KEY = 'Content Kind'
OLD_TITLE_KEY = 'Old Title'
NEW_TITLE_KEY = 'New Title'
OLD_DESCR_KEY = 'Old Description'
NEW_DESCR_KEY = 'New Description'
OLD_TAGS_KEY = 'Old Tags'
NEW_TAGS_KEY = 'New Tags'
OLD_COPYRIGHT_HOLDER_KEY = 'Old Copyright Holder'
NEW_COPYRIGHT_HOLDER_KEY = 'New Copyright Holder'
OLD_AUTHOR_KEY = 'Old Author'
NEW_AUTHOR_KEY = 'New Author'

CORRECTIONS_HEADER = [
    NODE_ID_KEY,
    SOURCE_ID_OR_CONTENT_ID_KEY,
    PATH_KEY,
    CONTENT_KIND_KEY,
    OLD_TITLE_KEY,
    NEW_TITLE_KEY,
    OLD_DESCR_KEY,
    NEW_DESCR_KEY,
    OLD_TAGS_KEY,
    NEW_TAGS_KEY,
    OLD_COPYRIGHT_HOLDER_KEY,
    NEW_COPYRIGHT_HOLDER_KEY,
    OLD_AUTHOR_KEY,
    NEW_AUTHOR_KEY,
]

ACTION_KEY = 'Action'
DEV_CORRECTIONS_HEADER = [ACTION_KEY] + CORRECTIONS_HEADER




GSHEETS_BASE = 'https://docs.google.com/spreadsheets/d/'
SHEET_ID = '1QKXvXxLS1dByxrcYHTT2Y2e-eglvDMhkXvSVvFppq20'       # Multaqaddarain K-12
CORRECTIONS_SHEET_GID = '1665468153'                            # Multaqaddarain K-12
SHEET_CSV_URL = GSHEETS_BASE + SHEET_ID + '/export?format=csv&gid=' + CORRECTIONS_SHEET_GID
SHEET_CSV_PATH = 'chefdata/corrections.csv'



# What columns to export metadata to...
TARGET_COLUMNS = {
    'title': [OLD_TITLE_KEY, NEW_TITLE_KEY],
    'description': [OLD_DESCR_KEY, NEW_DESCR_KEY],
    'tags': [OLD_TAGS_KEY, NEW_TAGS_KEY],
    'copyright_holder': [OLD_COPYRIGHT_HOLDER_KEY, NEW_COPYRIGHT_HOLDER_KEY],
    'author': [OLD_AUTHOR_KEY, NEW_AUTHOR_KEY],
}


# default_keys = ['node_id', 'content_id'] # 'studio_id', 'source_id']
default_export = ['title', 'description', 'tags', 'copyright_holder', 'author']

def download_structure_csv():
    response = requests.get(SHEET_CSV_URL)
    csv_data = response.content.decode('utf-8')
    with open(SHEET_CSV_PATH, 'w') as csvfile:
        csvfile.write(csv_data)
        print('Succesfully saved ' + SHEET_CSV_PATH)
    return SHEET_CSV_PATH

def _clean_dict(row):
    """
    Transform empty strings values of dict `row` to None.
    """
    row_cleaned = {}
    for key, val in row.items():
        if val is None or val == '':
            row_cleaned[key] = None
        else:
            row_cleaned[key] = val.strip()
    return row_cleaned




class CorretionsCsvFile(object):

    def __init__(self, csvfilepath='Corrections.csv', exportattributes=default_export):
        self.csvfilepath = csvfilepath
        self.exportattributes = exportattributes


    def download_channel_tree(self, channel_id):
        """
        Downloads a complete studio channel_tree from the Studio API.
        """
        pass

    # Import CSV metadata from external corrections
    ############################################################################

    def load_corrections_from_csv(self):
        csv_path = download_structure_csv()
        struct_list = []
        with open(csv_path, 'r') as csvfile:
            reader = csv.DictReader(csvfile, fieldnames=DEV_CORRECTIONS_HEADER)
            next(reader)  # Skip Headers row
            for row in reader:
                clean_row = _clean_dict(row)
                struct_list.append(clean_row)
        return struct_list


    # Export CSV metadata from external corrections
    ############################################################################

    def export_channel_tree_as_corrections_csv(self, channel_tree):
        """
        Create rows in Corrections.csv from a Studio channel, specified based on
        node_id and content_id.
        """
        file_path = self.csvfilepath
        if not os.path.exists(file_path):
            with open(file_path, 'w') as csv_file:
                csvwriter = csv.DictWriter(csv_file, CORRECTIONS_HEADER)
                csvwriter.writeheader()

        def _write_subtree(path_tuple, subtree, is_root=False):
            print('    '*len(path_tuple) + '  - ', subtree['title'])
            kind = subtree['kind']

            # TOPIC ############################################################
            if kind == 'topic':
                if is_root:
                    self.write_topic_row_from_studio_dict(path_tuple, subtree, is_root=is_root)
                    for child in subtree['children']:
                        _write_subtree(path_tuple, child)
                else:
                    self.write_topic_row_from_studio_dict(path_tuple, subtree)
                    for child in subtree['children']:
                        _write_subtree(path_tuple+[subtree['title']], child)

            # CONTENT NODES ####################################################
            elif kind in ['video', 'audio', 'document', 'html5']:
                self.write_content_row_from_studio_dict(path_tuple, subtree)

            # EXERCISE NODES ###################################################
            # elif kind == 'exercise':
            #     content_id = subtree['content_id']
            #     self.write_exercice_row_from_studio_dict(path_tuple, subtree, content_id)
            #     for question_dict in subtree['assessment_items']:
            #         self.write_question_row_from_question_dict(source_id, question_dict)
            else:
                print('>>>>> skipping node', subtree['title'])

        path_tuple = []
        _write_subtree(path_tuple, channel_tree, is_root=True)


    def write_common_row_attributes_from_studio_dict(self, row, studio_dict):
        # 1. IDENTIFIERS
        row[NODE_ID_KEY] = studio_dict['node_id']
        row[SOURCE_ID_OR_CONTENT_ID_KEY] = studio_dict['content_id']
        # PATH_KEY is set in specific function
        row[CONTENT_KIND_KEY] = studio_dict['kind']

        # 2. METADATA
        for exportattr in self.exportattributes:
            target_cols = TARGET_COLUMNS[exportattr]
            for target_col in target_cols:
                if exportattr == 'tags':
                    tags = studio_dict['tags']
                    tags_semicolon_separated = ';'.join(tags)
                    row[target_col] = tags_semicolon_separated
                else:
                    row[target_col] = studio_dict[exportattr]

    def write_topic_row_from_studio_dict(self, path_tuple, studio_dict, is_root=False):
        if is_root:
            return
        print('Generating Corrections.csv rows for path_tuple ', path_tuple, studio_dict['title'])
        file_path = self.csvfilepath
        with open(file_path, 'a') as csv_file:
            csvwriter = csv.DictWriter(csv_file, CORRECTIONS_HEADER)
            title = studio_dict['title']
            path_with_self = '/'.join(path_tuple+[title])
            topic_row = {}
            self.write_common_row_attributes_from_studio_dict(topic_row, studio_dict)
            # WRITE TOPIC ROW
            topic_row[PATH_KEY] = path_with_self
            csvwriter.writerow(topic_row)

    def write_content_row_from_studio_dict(self, path_tuple, studio_dict):
        file_path = self.csvfilepath
        with open(file_path, 'a') as csv_file:
            csvwriter = csv.DictWriter(csv_file, CORRECTIONS_HEADER)
            row = {}
            self.write_common_row_attributes_from_studio_dict(row, studio_dict)
            title = studio_dict['title']
            row[PATH_KEY] = '/'.join(path_tuple+[title])
            # WRITE ROW
            csvwriter.writerow(row)


def apply_corrections():
    pass



# 
# url = "http://localhost:8080/api/contentnode"
# 
# import requests
# 
# [{"title":"Topic 1","id":"bc8be361e6be4ada8bc793080b6f24d5", "tags":[], "assessment_items":[], "prerequisite":[], "kind":"topic", "parent":"7463b0d9f11a441b8898ef20f74474ce"}]
# 
# 
# payload = "[{\"title\":\"Topic 1\",\"id\":\"bc8be361e6be4ada8bc793080b6f24d5\", \"tags\":[], \"assessment_items\":[], \"prerequisite\":[], \"kind\":\"topic\", \"parent\":\"7463b0d9f11a441b8898ef20f74474ce\"}]\n\n"
# headers = {
#     'authorization': "Token <<<>>>>",
#     'content-type': "application/json",
#     'cache-control': "no-cache",
#     'postman-token': "1d8e9f2b-929c-edf8-a561-a0fb41ac9606"
#     }
# 
# response = requests.request("PATCH", url, data=payload, headers=headers)
# 
# print(response.text)
