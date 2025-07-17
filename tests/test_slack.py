import unittest

from mock import patch

from ricecooker.classes.nodes import ChannelNode
from ricecooker.utils.slack import send_slack_notification


class SlackTestCase(unittest.TestCase):
    @patch("ricecooker.utils.slack.requests.post")
    def test_send_slack_notification(self, mock_post):
        """
        Test that send_slack_notification sends a POST request to the correct URL with the correct payload.
        """
        channel = ChannelNode(
            "fake_source_id",
            "fake_source_domain",
            "Test Channel",
        )
        url = "https://studio.learningequality.org/en/channels/test-channel-id/"

        with patch.dict(
            "os.environ", {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/test"}
        ):
            send_slack_notification(channel, url)

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://hooks.slack.com/services/test")
        self.assertIn(
            "A new channel has been uploaded to Kolibri Studio:", kwargs["json"]["text"]
        )
        self.assertIn("Test Channel", kwargs["json"]["text"])
        self.assertIn(url, kwargs["json"]["text"])
