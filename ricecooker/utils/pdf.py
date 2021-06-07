import os
import subprocess

from tempfile import mkstemp
from ricecooker.utils.downloader import read


# pdftk output keys for parsing control simplicity
BOOKMARK_BEGIN = "BookmarkBegin"
LAST_BOOKMARK_BEGIN = "PageMediaBegin"
TITLE = "BookmarkTitle"
LEVEL = "BookmarkLevel"
PAGE_START = "BookmarkPageNumber"
NUM_OF_PAGES = "NumberOfPages"


def get_pdftk_line_value(line):
    """
    Returns everything right of the : in the given line. Useful for getting the value
    for a key in pdftk dump_data* output
    :param line:string
    :return:string
    """
    # Get everything right of the : sans spaces and newlines and quotes
    return line.split(":")[-1].strip(" \n")


class PDFParser(object):
    """
    Helper class for extracting table of contents and splitting PDFs into chapters.
    """

    path = None  # Local path to source PDF document that will be processed

    def __init__(self, source_path, directory="downloads"):
        self.directory = directory
        self.source_path = source_path
        self.toc_subchapters = None
        self.toc = None

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
        self.pdftk_dump_data = self._pdftk_dump_data()

    def close(self):
        """
        Close main pdf file when done.
        """
        self.file.close()  # Make sure zipfile closes no matter what

    def number_of_pages(self):
        """
        Returns the number of pages in the document
        """
        x = int(
            get_pdftk_line_value(
                # Find the line where the # of pages is defined
                next(line for line in self.pdftk_dump_data if NUM_OF_PAGES in line)
            )
        )
        return x

    def check_path(self):
        if not self.path:
            raise ValueError("self.path not found; call `open` first")

    def get_toc(self, subchapters=False):
        # This function was reimplemented in the move from PyPDF2 to pdftk for
        # processing PDF files and extracting the bookmarks metadata.
        # PyPDF2 was 0-indexed
        # pdftk is 1-indexed - so you'll see some -1s going on in here to simplify
        # the transition so that PDFParser works just as it did before
        chapters = list()

        # Init a chapter dict with None for its values. Note: page_end isn't
        # initialized here because it is calculated later on
        def new_chapter():
            return {key: None for key in [TITLE, LEVEL, PAGE_START]}

        # Checks that given chapter does not have None in its values
        def chapter_is_completed(chapter):
            return None not in chapter.values()

        chapter = new_chapter()

        # The dump needs to be processed line-by-line to get chapter data
        for idx, line in enumerate(self.pdftk_dump_data):
            # If the line is BOOKMARK_BEGIN or LAST_BOOKMARK_BEGIN then we
            # are about to start building a new set of chapter data.
            if BOOKMARK_BEGIN in line or LAST_BOOKMARK_BEGIN in line:
                if chapter_is_completed(chapter):
                    parent_chapter = next(
                        (
                            c
                            for c in reversed(chapters)
                            if chapter[LEVEL] - c[LEVEL] == 1
                        ),
                        None,
                    )
                    if parent_chapter:
                        chapter["parent"] = parent_chapter["id"]
                    chapter["id"] = idx  # Used to simplify hierarchy lookups
                    chapters.append(dict(chapter))
                    chapter = new_chapter()
            elif NUM_OF_PAGES in line:
                num_of_pages = int(get_pdftk_line_value(line))
            elif TITLE in line:
                chapter[TITLE] = get_pdftk_line_value(line).replace("\xa0", " ")
            elif LEVEL in line:
                chapter[LEVEL] = int(get_pdftk_line_value(line))
            elif PAGE_START in line:
                # Accommodate with -1 change to pdftk from PyPDF2
                chapter[PAGE_START] = int(get_pdftk_line_value(line)) - 1

        flat_chapters = list()
        for idx, chapter in enumerate(chapters):

            def are_siblings(ch1, ch2):
                # Returns whether both items are root or are children of the same parent
                return (ch1[LEVEL] == 1 and ch2[LEVEL] == 1) or ch1.get(
                    "parent", True
                ) == ch2.get("parent", False)

            next_chapter_of_same_level = next(
                (c for c in list(chapters)[(idx + 1) :] if are_siblings(c, chapter)),
                None,
            )

            # Handle potential subchapters (or skip them)
            if chapter[LEVEL] > 1:
                if not subchapters:
                    continue

                # Check if this is the last subchapter in a level and its page_end is its parent's page_end
                if not next_chapter_of_same_level:
                    # parent_chapter is the most recent chapter added to flat_chapters that is 1 level up
                    # and if we're here it absolutely exists
                    parent_chapter = next(
                        (
                            c
                            for c in reversed(flat_chapters)
                            if chapter[LEVEL] - c[LEVEL] == 1
                        ),
                        None,
                    )
                    chapter["page_end"] = parent_chapter["page_end"]
                    flat_chapters.append(chapter)
                    continue

                # We're working with one of several children of the same level - the page end of this is
                # the PAGE_START of the next_chapter_of_same_level
                chapter["page_end"] = next_chapter_of_same_level[PAGE_START]
                flat_chapters.append(chapter)
            else:
                # For non-subchapters, the process is the same
                if not next_chapter_of_same_level:
                    # For the last chapter the page_end is the last page of the doc
                    chapter["page_end"] = num_of_pages
                else:
                    chapter["page_end"] = next_chapter_of_same_level[PAGE_START]
                flat_chapters.append(chapter)

        # Recursively takes the chapter data we built above and converts it to the dict
        # that this class's methods expect
        def chapter_to_toc(chapter):
            content = {
                "title": chapter[TITLE],
                "page_start": chapter[PAGE_START],
                "page_end": chapter["page_end"],  # for now
            }
            if subchapters:
                # Get this chapter's children - we'll prepare content for each of them recursively
                children = [
                    chapter_to_toc(c)
                    for c in flat_chapters
                    if c.get("parent") == chapter["id"]
                ]
                if len(children):
                    content["children"] = children
            return content

        # Get just the root bookmark chapters - we'll use these as a starting point
        root_chapters = [chapter for chapter in flat_chapters if chapter[LEVEL] == 1]
        toc = list()
        for chapter in root_chapters:
            toc.append(chapter_to_toc(chapter))

        return toc

    def write_pagerange(self, pagerange, prefix=""):
        """
        Save the subset of pages specified in `pagerange` (dict) as separate PDF.
        e.g. pagerange = {'title':'First chapter', 'page_start':0, 'page_end':5}
        """
        slug = "".join(
            [c for c in pagerange["title"].replace(" ", "-") if c.isalnum() or c == "-"]
        )
        write_to_path = os.path.sep.join(
            [self.directory, "{}{}.pdf".format(prefix, slug)]
        )
        pdftk_command = "pdftk A={} cat A{}-{} output {}".format(
            self.file.name,
            pagerange["page_start"] + 1,
            pagerange["page_end"],
            write_to_path,
        ).split(" ")
        subprocess.run(pdftk_command)
        print(write_to_path)
        print(pagerange)
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
                if first_subchapter["page_start"] - chpagerange["page_start"] > 1:
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

    def _pdftk_dump_data(self):
        """
        Runs pdftk dump_data_utf8 and puts it into tempfile. This method
        returns the contents of that file as a list via readlines()
        :param self:
        :return: list of lines from the pdftk dump_data_utf8 output
        """
        fptr, file_path = mkstemp()
        subprocess.run(["pdftk", self.file.name, "dump_data_utf8", "output", file_path])
        lines = list()
        with open(file_path) as f:
            lines = f.readlines()
        return lines
