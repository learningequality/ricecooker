import json
import logging.handlers
import os
import requests
import subprocess
import websocket

from . import config
from . import __version__
from threading import Thread, Event
from queue import Empty, Queue

AUTH = None


class SushiBarClient(object):
    """Sends events/logs to the dashboard server."""

    def __init__(self, channel, username, token):
        self.run_id = None
        if not channel:
            return
        if self.__create_channel_if_needed(channel, username, token):
            self.run_id = self.__create_channel_run(channel, username, token)
        self.log_handler = self.__config_logger()

    def __create_channel_if_needed(self, channel, username, token):
        if not self.__channel_exists(channel):
            return self.__create_channel(channel, username, token)
        return True

    def __channel_exists(self, channel):
        url = config.sushi_bar_channels_url() + channel.get_node_id().hex + '/'
        try:
            response = requests.get(url, auth=AUTH)
            response.raise_for_status()
            return True
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
                config.sushi_bar_channels_url(),
                data=data,
                auth=AUTH)
            response.raise_for_status()
            return True
        except Exception as e:
            config.LOGGER.error('Error channel: %s' % e)
        return False

    def __create_channel_run(self, channel, username, token):
        """Sends a post request to create the channel run."""
        data = {
            'channel_id': channel.get_node_id().hex,
            'chef_name': self.__get_chef_name(),
            'ricecooker_version': __version__,
            'started_by_user': username,
            'started_by_user_token': token,
            'content_server': config.DOMAIN,
        }
        try:
            response = requests.post(
                config.sushi_bar_channel_runs_url(),
                data=data,
                auth=AUTH)
            response.raise_for_status()
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

    def __get_chef_name(self):
        chef_name = None
        try:
            origin = subprocess.check_output(['git', 'config', '--get',
                                              'remote.origin.url'])
            origin = origin.decode('UTF-8').strip()
            head = subprocess.check_output(['git', 'rev-parse', 'HEAD'])
            head = head.decode('UTF-8').strip()
            chef_name = origin + ':' + head
        except Exception as e:
            config.LOGGER.error('Chef name: %s' % e)
        return chef_name

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
                config.sushi_bar_stages_url(self.run_id),
                data=data,
                auth=AUTH)
            response.raise_for_status()
        except Exception as e:
            config.LOGGER.error('Error stage: %s' % e)

    def report_progress(self, stage, progress):
        if not self.run_id:
            return
        data = {
            'run_id': self.run_id,
            'stage': stage,
            'progress': progress,
        }
        try:
            response = requests.post(
                config.sushi_bar_progress_url(self.run_id),
                data=data,
                auth=AUTH)
            response.raise_for_status()
        except Exception as e:
            config.LOGGER.error('Error stage: %s' % e)

    def report_statistics(self, files):
        if not self.run_id:
            return
        resource_counts = {}
        resource_sizes = {}
        total_size = 0
        for f in files:
            path = config.get_storage_path(f)
            size = os.path.getsize(path)
            _, ext = os.path.splitext(f)
            resource_counts[ext] = resource_counts.get(ext, 0) + 1
            resource_sizes[ext] = resource_sizes.get(ext, 0) + size
            total_size += size
        resource_counts['total'] = len(files)
        resource_sizes['total'] = total_size
        data = {
            'run_id': self.run_id,
            'resource_counts': json.dumps(resource_counts),
            'resource_sizes': json.dumps(resource_sizes),
        }
        try:
            response = requests.patch(
                config.sushi_bar_channel_runs_detail_url(self.run_id),
                data=data,
                auth=AUTH)
            response.raise_for_status()
        except Exception as e:
            config.LOGGER.error('Error statistics: %s' % e)


class LoggingHandler(logging.Handler):
    """Sends logs to the dashboard server."""

    def __init__(self, run_id, queue):
        logging.Handler.__init__(self)
        self.run_id = run_id
        self.queue = queue

    def __del__(self):
        self.ws.close()

    def emit(self, record):
        try:
            log_data = record.__dict__
            log_data['run_id'] = self.run_id
            self.queue.put(json.dumps(log_data))
        except Exception as e:
            print('Logging error: %s, %s' % (self.ws.status, e))

class LoggingProxy(Thread):
    """
    Sends logs to the Sushi Bar server.
    """

    def __init__(self, run_id, queue):
        self.ws = websocket.create_connection(
            config.sushi_bar_logs_url(run_id))
        self.run_id = run_id
        self.queue = queue

    def run(self):
        while True:
            item = self.queue.get()
            self.ws.send(item)
            self.queue.task_done()

    def _stop(self):
