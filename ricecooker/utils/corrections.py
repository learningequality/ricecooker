import copy
import csv
import json
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




class CorretionsCsvFile(object):

    def __init__(self, csvfilepath='Corrections_template.csv', exportattrs=default_export):
        self.csvfilepath = csvfilepath
        self.exportattrs = exportattrs


    def download_channel_tree(self, channel_id):
        """
        Downloads a complete studio channel_tree from the Studio API.
        """
        pass



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








################################################################################
################################################################################
################################################################################
################################################################################





# CSV CORRECTIONS LOADERS
################################################################################

def save_gsheet_to_local_csv(gsheet_id, gid, csvfilepath='Corrections.csv'):
    GSHEETS_BASE = 'https://docs.google.com/spreadsheets/d/'
    SHEET_CSV_URL = GSHEETS_BASE + gsheet_id + '/export?format=csv&gid=' + gid
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
        reader = csv.DictReader(csvfile, fieldnames=DEV_CORRECTIONS_HEADER)
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
    for row in rows:
        if row[ACTION_KEY] == 'remove':
            deletions.append(row)
        elif row[ACTION_KEY] == '' or row[ACTION_KEY] == None:
            modifications.append(row)
        else:
            print('Uknown Action', row[ACTION_KEY])
    return {
        'modifications': modifications,
        'deletions': deletions,
    }


def get_corrections_by_node_id(csvfilepath, modification_attrs=['title']):
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
        for attr in modification_attrs:
            # print('Found MODIFY', attr, 'in row of CSV for node_id', node_id)
            old_key = TARGET_COLUMNS[attr][0]
            new_key = TARGET_COLUMNS[attr][1]
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
    return corrections_by_node_id



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

def find_nodes_by_content_id(subtree, cid):
    """
    Returns list of nodes in `subtree` that have `content_id=cid`.
    """
    return find_nodes_by_attr(subtree, 'content_id', value)

def find_nodes_by_node_id(subtree, cid):
    """
    Returns list of nodes in `subtree` that have `content_id=cid`.
    """
    return find_nodes_by_attr(subtree, 'content_id', value)


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









# CORRECTIONS API CALLS
################################################################################

def apply_modifications_for_node_id(api, channel_tree, channel_id, node_id, modifications_dict):
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
    content_id = row[SOURCE_ID_OR_CONTENT_ID_KEY]
    results = find_nodes_by_content_id(channel_tree, content_id)
    assert results, 'no match found based on conten_id'
    assert len(results)==1, 'multiple matches found...'
    tree_node = results[0]
    studio_id = tree_node['id']
    # node_before = unresolve_children(results[0])
    # node_before
    changes = correction_row_to_changes(row, attrs=['title'])  # Aldaryn only title correcotins...
    for changetype, attr, before_after in changes:
        val_before = before_after[0]
        val_after = before_after[1]
        print('Changing', attr, 'from', before, 'to', after)

    # api.put_contentnode(node_before)
    # print(content_id, studio_id, 'changes=', changes)


def apply_corrections_by_node_id(api, channel_tree, corrections_by_node_id):
    """
    Given a dict `corrections_by_node_id` of the form,
    {
        'nodes_modified': {
            '<nid1>': { modification dict1 },
            '<nid1>': { modification dict2 },
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
    pass





def apply_corrections(api, channel_id, csvfilepath, studiotreepath=None):
    if studiotreepath is None:
        studiotreepath = 'chefdata/studiotree_Multaqaddarain_K12.json'

    if os.path.exists(studiotreepath):
        channel_tree = json.load(open(studiotreepath, 'r'))
    else:
        root_studio_id = api.get_channel_root_studio_id(channel_id)
        channel_tree = api.get_tree_for_studio_id(root_studio_id)
        json.dump(channel_tree, open(studiotreepath, 'w'), indent=4, ensure_ascii=False, sort_keys=True)

    corrections = get_corrections(csvfilepath)
    for row in corrections['nodes_modified'][0:10]:
        apply_correction_for_node_id(api, channel_tree, row)

    # return corrections['nodes_deleted']



