import requests
import requests_cache
requests_cache.install_cache()

from ricecooker.config import LOGGER


STUDIO_URL = 'https://studio.learningequality.org'

NODES_ENDPOINT =         STUDIO_URL + '/api/get_nodes_by_ids_complete/'
LICENSES_LIST_ENDPOINT = STUDIO_URL + '/api/license'
# TODO https://studio.learningequality.org/api/get_node_path/ca8f380/18932/41b2549
# TODO http://develop.studio.learningequality.org/api/channel/094097ce6f395ec0b50aabd04943c6b3


class StudioApi(object):
    def __init__(self, token):
        self.token = token
        self.licenses_by_id = self.get_licenses()
        
    def get_licenses(self):
        headers = {"Authorization": "Token {0}".format(self.token)}
        response = requests.get(LICENSES_LIST_ENDPOINT, headers=headers)
        licenses_list = response.json()
        licenses_dict = {}
        for license in licenses_list:
            licenses_dict[license['id']] = license
        return licenses_dict

    def get_nodes_by_ids_complete(self, studio_id):
        headers = {"Authorization": "Token {0}".format(self.token)}
        url = NODES_ENDPOINT + studio_id
        LOGGER.info('  GET ' + url)
        response = requests.get(url, headers=headers)
        studio_node = response.json()[0]
        return studio_node

    def get_tree_for_studio_id(self, studio_id):
        """
        Returns the full json tree (recusive calls to /api/get_nodes_by_ids_complete)
        """
        channel_parent = {'children': []}  # this is like _ with children
        def _build_subtree(parent, studio_id):
            subtree = self.get_nodes_by_ids_complete(studio_id)
            if 'children' in subtree:
                children_refs = subtree['children']
                subtree['children'] = []
                for child_studio_id in children_refs:
                    _build_subtree(subtree, child_studio_id)
            parent['children'].append(subtree)
        _build_subtree(channel_parent, studio_id)
        channel = channel_parent['children'][0]
        return channel

