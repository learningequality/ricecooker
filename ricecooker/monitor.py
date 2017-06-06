import datetime
import requests

from . import config
from .managers.progress import Status


class Monitor(object):
    """Sends events/logs to the dashboard server."""

    def __init__(self, token):
        """Sends a post request to create the channel run."""
        self.auth = (config.DASHBOARD_USER, config.DASHBOARD_PASSWORD)
        self.token = token
        self.channel_id = None
        self.run_id = None
        data = {'token': self.token}
        try:
            response = requests.post(
                config.dashboard_channel_runs_url(),
                data=data,
                auth=self.auth)
            config.LOGGER.info('Create channel run: %s' % response.status_code)
            self.run_id = response.json()['id']
        except Exception as e:
            config.LOGGER.error('Error channel run: %s' % e)

    def set_channel_id(self, channel_id):
        """Updates the channel run with the channel id"""
        if not self.run_id:
            return
        self.channel_id = channel_id
        data = {'token': self.token, 'channel_id': self.channel_id}
        try:
            response = requests.put(
                config.dashboard_channel_runs_url() + str(self.run_id) + '/',
                data=data,
                auth=self.auth)
            config.LOGGER.info('Update channel run : %s' % response.status_code)
        except Exception as e:
            config.LOGGER.error('Error channel run: %s' % e)

    def report_event(self, event, progress):
        if not self.run_id:
            return
        now = datetime.datetime.now()
        data = {
            'run_id': self.run_id,
            'event': event,
            'progress': progress,
            'timestamp': now
        }
        try:
            response = requests.post(
                config.dashboard_events_url(),
                data=data,
                auth=self.auth)
            config.LOGGER.info('Create event: %s' % response.status_code)
        except Exception as e:
            config.LOGGER.error('Error event: %s' % e)

    def report_construct_channel_progress(self, progress):
        self.report_event(Status.CONSTRUCT_CHANNEL, progress)
