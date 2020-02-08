import copy
import os
from pprint import pprint
import pytest
import re
import requests
from tempfile import TemporaryDirectory

from PyPDF2 import PdfFileReader
from ricecooker.classes import nodes, files

from ricecooker.utils.pdf import PDFParser                                 # SIT



# Fixtures
################################################################################

@pytest.fixture
def downloads_dir():
    with TemporaryDirectory() as temp_dir:
        yield temp_dir

@pytest.fixture
def doc1_with_toc_path():
    doc1_with_toc_path = os.path.join('tests', 'testcontent', 'samples', 'sample_doc_with_toc.pdf')
    assert os.path.exists(doc1_with_toc_path), 'Error mising test file ' + doc1_with_toc_path
    return doc1_with_toc_path

def _save_file_url_to_path(url, path):
    if not os.path.exists(path):
        with open(path, 'wb') as f:
            resp = requests.get(url, stream=True)
            for chunk in resp.iter_content(chunk_size=1048576):
                f.write(chunk)
            f.flush()
    assert os.path.exists(path), 'Error mising test file ' + path

@pytest.fixture
def doc2_with_toc_path():
    """
    A PDF with lots of chapters.
    """
    doc2_with_toc_path = os.path.join('tests', 'testcontent', 'downloaded', 'Beyond-Good-and-Evil-Galbraithcolor.pdf')
    _save_file_url_to_path('https://s3-us-west-2.amazonaws.com/pressbooks-samplefiles/'
                           'GalbraithColorTheme/Beyond-Good-and-Evil-Galbraithcolor.pdf',
                            doc2_with_toc_path)
    assert os.path.exists(doc2_with_toc_path), 'Error mising test file ' + doc2_with_toc_path
    return doc2_with_toc_path


@pytest.fixture
def doc3_with_toc_path():
    """
    A Gutenberg textbook PDF with a chapter-subchapter structure.
    """
    doc3_with_toc_path = os.path.join('tests', 'testcontent', 'downloaded', '41568-pdf.pdf')
    _save_file_url_to_path('https://www.gutenberg.org/files/41568/41568-pdf.pdf',
                            doc3_with_toc_path)
    assert os.path.exists(doc3_with_toc_path), 'Error mising test file ' + doc3_with_toc_path
    return doc3_with_toc_path


# Chapters only
################################################################################

def test_get_toc(doc1_with_toc_path, downloads_dir):
    with PDFParser(doc1_with_toc_path, directory=downloads_dir)  as pdfparser:
        chapters_toc = pdfparser.get_toc()
        for chapter_dict in chapters_toc:
            _check_pagerange_matches_title_len(chapter_dict)

def test_split_chapters(doc1_with_toc_path, downloads_dir):
    with PDFParser(doc1_with_toc_path, directory=downloads_dir) as pdfparser:
        chapters = pdfparser.split_chapters()
        # pprint(chapters)
        for chapter in chapters:
            chapter_path = chapter['path']
            assert chapter_path.endswith('.pdf'), 'wrong extension -- expected .pdf'
            assert os.path.exists(chapter_path), 'missing split PDF file'
            _check_path_matches_title_len(chapter)

def test_split_chapters_alt(doc1_with_toc_path, downloads_dir):
    with PDFParser(doc1_with_toc_path, directory=downloads_dir) as pdfparser:
        chapters_toc = pdfparser.get_toc()
        chapters = pdfparser.split_chapters(jsondata=chapters_toc)
        # pprint(chapters)
        for chapter in chapters:
            chapter_path = chapter['path']
            assert chapter_path.endswith('.pdf'), 'wrong extension -- expected .pdf'
            assert os.path.exists(chapter_path), 'missing split PDF file'
            _check_path_matches_title_len(chapter)


def test_split_chapters2(doc2_with_toc_path, downloads_dir):
    with PDFParser(doc2_with_toc_path, directory=downloads_dir) as pdfparser:
        chapters = pdfparser.split_chapters()
        # pprint(chapters)
        for chapter in chapters:
            chapter_path = chapter['path']
            assert chapter_path.endswith('.pdf'), 'wrong extension -- expected .pdf'
            assert os.path.exists(chapter_path), 'missing split PDF file'
        #
        assert _get_pdf_len(chapters[0]) == 2, 'wrong length for ch ' + str(chapters[0])
        assert _get_pdf_len(chapters[1]) == 2, 'wrong length for ch ' + str(chapters[1])
        assert _get_pdf_len(chapters[2]) == 4, 'wrong length for ch ' + str(chapters[2])
        assert _get_pdf_len(chapters[3]) == 21, 'wrong length for ch ' + str(chapters[3])
        assert _get_pdf_len(chapters[4]) == 19, 'wrong length for ch ' + str(chapters[4])
        assert _get_pdf_len(chapters[5]) == 16, 'wrong length for ch ' + str(chapters[5])
        assert _get_pdf_len(chapters[6]) == 9,  'wrong length for ch ' + str(chapters[6])
        assert _get_pdf_len(chapters[7]) == 21, 'wrong length for ch ' + str(chapters[7])
        assert _get_pdf_len(chapters[8]) == 18, 'wrong length for ch ' + str(chapters[8])
        assert _get_pdf_len(chapters[9]) == 23,  'wrong length for ch ' + str(chapters[9])
        assert _get_pdf_len(chapters[10]) == 23, 'wrong length for ch ' + str(chapters[10])
        assert _get_pdf_len(chapters[11]) == 30, 'wrong length for ch ' + str(chapters[11])
        assert _get_pdf_len(chapters[12]) == 4,  'wrong length for ch ' + str(chapters[12])


def test_split_chapters3(doc3_with_toc_path, downloads_dir):
    # print(doc3_with_toc_path)
    with PDFParser(doc3_with_toc_path, directory=downloads_dir) as pdfparser:
        chapters = pdfparser.split_chapters()
        # pprint(chapters)
        for chapter in chapters:
            chapter_path = chapter['path']
            assert chapter_path.endswith('.pdf'), 'wrong extension -- expected .pdf'
            assert os.path.exists(chapter_path), 'missing split PDF file'
            assert _get_pdf_len(chapters[0]) == 1, 'wrong length for ch ' + str(chapters[0])
            assert _get_pdf_len(chapters[1]) == 1, 'wrong length for ch ' + str(chapters[1])
            assert _get_pdf_len(chapters[2]) == 2, 'wrong length for ch ' + str(chapters[2])
            assert _get_pdf_len(chapters[3]) == 206, 'wrong length for ch ' + str(chapters[3])
            assert _get_pdf_len(chapters[4]) == 9, 'wrong length for ch ' + str(chapters[4])
            assert _get_pdf_len(chapters[5]) == 9, 'wrong length for ch ' + str(chapters[5])
            # print('assert _get_pdf_len(chapters[]) ==', str(_get_pdf_len(chapter))+', \'wrong length for ch \' + str(chapters[])')


# Chapters and subchapters
################################################################################

def test_get_toc_subchapters(doc1_with_toc_path, downloads_dir):
    with PDFParser(doc1_with_toc_path, directory=downloads_dir) as pdfparser:
        chapters_toc = pdfparser.get_toc(subchapters=True)
        for chapter_dict in chapters_toc:
            if 'children' in chapter_dict and chapter_dict['children']:
                for subchapter_dict in chapter_dict['children']:
                    _check_pagerange_matches_title_len(subchapter_dict)
            else:
                _check_pagerange_matches_title_len(chapter_dict)


def test_split_subchapters(doc1_with_toc_path, downloads_dir):
    with PDFParser(doc1_with_toc_path, directory=downloads_dir) as pdfparser:
        chapters = pdfparser.split_subchapters()
        # pprint(chapters)
        for ch in chapters[0:4]:
            assert 'children' not in ch, 'first four chapters have no subchapters...'
        assert _get_pdf_len(chapters[0]) == 1, 'wrong num pages in ' + str(chapters[0])
        assert _get_pdf_len(chapters[1]) == 1, 'wrong num pages in ' + str(chapters[1])
        assert _get_pdf_len(chapters[2]) == 2, 'wrong num pages in ' + str(chapters[2])
        assert _get_pdf_len(chapters[3]) == 3, 'wrong num pages in ' + str(chapters[3])

        ch4 = chapters[4]
        assert 'children' in ch4, 'no children'
        assert len(ch4['children']) == 2
        assert _get_pdf_len(ch4['children'][0]) == 1, 'wrong num pages in ' + str(ch4['children'][0])
        assert _get_pdf_len(ch4['children'][1]) == 1, 'wrong num pages in ' + str(ch4['children'][1])

        ch5 = chapters[5]
        assert 'children' in ch5, 'no children'
        assert len(ch5['children']) == 3
        assert _get_pdf_len(ch5['children'][0]) == 1, 'wrong num pages in ' + str(ch5['children'][0])
        assert _get_pdf_len(ch5['children'][1]) == 1, 'wrong num pages in ' + str(ch5['children'][1])
        assert _get_pdf_len(ch5['children'][2]) == 1, 'wrong num pages in ' + str(ch5['children'][2])




def test_split_subchapters3(doc3_with_toc_path, downloads_dir):
    with PDFParser(doc3_with_toc_path, directory=downloads_dir) as pdfparser:
        chapters = pdfparser.split_subchapters()
        ch3 = chapters[3]
        assert 'children' in ch3, 'no subchapters found in  ch3'
        assert len(ch3['children']) == 17, 'wrong number of subchapters'
        subchs = ch3['children']
        assert _get_pdf_len(subchs[0]) == 6, 'wrong length for subch ' + str(subchs[0])
        assert _get_pdf_len(subchs[1]) == 8, 'wrong length for subch ' + str(subchs[1])
        assert _get_pdf_len(subchs[2]) == 14, 'wrong length for subch ' + str(subchs[2])
        assert _get_pdf_len(subchs[3]) == 14, 'wrong length for subch ' + str(subchs[3])
        assert _get_pdf_len(subchs[4]) == 11, 'wrong length for subch ' + str(subchs[4])
        assert _get_pdf_len(subchs[5]) == 13, 'wrong length for subch ' + str(subchs[5])
        assert _get_pdf_len(subchs[6]) == 13, 'wrong length for subch ' + str(subchs[6])
        assert _get_pdf_len(subchs[7]) == 10, 'wrong length for subch ' + str(subchs[7])
        assert _get_pdf_len(subchs[8]) == 13, 'wrong length for subch ' + str(subchs[8])
        assert _get_pdf_len(subchs[9]) == 15, 'wrong length for subch ' + str(subchs[9])
        assert _get_pdf_len(subchs[10]) == 16, 'wrong length for subch ' + str(subchs[10])
        assert _get_pdf_len(subchs[11]) == 7, 'wrong length for subch ' + str(subchs[11])
        assert _get_pdf_len(subchs[12]) == 18, 'wrong length for subch ' + str(subchs[12])
        assert _get_pdf_len(subchs[13]) == 20, 'wrong length for subch ' + str(subchs[13])
        assert _get_pdf_len(subchs[14]) == 15, 'wrong length for subch ' + str(subchs[14])
        assert _get_pdf_len(subchs[15]) == 8, 'wrong length for subch ' + str(subchs[15])
        assert _get_pdf_len(subchs[16]) == 5, 'wrong length for subch ' + str(subchs[16])


# Test helpers
################################################################################

def _get_pdf_len(str_or_dict_with_path_attr):
    if isinstance(str_or_dict_with_path_attr, str):
        path = str_or_dict_with_path_attr
    else:
        path = str_or_dict_with_path_attr['path']
    with open(path, 'rb') as pdffile:
        pdf = PdfFileReader(pdffile)
        return pdf.numPages


def _check_pagerange_matches_title_len(pagerange):
    # print(chapter_dict)
    title = pagerange['title']
    m = re.search(r'\(len=(?P<len>\d*)\)',  title)
    assert m, 'no len=?? found in title'
    len_expected = int(m.groupdict()['len'])
    len_observed = pagerange['page_end'] - pagerange['page_start']
    assert len_observed == len_expected, 'Wrong page_range len detected in ' + str(pagerange)

def _check_path_matches_title_len(chapter_dict):
    # print(chapter_dict)
    title = chapter_dict['title']
    m = re.search(r'\(len=(?P<len>\d*)\)',  title)
    assert m, 'no len=?? found in title'
    len_expected = int(m.groupdict()['len'])
    len_observed = _get_pdf_len(chapter_dict['path'])
    assert len_observed == len_expected, 'Wrong len detected in ' + str(chapter_dict)

