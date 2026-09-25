import os
import tempfile
import zipfile
import zlib


def _read_file(path):
    with open(path, "rb") as f:
        return f.read()


def find_common_root(names):
    """Return the common parent directory shared by all file paths.

    Ported from Studio's ``findCommonRoot`` (frontend/shared/utils/zipFile.js).
    ``names`` are POSIX-style, non-directory archive member paths.
    """
    paths = [n.split("/")[:-1] for n in names]
    if not paths:
        return ""
    if len(paths) == 1:
        return "/".join(paths[0])
    first = paths[0]
    common = []
    for i, part in enumerate(first):
        for other in paths[1:]:
            if i >= len(other) or other[i] != part:
                return "/".join(common)
        common.append(part)
    return "/".join(common)


def find_html_entrypoint(names):
    """Return the archive member that is the HTML entry point, or None.

    Ported from Studio's ``findFirstHtml`` (frontend/shared/utils/zipFile.js):
    prefer ``index.html`` at the common-root-stripped root, then any
    ``index.html``, then the shallowest / shortest-named ``.html`` file.

    ``names`` are POSIX-style archive member paths (as from ``namelist()``).
    """
    html_files = [n for n in names if n.lower().endswith(".html")]
    if not html_files:
        return None
    common_root = find_common_root(names)
    prefix = common_root + "/" if common_root else ""
    normalized = [
        (n, n[len(prefix) :] if prefix and n.startswith(prefix) else n)
        for n in html_files
    ]
    for original, norm in normalized:
        if norm == "index.html":
            return original
    for original, norm in normalized:
        if norm.split("/")[-1] == "index.html":
            return original
    normalized.sort(key=lambda t: (t[1].count("/"), len(t[1])))
    return normalized[0][0]


def directory_member_names(directory):
    """Every file in ``directory``, as archive-style paths relative to it."""
    return [
        os.path.relpath(os.path.join(dirpath, name), directory).replace(os.sep, "/")
        for dirpath, _, filenames in os.walk(directory)
        for name in filenames
    ]


def _assert_reference_zlib():
    """
    Refuse to build predictable zips on interpreters linked against zlib-ng.

    zlib-ng emits different DEFLATE bytes than zlib at every level and strategy, and
    predictable-zip MD5s are pinned in Studio's JavaScript and already in use for
    deduplication. CPython 3.14 exposes ``zlib.ZLIBNG_VERSION``; older builds only
    advertise it as ``1.3.1.zlib-ng`` in ``ZLIB_RUNTIME_VERSION``.
    """
    zlibng_version = getattr(zlib, "ZLIBNG_VERSION", None)
    if zlibng_version is None and "zlib-ng" in zlib.ZLIB_RUNTIME_VERSION:
        zlibng_version = zlib.ZLIB_RUNTIME_VERSION
    if zlibng_version is not None:
        raise RuntimeError(
            "This interpreter's zlib is backed by zlib-ng {}, which compresses to "
            "different bytes than the reference zlib, so archives built here would "
            "not match the file hashes Kolibri Studio expects. Use a Python built "
            "against regular zlib (on Windows, 3.13 or earlier).".format(zlibng_version)
        )


def create_predictable_zip(path, entrypoint=None, file_converter=None):
    """
    Create a zip file with predictable sort order and metadata so that MD5 will
    stay consistent if zipping the same content twice.
    Args:
        path (str): absolute path either to a directory to zip up, or an existing zip file to convert.
        entrypoint (str or None): if specified, a relative file path in the zip to serve as the first page to load
    Returns: path (str) to the output zip file
    """
    _assert_reference_zlib()
    extension = "zip"
    # if path is a directory, recursively enumerate all the files under the directory
    if os.path.isdir(path):
        paths = directory_member_names(path)

        def reader(x):
            return _read_file(os.path.join(path, x))

    # otherwise, if it's a zip file, open it up and pull out the list of names
    elif os.path.isfile(path):
        extension = os.path.splitext(path)[1]
        inputzip = zipfile.ZipFile(path)
        paths = inputzip.namelist()

        def reader(x):
            return inputzip.read(x)

    # create a temporary zip file path to write the output into
    zippathfd, zippath = tempfile.mkstemp(suffix=".{}".format(extension))

    with zipfile.ZipFile(zippath, "w", compression=zipfile.ZIP_DEFLATED) as outputzip:
        # loop over the file paths in sorted order, to ensure a predictable zip
        for filepath in sorted(paths):
            write_file_to_zip_with_neutral_metadata(
                outputzip,
                filepath,
                file_converter(filepath, reader)
                if file_converter
                else reader(filepath),
            )
        os.fdopen(zippathfd).close()
    return zippath


def write_file_to_zip_with_neutral_metadata(zfile, filepath, content):
    """
    Write the string `content` to `filepath` in the open ZipFile `zfile`.
    Args:
        zfile (ZipFile): open ZipFile to write the content into
        filepath (str): the file path within the zip file to write into
        content (str): the content to write into the zip
    Returns: None
    """
    # Convert any windows file separators to unix style for consistent
    # file paths in the zip file
    filepath = filepath.replace("\\", "/")
    info = zipfile.ZipInfo(filepath, date_time=(2015, 10, 21, 7, 28, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.comment = "".encode()
    info.create_system = 0
    zfile.writestr(info, content)
