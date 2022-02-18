import os
import zipfile
from io import BytesIO

import ebooklib.epub
from pdf2image import convert_from_path
from PIL import Image

from .thumbscropping import scale_and_crop


# SMARTCROP UTILS
################################################################################

THUMBNAIL_SIZE = (400, 225)  # 16:9 aspect ratio


def scale_and_crop_thumbnail(image, size=THUMBNAIL_SIZE, crop="smart", **kwargs):
    """
    Scale and crop the PIL Image ``image`` to maximum dimensions of ``size``.
    By default, ``crop`` is set to "smart" which will crop the image down to size
    based on the entropy content of the pixels. The other options are:
    * Use ``crop="0,0"`` to crop from the left and top edges
    * Use ``crop=",0"`` to crop from the top edge.
    Optional keyword arguments:
    * ``zoom=X``: crop outer X% before starting
    * ``target``: recenter here before cropping (default center ``(50, 50)``)
    See the ``scale_and_crop`` docs in ``thumbscropping.py`` for more details.
    """
    return scale_and_crop(image, size, crop=crop, upscale=True, **kwargs)


# THUMBNAILS FOR CONTENT KINDS
################################################################################


def create_image_from_epub(epubfile, fpath_out, crop=None):
    """
    Generate a thumbnail image from `epubfile` and save it to `fpath_out`.
    Raises ThumbnailGenerationError if thumbnail extraction fails.
    """
    try:
        book = ebooklib.epub.read_epub(epubfile)
        # 1. try to get cover image from book metadata (content.opf)
        cover_item = None
        covers = book.get_metadata("http://www.idpf.org/2007/opf", "cover")
        if covers:
            cover_tuple = covers[0]  # ~= (None, {'name':'cover', 'content':'item1'})
            cover_item_id = cover_tuple[1]["content"]
            for item in book.items:
                if item.id == cover_item_id:
                    cover_item = item
        if cover_item:
            image_data = BytesIO(cover_item.get_content())
        else:
            # 2. fallback to get first image in the ePub file
            images = list(book.get_items_of_type(ebooklib.ITEM_IMAGE))
            if not images:
                raise ThumbnailGenerationError(
                    "ePub file {} contains no images.".format(epubfile)
                )
            # TODO: get largest image of the bunch
            image_data = BytesIO(images[0].get_content())

        # Save image_data to fpath_out
        im = Image.open(image_data)
        im = scale_and_crop_thumbnail(im, crop=crop)
        im.save(fpath_out)
    except Exception as e:
        raise ThumbnailGenerationError("Fail on ePub {} {}".format(epubfile, e))


def create_image_from_zip(htmlfile, fpath_out, crop="smart"):
    """
    Create an image from the html5 zip at htmlfile and write result to fpath_out.
    Raises ThumbnailGenerationError if thumbnail extraction fails.
    """
    biggest_name = None
    size = 0
    try:
        with zipfile.ZipFile(htmlfile, "r") as zf:
            # get the biggest (most pixels) image in the zip
            image_exts = ["png", "PNG", "jpeg", "JPEG", "jpg", "JPG"]
            for filename in zf.namelist():
                _, dotext = os.path.splitext(filename)
                ext = dotext[1:]
                if ext in image_exts:
                    with zf.open(filename) as fhandle:
                        image_data = fhandle.read()
                        with BytesIO(image_data) as bhandle:
                            img = Image.open(bhandle)
                            img_size = img.size[0] * img.size[1]
                            if img_size > size:
                                biggest_name = filename
                                size = img_size
            if biggest_name is None:
                raise ThumbnailGenerationError(
                    "HTML5 zip file {} contains no images.".format(htmlfile)
                )
            with zf.open(biggest_name) as fhandle:
                image_data = fhandle.read()
                with BytesIO(image_data) as bhandle:
                    img = Image.open(bhandle)
                    img = scale_and_crop_thumbnail(img, crop=crop)
                    img.save(fpath_out)
    except Exception as e:
        raise ThumbnailGenerationError("Fail on zip {} {}".format(htmlfile, e))


def create_image_from_pdf_page(fpath_in, fpath_out, page_number=0, crop=None):
    """
    Create an image from the pdf at fpath_in and write result to fpath_out.
    """
    try:
        assert fpath_in.endswith("pdf"), "File must be in pdf format"
        pages = convert_from_path(
            fpath_in, 500, first_page=page_number, last_page=page_number + 1
        )
        page = pages[0]
        # resize
        page = scale_and_crop_thumbnail(page, zoom=10, crop=crop)
        page.save(fpath_out, "PNG")
    except Exception as e:
        raise ThumbnailGenerationError("Fail on PDF {} {}".format(fpath_in, e))


# TILED THUMBNAILS FOR TOPIC NODES (FOLDERS)
################################################################################


def create_tiled_image(source_images, fpath_out):
    """
    Create a 16:9 tiled image from list of image paths provided in source_images
    and write result to fpath_out.
    """
    try:
        sizes = {1: 1, 4: 2, 9: 3, 16: 4, 25: 5, 36: 6, 49: 7}
        assert (
            len(source_images) in sizes.keys()
        ), "Number of images must be a perfect square <= 49"
        root = sizes[len(source_images)]

        images = list(map(Image.open, source_images))
        new_im = Image.new("RGBA", THUMBNAIL_SIZE)
        offset = (
            int(float(THUMBNAIL_SIZE[0]) / float(root)),
            int(float(THUMBNAIL_SIZE[1]) / float(root)),
        )

        index = 0
        for y_index in range(root):
            for x_index in range(root):
                im = scale_and_crop_thumbnail(images[index], size=offset)
                new_im.paste(im, (int(offset[0] * x_index), int(offset[1] * y_index)))
                index = index + 1
        new_im.save(fpath_out)
    except Exception as e:
        raise ThumbnailGenerationError("Failed due to {}".format(e))


def convert_image(filename, dest_dir=None, size=None, format="PNG"):
    """
    Converts an image to a specified output format. The converted image will have the same
    file basename as filename, but with the extension of the converted format.

    :param filename: Filename of image to covert.
    :param dest_dir: Destination directory for image, if None will save to same directory as filename.
    :param size: Tuple of size of new image, if None, image is not resized.
    :param format: File extension of format to convert to (e.g. PNG, JPG), Defaults to PNG.

    :returns: Path to converted file.
    """

    assert os.path.exists(filename), "Image file not found: {}".format(
        os.path.abspath(filename)
    )

    if not dest_dir:
        dest_dir = os.path.dirname(os.path.abspath(filename))

    dest_filename_base = os.path.basename(filename)
    base, ext = os.path.splitext(dest_filename_base)
    new_filename = base + ".{}".format(format.lower())
    dest_filename = os.path.join(dest_dir, new_filename)

    img = Image.open(filename)

    dest_img = img.convert("RGB")

    # resive image to thumbnail dimensions
    if size:
        dest_img = dest_img.resize(size, Image.ANTIALIAS)
    dest_img.save(dest_filename)

    return dest_filename


# EXCEPTIONS
################################################################################


class ThumbnailGenerationError(Exception):
    """
    Custom error returned when thumbnail extraction process fails.
    """
