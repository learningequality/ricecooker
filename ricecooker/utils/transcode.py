import os
import subprocess
def transcode_video(source_filename, target_filename=None):
    new_fn = target_filename or source_filename + "_transcoded.mp4"
    # note: -n skips if file already exists, use -y to overwrite
    command = ["ffmpeg", "-i", source_filename, "-vcodec", "h264", "-acodec", "aac", "-strict", "2",
               "-crf", "24", "-y", "-hide_banner", "-loglevel", "warning", "-vf",
               "scale=trunc(iw/2)*2:trunc(ih/2)*2", new_fn]

    if not os.path.exists(new_fn):
        subprocess.check_call(command)
        print("Successfully transcoded")
    else:
        print("... used cached file")
    return new_fn

def transcode_audio(source_filename, target_filename=None):
    "This should also be useful for removing video from videos, leaving just an MP3"
    new_fn = target_filename or source_filename + "_transcoded.mp3"
    # note: -n skips if file already exists, use -y to overwrite
    command = ["ffmpeg", "-i", source_filename, "-acodec", "mp3", "-ac", "2", "-ab", "192k",
               "-y", "-hide_banner", "-loglevel", "warning", new_fn]

    if not os.path.exists(new_fn):
        subprocess.check_call(command)
        print("Successfully transcoded")
    else:
        print("... used cached file")
    return new_fn
