from ricecooker.classes import nodes


def test_publish_empty(channel, topic, video, audio, html, document, exercise):
    channel.export_to_kolibri_db()
