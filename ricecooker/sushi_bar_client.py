import datetime
import requests
import logging.handlers

from . import config
from . import __version__

AUTH = (config.DASHBOARD_USER, config.DASHBOARD_PASSWORD)


class SushiBarClient(object):
    """Sends events/logs to the dashboard server."""

    def __init__(self, channel, username, token):
        self.run_id = None
        if not channel:
            return
        if self.__create_channel_if_needed(channel, username, token):
            self.run_id = self.__create_channel_run(channel, token)
        self.log_handler = self.__config_logger()

    def __create_channel_if_needed(self, channel, username, token):
        if not self.__channel_exists(channel):
            return self.__create_channel(channel, username, token)
        return True

    def __channel_exists(self, channel):
        url = config.dashboard_channels_url() + channel.get_node_id().hex + '/'
        try:
            response = requests.get(url, auth=AUTH)
            return True if response.status_code == 200 else False
        except Exception as e:
            config.LOGGER.error('Error channel exists: %s' % e)
        return False

    def __create_channel(self, channel, username, token):
        data = {
            'channel_id': channel.get_node_id().hex,
            'name': channel.title,
            'description': channel.description,
            'source_domain': channel.source_domain,
            'source_id': channel.source_id,
            'user_registered_by': username,
            'user_token': token,
            'content_server': config.DOMAIN
        }
        try:
            response = requests.post(
                config.dashboard_channels_url(),
                data=data,
                auth=AUTH)
            return True
        except Exception as e:
            config.LOGGER.error('Error channel: %s' % e)
        return False

    def __create_channel_run(self, channel, token):
        """Sends a post request to create the channel run."""
        data = {
            'channel_id': channel.get_node_id().hex,
            'chef_name': 'x',
            'token': token
        }
        try:
            response = requests.post(
                config.dashboard_channel_runs_url(),
                data=data,
                auth=AUTH)
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

    def report_stage(self, stage, duration):
        if not self.run_id:
            return
        data = {
            'run_id': self.run_id,
            'stage': stage,
            'duration': duration,
        }
        try:
            response = requests.post(
                config.dashboard_stages_url(self.run_id),
                data=data,
                auth=AUTH)
        except Exception as e:
            config.LOGGER.error('Error stage: %s' % e)


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
                config.dashboard_logs_url(self.run_id),
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
