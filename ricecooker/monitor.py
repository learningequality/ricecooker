import datetime
import requests

from . import config


class Monitor(object):
    def __init__(self, token):
        self.token = token
        self.source_id = None

    def set_source_id(self, source_id):
        self.source_id = source_id

    def report_progress(self, status):
        now = datetime.datetime.now()
        data = {
            'token': self.token,
            'channel_id': self.source_id if self.source_id else "unknown",
            'event': status,
            'timestamp': now
        }
        response = requests.post(
            config.dashboard_progress_url(),
            data=data,
            auth=(config.DASHBOARD_USER, config.DASHBOARD_PASSWORD))
        if response.status_code != 200:
            config.LOGGER.error('Unable to report status: %s' %
                                (response.status_code))
