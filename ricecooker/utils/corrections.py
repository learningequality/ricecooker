#!/usr/bin/env python
import argparse
import copy
import csv
from datetime import datetime
import dictdiffer
import json
import os
import requests

from ricecooker.config import LOGGER


# CONFIG CONSTANTS for data directories
################################################################################
STUDIO_CREDENTIALS='credentials/studio.json'
CHEFDATA_DIR = 'chefdata'
STUDIO_TREES_DIR = os.path.join(CHEFDATA_DIR, 'studiotrees')
if not os.path.exists(STUDIO_TREES_DIR):
    os.makedirs(STUDIO_TREES_DIR)
CORRECTIONS_DIR = os.path.join(CHEFDATA_DIR, 'corrections')
if not os.path.exists(CORRECTIONS_DIR):
    os.makedirs(CORRECTIONS_DIR)



# CORRECTIONS STRUCTURE v0.2
################################################################################

ACTION_KEY = 'Action'
NODE_ID_KEY = 'Node ID'
CONTENT_ID_KEY = 'Content ID'
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
    ACTION_KEY,
    NODE_ID_KEY,
    CONTENT_ID_KEY,
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







# Studio Tree Local Cache queries
################################################################################

def get_channel_tree(api, channel_id, suffix='', update=True):
    """
    Downloads the entire main tree of a Studio channel to a local json file.
    """
    filename = os.path.join(STUDIO_TREES_DIR, channel_id + suffix + '.json')
    if os.path.exists(filename) and not update:
        print('  Loading cached tree for channel_id=', channel_id, 'from', filename)
        channel_tree = json.load(open(filename, 'r'))
        return channel_tree
    else:
        print('  Downloading tree for channel_id=', channel_id, ' and saving to', filename)
        root_studio_id = api.get_channel_root_studio_id(channel_id)
        # next step takes long since recursively making O(n) API calls!
        channel_tree = api.get_tree_for_studio_id(root_studio_id)
        json.dump(channel_tree, open(filename, 'w'), indent=4, ensure_ascii=False, sort_keys=True)
        return channel_tree



def print_channel_tree(channel_tree):
    """
    Print tree structure.
    """
    def print_tree(subtree, indent=''):
        kind = subtree.get("kind", 'topic')  # topic default to handle channel root
        if kind == "exercise":
            print(indent, subtree['title'],
                          'kind=', subtree['kind'],
                          len(subtree['assessment_items']), 'questions',
                          len(subtree['files']), 'files')
        else:
            print(indent, subtree['title'],
                          'kind=', subtree['kind'],
                          len(subtree['files']), 'files')
        for child in subtree['children']:
            print_tree(child, indent=indent+'    ')
    print_tree(channel_tree)



# CORECTIONS EXPORT
################################################################################

class CorretionsCsvFileExporter(object):

    def __init__(self, csvfilepath='corrections-export.csv', exportattrs=default_export):
        self.csvfilepath = csvfilepath
        self.exportattrs = exportattrs

    def download_channel_tree(self, api, channel_id):
        """
        Downloads a complete studio channel_tree from the Studio API.
        """
        channel_tree = get_channel_tree(api, channel_id, suffix='-export')
        return channel_tree


    # Export CSV metadata from external corrections
    ############################################################################

    def export_channel_tree_as_corrections_csv(self, channel_tree):
        """
        Create rows in corrections.csv from a Studio channel, specified based on
        node_id and content_id.
        """
        file_path = self.csvfilepath
        if os.path.exists(file_path):
            print('Overwriting previous export', file_path)
        with open(file_path, 'w') as csv_file:
            csvwriter = csv.DictWriter(csv_file, CORRECTIONS_HEADER)
            csvwriter.writeheader()

        def _write_subtree(path_tuple, subtree, is_root=False):
            # print('    '*len(path_tuple) + '  - ', subtree['title'])
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
        row[CONTENT_ID_KEY] = studio_dict['content_id']
        # PATH_KEY is set in specific function
        row[CONTENT_KIND_KEY] = studio_dict['kind']

        # 2. METADATA
        for exportattr in self.exportattrs:
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
        print('Generating corrections-export.csv rows for path_tuple ', path_tuple, studio_dict['title'])
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








# CSV CORRECTIONS LOADERS
################################################################################

def save_gsheet_to_local_csv(gsheet_id, gid, csvfilepath='corrections-import.csv'):
    GSHEETS_BASE = 'https://docs.google.com/spreadsheets/d/'
    SHEET_CSV_URL = GSHEETS_BASE + gsheet_id + '/export?format=csv&gid=' + gid
    print(SHEET_CSV_URL)
    response = requests.get(SHEET_CSV_URL)
    csv_data = response.content.decode('utf-8')
    with open(csvfilepath, 'w') as csvfile:
        csvfile.write(csv_data)
        print('Succesfully saved ' + csvfilepath)
    return csvfilepath


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


def load_corrections_from_csv(csvfilepath):
    csv_path = csvfilepath     # download_structure_csv()
    struct_list = []
    with open(csv_path, 'r') as csvfile:
        reader = csv.DictReader(csvfile, fieldnames=CORRECTIONS_HEADER)
        next(reader)  # Skip Headers row
        for row in reader:
            clean_row = _clean_dict(row)
            struct_list.append(clean_row)
    return struct_list


def get_csv_corrections(csvfilepath):
    """
    Return a GROUP BY `corrkind` dictionary of rows from the CSV file.
    """
    modifications = []
    deletions = []
    rows = load_corrections_from_csv(csvfilepath)
    for i, row in enumerate(rows):
        if row[ACTION_KEY] == '' or row[ACTION_KEY] == None:
            print('Skipping no-action row', i+1)
        elif row[ACTION_KEY] == 'modify':
            modifications.append(row)
        elif row[ACTION_KEY] == 'delete':
            deletions.append(row)
        else:
            print('Uknown Action', row[ACTION_KEY])
    return {
        'modifications': modifications,
        'deletions': deletions,
    }


def get_corrections_by_node_id(csvfilepath, modifyattrs):
    """
    Convert CSV to internal representaiton of corrections as dicts by node_id.
    """
    corrections_by_node_id = {
        'nodes_modified': {},
        'nodes_added': {},
        'nodes_deleted': {},
        'nodes_moved': {},
    }
    csv_corrections = get_csv_corrections(csvfilepath)  # CSV rows GROUP BY corrkind
    #
    # Modifications
    for row in csv_corrections['modifications']:
        node_id = row[NODE_ID_KEY]
        # print('Found MODIFY row of CSV  for node_id', node_id)
        #
        # find all modified attributes
        attributes = {}
        for attr in modifyattrs:
            # print('Found MODIFY', attr, 'in row of CSV for node_id', node_id)
            old_key = TARGET_COLUMNS[attr][0]
            new_key = TARGET_COLUMNS[attr][1]
            if row[new_key] == row[old_key]:   # skip if the same
                continue
            else:
                attributes[attr] = {
                    'changed': True,
                    'value': row[new_key],
                    'old_value': row[old_key],
                }
        # prepare modifications_dict
        modifications_dict = {
            'attributes': attributes,
        }
        # add to to corrections_by_node_id
        corrections_by_node_id['nodes_modified'][node_id] = modifications_dict
    #
    # Deletions
    for row in csv_corrections['deletions']:
        node_id = row[NODE_ID_KEY]
        # print('Found DELETE row in CSV for node_id', node_id)
        corrections_by_node_id['nodes_deleted'][node_id] = {'node_id':node_id}
    #
    # TODO: Additions
    # TODO: Moves
    datetimesuffix = datetime.now().strftime("%Y-%m-%d__%H%M")
    correctionspath = os.path.join(CORRECTIONS_DIR, 'imported-' + datetimesuffix + '.json')
    json.dump(corrections_by_node_id, open(correctionspath, 'w'), indent=4, ensure_ascii=False, sort_keys=True)
    #
    return correctionspath



# Tree querying API
################################################################################


def find_nodes_by_attr(subtree, attr, value):
    """
    Returns list of nodes in `subtree` that have attribute `attr` equal to `value`.
    """
    results = []
    if subtree[attr] == value:
        results.append(subtree)
    if 'children' in subtree:
        for child in subtree['children']:
            child_restuls = find_nodes_by_attr(child, attr, value)
            results.extend(child_restuls)
    return results

def find_nodes_by_content_id(subtree, content_id):
    return find_nodes_by_attr(subtree, 'content_id', content_id)

def find_nodes_by_node_id(subtree, node_id):
    return find_nodes_by_attr(subtree, 'node_id', node_id)

def find_nodes_by_original_source_node_id(subtree, original_source_node_id):
    return find_nodes_by_attr(subtree, 'original_source_node_id', original_source_node_id)

def unresolve_children(node):
    """
    Return copy of node with children = list of studio_id references instead of full data.
    """
    node =  copy.deepcopy(node)
    if 'children' in node:
        new_children = []
        for child in node['children']:
            new_children.append(child['id'])
        node['children'] = new_children
    return node






# SPECIAL REMAP NEEDED FOR ALDARYN CORRECTIONS
################################################################################

def remap_original_source_node_id_to_node_id(channel_tree, corrections_by_original_source_node_id):
    ALL_COORECTIONS_KINDS = ['nodes_modified', 'nodes_added', 'nodes_deleted', 'nodes_moved']
    corrections_by_node_id = {}
    for correction_kind in ALL_COORECTIONS_KINDS:
        if correction_kind in corrections_by_original_source_node_id:
            corrections_by_node_id[correction_kind] = {}
            corrections_dict = corrections_by_original_source_node_id[correction_kind]
            for original_source_node_id, correction in corrections_dict.items():
                results = find_nodes_by_original_source_node_id(channel_tree, original_source_node_id)
                assert results, 'no match found based on original_source_node_id search'
                assert len(results)==1, 'multiple matches found...'
                tree_node = results[0]
                node_id = tree_node['node_id'] 
                corrections_by_node_id[correction_kind][node_id] = correction
    return corrections_by_node_id






# CORRECTIONS API CALLS
################################################################################

def apply_modifications_for_node_id(api, channel_tree, node_id, modifications_dict):
    """
    Given a modification dict of the form,
        modifications_dict = {
            'attributes': {
                'title': {
                    'changed': (bool),
                    'value': (str),
                    'old_value': (str),
                },
                'files': ([{
                    'filename': (str),
                    'file_size': (int),
                    'preset': (str)
                }]),
                'assessment_items': ([AssessmentItem]),
                'tags': ([Tag]),
                ...
            }
        }
    this function will make obtain GET the current node data from Studio API,
    apply the modifications to the local json data, then PUT the data on Studio.
    """
    # print('MODIFYING node_id=', node_id)
    results = find_nodes_by_node_id(channel_tree, node_id)
    assert results, 'no match found based on node_id search'
    assert len(results)==1, 'multiple matches found...'
    tree_node = results[0]
    studio_id = tree_node['id']
    # node_before = unresolve_children(tree_node)
    node_before = api.get_contentnode(studio_id)
    # print('node_before', node_before)

    # PREPARE data for PUT request  (starting form copy of old)
    data = {}
    ATTRS_TO_COPY = ['kind', 'id', 'tags', 'prerequisite', 'parent']
    for attr in ATTRS_TO_COPY:
        data[attr] = node_before[attr]
    #
    # ADD new_values modified 
    modifications = modifications_dict['attributes']
    for attr, values_diff in modifications.items():
        if values_diff['changed']:
            current_value = node_before[attr]
            expected_old_value = values_diff['old_value']
            new_value = values_diff['value']
            if expected_old_value == new_value:   # skip if the same
                continue
            if current_value != expected_old_value:
                print('WARNING expected old value', expected_old_value, 'for', attr, 'but current node value is', current_value)
            # print('Changing current_value', current_value, 'for', attr, 'to new value', new_value)
            data[attr] = new_value
        else:
            print('Skipping attribute', attr, 'because key changed==False')

    # PUT
    print('PUT studio_id=', studio_id, 'node_id=', node_id)
    response_data = api.put_contentnode(data)

    # Check what changed
    node_after = api.get_contentnode(studio_id)
    diffs = list(dictdiffer.diff(node_before, node_after))
    print('  diff=', diffs)
    return response_data


def apply_deletion_for_node_id(api, channel_tree, channel_id, node_id, deletion_dict):
    results = find_nodes_by_node_id(channel_tree, node_id)
    assert results, 'no match found based on node_id search'
    assert len(results)==1, 'multiple matches found...'
    tree_node = results[0]
    studio_id = tree_node['id']
    # node_before = unresolve_children(tree_node)
    node_before = api.get_contentnode(studio_id)
    
    # PREPARE data for DLETE request
    data = {}
    data['id'] = node_before['id']

    # DELETE
    print('DELETE studio_id=', studio_id, 'node_id=', node_id)
    response_data = api.delete_contentnode(data, channel_id)

    # Check what changed
    node_after = api.get_contentnode(studio_id)
    diffs = list(dictdiffer.diff(node_before, node_after))
    print('  diff=', diffs)

    return response_data


def apply_corrections_by_node_id(api, channel_tree, channel_id, corrections_by_node_id):
    """
    Given a dict `corrections_by_node_id` of the form,
    {
        'nodes_modified': {
            '<node_id (str)>': { modification dict1 },
            '<node_id (str)>': { modification dict2 },
        }
        'nodes_added': {
            '<node_id (str)>': { 'new_parent': (str),  'attributes': {...}},
        },
        'nodes_deleted': {
            '<node_id (str)>': {'old_parent': (str), 'attributes': {...}},
        },
        'nodes_moved': {
            '<node_id (str)>': {'old_parent': (str), 'new_parent': (str), 'attributes': {...}},
        },
    }
    this function will make the appropriate Studio API calls to apply the patch.
    """
    LOGGER.debug('Applying corrections...')
    #
    # Modifications
    for node_id, modifications_dict in corrections_by_node_id['nodes_modified'].items():
        apply_modifications_for_node_id(api, channel_tree, node_id, modifications_dict)
    #
    # Deletions
    for node_id, deletion_dict in corrections_by_node_id['nodes_deleted'].items():
        apply_deletion_for_node_id(api, channel_tree, channel_id, node_id, deletion_dict)
    # TODO: Additions
    # TODO: Moves







from ricecooker.utils.libstudio import StudioApi

def get_studio_api(studio_creds=None):
    if studio_creds is None:
        if not os.path.exists(STUDIO_CREDENTIALS):
            print('ERROR: Studio credentials file', STUDIO_CREDENTIALS, 'not found')
            print("""Please create the file and put the following informaiton in it:
            {
              "token": "<your studio token>",
              "username": "<your studio username>",
              "password": "<your studio password>",
            }
            """)
            raise ValueError('Missing credentials')
        studio_creds = json.load(open(STUDIO_CREDENTIALS))
    #
    # Studio API client (note currently needs both session auth and token as well)
    api = StudioApi(
            token=studio_creds['token'],
            username=studio_creds['username'],
            password=studio_creds['password'],
            studio_url=studio_creds.get('studio_url', 'https://studio.learningequality.org')
    )
    return api


def export_corrections_csv(args):
    api = get_studio_api()
    channel_tree = get_channel_tree(api, args.channel_id, suffix='-export')
    print_channel_tree(channel_tree)
    csvexporter = CorretionsCsvFileExporter()
    csvexporter.export_channel_tree_as_corrections_csv(channel_tree)


def apply_corrections(args):
    # 1. LOAD Studio channel_tree (needed for lookups by node_id, content_id, etc.)
    api = get_studio_api()
    channel_tree = get_channel_tree(api, args.channel_id, suffix='-before')
    #
    # 2. IMPORT the corrections from the Spreadsheet
    csvfilepath = 'corrections-import.csv'
    save_gsheet_to_local_csv(args.gsheet_id, args.gid, csvfilepath=csvfilepath)
    #
    # 3. TRANSFORM corrections-import.csv to Studio detailed diff format
    modifyattrs = args.modifyattrs.split(',')   # using only selected attributes
    correctionspath = get_corrections_by_node_id(csvfilepath, modifyattrs)
    #
    # Special case: when export was performed on source channel, but we want to
    # apply the corrections to a cloned channel. In that cases, the `Node ID`
    # column in the CSV corresponds to the `original_source_node_id` attribute
    # of the nodes in the derivative channel so we must do a remapping:
    if args.primarykey == 'original_source_node_id':
        corrections_by_original_source_node_id = json.load(open(correctionspath))
        corrections_by_node_id = remap_original_source_node_id_to_node_id(channel_tree, corrections_by_original_source_node_id)
        json.dump(corrections_by_node_id, open(correctionspath, 'w'), indent=4, ensure_ascii=False, sort_keys=True)
        print('Finished original_source_node_id-->node_id lookup and remapping.')
    elif args.primarykey in ['content_id', 'studio_id']:
        raise NotImplementedError('Using content_id and studio_id not ready yet.')
    #
    # Early exit if running the `importonly` command
    if args.command == 'importonly':
        print('Corrections json file imported. See', correctionspath)
        return correctionspath
    #
    # 4. LOAD corrections.json (four lists of corrections organized by nod_id)
    corrections_by_node_id = json.load(open(correctionspath))
    #
    # 5. Apply the corrections
    apply_corrections_by_node_id(api, channel_tree, args.channel_id, corrections_by_node_id)
    #
    # 6. SAVE the Studio tree after corrections for review of what was changed
    channel_tree = get_channel_tree(api, args.channel_id, suffix='-after')



def correctionsmain():
    """
    Command line interface for applying bulk-edit corrections:
    """
    parser = argparse.ArgumentParser(description='Bulk channel edits via CSV/sheets.')
    parser.add_argument('command', help='One of export|importonly|apply',
                        choices=['export', 'importonly', 'apply'])
    parser.add_argument('channel_id', help='The studio Channel ID to edit')
    parser.add_argument('--primarykey', help='Which idendifier to use when looking up nodes',
                        choices=['node_id', 'content_id', 'original_source_node_id', 'studio_id'],
                        default='node_id')
    parser.add_argument('--gsheet_id', help='Google spreadsheets sheet ID (public)')
    parser.add_argument('--gid', help='The gid argument to indicate which sheet', default='0')
    parser.add_argument('--modifyattrs', help='Which attributes to modify',
                        default='title,description,author,copyright_holder')
    args = parser.parse_args()
    # print("in corrections.main with cliargs", args)
    if args.command == 'export':
        export_corrections_csv(args)
    elif args.command in ['importonly', 'apply']:
        apply_corrections(args)
    else:
        raise ValueError('Unrecognized command')


if __name__ == '__main__':
    correctionsmain()

