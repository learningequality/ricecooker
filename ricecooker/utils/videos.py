import logging
import os
import re
import subprocess

from le_utils.constants import format_presets

from .images import ThumbnailGenerationError

LOGGER = logging.getLogger("VideoResource")
LOGGER.setLevel(logging.DEBUG)


def guess_video_preset_by_resolution(videopath):
    """
    Run `ffprobe` to find resolution classify as high resolution (video height >= 720),
    or low resolution (video height < 720).
    Return appropriate video format preset: VIDEO_HIGH_RES or VIDEO_LOW_RES.
    """
    try:
        LOGGER.debug("Entering 'guess_video_preset_by_resolution' method")
        result = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_entries",
                "stream=width,height",
                "-of",
                "default=noprint_wrappers=1",
                str(videopath),
            ]
        )
        LOGGER.debug("ffprobe stream result = {}".format(result))
        pattern = re.compile("width=([0-9]*)[^height]+height=([0-9]*)")
        match = pattern.search(str(result))
        if match is None:
            return format_presets.VIDEO_LOW_RES
        _, height = int(match.group(1)), int(match.group(2))
        if height >= 720:
            LOGGER.info("Video preset from {} = high resolution".format(videopath))
            return format_presets.VIDEO_HIGH_RES
        else:
            LOGGER.info("Video preset from {} = low resolution".format(videopath))
            return format_presets.VIDEO_LOW_RES
    except Exception as e:
        LOGGER.warning(e)
        return format_presets.VIDEO_LOW_RES


def extract_thumbnail_from_video(fpath_in, fpath_out, overwrite=False):
    """
    Extract a thumbnail from the video given through the `fobj_in` file object.
    The thumbnail image will be written in the file object given in `fobj_out`.
    """
    try:
        result = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                "-loglevel",
                "panic",
                str(fpath_in),
            ]
        )

        midpoint = float(re.search("\\d+\\.\\d+", str(result)).group()) / 2
        # scale parameters are from https://trac.ffmpeg.org/wiki/Scaling
        scale = "scale=400:225:force_original_aspect_ratio=decrease,pad=400:225:(ow-iw)/2:(oh-ih)/2"
        command = [
            "ffmpeg",
            "-y" if overwrite else "-n",
            "-i",
            str(fpath_in),
            "-vf",
            scale,
            "-vcodec",
            "png",
            "-nostats",
            "-ss",
            str(midpoint),
            "-vframes",
            "1",
            "-q:v",
            "2",
            "-loglevel",
            "panic",
            str(fpath_out),
        ]
        subprocess.check_output(command, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        raise ThumbnailGenerationError("{}: {}".format(e, e.output))


def extract_duration_of_media(fpath_in):
    try:
        if os.path.exists(fpath_in):
            result = subprocess.check_output(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    "-loglevel",
                    "panic",
                    str(fpath_in),
                ]
            )
            return result.decode("utf-8")
    except Exception as ex:
        LOGGER.warning(ex)
        raise ex


class VideoCompressionError(Exception):
    """
    Custom error returned when `ffmpeg` compression exits with a non-zero status.
    """


def compress_video(source_file_path, target_file, overwrite=False, **kwargs):
    """
    Compress and scale video at `source_file_path` using setting provided in `kwargs`:
      - max_height (int): set a limit for maximum vertical resolution (default: 480)
      - max_width (int): set a limit for maximum horizontal resolution for video
      - crf (int): set compression constant rate factor (default 32 = compress a lot)
    Save compressed output video to `target_file`.
    """
    # scaling
    # The output width and height for ffmpeg scale param must be divisible by 2
    # using value -2 to get robust behaviour: maintains the aspect ratio and also
    # ensure the calculated dimension is divisible by 2
    if "max_width" in kwargs:
        scale = "'w=trunc(min(iw,{max_width})/2)*2:h=-2'".format(
            max_width=kwargs["max_width"]
        )
    elif "max_height" in kwargs:
        scale = "'w=-2:h=trunc(min(ih,{max_height})/2)*2'".format(
            max_height=kwargs["max_height"]
        )
    else:
        scale = "'w=-2:h=trunc(min(ih,480)/2)*2'"  # default to max-height 480px

    # set constant rate factor, see https://trac.ffmpeg.org/wiki/Encode/H.264#crf
    crf = kwargs["crf"] if "crf" in kwargs else 32

    # run command
    command = [
        "ffmpeg",
        "-y" if overwrite else "-n",
        "-i",
        source_file_path,
        "-profile:v",
        "baseline",
        "-level",
        "3.0",
        "-b:a",
        "32k",
        "-ac",
        "1",
        "-vf",
        "scale={}".format(scale),
        "-crf",
        str(crf),
        "-preset",
        "slow",
        "-v",
        "error",
        "-strict",
        "-2",
        "-stats",
        target_file,
    ]
    try:
        subprocess.check_output(command, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        raise VideoCompressionError("{}: {}".format(e, e.output))
