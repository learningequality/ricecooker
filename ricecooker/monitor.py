import datetime
import requests

from . import config


class Monitor(object):
    def __init__(self, token):
        self.token = token
        self.channel_id = None

    def set_channel_id(self, channel_id):
        self.channel_id = channel_id

    def report_progress(self, status):
        if not self.token or not self.channel_id:
            return
        now = datetime.datetime.now()
        data = {
            'token': self.token,
            'channel_id': self.channel_id,
            'event': status,
            'timestamp': now
        }
        response = requests.post(
            config.dashboard_progress_url(),
            data=data,
            auth=(config.DASHBOARD_USER, config.DASHBOARD_PASSWORD))
        if response.status_code != 200:
            config.LOGGER.error('Unable to report status: %s' %
                                response.status_code)
