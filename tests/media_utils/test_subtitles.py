import codecs
import hashlib
import os
import tempfile
from unittest import TestCase

from le_utils.constants import file_formats
from le_utils.constants import languages

from ricecooker.utils.subtitles import build_subtitle_converter_from_file
from ricecooker.utils.subtitles import InvalidSubtitleFormatError
from ricecooker.utils.subtitles import InvalidSubtitleLanguageError
from ricecooker.utils.subtitles import LANGUAGE_CODE_UNKNOWN

test_files_dir = os.path.join(
    os.path.abspath(os.path.dirname(__file__)), "files", "subtitles"
)


class SubtitleConverterTest(TestCase):
    def get_file_hash(self, path):
        hash = hashlib.md5()
        with open(path, "rb") as fobj:
            for chunk in iter(lambda: fobj.read(2097152), b""):
                hash.update(chunk)

        return hash.hexdigest()

    def assertFilesEqual(self, expected_file, actual_file):
        with codecs.open(actual_file, "rb", encoding="utf-8") as act, codecs.open(
            expected_file, "rb", encoding="utf-8"
        ) as exp:
            for actual_str, expected_str in zip(act.readlines(), exp.readlines()):
                self.assertEqual(actual_str.strip(), expected_str.strip())

    def test_replace_unknown_language(self):
        expected_language = languages.getlang_by_name("Arabic")

        converter = build_subtitle_converter_from_file(
            os.path.join(test_files_dir, "basic.srt")
        )

        self.assertTrue(converter.has_language(LANGUAGE_CODE_UNKNOWN))
        converter.replace_unknown_language(expected_language.code)

        self.assertTrue(converter.has_language(expected_language.code))
        self.assertFalse(converter.has_language(LANGUAGE_CODE_UNKNOWN))

    def test_srt_conversion(self):
        expected_file = os.path.join(test_files_dir, "basic.vtt")
        expected_language = languages.getlang_by_name("Arabic")

        converter = build_subtitle_converter_from_file(
            os.path.join(test_files_dir, "basic.srt")
        )
        converter.replace_unknown_language(expected_language.code)

        actual_file_d, actual_file_name = tempfile.mkstemp()

        converter.write(actual_file_name, expected_language.code)
        self.assertFilesEqual(expected_file, actual_file_name)

        os.close(actual_file_d)
        os.remove(actual_file_name)

    def test_expected_srt_conversion(self):
        expected_format = file_formats.SRT
        expected_file = os.path.join(test_files_dir, "basic.vtt")
        expected_language = languages.getlang_by_name("Arabic")

        converter = build_subtitle_converter_from_file(
            os.path.join(test_files_dir, "basic.srt"), in_format=expected_format
        )
        converter.replace_unknown_language(expected_language.code)

        actual_file_d, actual_file_name = tempfile.mkstemp()

        converter.write(actual_file_name, expected_language.code)
        self.assertFilesEqual(expected_file, actual_file_name)

        os.close(actual_file_d)
        os.remove(actual_file_name)

    def test_not_expected_type(self):
        expected_format = file_formats.SCC
        expected_language = languages.getlang_by_name("Arabic")

        converter = build_subtitle_converter_from_file(
            os.path.join(test_files_dir, "basic.srt"), in_format=expected_format
        )

        with self.assertRaises(InvalidSubtitleFormatError):
            converter.convert(expected_language.code)

    def test_invalid_format(self):
        expected_language = languages.getlang_by_name("English")

        converter = build_subtitle_converter_from_file(
            os.path.join(test_files_dir, "not.txt")
        )

        with self.assertRaises(InvalidSubtitleFormatError):
            converter.convert(expected_language.code)

    def test_invalid_format__empty(self):
        expected_language = languages.getlang_by_name("English")

        converter = build_subtitle_converter_from_file(
            os.path.join(test_files_dir, "empty.ttml")
        )

        with self.assertRaises(InvalidSubtitleFormatError, msg="Caption file is empty"):
            converter.convert(expected_language.code)

    def test_valid_language(self):
        expected_file = os.path.join(test_files_dir, "encapsulated.vtt")
        expected_language = languages.getlang_by_name("English")

        converter = build_subtitle_converter_from_file(
            os.path.join(test_files_dir, "encapsulated.sami")
        )
        self.assertTrue(converter.has_language(expected_language.code))

        actual_file_d, actual_file_name = tempfile.mkstemp()

        converter.write(actual_file_name, expected_language.code)
        self.assertFilesEqual(expected_file, actual_file_name)

        os.close(actual_file_d)
        os.remove(actual_file_name)

    def test_invalid_language(self):
        expected_language = languages.getlang_by_name("Spanish")

        converter = build_subtitle_converter_from_file(
            os.path.join(test_files_dir, "encapsulated.sami")
        )

        with self.assertRaises(InvalidSubtitleLanguageError):
            converter.convert(expected_language.code)
