import os
import shutil
import tempfile


def test_publish_channel(channel, topic, video, audio, html, document, exercise):
    export_dir = tempfile.mkdtemp()
    try:
        channel.export_to_kolibri_db(export_dir=export_dir)
        assert os.path.exists(os.path.join(export_dir, 'content', 'databases', channel.id + '.sqlite3'))
        assert os.path.exists(os.path.join(export_dir, 'content', 'storage'))
    finally:
        shutil.rmtree(export_dir)
