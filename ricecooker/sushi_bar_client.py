import datetime
import requests
import logging.handlers

from . import config
from .managers.progress import Status

AUTH = (config.DASHBOARD_USER, config.DASHBOARD_PASSWORD)


class SushiBarClient(object):
    """Sends events/logs to the dashboard server."""

    def __init__(self, token):
        self.token = token
        self.run_id = None
        self.log_handler = None

    def __create_channel(self, channel_id):
        data = {
            'channel_id': channel_id,
        }
        try:
            response = requests.post(
                config.dashboard_channels_url(),
                data=data,
                auth=AUTH)
            config.LOGGER.info('Create channel: %s' % response.status_code)
            return response.json()['id']
        except Exception as e:
            config.LOGGER.error('Error channel: %s' % e)
        return None

    def __create_run(self, channel_pk):
        """Sends a post request to create the channel run."""
        data = {'channel': channel_pk, 'chef_name': 'x', 'token': self.token}
        try:
            response = requests.post(
                config.dashboard_channel_runs_url(),
                data=data,
                auth=AUTH)
            config.LOGGER.info('Create channel run: %s' % response.status_code)
            return response.json()['run_id']
        except Exception as e:
            config.LOGGER.error('Error channel run: %s' % e)
        return None

    def __config_logger(self):
        if not self.run_id:
            return None
        log_handler = LoggingHandler(self.run_id)
        config.LOGGER.addHandler(log_handler)
        return log_handler

    def set_channel_id(self, channel_id):
        """Updates the channel run with the channel id"""
        channel_pk = self.__create_channel(channel_id)
        self.run_id = self.__create_run(channel_pk)
        self.log_handler = self.__config_logger()

    def report_stage(self, stage, duration):
        if not self.run_id:
            return
        now = datetime.datetime.now()
        data = {
            'run_id': self.run_id,
            'stage': stage,
            'duration': duration,
        }
        try:
            response = requests.post(
                config.dashboard_events_url(),
                data=data,
                auth=AUTH)
            config.LOGGER.info('Create event: %s' % response.status_code)
        except Exception as e:
            config.LOGGER.error('Error event: %s' % e)


class LoggingHandler(logging.Handler):
    """Sends logs to the dashboard server."""

    def __init__(self, run_id):
        logging.Handler.__init__(self)
        self.run_id = run_id
        self.setFormatter(LoggingFormatter(run_id))

    def emit(self, record):
        data = self.format(record)
        try:
            requests.post(
                config.dashboard_logs_url(),
                data=data,
                auth=AUTH)
        except Exception as e:
            print('Logging error: %s' % e)


class LoggingFormatter(logging.Formatter):
    def __init__(self, run_id):
        self.run_id = run_id

    def format(self, record):
        data = {
            'run_id': self.run_id,
            'created': record.created,
            'message': record.msg
        }
        return data
