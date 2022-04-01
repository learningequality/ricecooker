import os

import PIL
import pytest

from .test_videos import bad_video  # noqa F401
from .test_videos import high_res_video  # noqa F401
from .test_videos import low_res_video  # noqa F401
from .test_videos import TempFile  # noqa F401
from ricecooker.utils import images
from ricecooker.utils import videos


tests_dir = os.path.dirname(os.path.abspath(__file__))
files_dir = os.path.join(tests_dir, "files")
outputs_dir = os.path.join(files_dir, "expected_output")

# these settings are chosen to match our current use case in Studio
studio_cmap_options = {"name": "BuPu", "vmin": 0.3, "vmax": 0.7, "color": "black"}


SHOW_THUMBS = False  # set to True to show outputs when running tests locally


# TESTS
################################################################################


class BaseThumbnailGeneratorTestCase(object):
    def check_is_png_file(self, output_file):
        PNG_MAGIC_NUMBER = b"\x89P"
        with open(output_file, "rb") as f:
            f.seek(0)
            assert f.read(2) == PNG_MAGIC_NUMBER
            f.close()

    def check_thumbnail_generated(self, output_file):
        """
        Checks that a thumbnail file at output_file exists and not too large.
        """
        assert os.path.exists(output_file)
        im = PIL.Image.open(output_file)
        width, height = im.size
        if SHOW_THUMBS:
            im.show()
        assert width < 1000, "thumbnail generated is too large (w >= 1000)"
        assert height < 1000, "thumbnail generated is too tall (h >= 1000)"
        return im

    def check_16_9_format(self, output_file):
        """
        Checks that a thumbnail file at output_file exists and not too large,
        and roughly in 16:9 aspect ratio.
        """
        assert os.path.exists(output_file)
        im = PIL.Image.open(output_file)
        width, height = im.size
        assert float(width) / float(height) == 16.0 / 9.0
        if SHOW_THUMBS:
            im.show()
        return im


class Test_pdf_thumbnail_generation(BaseThumbnailGeneratorTestCase):
    def test_generates_thumbnail(self, tmpdir):
        input_file = os.path.join(files_dir, "generate_thumbnail", "sample.pdf")
        assert os.path.exists(input_file)
        output_file = tmpdir.join("pdf.png").strpath
        images.create_image_from_pdf_page(input_file, output_file)
        self.check_thumbnail_generated(output_file)

    def test_generates_16_9_thumbnail(self, tmpdir):
        input_file = os.path.join(files_dir, "generate_thumbnail", "sample.pdf")
        assert os.path.exists(input_file)
        output_file = tmpdir.join("pdf_16_9.png").strpath
        images.create_image_from_pdf_page(input_file, output_file, crop="smart")
        self.check_16_9_format(output_file)

    def test_raises_for_missing_file(self, tmpdir):
        input_file = os.path.join(files_dir, "file_that_does_not_exist.pdf")
        assert not os.path.exists(input_file)
        output_file = tmpdir.join("thumbnail.png").strpath
        with pytest.raises(images.ThumbnailGenerationError):
            images.create_image_from_pdf_page(input_file, output_file)

    def test_raises_for_invalid_pdf(self, tmpdir, bad_pdf_file):
        input_file = bad_pdf_file.name
        output_file = tmpdir.join("thumbnail.png").strpath
        with pytest.raises(images.ThumbnailGenerationError):
            images.create_image_from_pdf_page(input_file, output_file)


class Test_html_zip_thumbnail_generation(BaseThumbnailGeneratorTestCase):
    def test_generates_16_9_thumbnail(self, tmpdir):
        """
        The test fixtue `sample.zip` contains three images, one tall, one wide,
        and one roughly square. The "choose largest area" logic shoudl select the
        blue one to use as the thumbnail.
        """
        input_file = os.path.join(files_dir, "generate_thumbnail", "sample.zip")
        assert os.path.exists(input_file)
        output_file = tmpdir.join("zipfile.png").strpath
        images.create_image_from_zip(input_file, output_file)
        im = self.check_16_9_format(output_file)
        # check is blue image
        r, g, b = im.getpixel((1, 1))
        assert b > g and b > r, (r, g, b)

    def test_raises_for_missing_file(self, tmpdir):
        input_file = os.path.join(files_dir, "file_that_does_not_exist.zip")
        assert not os.path.exists(input_file)
        output_file = tmpdir.join("thumbnail.png").strpath
        with pytest.raises(images.ThumbnailGenerationError):
            images.create_image_from_zip(input_file, output_file)

    def test_raises_for_invalid_zip(self, tmpdir, bad_zip_file):
        input_file = bad_zip_file.name
        output_file = tmpdir.join("thumbnail.png").strpath
        with pytest.raises(images.ThumbnailGenerationError):
            images.create_image_from_zip(input_file, output_file)


class Test_tiled_thumbnail_generation(BaseThumbnailGeneratorTestCase):
    def test_generates_brazil_thumbnail(self, tmpdir):
        input_file = os.path.join(files_dir, "thumbnails", "BRAlogo1.png")
        assert os.path.exists(input_file)
        input_files = [input_file, input_file, input_file, input_file]
        output_file = tmpdir.join("tiled.png").strpath
        images.create_tiled_image(input_files, output_file)
        self.check_16_9_format(output_file)

    def test_generates_kolibris_thumbnail(self, tmpdir):
        filenames = ["BRAlogo1.png", "toosquare.png", "tootall.png", "toowide.png"]
        input_files = []
        for filename in filenames:
            input_file = os.path.join(files_dir, "thumbnails", filename)
            assert os.path.exists(input_file)
            input_files.append(input_file)
        output_file = tmpdir.join("tiled.png").strpath
        images.create_tiled_image(input_files, output_file)
        self.check_16_9_format(output_file)

    def test_raises_for_missing_file(self, tmpdir):
        input_file = os.path.join(files_dir, "file_that_does_not_exist.png")
        assert not os.path.exists(input_file)
        input_files = [input_file, input_file, input_file, input_file]
        output_file = tmpdir.join("tiled.png").strpath
        with pytest.raises(images.ThumbnailGenerationError):
            images.create_tiled_image(input_files, output_file)

    def test_raises_for_wrong_number_of_files(self, tmpdir):
        input_file = os.path.join(files_dir, "file_that_does_not_exist.png")
        assert not os.path.exists(input_file)
        input_files = [input_file, input_file, input_file, input_file]
        output_file = tmpdir.join("tiled.png").strpath
        with pytest.raises(images.ThumbnailGenerationError):
            images.create_tiled_image(input_files, output_file)

    def test_raises_for_invalid_png(self, tmpdir, bad_png_file):
        input_file = bad_png_file.name
        input_files = [input_file, input_file, input_file, input_file]
        output_file = tmpdir.join("tiled.png").strpath
        with pytest.raises(images.ThumbnailGenerationError):
            images.create_tiled_image(input_files, output_file)


class Test_epub_thumbnail_generation(BaseThumbnailGeneratorTestCase):
    def test_generates_thumbnail(self, tmpdir):
        input_file = os.path.join(files_dir, "generate_thumbnail", "sample.epub")
        assert os.path.exists(input_file)
        output_file = tmpdir.join("epub.png").strpath
        images.create_image_from_epub(input_file, output_file)
        self.check_thumbnail_generated(output_file)

    def test_generates_16_9_thumbnail(self, tmpdir):
        input_file = os.path.join(files_dir, "generate_thumbnail", "sample.epub")
        assert os.path.exists(input_file)
        output_file = tmpdir.join("epub_16_9.png").strpath
        images.create_image_from_epub(input_file, output_file, crop="smart")
        self.check_16_9_format(output_file)

    def test_generates_16_9_thumbnail_from_top(self, tmpdir):
        input_file = os.path.join(files_dir, "generate_thumbnail", "sample.epub")
        assert os.path.exists(input_file)
        output_file = tmpdir.join("epub_16_9_top.png").strpath
        images.create_image_from_epub(input_file, output_file, crop=",0")
        self.check_16_9_format(output_file)

    def test_raises_for_missing_file(self, tmpdir):
        input_file = os.path.join(files_dir, "file_that_does_not_exist.epub")
        assert not os.path.exists(input_file)
        output_file = tmpdir.join("thumbnail.png").strpath
        with pytest.raises(images.ThumbnailGenerationError):
            images.create_image_from_epub(input_file, output_file)

    def test_raises_for_invalid_epub(self, tmpdir, bad_epub_file):
        input_file = bad_epub_file.name
        output_file = tmpdir.join("thumbnail.png").strpath
        with pytest.raises(images.ThumbnailGenerationError):
            images.create_image_from_epub(input_file, output_file)


class Test_video_thumbnail_generation(BaseThumbnailGeneratorTestCase):
    def test_generates_16_9_thumbnail_from_low_res(
        self, tmpdir, low_res_video  # noqa F811
    ):
        input_file = low_res_video.name
        output_file = tmpdir.join("low_res_video_thumbnail.png").strpath
        videos.extract_thumbnail_from_video(input_file, output_file, overwrite=True)
        self.check_16_9_format(output_file)
        self.check_is_png_file(output_file)

    def test_generates_16_9_thumbnail_from_high_res(
        self, tmpdir, high_res_video  # noqa F811
    ):
        input_file = high_res_video.name
        output_file = tmpdir.join("high_res_video_thumbnail.png").strpath
        videos.extract_thumbnail_from_video(input_file, output_file, overwrite=True)
        self.check_16_9_format(output_file)
        self.check_is_png_file(output_file)

    def test_raises_for_missing_file(self, tmpdir):
        input_file = os.path.join(files_dir, "file_that_does_not_exist.mp4")
        assert not os.path.exists(input_file)
        output_file = tmpdir.join("thumbnail.png").strpath
        with pytest.raises(images.ThumbnailGenerationError):
            videos.extract_thumbnail_from_video(input_file, output_file, overwrite=True)

    def test_bad_video_raises(self, tmpdir, bad_video):  # noqa F811
        input_file = bad_video.name
        output_file = tmpdir.join("bad_video_thumbnail.png").strpath
        with pytest.raises(images.ThumbnailGenerationError):
            videos.extract_thumbnail_from_video(input_file, output_file, overwrite=True)


# FIXTURES
################################################################################


@pytest.fixture
def bad_audio_file():
    with TempFile(suffix=".mp3") as f:
        f.write(b"no mp3 here; ffmpeg should error out.")
        f.flush()
    return f  # returns a temporary file with a closed file descriptor


@pytest.fixture
def bad_pdf_file():
    with TempFile(suffix=".pdf") as f:
        f.write(b"no pdf here; thumbnail extraction should error out.")
        f.flush()
    return f  # returns a temporary file with a closed file descriptor


@pytest.fixture
def bad_zip_file():
    with TempFile(suffix=".zip") as f:
        f.write(b"no zip here; thumbnail extraction should error out.")
        f.flush()
    return f  # returns a temporary file with a closed file descriptor


@pytest.fixture
def bad_epub_file():
    with TempFile(suffix=".epub") as f:
        f.write(b"no epub here; thumbnail extraction should error out.")
        f.flush()
    return f  # returns a temporary file with a closed file descriptor


@pytest.fixture
def bad_png_file():
    with TempFile(suffix=".png") as f:
        f.write(b"no image here; tiled thumbnail processing should error out.")
        f.flush()
    return f  # returns a temporary file with a closed file descriptor
