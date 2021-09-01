import os
import subprocess

from re import sub
from tempfile import mkstemp
from ricecooker.utils.downloader import read


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
        self.cpdf_output = self._cpdf_output()
        self.page_count = self._number_of_pages()

    def close(self):
        """
        Close main pdf file when done.
        """
        self.file.close()  # Make sure zipfile closes no matter what

    def _number_of_pages(self):
        """
        Returns the number of pages in the document
        """
        try:
            out = subprocess.run(
                ["cpdf", self.file.name, "-pages"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        except subprocess.CalledProcessError as e:
            print("Error: ", e.stderr.decode('utf8'))
            raise

        return int(out.stdout.decode('utf8').strip())


    def check_path(self):
        if not self.path:
            raise ValueError("self.path not found; call `open` first")

    def get_toc(self, subchapters=False):
        """
        Parses self.cpdf_output to generate list of Bookmarks where a
        Bookmark has a title, page_start, page_end and optionally children
        of that same form
        """

        chapters = list()
        for idx, line in enumerate(self.cpdf_output):
            try:
                if line:
                    level, title, page_start = line.split('"')[0:3]
                else:
                    continue
            except ValueError as e:
                print("Error splitting line ", line.split('"'), e)
                raise

            # Splitting this way makes it easy to get the data I want, but 
            # comes along with padded whitespace
            level = int(level.strip())
            # Sometimes this isn't only numbers - cpdf output is funky
            page_start = int(sub(r"[^0-9]", "", page_start)) - 1 

            # add all level 0 in any case, but everything if subchapters is True
            if level == 0 or subchapters:
                parent_chapter = next(
                    (
                        c
                        for c in reversed(chapters)
                        if level - c["level"] == 1
                    ),
                    None,
                )
                parent = None
                if parent_chapter:
                    parent = parent_chapter["id"]
                chapters.append({
                    "id": idx,
                    "title": title,
                    "level": level,
                    "page_start": page_start,
                    "parent": parent,
                })

        flat_chapters = list()
        for idx, chapter in enumerate(chapters):
            chapter["id"] = idx # simplifies hierarchy lookups
            def are_siblings(ch1, ch2):
                # Returns whether both items are root or are children of the same parent
                return (ch1["level"] == 0 and ch2["level"] == 0) or ch1.get(
                    "parent", True
                ) == ch2.get("parent", False)

            next_chapter_of_same_level = next(
                (c for c in list(chapters)[(idx + 1) :] if are_siblings(c, chapter)),
                None,
            )

            # Handle potential subchapters (or skip them)
            if chapter["level"] > 0:
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
                            if chapter["level"] - c["level"] == 1
                        ),
                        None,
                    ) or dict()
                    chapter["page_end"] = parent_chapter["page_end"]
                    flat_chapters.append(chapter)
                    continue

                # We're working with one of several children of the same level - the page end of this is
                # the page_start of the next_chapter_of_same_level
                chapter["page_end"] = next_chapter_of_same_level["page_start"]
                flat_chapters.append(chapter)

            else:
                # For non-subchapters, the process is the same
                if not next_chapter_of_same_level:
                    # For the last chapter the page_end is the last page of the doc
                    chapter["page_end"] = self.page_count
                else:
                    chapter["page_end"] = next_chapter_of_same_level["page_start"]
                flat_chapters.append(chapter)

        # Recursively takes the chapter data we built above and converts it to the dict
        # that this class's methods expect
        def chapter_to_toc(chapter):
            content = {
                "title": chapter["title"],
                "page_start": chapter["page_start"],
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
        root_chapters = [chapter for chapter in flat_chapters if chapter["level"] == 0]
        toc = list()
        for chapter in root_chapters:
            toc.append(chapter_to_toc(chapter))

        return toc


    def write_pagerange(self, pagerange, prefix=""):
        """
        Save the subset of pages specified in `pagerange` (dict) as separate PDF.
        e.g. pagerange = {"title": "First chapter", "page_start": 0, "page_end": 1 }
        """
        slug = "".join(
            [c for c in pagerange["title"].replace(" ","-") if c.isalnum() or c == "-"]
        )
        write_to_path = os.path.sep.join(
            [self.directory, "{}{}.pdf".format(prefix,slug)]
        )
        formatted_range = "{}-{}".format(pagerange["page_start"] + 1, pagerange["page_end"])
        command = ["cpdf", self.file.name, formatted_range, "-o", write_to_path]
        try:
            out = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            print("Error: ", e.stderr.decode('utf8'))
            raise
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

    def _cpdf_output(self):
        """
        Runs the cpdf command extracting utf-8 bookmarks
        :return: list of lines from cpdf -utf-8 -list-bookmarks output for self.file
        """
        try:
            out = subprocess.run(
                ["cpdf", self.file.name, "-utf8", "-list-bookmarks", "-stdout"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        except subprocess.CalledProcessError as e:
            print("Error: ", e.stderr.decode('utf8'))
            raise
        return out.stdout.decode('utf8').split("\n")

