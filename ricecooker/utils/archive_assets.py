"""Process an extracted archive in place: download external refs, compress media.

Archive content (HTML5 zip, H5P, IMSCP) may reference external URLs that do not
resolve offline. :class:`ArchiveProcessor` operates on an extracted archive
directory in two passes:

1. A reference-led walk that routes every external reference through the running
   file pipeline (download + convert), places the result next to its referencing
   file, and rewrites the reference — so every referenced asset is reachable.
2. A scoped conversion pass that recompresses every media file it can.

Reference detection is delegated to
:class:`~ricecooker.utils.references.ReferenceMapper` instances, so a new file
type needs only a mapper. Downloaded content is untrusted: bytes are written to
disk, never executed. Hand the directory to ``create_predictable_zip`` afterwards
to reseal the archive.
"""

import os
import shutil
from collections import deque

from ricecooker.config import LOGGER
from ricecooker.utils.pipeline.exceptions import ExpectedFileException
from ricecooker.utils.pipeline.exceptions import InvalidFileException
from ricecooker.utils.references import DEFAULT_MAPPERS
from ricecooker.utils.references import is_external_url
from ricecooker.utils.utils import extract_path_ext


class ArchiveProcessor:
    """Downloads external references and compresses media in an extracted archive.

    Operates on ``directory`` in place, reusing the running ``pipeline`` so an
    external reference is downloaded and converted through the same stages, config
    and caches as every other file. Detection is delegated to ``mappers``; the
    first that handles a file scans it.
    """

    def __init__(
        self,
        directory,
        pipeline,
        *,
        convert_stage=None,
        mappers=DEFAULT_MAPPERS,
        audio_settings=None,
        video_settings=None,
    ):
        self.directory = directory
        self.pipeline = pipeline
        # The pipeline's CONVERT stage, used directly for the media-compression
        # pass. The constructing handler is itself a CONVERT-stage child, so it
        # hands its own parent down rather than have us rediscover it.
        self.convert_stage = convert_stage
        self.mappers = mappers
        self.audio_settings = audio_settings or {}
        self.video_settings = video_settings or {}
        # Fetched URL -> pipeline output path (None on failure): fetch each URL
        # once and terminate cycles in downloaded CSS.
        self.visited = {}

    @property
    def media_extensions(self):
        """Extensions the convert stage recompresses without changing the container.

        Read off the CONVERT stage's own media handlers — the single source of
        truth for which containers they keep in place — rather than a separate
        hardcoded list. A file the stage would re-encode to a new extension
        (e.g. gif -> png), breaking references to it, declares no such set and is
        left untouched.
        """
        extensions = set()
        for handler in getattr(self.convert_stage, "_children", []):
            extensions |= getattr(handler, "SUPPORTED_VIDEO_EXTS", set())
            extensions |= getattr(handler, "SUPPORTED_AUDIO_EXTS", set())
        return extensions

    def process(self):
        """Download external refs, then compress media, in place."""
        self._download_external_refs()
        if self.audio_settings or self.video_settings:
            self._compress_media()

    def _walk_files(self):
        for root, _dirs, files in os.walk(self.directory):
            for name in files:
                yield os.path.join(root, name)

    # -- pass 1: external references -------------------------------------

    def _download_external_refs(self):
        """Reference-led walk: fetch every external ref so it resolves offline."""
        self.worklist = deque()
        for abspath in self._walk_files():
            mapper = self._mapper_for(abspath)
            if mapper is not None:
                self.worklist.append((abspath, mapper))
        while self.worklist:
            source_path, mapper = self.worklist.popleft()
            self._process_file(source_path, mapper)

    def _mapper_for(self, abspath):
        """Return the first mapper that handles ``abspath``, or ``None``.

        Mappers match on the archive-relative path, so path-keyed mappers such as
        H5P's ``content/content.json`` resolve correctly.
        """
        rel_path = os.path.relpath(abspath, self.directory)
        for mapper in self.mappers:
            if mapper.handles(rel_path):
                return mapper
        return None

    def _process_file(self, source_path, mapper):
        """Download ``source_path``'s external refs and rewrite them in place."""
        try:
            with open(source_path, encoding="utf-8") as fh:
                content = fh.read()
        except (OSError, UnicodeDecodeError) as e:
            LOGGER.warning(
                "Could not read {} for ref scanning: {}".format(source_path, e)
            )
            return

        source_dir = os.path.dirname(source_path)
        rewrote = False

        def localize(ref):
            nonlocal rewrote
            if not is_external_url(ref):
                return ref
            asset_path = self._fetch_into(ref, source_dir)
            if asset_path is None:
                return ref
            rewrote = True
            return os.path.relpath(asset_path, source_dir).replace(os.sep, "/")

        rewritten, _urls = mapper.map(content, localize)
        # Only write back when a download replaced a reference.
        if rewrote:
            with open(source_path, "w", encoding="utf-8") as fh:
                fh.write(rewritten)

    def _fetch_into(self, url, source_dir):
        """Fetch ``url`` through the pipeline and copy it into ``source_dir``.

        Returns the copied asset's path, or ``None`` on failure. A newly fetched
        asset a mapper handles (e.g. a ``.css`` file) is enqueued so its own
        references resolve recursively; the ``visited`` guard stops cycles.
        """
        newly_fetched = url not in self.visited
        if newly_fetched:
            self.visited[url] = self._run_pipeline(url)
        output_path = self.visited[url]
        if output_path is None:
            return None

        asset_path = os.path.join(source_dir, os.path.basename(output_path))
        if not os.path.exists(asset_path):
            shutil.copyfile(output_path, asset_path)

        if newly_fetched:
            mapper = self._mapper_for(asset_path)
            if mapper is not None:
                self.worklist.append((asset_path, mapper))
        return asset_path

    def _run_pipeline(self, url):
        """Run ``url`` through the pipeline; return its output path or ``None``."""
        # Download handlers key off a URL scheme; a protocol-relative ref (//host/x)
        # has none, so default it to https.
        fetch_url = "https:" + url if url.startswith("//") else url
        try:
            results = self.pipeline.execute(fetch_url)
        except (InvalidFileException, ExpectedFileException) as e:
            LOGGER.warning(
                "Could not download external resource, leaving reference unrewritten: {} ({})".format(
                    url, e
                )
            )
            return None
        # The last stage's output is the fully processed file.
        return results[-1].path if results else None

    # -- pass 2: media compression --------------------------------------

    def _compress_media(self):
        """Scoped conversion pass: recompress every media file in place."""
        if self.convert_stage is None:
            return
        media_extensions = self.media_extensions
        for abspath in self._walk_files():
            try:
                ext = extract_path_ext(abspath)
            except ValueError:
                continue
            if ext not in media_extensions:
                continue
            results = self.convert_stage.execute(
                abspath,
                context={
                    "audio_settings": self.audio_settings,
                    "video_settings": self.video_settings,
                },
                skip_cache=True,
            )
            # An untouched file keeps its path; otherwise copy the compressed
            # output back over the original so references to it stay valid.
            output_path = results[0].path if results else abspath
            if os.path.abspath(output_path) != os.path.abspath(abspath):
                shutil.copyfile(output_path, abspath)
