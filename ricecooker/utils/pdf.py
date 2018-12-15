import os
import tempfile

from PyPDF2 import PdfFileWriter, PdfFileReader
from PyPDF2.generic import Destination, NullObject
from PyPDF2.utils import PdfReadError
from utils.downloader import read


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
    path = None

    def __init__(self, url_or_path, directory="downloads"):
        self.directory = directory
        self.download_url = url_or_path

    def __enter__(self):
        """ Called when opening context (e.g. with HTMLWriter() as writer: ) """
        self.open()
        return self

    def __exit__(self, type, value, traceback):
        """ Called when closing context """
        self.close()


    def open(self):
        """ open: Opens pdf file to read from
            Args: None
            Returns: None
        """
        filename = os.path.basename(self.download_url)
        folder, _ext = os.path.splitext(filename)
        self.path = os.path.sep.join([self.directory, folder, filename])
        if not os.path.exists(os.path.dirname(self.path)):
            os.makedirs(os.path.dirname(self.path))

        # Download full pdf if it hasn't already been downloaded
        if not os.path.isfile(self.path):
            with open(self.path, "wb") as fobj:
                fobj.write(read(self.download_url))

        self.file = open(self.path, 'rb')
        self.pdf = CustomPDFReader(self.file)

    def close(self):
        """ close: Close main pdf file when done
            Args: None
            Returns: None
        """
        self.file.close() # Make sure zipfile closes no matter what

    def check_path(self):
        if not self.path:
            raise ImplementationError("Cannot read file: no path provided (must call `open`)")

    def get_toc(self):
        self.check_path()
        pages = []
        index = 0

        for dest in self.pdf.getOutlines():
            # Only factor in whole chapters, not subchapters (lists)
            if isinstance(dest, CustomDestination) and not isinstance(dest['/Page'], NullObject):
                page_num = self.pdf.getDestinationPageNumber(dest)
                pages.append({
                    "title": dest['/Title'].replace('\xa0', ' '),
                    "page_start": page_num if index != 0 else 0,
                    "page_end": self.pdf.numPages
                })

                # Go back to previous chapter and set page_end
                if index > 0:
                    pages[index - 1]["page_end"] = page_num
                index += 1

        return pages

    def split_chapters(self, jsondata=None):
        self.check_path()

        toc = jsondata or self.get_toc()
        directory = os.path.dirname(self.path)
        chapters = []
        for index, chapter in enumerate(toc):
            writer = PdfFileWriter()
            slug = "".join([c for c in chapter['title'].replace(" ", "-") if c.isalnum() or c == "-"])
            write_to_path = os.path.sep.join([directory, "{}.pdf".format(slug)])

            for page in range(chapter['page_start'], chapter['page_end']):
                writer.addPage(self.pdf.getPage(page))
                writer.removeLinks() # Must be done every page

            with open(write_to_path, 'wb') as outfile:

                writer.write(outfile)

            chapters.append({"title": chapter['title'], "path": write_to_path})

        return chapters
