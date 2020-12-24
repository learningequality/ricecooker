import shutil
import tempfile


def test_publish_empty(channel, topic, video, audio, html, document, exercise):
    export_dir = tempfile.mkdtemp()
    try:
        channel.export_to_kolibri_db(export_dir='/Volumes/BigDisk/KOLIBRI_DATA')
    finally:
        shutil.rmtree(export_dir)
