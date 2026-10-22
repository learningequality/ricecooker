import os

from pypdf import PdfReader
from pypdf import PdfWriter
from pypdf.errors import LimitReachedError
from pypdf.errors import PdfReadError
from pypdf.generic import Destination
from pypdf.generic import Fit
from pypdf.generic import NullObject

from ricecooker.utils.pipeline.transfer import read


class CustomPDFReader(PdfReader):
    def _handle_encryption(self, password):
        # PyPDF2 1.28.6 did not decrypt with the empty user password
        raise PdfReadError("file has not been decrypted")

    def _basic_validation(self, stream):
        # PyPDF2 1.26 had no %PDF- header check
        stream.seek(0, os.SEEK_END)

    @staticmethod
    def _get_xref_issues(stream, startxref):
        # PyPDF2 1.26's startxref handling: no pre-check, so no full-file xref rebuild
        return 0

    def _sanitize_pdf15_xref_stream_index_pairs(
        self, index_pairs, entry_sizes, xref_stream
    ):
        try:
            return super()._sanitize_pdf15_xref_stream_index_pairs(
                index_pairs, entry_sizes, xref_stream
            )
        except LimitReachedError:
            # PyPDF2 1.28.6 read entries past the xref stream's data as free; strict pypdf raises, non-strict clamps the count
            self.strict = False
            try:
                return super()._sanitize_pdf15_xref_stream_index_pairs(
                    index_pairs, entry_sizes, xref_stream
                )
            finally:
                self.strict = True

    def _build_destination(self, title, array):
        try:
            return super()._build_destination(title, array)
        except PdfReadError:
            # Strict pypdf raises on an unknown fit type; ricecooker's PyPDF2 CustomDestination kept the entry
            return Destination(title, array[0], Fit.fit())

    def _build_outline_item(self, node):
        # PyPDF2 1.28.6 skipped outline entries without /Title; strict pypdf raises
        if "/Title" not in node:
            return None
        return super()._build_outline_item(node)

    @property
    def outline(self):
        # PyPDF2 1.28.6 returned an empty outline when the catalog's /Outlines object was missing
        if "/Outlines" in self.root_object:
            try:
                self.root_object["/Outlines"]
            except PdfReadError:
                return []
        return super().outline


class PDFParser(object):
    """
    Helper class for extracting table of contents and splitting PDFs into chapters.
    """

    path = None  # Local path to source PDF document that will be processed

    def __init__(self, source_path, directory="downloads"):
        self.directory = directory
        self.source_path = source_path

    def __enter__(self):
        """
        Called when opening context (e.g. `with PDFParser() as pdfparser: ...` )
        """
        self.open()
        return self

    def __exit__(self, type, value, traceback):
        """
        Called when closing context.
        """
        self.close()

    def open(self, update=False):
        """
        Opens pdf file to read from.
        """
        filename = os.path.basename(self.source_path)
        folder, _ext = os.path.splitext(filename)
        self.path = os.path.sep.join([self.directory, folder, filename])
        if not os.path.exists(os.path.dirname(self.path)):
            os.makedirs(os.path.dirname(self.path))

        # Download full pdf if it hasn't already been downloaded
        if not os.path.isfile(self.path) or update:
            with open(self.path, "wb") as fobj:
                fobj.write(read(self.source_path))

        self.file = open(self.path, "rb")
        try:
            self.pdf = CustomPDFReader(self.file, strict=True)
        except Exception:
            self.file.close()
            raise

    def close(self):
        """
        Close main pdf file when done.
        """
        self.file.close()  # Make sure zipfile closes no matter what

    def check_path(self):
        if not self.path:
            raise ValueError("self.path not found; call `open` first")

    def _get_page_number(self, dest, default=None):
        if not isinstance(dest, Destination) or isinstance(dest.page, NullObject):
            return None
        page_num = self.pdf.get_destination_page_number(dest)
        return default if page_num is None else page_num

    def get_toc(self, subchapters=False):  # noqa: C901
        """
        Returns table-of-contents information extracted from the PDF doc.
        When `subchapters=False`, the output is a list of this form

        .. code-block:: python

            [
                {'title': 'First chapter',  'page_start': 0,  'page_end': 10},
                {'title': 'Second chapter', 'page_start': 10, 'page_end': 20},
                ...
            ]

        Use the `split_chapters` method to process this list.
        When `subchapters=True`, the output is chapter-subchapter tree structure,
        that can be processed using the `split_subchapters` method.
        """
        self.check_path()
        chapters = []
        index = 0

        for dest in self.pdf.outline:
            page_num = self._get_page_number(dest, default=0 if index == 0 else None)
            # Process chapters
            if page_num is not None:
                chapter_pagerange = {
                    "title": dest["/Title"].replace("\xa0", " "),
                    "page_start": page_num if index != 0 else 0,
                    "page_end": len(self.pdf.pages),
                }
                if subchapters:
                    chapter_pagerange["children"] = []
                chapters.append(chapter_pagerange)

                if index > 0:
                    # Go back to previous chapter and set page_end
                    chapters[index - 1]["page_end"] = page_num
                    if subchapters:
                        previous_chapter = chapters[index - 1]
                        if previous_chapter["children"]:
                            # Go back to previous subchapter and set page_end
                            previous_chapter["children"][-1]["page_end"] = page_num
                index += 1

            # Attach subchapters (lists) as children to last chapter
            elif subchapters and isinstance(dest, list) and chapters:
                parent = chapters[index - 1]
                subindex = 0
                for subdest in dest:
                    subpage_num = self._get_page_number(subdest)
                    if subpage_num is not None:
                        parent["children"].append(
                            {
                                "title": subdest["/Title"].replace("\xa0", " "),
                                "page_start": subpage_num,
                                "page_end": len(self.pdf.pages),
                            }
                        )
                        if subindex > 0:
                            parent["children"][subindex - 1]["page_end"] = subpage_num
                        subindex += 1

        return chapters

    def write_pagerange(self, pagerange, prefix=""):
        """
        Save the subset of pages specified in `pagerange` (dict) as separate PDF.
        e.g. pagerange = {'title':'First chapter', 'page_start':0, 'page_end':5}
        """
        writer = PdfWriter()
        slug = "".join(
            [c for c in pagerange["title"].replace(" ", "-") if c.isalnum() or c == "-"]
        )
        write_to_path = os.path.sep.join(
            [self.directory, "{}{}.pdf".format(prefix, slug)]
        )
        for page in range(pagerange["page_start"], pagerange["page_end"]):
            writer.add_page(self.pdf.pages[page], excluded_keys=("/Annots",))
        with open(write_to_path, "wb") as outfile:
            writer.write(outfile)
        return write_to_path

    def split_chapters(self, jsondata=None, prefix=""):
        """
        Split the PDF doc into individual chapters based on the page-range info,
        storing individual split PDFs in the output folder `self.directory`.
        By default, we use the `self.get_toc()` to get the chapters page ranges.
        Pass in the page range dict `jsondata` to customize split points.
        """
        self.check_path()

        toc = jsondata or self.get_toc()
        chapters = []
        for index, chpagerange in enumerate(toc):
            newprefix = prefix + str(index) + "-"
            write_to_path = self.write_pagerange(chpagerange, prefix=newprefix)
            chapters.append({"title": chpagerange["title"], "path": write_to_path})
        return chapters

    def split_subchapters(self, jsondata=None):
        """
        Transform a PDF doc into tree of chapters (topics) and subchapters (docs)
        based on the page-range information obtained from the PDF table of contents
        or manually passed in through `jsondata`.
        Individual split PDFs are stored in the output folder `self.directory`.
        """
        self.check_path()

        toc = jsondata or self.get_toc(subchapters=True)
        chapters = []

        for index, chpagerange in enumerate(toc):
            # chapter prefix of the form 1-, 2-, 3-,... to avoid name conflicsts
            chprefix = str(index) + "-"
            # Case A: chapter with no subchapters
            if "children" not in chpagerange or not chpagerange["children"]:
                write_to_path = self.write_pagerange(chpagerange, prefix=chprefix)
                chapters.append({"title": chpagerange["title"], "path": write_to_path})

            # Case B: chapter with subchapters
            elif "children" in chpagerange:
                chapter_topic = {"title": chpagerange["title"], "children": []}
                subchpageranges = chpagerange["children"]
                first_subchapter = subchpageranges[0]

                # Handle case when chapter has "intro pages" before first subchapter
                if first_subchapter["page_start"] > chpagerange["page_start"]:
                    chintro_pagerange = {
                        "title": chpagerange["title"],
                        "page_start": chpagerange["page_start"],
                        "page_end": first_subchapter["page_start"],
                    }
                    write_to_path = self.write_pagerange(
                        chintro_pagerange, prefix=chprefix
                    )
                    chapter_topic["children"].append(
                        {"title": chpagerange["title"], "path": write_to_path}
                    )

                # Handle all subchapters
                subchapter_nodes = self.split_chapters(
                    jsondata=subchpageranges, prefix=chprefix
                )
                chapter_topic["children"].extend(subchapter_nodes)
                chapters.append(chapter_topic)

        return chapters
