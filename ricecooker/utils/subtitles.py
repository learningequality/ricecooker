import codecs

from le_utils.constants import file_formats
from pycaption import CaptionReadError
from pycaption import CaptionReadNoCaptions
from pycaption import CaptionSet
from pycaption import DFXPReader
from pycaption import SAMIReader
from pycaption import SCCReader
from pycaption import SRTReader
from pycaption import WebVTTReader
from pycaption import WebVTTWriter
from pycaption.base import DEFAULT_LANGUAGE_CODE


LANGUAGE_CODE_UNKNOWN = DEFAULT_LANGUAGE_CODE


class InvalidSubtitleFormatError(TypeError):
    """
    Custom error indicating a format that is invalid
    """


class InvalidSubtitleLanguageError(ValueError):
    """
    Custom error indicating that the provided language isn't present in a captions file
    """


class SubtitleReader:
    """
    A wrapper class for the pycaption readers since the interface differs between all. This will
    call read with `LANGUAGE_CODE_UNKNOWN` if `requires_language` is `True`
    """

    def __init__(self, reader, requires_language=False):
        """
        :param reader: A pycaption reader
        :type reader: WebVTTReader, SRTReader, SAMIReader, SCCReader, DFXPReader
        :param requires_language: A boolean specifying whether the reader requires a language
        :type requires_language: bool
        """
        self.reader = reader
        self.requires_language = requires_language

    def read(self, caption_str):
        """
        Handles detecting and reading the captions

        :param caption_str: A string with the captions contents
        :type caption_str: str
        :return: The captions from the file in a `CaptionSet` or `None` if unsupported
        :rtype: CaptionSet, None
        """
        # attempt detection first, being accepting of failure
        try:
            if not self.reader.detect(caption_str):
                return None
        except UnicodeDecodeError:
            return None

        # after detection, if read fails, be aggressive and throw an error
        try:
            if self.requires_language:
                return self.reader.read(caption_str, lang=LANGUAGE_CODE_UNKNOWN)

            return self.reader.read(caption_str)
        except CaptionReadNoCaptions:
            raise InvalidSubtitleFormatError("Caption file has no captions")
        except (CaptionReadError, UnicodeDecodeError) as e:
            raise InvalidSubtitleFormatError("Caption file is invalid: {}".format(e))
        # allow other errors to be passed through


class SubtitleConverter:
    """
    This class converts subtitle files to the preferred VTT format
    """

    def __init__(self, readers, caption_str):
        """
        :param readers: An array of `SubtitleReader` instances
        :param caption_str: A string with the captions content
        """
        self.readers = readers
        self.caption_str = caption_str
        self.writer = WebVTTWriter()
        # set "video size" to 100 since other types may have layout, 100 should work to generate %
        self.writer.video_width = 100
        self.writer.video_height = self.writer.video_width * 6 / 19
        self.caption_set = None

    def get_caption_set(self):
        """
        Detects and reads the `caption_str` into the cached `caption_set` property and returns it.

        :return: CaptionSet
        """
        if self.caption_set:
            return self.caption_set

        for reader in self.readers:
            self.caption_set = reader.read(self.caption_str)
            if self.caption_set is not None:
                break
        else:
            self.caption_set = None
            raise InvalidSubtitleFormatError(
                "Subtitle file is unsupported or unreadable"
            )

        if self.caption_set.is_empty():
            raise InvalidSubtitleLanguageError("Captions set is invalid")
        return self.caption_set

    def get_language_codes(self):
        """
        This gets the language codes as defined by the caption string. Some caption formats do not
        specify languages, which in that case a special code (constant `LANGUAGE_CODE_UNKNOWN`)
        will be present.

        :return: An array of language codes as defined in the subtitle file.
        """
        return self.get_caption_set().get_languages()

    def has_language(self, lang_code):
        """
        Determines if current caption set to be converted is/has an unknown language. This would
        happen with SRT or other files where language is not specified

        :param: lang_code: A string of the language code to check
        :return: bool
        """
        return lang_code in self.get_language_codes()

    def replace_unknown_language(self, lang_code):
        """
        This essentially sets the "unknown" language in the caption set, by replacing the key
        with this new language code

        :param lang_code: A string with the language code to replace the unknown language with
        """
        caption_set = self.get_caption_set()

        captions = {}
        for lang in caption_set.get_languages():
            set_lang = lang_code if lang == LANGUAGE_CODE_UNKNOWN else lang
            captions[set_lang] = caption_set.get_captions(lang)

        # Replace caption_set with new version, having replaced unknown language
        self.caption_set = CaptionSet(
            captions,
            styles=dict(caption_set.get_styles()),
            layout_info=caption_set.layout_info,
        )

    def write(self, out_filename, lang_code):
        """
        Convenience method to write captions as file. Captions contents must be unicode for
        conversion.

        :param out_filename: A string path to put the converted captions contents
        :param lang_code: A string of the language code to write
        """
        with codecs.open(out_filename, "w", encoding="utf-8") as converted_file:
            converted_file.write(self.convert(lang_code))

    def convert(self, lang_code):
        """
        Converts the caption set to the VTT format

        :param lang_code: A string with one of the languages to output the captions for
        :type: lang_code: str
        :return: A string with the converted caption contents
        :rtype: str
        """
        caption_set = self.get_caption_set()
        captions = caption_set.get_captions(lang_code)

        if not captions:
            raise InvalidSubtitleLanguageError(
                "Language '{}' is not present in caption set".format(lang_code)
            )

        styles = caption_set.get_styles()
        layout_info = caption_set.get_layout_info(lang_code)
        lang_caption_set = CaptionSet(
            {lang_code: captions}, styles=dict(styles), layout_info=layout_info
        )
        return self.writer.write(lang_caption_set)


#####################
# FACTORY FUNCTIONS #
#####################


def build_dfxp_reader():
    return SubtitleReader(DFXPReader())


def build_sami_reader():
    return SubtitleReader(SAMIReader())


def build_scc_reader():
    return SubtitleReader(SCCReader(), requires_language=True)


def build_srt_reader():
    return SubtitleReader(SRTReader(), requires_language=True)


def build_vtt_reader():
    return SubtitleReader(WebVTTReader(), requires_language=True)


BUILD_READER_MAP = {
    file_formats.VTT: build_vtt_reader,
    file_formats.SRT: build_srt_reader,
    file_formats.SAMI: build_sami_reader,
    file_formats.SCC: build_scc_reader,
    file_formats.TTML: build_dfxp_reader,
    file_formats.DFXP: build_dfxp_reader,
}


def build_subtitle_reader(reader_format):
    if reader_format not in BUILD_READER_MAP:
        raise InvalidSubtitleFormatError("Unsupported")
    return BUILD_READER_MAP[reader_format]()


def build_subtitle_readers():
    readers = []
    for reader_format, build in BUILD_READER_MAP.items():
        readers.append(build())
    return readers


def build_subtitle_converter(caption_str, in_format=None):
    """
    Builds a subtitle converter used to convert subtitle files to VTT format

    :param caption_str: A string with the captions contents
    :type: captions_str: str
    :param in_format: A string with expected format of the file to be converted
    :type: in_format: str
    :return: A SubtitleConverter
    :rtype: SubtitleConverter
    """
    readers = []
    if in_format is not None:
        readers.append(build_subtitle_reader(in_format))
    else:
        readers = build_subtitle_readers()

    return SubtitleConverter(readers, caption_str)


def build_subtitle_converter_from_file(captions_filename, in_format=None):
    """
    Reads `captions_filename` as the file to be converted, and returns a `SubtitleConverter`
    instance that can be used to do the conversion.

    :param captions_filename: A string path to the captions file to parse
    :type: captions_filename: str
    :param in_format: A string with expected format of `captions_filename`, otherwise detected
    :type: in_format: str
    :return: A SubtitleConverter
    :rtype: SubtitleConverter
    """
    with codecs.open(captions_filename, encoding="utf-8") as captions_file:
        captions_str = captions_file.read()

    return build_subtitle_converter(captions_str, in_format)
