import os
import subprocess

from tempfile import NamedTemporaryFile
from PyPDF2 import PdfFileWriter, PdfFileReader
from PyPDF2.generic import Destination, NullObject
from PyPDF2.utils import PdfReadError
from ricecooker.utils.downloader import read


class CustomDestination(Destination):
    def __init__(self, title, page, typ, *args):
        try:
            super(CustomDestination, self).__init__(title, page, typ, *args)
        except PdfReadError:
            pass

class CustomPDFReader(PdfFileReader):
    def _buildDestination(self, title, array):
        page, typ = array[0:2]
        array = array[2:]
        return CustomDestination(title, page, typ, *array)


class PDFParser(object):
    """
    Helper class for extracting table of contents and splitting PDFs into chapters.
    """
    path = None       # Local path to source PDF document that will be processed

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

        self.file = open(self.path, 'rb')
        self.pdf = CustomPDFReader(self.file)

    def close(self):
        """
        Close main pdf file when done.
        """
        self.file.close() # Make sure zipfile closes no matter what

    def check_path(self):
        if not self.path:
            raise ValueError("self.path not found; call `open` first")

    def get_toc(self, subchapters=False):
        temp_file = NamedTemporaryFile()
        subprocess.run(["pdftk", self.file.name, "dump_data_utf8", "output", temp_file.name])

        # pdftk output keys for parsing control simplicity
        CHAPTER_DELIMITER = "BookmarkBegin"
        LAST_CHAPTER_DELIMITER = "PageMediaBegin"
        TITLE = "BookmarkTitle"
        LEVEL = "BookmarkLevel"
        PAGE_START = "BookmarkPageNumber"
        NUM_OF_PAGES = "NumberOfPages"

        def get_line_value(_line):
            # Get everything right of the : sans spaces and newlines and quotes
            return _line.split(":")[-1].strip(" \n")

        # Start by parsing each of the Bookmarks from the pdftk output into a
        # usable Python dictionary for further processing - this includes children
        chapters = []
        num_of_pages = None
        chapter = None
        for line in temp_file.readlines():
            line = line.decode('utf-8')

            # If we're at the delimiters, we're parsing a new chapter or we're done
            if CHAPTER_DELIMITER in line or LAST_CHAPTER_DELIMITER in line:
                # If we have chapter and we already filled it out - cast it to dict
                # to pass by value and not by reference to append() (shallow copy only)
                if chapter and None not in chapter.values():
                    chapters.append(dict(chapter))
                # No matter what, we should leave this by initializing chapter anew
                chapter = {key: None for key in [TITLE, LEVEL, PAGE_START]}
                continue
            elif NUM_OF_PAGES in line:
                num_of_pages = int(get_line_value(line))
            elif TITLE in line:
                chapter[TITLE] = get_line_value(line).replace("\xa0", " ")
            elif LEVEL in line:
                chapter[LEVEL] = int(get_line_value(line))
            elif PAGE_START in line:
                chapter[PAGE_START] = int(get_line_value(line)) - 1


        toc = []
        for idx, chapter in enumerate(chapters):
            if chapter[LEVEL] == 1:
                try:
                    # page_end is the start_page of the next chapter where it is level 1 (root node)
                    page_end = [ch for ch in chapters[idx+1:] if ch[LEVEL] == 1][0][PAGE_START]
                except (KeyError, IndexError):
                    # We got the `num_of_pages` variable for this exact reason - we're at the last
                    # chapter and it's last page is going to be this value
                    page_end = num_of_pages

                content = {
                    'title': chapter[TITLE],
                    'page_start': chapter[PAGE_START],
                    'page_end': page_end
                }
                toc.append(content)
            else:
                if not subchapters:
                    continue

                # We want to get the next child to help us get correct page numbers
                next_child = None
                try:
                    next_child = chapters[idx+1]
                except (KeyError, IndexError):
                    # We're not mad about it, just don't want to crash over it as
                    # the other acceptable value for next_child is None
                    pass

                # All items are in order - so the last in toc is the parent
                parent = toc[-1]

                if "children" not in parent:
                    parent["children"] = list()

                parent["children"].append(
                    {
                        'title': chapter[TITLE],
                        'page_start': chapter[PAGE_START],
                        # If there is not next_child, we're on the last item and page_end == page_start + 1
                        # - the +1 is because `page_end` refers to the page after you end.
                        'page_end': next_child and next_child[PAGE_START] or (chapter[PAGE_START] + 1)
                    }
                )

        toc[-1]['page_end'] = num_of_pages
        temp_file.close()
        return toc

    def get_old_toc(self, subchapters=False):
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

        for dest in self.pdf.getOutlines():

            # Process chapters
            if isinstance(dest, CustomDestination) and not isinstance(dest['/Page'], NullObject):
                page_num = self.pdf.getDestinationPageNumber(dest)
                chapter_pagerange = {
                    "title": dest['/Title'].replace('\xa0', ' '),
                    "page_start": page_num if index != 0 else 0,
                    "page_end": self.pdf.numPages,
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
            elif subchapters and isinstance(dest, list):
                parent = chapters[index - 1]
                subindex = 0
                for subdest in dest:
                    if isinstance(subdest, CustomDestination) and not isinstance(subdest['/Page'], NullObject):
                        subpage_num = self.pdf.getDestinationPageNumber(subdest)
                        parent['children'].append({
                            "title": subdest['/Title'].replace('\xa0', ' '),
                            "page_start": subpage_num,
                            "page_end": self.pdf.numPages
                        })
                        if subindex > 0:
                            parent['children'][subindex - 1]["page_end"] = subpage_num
                        subindex +=1

        return chapters

    def write_pagerange(self, pagerange, prefix=''):
        """
        Save the subset of pages specified in `pagerange` (dict) as separate PDF.
        e.g. pagerange = {'title':'First chapter', 'page_start':0, 'page_end':5}
        """
        writer = PdfFileWriter()
        slug = "".join([c for c in pagerange['title'].replace(" ", "-") if c.isalnum() or c == "-"])
        write_to_path = os.path.sep.join([self.directory, "{}{}.pdf".format(prefix, slug)])
        for page in range(pagerange['page_start'], pagerange['page_end']):
            writer.addPage(self.pdf.getPage(page))
            writer.removeLinks()                   # must be done every page
        with open(write_to_path, 'wb') as outfile:
            writer.write(outfile)
        return write_to_path


    def split_chapters(self, jsondata=None, prefix=''):
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
            newprefix = prefix + str(index) + '-'
            write_to_path = self.write_pagerange(chpagerange, prefix=newprefix)
            chapters.append({"title": chpagerange['title'], "path": write_to_path})
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
            chprefix = str(index) + '-'
            # Case A: chapter with no subchapters
            if 'children' not in chpagerange or not chpagerange['children']:
                write_to_path = self.write_pagerange(chpagerange, prefix=chprefix)
                chapters.append({"title": chpagerange['title'], "path": write_to_path})

            # Case B: chapter with subchapters
            elif 'children' in chpagerange:
                chapter_topic = { 'title': chpagerange['title'], 'children': [] }
                subchpageranges = chpagerange['children']
                first_subchapter = subchpageranges[0]

                # Handle case when chapter has "intro pages" before first subchapter
                if first_subchapter['page_start'] > chpagerange['page_start']:
                    chintro_pagerange = {
                        'title': chpagerange['title'],
                        'page_start': chpagerange['page_start'],
                        'page_end': first_subchapter['page_start']
                    }
                    write_to_path = self.write_pagerange(chintro_pagerange, prefix=chprefix)
                    chapter_topic['children'].append({"title": chpagerange['title'], "path": write_to_path})

                # Handle all subchapters
                subchapter_nodes = self.split_chapters(jsondata=subchpageranges, prefix=chprefix)
                chapter_topic['children'].extend(subchapter_nodes)
                chapters.append(chapter_topic)

        return chapters
