import datetime
import requests

from . import config
from .managers.progress import Status

class Monitor(object):
    def __init__(self, token):
        self.token = token
        self.channel_id = None

    def set_channel_id(self, channel_id):
        self.channel_id = channel_id

    def report_progress(self, status, progress):
        if not self.token or not self.channel_id:
            return
        now = datetime.datetime.now()
        data = {
            'token': self.token,
            'channel_id': self.channel_id,
            'status': status,
            'progress': progress,
            'timestamp': now
        }
        try:
            response = requests.post(
                config.dashboard_progress_url(),
                data=data,
                auth=(config.DASHBOARD_USER, config.DASHBOARD_PASSWORD))
            config.LOGGER.info('Monitor response status: %s' %
                                response.status_code)
        except Exception as e:
            config.LOGGER.error('Error while reporting progress: %s' % e)

    def report_construct_channel_progress(self, progress):
        self.report_progress(Status.CONSTRUCT_CHANNEL, progress)
