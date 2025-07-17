import os

import requests

from ricecooker.config import LOGGER


def send_slack_notification(channel, url):
    """
    Send a notification to a Slack channel.
    :param channel: The channel to send the notification to.
    :param url: The URL of the channel.
    """
    if not channel or not url:
        return

    # Get the webhook URL from the environment variable
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        return

    # Create the message payload
    payload = {
        "text": f"A new channel has been uploaded to Kolibri Studio: *{channel.title}* ({channel.get_node_id().hex}). You can view it here: {url}"
    }

    # Send the request to the webhook URL
    try:
        r = requests.post(webhook_url, json=payload)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        LOGGER.error(f"Failed to send Slack notification: {e}")
