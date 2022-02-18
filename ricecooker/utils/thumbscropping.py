import math
import re
import sys
import types

from PIL import Image

# Useful for very coarse version differentiation.
PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

if PY3:
    string_types = (str,)
    integer_types = (int,)
    class_types = (type,)
    text_type = str
    binary_type = bytes
else:
    string_types = (basestring,)  # noqa: F821
    integer_types = (int, long)  # noqa: F821
    class_types = (type, types.ClassType)
    text_type = unicode  # noqa: F821
    binary_type = str

# SmileyChris/easy-thumbnails is licensed under the BSD 3-Clause "New" or "Revised" License
# Copyright (c) 2009, Chris Beaven
# All rights reserved.
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright notice,
#       this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright notice,
#       this list of conditions and the following disclaimer in the documentation
#       and/or other materials provided with the distribution.
#     * Neither the name easy-thumbnails nor the names of its contributors may be
#       used to endorse or promote products derived from this software without
#       specific prior written permission.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
# ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


def image_entropy(im):
    """
    Calculate the entropy of an image. Used for "smart cropping".
    """
    if not isinstance(im, Image.Image):
        # Can only deal with PIL images. Fall back to a constant entropy.
        return 0
    hist = im.histogram()
    hist_size = float(sum(hist))
    hist = [h / hist_size for h in hist]
    return -sum([p * math.log(p, 2) for p in hist if p != 0])


def _compare_entropy(start_slice, end_slice, slice, difference):
    """
    Calculate the entropy of two slices (from the start and end of an axis),
    returning a tuple containing the amount that should be added to the start
    and removed from the end of the axis.
    """
    start_entropy = image_entropy(start_slice)
    end_entropy = image_entropy(end_slice)
    if end_entropy and abs(start_entropy / end_entropy - 1) < 0.01:
        # Less than 1% difference, remove from both sides.
        if difference >= slice * 2:
            return slice, slice
        half_slice = slice // 2
        return half_slice, slice - half_slice
    if start_entropy > end_entropy:
        return 0, slice
    else:
        return slice, 0


def scale_and_crop(  # noqa: C901
    im, size, crop=False, upscale=False, zoom=None, target=None, **kwargs
):
    """
    Handle scaling and cropping the source image.
    Images can be scaled / cropped against a single dimension by using zero
    as the placeholder in the size. For example, ``size=(100, 0)`` will cause
    the image to be resized to 100 pixels wide, keeping the aspect ratio of
    the source image.
    crop
        Crop the source image height or width to exactly match the requested
        thumbnail size (the default is to proportionally resize the source
        image to fit within the requested thumbnail size).
        By default, the image is centered before being cropped. To crop from
        the edges, pass a comma separated string containing the ``x`` and ``y``
        percentage offsets (negative values go from the right/bottom). Some
        examples follow:
        * ``crop="0,0"`` will crop from the left and top edges.
        * ``crop="-10,-0"`` will crop from the right edge (with a 10% offset)
          and the bottom edge.
        * ``crop=",0"`` will keep the default behavior for the x axis
          (horizontally centering the image) and crop from the top edge.
        The image can also be "smart cropped" by using ``crop="smart"``. The
        image is incrementally cropped down to the requested size by removing
        slices from edges with the least entropy.
        Finally, you can use ``crop="scale"`` to simply scale the image so that
        at least one dimension fits within the size dimensions given (you may
        want to use the upscale option too).
    upscale
        Allow upscaling of the source image during scaling.
    zoom
        A percentage to zoom in on the scaled image. For example, a zoom of
        ``40`` will clip 20% off each side of the source image before
        thumbnailing.
    target
        Set the focal point as a percentage for the image if it needs to be
        cropped (defaults to ``(50, 50)``).
        For example, ``target="10,20"`` will set the focal point as 10% and 20%
        from the left and top of the image, respectively. If the image needs to
        be cropped, it will trim off the right and bottom edges until the focal
        point is centered.
        Can either be set as a two-item tuple such as ``(20, 30)`` or a comma
        separated string such as ``"20,10"``.
        A null value such as ``(20, None)`` or ``",60"`` will default to 50%.
    """
    source_x, source_y = [float(v) for v in im.size]
    target_x, target_y = [int(v) for v in size]

    if crop or not target_x or not target_y:
        scale = max(target_x / source_x, target_y / source_y)
    else:
        scale = min(target_x / source_x, target_y / source_y)

    # Handle one-dimensional targets.
    if not target_x:
        target_x = round(source_x * scale)
    elif not target_y:
        target_y = round(source_y * scale)

    if zoom:
        if not crop:
            target_x = round(source_x * scale)
            target_y = round(source_y * scale)
            crop = True
        scale *= (100 + int(zoom)) / 100.0

    if scale < 1.0 or (scale > 1.0 and upscale):
        # Resize the image to the target size boundary. Round the scaled
        # boundary sizes to avoid floating point errors.
        im = im.resize(
            (int(round(source_x * scale)), int(round(source_y * scale))),
            resample=Image.ANTIALIAS,
        )

    if crop:
        # Use integer values now.
        source_x, source_y = im.size
        # Difference between new image size and requested size.
        diff_x = int(source_x - min(source_x, target_x))
        diff_y = int(source_y - min(source_y, target_y))
        if crop != "scale" and (diff_x or diff_y):
            if isinstance(target, string_types):
                target = re.match(r"(\d+)?,(\d+)?$", target)
                if target:
                    target = target.groups()
            if target:
                focal_point = [int(n) if (n or n == 0) else 50 for n in target]
            else:
                focal_point = 50, 50
            # Crop around the focal point
            halftarget_x, halftarget_y = int(target_x / 2), int(target_y / 2)
            focal_point_x = int(source_x * focal_point[0] / 100)
            focal_point_y = int(source_y * focal_point[1] / 100)
            box = [
                max(0, min(source_x - target_x, focal_point_x - halftarget_x)),
                max(0, min(source_y - target_y, focal_point_y - halftarget_y)),
            ]
            box.append(int(min(source_x, box[0] + target_x)))
            box.append(int(min(source_y, box[1] + target_y)))
            # See if an edge cropping argument was provided.
            edge_crop = isinstance(crop, string_types) and re.match(
                r"(?:(-?)(\d+))?,(?:(-?)(\d+))?$", crop
            )
            if edge_crop and filter(None, edge_crop.groups()):
                x_right, x_crop, y_bottom, y_crop = edge_crop.groups()
                if x_crop:
                    offset = min(int(target_x) * int(x_crop) // 100, diff_x)
                    if x_right:
                        box[0] = diff_x - offset
                        box[2] = source_x - offset
                    else:
                        box[0] = offset
                        box[2] = source_x - (diff_x - offset)
                if y_crop:
                    offset = min(int(target_y) * int(y_crop) // 100, diff_y)
                    if y_bottom:
                        box[1] = diff_y - offset
                        box[3] = source_y - offset
                    else:
                        box[1] = offset
                        box[3] = source_y - (diff_y - offset)
            # See if the image should be "smart cropped".
            elif crop == "smart":
                left = top = 0
                right, bottom = source_x, source_y
                while diff_x:
                    slice = min(diff_x, max(diff_x // 5, 10))
                    start = im.crop((left, 0, left + slice, source_y))
                    end = im.crop((right - slice, 0, right, source_y))
                    add, remove = _compare_entropy(start, end, slice, diff_x)
                    left += add
                    right -= remove
                    diff_x = diff_x - add - remove
                while diff_y:
                    slice = min(diff_y, max(diff_y // 5, 10))
                    start = im.crop((0, top, source_x, top + slice))
                    end = im.crop((0, bottom - slice, source_x, bottom))
                    add, remove = _compare_entropy(start, end, slice, diff_y)
                    top += add
                    bottom -= remove
                    diff_y = diff_y - add - remove
                box = (left, top, right, bottom)
            # Finally, crop the image!
            im = im.crop(box)
    return im
