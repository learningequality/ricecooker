import json
import logging
import os
import re
import struct
import subprocess
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from typing import Tuple

from le_utils.constants import format_presets

from ricecooker import config

from .images import ThumbnailGenerationError

LOGGER = logging.getLogger("VideoResource")
LOGGER.setLevel(logging.DEBUG)

STALL_TIMEOUT = 300
PROBE_TIMEOUT = 60
VP9_MAX_BITS_PER_PIXEL = 0.1
# webm can only carry text subtitles.
BITMAP_SUBTITLE_CODECS = {"dvb_subtitle", "dvd_subtitle", "hdmv_pgs_subtitle", "xsub"}


def run_ffmpeg(args):
    cmd = ["ffmpeg", "-nostats", "-progress", "pipe:1", *args]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
    )
    progress = []
    stderr = []
    last_advance = time.monotonic()

    def read_progress():
        nonlocal last_advance
        position = None
        with proc.stdout:
            for line in proc.stdout:
                if progress and progress[-1] == "progress=continue\n":
                    progress.clear()
                progress.append(line)
                if line.startswith("out_time=") and line != position:
                    position = line
                    last_advance = time.monotonic()

    def read_stderr():
        with proc.stderr:
            stderr.append(proc.stderr.read())

    progress_reader = threading.Thread(target=read_progress, daemon=True)
    stderr_reader = threading.Thread(target=read_stderr, daemon=True)
    progress_reader.start()
    stderr_reader.start()
    stalled = False
    try:
        while progress_reader.is_alive():
            idle = time.monotonic() - last_advance
            if idle >= STALL_TIMEOUT:
                stalled = True
                proc.kill()
                break
            progress_reader.join(STALL_TIMEOUT - idle)
        returncode = proc.wait()
    except BaseException:
        proc.kill()
        proc.wait()
        raise
    join_timeout = 1 if stalled else None
    progress_reader.join(join_timeout)
    stderr_reader.join(join_timeout)
    output, errors = "".join(progress), "".join(stderr)
    if stalled:
        raise subprocess.TimeoutExpired(cmd, STALL_TIMEOUT, output, errors)
    return subprocess.CompletedProcess(cmd, returncode, output, errors)


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
            ],
            stdin=subprocess.DEVNULL,
            timeout=PROBE_TIMEOUT,
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
            ],
            stdin=subprocess.DEVNULL,
            timeout=PROBE_TIMEOUT,
        )

        midpoint = float(re.search("\\d+\\.\\d+", str(result)).group()) / 2
        # scale parameters are from https://trac.ffmpeg.org/wiki/Scaling
        scale = "scale=400:225:force_original_aspect_ratio=decrease,pad=400:225:(ow-iw)/2:(oh-ih)/2"
        command = [
            "ffmpeg",
            "-y" if overwrite else "-n",
            "-ss",
            str(midpoint),
            "-i",
            str(fpath_in),
            "-vf",
            scale,
            "-vcodec",
            "png",
            "-nostats",
            "-vframes",
            "1",
            "-q:v",
            "2",
            "-loglevel",
            "panic",
            str(fpath_out),
        ]
        subprocess.check_output(
            command,
            stdin=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            timeout=PROBE_TIMEOUT,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        raise ThumbnailGenerationError("{}: {}".format(e, e.output))
    except AttributeError:
        raise ThumbnailGenerationError(
            "No suitable frame for thumbnail generation was found"
        )


def _get_stream_duration(fpath_in):
    progress = run_ffmpeg(
        ["-v", "error", "-i", str(fpath_in), "-f", "null", "-"]
    ).stdout
    time_code = re.findall(r"^out_time=(\S+)$", progress, re.MULTILINE)[-1]
    hours, minutes, seconds = time_code.split(":")
    # ffmpeg 6.1 ends at the last frame's start (0.933333 for a 1s clip)
    return (int(hours) * 60 + int(minutes)) * 60 + round(float(seconds))


def extract_duration_of_media(fpath_in, extension):
    """
    For more details on these commands, refer to the ffmpeg Wiki:
    https://trac.ffmpeg.org/wiki/FFprobeTips#Formatcontainerduration
    """
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
                    "-f",
                    extension,
                    str(fpath_in),
                ],
                stdin=subprocess.DEVNULL,
                timeout=PROBE_TIMEOUT,
            )
            result = result.decode("utf-8").strip()
            try:
                return int(float(result))
            except ValueError:
                # This can happen if ffprobe returns N/A for the duration
                # So instead we try to stream the entire file to get the value
                return _get_stream_duration(fpath_in)
    except Exception as ex:
        LOGGER.warning(ex)
        raise ex


class VideoCompressionError(Exception):
    """
    Custom error returned when `ffmpeg` compression exits with a non-zero status.
    """


def _vp9_bit_rate(video, max_height, max_width=None):
    try:
        fps = Fraction(video["avg_frame_rate"])
    except (TypeError, KeyError, ValueError, ZeroDivisionError):
        return 0
    width, height = display_size(video)
    if max_width is not None:
        scale = min(1, int(max_width) / width)
    elif max_height == "ih":
        scale = 1
    else:
        scale = min(1, int(max_height) / height)
    return int(VP9_MAX_BITS_PER_PIXEL * width * height * scale**2 * fps)


def compress_video(source_file_path, target_file, overwrite=False, **kwargs):
    """
    Compress and scale video at `source_file_path` using settings provided in `kwargs`.
    Can convert between formats - output format is determined by the extension of target_file.
    For MP4 output, uses H.264 codec with faststart flag.
    For WebM output, uses VP9 codec which is optimized for web streaming.

    Args:
        source_file_path (str): Path to source video file
        target_file (str): Path where compressed video will be saved
        overwrite (bool): Whether to overwrite existing target_file
        **kwargs:
            max_height (int): Maximum vertical resolution (default: 480)
            max_width (int): Maximum horizontal resolution
            crf (int): Compression constant rate factor (default: 32 for mp4, 35 for webm)

    Raises:
        VideoCompressionError: If compression fails
    """
    # Get input format
    ext = os.path.splitext(target_file)[1].lower()
    is_webm = ext == ".webm"

    # scaling
    # The output width and height for ffmpeg scale param must be divisible by 2
    # using value -2 to get robust behaviour: maintains the aspect ratio and also
    # ensure the calculated dimension is divisible by 2
    if "max_width" in kwargs:
        scale = "'w=trunc(min(iw,{max_width})/2)*2:h=-2'".format(
            max_width=kwargs["max_width"]
        )
    else:
        scale = "'w=-2:h=trunc(min(ih,{max_height})/2)*2'".format(
            max_height=kwargs.get("max_height", config.VIDEO_HEIGHT or "480")
        )

    # Default CRF values differ by format
    crf = kwargs.get("crf", 35 if is_webm else 32)

    # Map streams the way ffmpeg's default selection does, minus cover art,
    # which mp4 can't carry as H.264.
    streams = (probe_media(source_file_path) or {}).get("streams", [])
    video = video_stream(streams)
    selected = [video, audio_stream(streams)]
    if is_webm:
        selected.append(
            next(
                (
                    s
                    for s in streams
                    if s.get("codec_type") == "subtitle"
                    and s.get("codec_name") not in BITMAP_SUBTITLE_CODECS
                ),
                None,
            )
        )
    stream_maps = [arg for s in selected if s for arg in ("-map", f"0:{s['index']}")]

    # Common parameters that apply to both formats
    command = [
        "-y" if overwrite else "-n",
        "-i",
        source_file_path,
        "-vf",
        "scale={}".format(scale),
        "-pix_fmt",
        "yuv420p",
        *stream_maps,
        "-b:a",
        "32k",
        "-ac",
        "1",
        "-crf",
        str(crf),
        "-v",
        "error",
        "-strict",
        "-2",
    ]

    # Format-specific parameters
    if is_webm:
        bit_rate = _vp9_bit_rate(
            video,
            kwargs.get("max_height", config.VIDEO_HEIGHT or "480"),
            kwargs.get("max_width"),
        )
        command.extend(
            [
                "-c:v",
                "libvpx-vp9",
                "-b:v",
                str(bit_rate),
                "-maxrate",
                str(bit_rate),
                "-bufsize",
                str(2 * bit_rate),
                "-deadline",
                "good",
                "-cpu-used",
                "1",
            ]
        )
    else:
        command.extend(
            [
                "-profile:v",
                "baseline",
                "-level",
                "3.0",
                "-preset",
                "slow",
                "-movflags",
                "faststart",
            ]
        )

    command.append(target_file)

    try:
        run_ffmpeg(command).check_returncode()
    except subprocess.CalledProcessError as e:
        raise VideoCompressionError("{}: {}".format(e, e.stderr))
    except (BrokenPipeError, IOError) as e:
        raise VideoCompressionError("{}".format(e))


def web_faststart_video(source_file_path, target_file, overwrite=False):
    """
    Add faststart flag to an mp4 file
    """
    ext = os.path.splitext(target_file)[1].lower()
    if ext == ".webm":
        raise VideoCompressionError(
            "web_faststart_video not needed for WebM files - the WebM container format is already optimized for web streaming"
        )

    command = [
        "-y" if overwrite else "-n",
        "-i",
        source_file_path,
        "-map",
        "0",
        # mp4 can't copy data tracks such as timecode
        "-map",
        "-0:d?",
        "-c",
        "copy",
        "-v",
        "error",
        "-strict",
        "-2",
        "-movflags",
        "faststart",
        target_file,
    ]
    try:
        run_ffmpeg(command).check_returncode()
    except subprocess.CalledProcessError as e:
        raise VideoCompressionError("{}: {}".format(e, e.stderr))
    except (BrokenPipeError, IOError) as e:
        raise VideoCompressionError("{}".format(e))


def validate_media_file(file_path: str) -> Tuple[bool, str]:
    """
    Validate media file integrity by attempting to decode the entire file.

    Args:
        file_path (str): Path to the media file to validate

    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """

    cmd = [
        "-v",
        "error",  # Only show errors
        "-i",
        file_path,
        "-f",
        "null",  # Output format null (discards output)
        "-",  # Output to pipe
    ]
    result = run_ffmpeg(cmd)

    if result.returncode != 0:
        lines = [line for line in result.stderr.splitlines() if line.strip()]
        if not lines:
            return False, "ffmpeg could not decode the file"
        # The first "[demuxer @ addr] " tagged line carries the cause; untagged
        # lines before it can be probe noise. ffmpeg < 6.1 may print only
        # "<path>: <reason>", untagged.
        tag = re.compile(r"^\[[^\]]* @ (?:0x)?[0-9a-fA-F]+\] ")
        line = next((line for line in lines if tag.match(line)), lines[0])
        line = tag.sub("", line).removeprefix(f"{file_path}: ")
        # Sibling files an ffconcat or HLS input names resolve against the
        # storage directory.
        directory = os.path.dirname(file_path)
        if directory:
            for sep in {os.sep, "/"}:
                line = line.replace(directory + sep, "")
        return False, line

    return True, ""


def _ffprobe(file_path, *args):
    try:
        return subprocess.check_output(
            ["ffprobe", "-v", "error", *args, str(file_path)],
            stdin=subprocess.DEVNULL,
            timeout=PROBE_TIMEOUT,
            text=True,
        )
    except (subprocess.CalledProcessError, OSError):
        return None


def probe_media(file_path):
    result = _ffprobe(
        file_path,
        "-show_entries",
        "stream=index,codec_type,codec_name,width,height,pix_fmt,bit_rate,avg_frame_rate,channels"
        ":stream_side_data=rotation:stream_disposition=attached_pic,default",
        "-of",
        "json",
    )
    return None if result is None else json.loads(result)


def _best_stream(streams, codec_type, size):
    # ffmpeg's default selection score; max() keeps the first of equals, as ffmpeg does.
    candidates = [
        s
        for s in streams
        if s.get("codec_type") == codec_type
        and not s.get("disposition", {}).get("attached_pic")
    ]
    return max(
        candidates,
        key=lambda s: size(s) + 5000000 * s.get("disposition", {}).get("default", 0),
        default=None,
    )


def video_stream(streams):
    return _best_stream(
        streams, "video", lambda s: s.get("width", 0) * s.get("height", 0)
    )


def audio_stream(streams):
    return _best_stream(streams, "audio", lambda s: s.get("channels", 0))


def display_size(stream):
    rotation = next(
        (d["rotation"] for d in stream.get("side_data_list", []) if "rotation" in d),
        0,
    )
    if int(rotation) % 180:
        return stream["height"], stream["width"]
    return stream["width"], stream["height"]


@dataclass
class PacketTotals:
    bits: int = 0
    count: int = 0
    duration: float = 0.0


def probe_packets(file_path):
    try:
        output = _ffprobe(
            file_path,
            "-show_entries",
            "packet=stream_index,size,duration_time",
            "-of",
            "compact=p=0",
        )
    except subprocess.TimeoutExpired:
        # Too long to scan; empty totals make the video non-compliant.
        output = None
    totals = defaultdict(PacketTotals)
    for line in (output or "").splitlines():
        packet = dict(field.split("=", 1) for field in line.split("|") if field)
        stream = totals[int(packet["stream_index"])]
        stream.bits += 8 * int(packet["size"])
        stream.count += 1
        try:
            stream.duration += float(packet.get("duration_time"))
        except (TypeError, ValueError):
            pass
    return totals


def is_faststart(file_path):
    with open(file_path, "rb") as f:
        while True:
            header = f.read(8)
            if len(header) < 8:
                return False
            size, box_type = struct.unpack(">I4s", header)
            if box_type == b"moov":
                return True
            if size == 1:
                size = struct.unpack(">Q", f.read(8))[0] - 8
            if box_type == b"mdat" or size < 8:
                return False
            f.seek(size - 8, os.SEEK_CUR)
