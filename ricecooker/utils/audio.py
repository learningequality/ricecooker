import logging
import subprocess
from enum import Enum

LOGGER = logging.getLogger("AudioResource")
LOGGER.setLevel(logging.DEBUG)


class AudioCompressionError(Exception):
    """
    Custom error returned when `ffmpeg` compression exits with a non-zero status.
    """


AudioEncoding = Enum("AudioEncoding", ["CBR", "VBR"])

# Allowed Constant Bit Rate values for MP3 encoding.
CBR_VALUES = {8, 16, 24, 32, 40, 48, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320}
# Allowed Variable Bit Rate values for MP3 encoding.
VBR_VALUES = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9}


def compress_audio(
    source_file_path,
    target_file,
    overwrite=False,
    encoding=AudioEncoding.CBR,
    bit_rate=96,
    vbr=7,
):
    """
    Compress audio at `source_file_path` using setting provided:
      - encoding: Use Constant or Variable Bit Rate encoding (default CBR)
      - bit_rate (int): CBR bit_rate
      - vbr (int): lame setting for VBR
    Save compressed output audio to `target_file`.
    """

    if not isinstance(encoding, AudioEncoding):
        raise TypeError("encoding value must be {} enum value".format(AudioEncoding))

    if not isinstance(bit_rate, int):
        raise TypeError("bit_rate must be an integer")

    if bit_rate not in CBR_VALUES:
        raise ValueError("bit_rate must be one of {}".format(CBR_VALUES))

    if not isinstance(vbr, int):
        raise TypeError("vbr must be an integer")

    if vbr not in VBR_VALUES:
        raise ValueError("vbr must be one of {}".format(VBR_VALUES))

    if encoding is AudioEncoding.CBR:
        option_name = "-b:a"
        value = bit_rate
    else:
        option_name = "-qscale:a"
        value = vbr

    # run command
    command = [
        "ffmpeg",
        "-y" if overwrite else "-n",
        "-i",
        source_file_path,
        "-codec:a",
        "libmp3lame",
        option_name,
        str(value),
        target_file,
    ]
    try:
        subprocess.check_output(command, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        raise AudioCompressionError("{}: {}".format(e, e.output))
    except (BrokenPipeError, IOError) as e:
        raise AudioCompressionError("{}".format(e))
