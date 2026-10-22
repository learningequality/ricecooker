import os
import re
from tempfile import TemporaryDirectory

import pytest
from conftest import sample_path
from pypdf import PdfReader
from pypdf import PdfWriter
from pypdf.annotations import Link
from pypdf.annotations import Text
from pypdf.errors import PdfReadError
from pypdf.generic import DecodedStreamObject
from pypdf.generic import DictionaryObject
from pypdf.generic import IndirectObject
from pypdf.generic import NameObject
from pypdf.generic import NullObject

from ricecooker.utils.pdf import PDFParser  # SIT

# Fixtures
################################################################################


@pytest.fixture
def downloads_dir():
    with TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def doc1_with_toc_path():
    doc1_with_toc_path = os.path.join(
        "tests", "testcontent", "samples", "sample_doc_with_toc.pdf"
    )
    assert os.path.exists(doc1_with_toc_path), (
        "Error mising test file " + doc1_with_toc_path
    )
    return doc1_with_toc_path


@pytest.fixture
def doc2_with_toc_path():
    """
    A PDF with lots of chapters.
    """
    return sample_path("Beyond-Good-and-Evil-Galbraithcolor.pdf")


@pytest.fixture
def doc3_with_toc_path():
    """
    A Gutenberg textbook PDF with a chapter-subchapter structure.
    """
    return sample_path("41568-pdf.pdf")


# Chapters only
################################################################################


def test_get_toc(doc1_with_toc_path, downloads_dir):
    with PDFParser(doc1_with_toc_path, directory=downloads_dir) as pdfparser:
        chapters_toc = pdfparser.get_toc()
        for chapter_dict in chapters_toc:
            _check_pagerange_matches_title_len(chapter_dict)


def test_split_chapters(doc1_with_toc_path, downloads_dir):
    with PDFParser(doc1_with_toc_path, directory=downloads_dir) as pdfparser:
        chapters = pdfparser.split_chapters()
        # pprint(chapters)
        for chapter in chapters:
            chapter_path = chapter["path"]
            assert chapter_path.endswith(".pdf"), "wrong extension -- expected .pdf"
            assert os.path.exists(chapter_path), "missing split PDF file"
            _check_path_matches_title_len(chapter)


def test_split_chapters_have_no_acroform(doc1_with_toc_path, downloads_dir):
    with PDFParser(doc1_with_toc_path, directory=downloads_dir) as pdfparser:
        chapters = pdfparser.split_chapters()
    for chapter in chapters:
        with open(chapter["path"], "rb") as f:
            reader = PdfReader(f)
            assert "/AcroForm" not in reader.trailer["/Root"]
            assert "/NeedAppearances" not in reader.trailer["/Info"]


@pytest.mark.parametrize(
    "name", ["aes128_owner_password.pdf", "aes256_owner_password.pdf"]
)
def test_open_encrypted_pdf_fails(name, downloads_dir):
    with pytest.raises(PdfReadError):
        PDFParser(sample_path(name), directory=downloads_dir).open()


def _write_modified(
    src_path, tmp_path, startxref=None, prefix=b"", suffix=b"", replace=None
):
    with open(src_path, "rb") as f:
        data = f.read()
    if replace is not None:
        data = data.replace(*replace)
    if startxref is not None:
        match = list(re.finditer(rb"startxref\s+(\d+)", data))[-1]
        new = str(startxref(int(match.group(1)), len(data))).encode()
        data = data[: match.start(1)] + new + data[match.end(1) :]
    path = str(tmp_path / "modified.pdf")
    with open(path, "wb") as f:
        f.write(prefix + data + suffix)
    return path


@pytest.mark.parametrize(
    "modification",
    [
        {"startxref": lambda pos, size: pos - 1},
        {"startxref": lambda pos, size: pos + 1},
        {"prefix": b"\n"},
        {"prefix": b"x"},
        {"suffix": b"x" * 100 * 1024},
    ],
)
def test_open_with_slightly_malformed_pdf(
    doc1_with_toc_path, downloads_dir, tmp_path, modification
):
    path = _write_modified(doc1_with_toc_path, tmp_path, **modification)
    with PDFParser(doc1_with_toc_path, directory=downloads_dir) as pdfparser:
        expected_toc = pdfparser.get_toc()
    with PDFParser(path, directory=downloads_dir) as pdfparser:
        assert pdfparser.get_toc() == expected_toc


def test_open_with_distant_startxref_fails(doc3_with_toc_path, downloads_dir, tmp_path):
    path = _write_modified(
        doc3_with_toc_path, tmp_path, startxref=lambda pos, size: size // 2
    )
    with pytest.raises(PdfReadError):
        PDFParser(path, directory=downloads_dir).open()


def test_open_with_prev_zero_fails(doc3_with_toc_path, downloads_dir, tmp_path):
    with open(doc3_with_toc_path, "rb") as f:
        data = f.read()
    i = data.index(b"<<", data.rfind(b"trailer")) + 2
    path = str(tmp_path / "prev0.pdf")
    with open(path, "wb") as f:
        f.write(data[:i] + b" /Prev 0 " + data[i:])
    with pytest.raises(PdfReadError):
        PDFParser(path, directory=downloads_dir).open()


def test_open_with_overstated_xref_stream_size(
    doc1_with_toc_path, downloads_dir, tmp_path
):
    path = _write_modified(
        doc1_with_toc_path, tmp_path, replace=(b"/Size\n101/W", b"/Size\n150/W")
    )
    with PDFParser(doc1_with_toc_path, directory=downloads_dir) as pdfparser:
        expected_toc = pdfparser.get_toc()
    with PDFParser(path, directory=downloads_dir) as pdfparser:
        assert pdfparser.get_toc() == expected_toc
        assert len(pdfparser.split_chapters()) == len(expected_toc)


def test_get_toc_with_unknown_destination_type(
    doc2_with_toc_path, downloads_dir, tmp_path
):
    path = _write_modified(doc2_with_toc_path, tmp_path, replace=(b"/XYZ", b"/XYW"))
    with PDFParser(doc2_with_toc_path, directory=downloads_dir) as pdfparser:
        expected_toc = pdfparser.get_toc()
    with PDFParser(path, directory=downloads_dir) as pdfparser:
        assert pdfparser.get_toc() == expected_toc


def _make_pdf(num_pages, outline):
    writer = PdfWriter()
    for i in range(num_pages):
        page = writer.add_blank_page(100, 100)
        contents = DecodedStreamObject()
        contents.set_data("% marker-{}".format(i).encode())
        page.replace_contents(contents)
    items = [writer.add_outline_item(title, page) for title, page in outline]
    return writer, items


def _save_pdf(writer, tmp_path):
    path = str(tmp_path / "made.pdf")
    with open(path, "wb") as f:
        writer.write(f)
    return path


def test_split_chapters_excludes_linked_pages(downloads_dir, tmp_path):
    writer, _ = _make_pdf(4, [("A", 0), ("B", 2)])
    writer.add_annotation(0, Link(rect=(0, 0, 10, 10), target_page_index=3))
    writer.add_annotation(0, Text(rect=(20, 20, 30, 30), text="note"))
    path = _save_pdf(writer, tmp_path)
    with PDFParser(path, directory=downloads_dir) as pdfparser:
        chapters = pdfparser.split_chapters()
    with open(chapters[0]["path"], "rb") as f:
        data = f.read()
    assert b"marker-0" in data
    assert b"marker-3" not in data
    assert "/Annots" not in PdfReader(chapters[0]["path"]).pages[0]


def test_get_toc_skips_untitled_outline_entry(downloads_dir, tmp_path):
    writer, items = _make_pdf(6, [("A", 0), ("B", 2), ("C", 4)])
    del items[1].get_object()["/Title"]
    path = _save_pdf(writer, tmp_path)
    with PDFParser(path, directory=downloads_dir) as pdfparser:
        assert pdfparser.get_toc() == [
            {"title": "A", "page_start": 0, "page_end": 4},
            {"title": "C", "page_start": 4, "page_end": 6},
        ]


def test_get_toc_with_missing_outlines_object_is_empty(downloads_dir, tmp_path):
    writer, _items = _make_pdf(6, [("A", 0), ("B", 2)])
    writer.root_object[NameObject("/Outlines")] = IndirectObject(9999, 0, writer)
    path = _save_pdf(writer, tmp_path)
    with PDFParser(path, directory=downloads_dir) as pdfparser:
        assert pdfparser.get_toc() == []
        assert pdfparser.get_toc(subchapters=True) == []


def test_get_toc_skips_destination_outside_page_tree(downloads_dir, tmp_path):
    writer, items = _make_pdf(6, [("A", 0), ("B", 2), ("C", 4)])
    writer.add_outline_item("C.1", 4, parent=items[2])
    subitem = writer.add_outline_item("C.2", 5, parent=items[2])
    orphan = writer._add_object(
        DictionaryObject({NameObject("/Type"): NameObject("/Page")})
    )
    for item in (items[1], subitem):
        item.get_object()["/A"].get_object()["/D"][0] = orphan
    path = _save_pdf(writer, tmp_path)
    with PDFParser(path, directory=downloads_dir) as pdfparser:
        assert pdfparser.get_toc() == [
            {"title": "A", "page_start": 0, "page_end": 4},
            {"title": "C", "page_start": 4, "page_end": 6},
        ]
        assert pdfparser.get_toc(subchapters=True) == [
            {"title": "A", "page_start": 0, "page_end": 4, "children": []},
            {
                "title": "C",
                "page_start": 4,
                "page_end": 6,
                "children": [{"title": "C.1", "page_start": 4, "page_end": 6}],
            },
        ]
        assert len(pdfparser.split_chapters()) == 2


def test_get_toc_keeps_first_chapter_outside_page_tree(downloads_dir, tmp_path):
    writer, items = _make_pdf(4, [("A", 0), ("B", 2)])
    writer.add_outline_item("A.1", 1, parent=items[0])
    orphan = writer._add_object(
        DictionaryObject({NameObject("/Type"): NameObject("/Page")})
    )
    items[0].get_object()["/A"].get_object()["/D"][0] = orphan
    path = _save_pdf(writer, tmp_path)
    with PDFParser(path, directory=downloads_dir) as pdfparser:
        assert pdfparser.get_toc(subchapters=True) == [
            {
                "title": "A",
                "page_start": 0,
                "page_end": 2,
                "children": [{"title": "A.1", "page_start": 1, "page_end": 2}],
            },
            {"title": "B", "page_start": 2, "page_end": 4, "children": []},
        ]
        assert len(pdfparser.split_subchapters()) == 2


def test_get_toc_drops_children_of_unresolved_first_chapter(downloads_dir, tmp_path):
    writer, items = _make_pdf(4, [("A", 0), ("B", 2)])
    writer.add_outline_item("A.1", 1, parent=items[0])
    items[0].get_object()["/A"].get_object()["/D"][0] = NullObject()
    path = _save_pdf(writer, tmp_path)
    with PDFParser(path, directory=downloads_dir) as pdfparser:
        assert pdfparser.get_toc(subchapters=True) == [
            {"title": "B", "page_start": 0, "page_end": 4, "children": []},
        ]


def test_split_chapters_alt(doc1_with_toc_path, downloads_dir):
    with PDFParser(doc1_with_toc_path, directory=downloads_dir) as pdfparser:
        chapters_toc = pdfparser.get_toc()
        chapters = pdfparser.split_chapters(jsondata=chapters_toc)
        # pprint(chapters)
        for chapter in chapters:
            chapter_path = chapter["path"]
            assert chapter_path.endswith(".pdf"), "wrong extension -- expected .pdf"
            assert os.path.exists(chapter_path), "missing split PDF file"
            _check_path_matches_title_len(chapter)


def test_split_chapters2(doc2_with_toc_path, downloads_dir):
    with PDFParser(doc2_with_toc_path, directory=downloads_dir) as pdfparser:
        chapters = pdfparser.split_chapters()
        # pprint(chapters)
        for chapter in chapters:
            chapter_path = chapter["path"]
            assert chapter_path.endswith(".pdf"), "wrong extension -- expected .pdf"
            assert os.path.exists(chapter_path), "missing split PDF file"
        #
        assert _get_pdf_len(chapters[0]) == 2, "wrong length for ch " + str(chapters[0])
        assert _get_pdf_len(chapters[1]) == 2, "wrong length for ch " + str(chapters[1])
        assert _get_pdf_len(chapters[2]) == 4, "wrong length for ch " + str(chapters[2])
        assert _get_pdf_len(chapters[3]) == 21, "wrong length for ch " + str(
            chapters[3]
        )
        assert _get_pdf_len(chapters[4]) == 19, "wrong length for ch " + str(
            chapters[4]
        )
        assert _get_pdf_len(chapters[5]) == 16, "wrong length for ch " + str(
            chapters[5]
        )
        assert _get_pdf_len(chapters[6]) == 9, "wrong length for ch " + str(chapters[6])
        assert _get_pdf_len(chapters[7]) == 21, "wrong length for ch " + str(
            chapters[7]
        )
        assert _get_pdf_len(chapters[8]) == 18, "wrong length for ch " + str(
            chapters[8]
        )
        assert _get_pdf_len(chapters[9]) == 23, "wrong length for ch " + str(
            chapters[9]
        )
        assert _get_pdf_len(chapters[10]) == 23, "wrong length for ch " + str(
            chapters[10]
        )
        assert _get_pdf_len(chapters[11]) == 30, "wrong length for ch " + str(
            chapters[11]
        )
        assert _get_pdf_len(chapters[12]) == 4, "wrong length for ch " + str(
            chapters[12]
        )


def test_split_chapters3(doc3_with_toc_path, downloads_dir):
    # print(doc3_with_toc_path)
    with PDFParser(doc3_with_toc_path, directory=downloads_dir) as pdfparser:
        chapters = pdfparser.split_chapters()
        # pprint(chapters)
        for chapter in chapters:
            chapter_path = chapter["path"]
            assert chapter_path.endswith(".pdf"), "wrong extension -- expected .pdf"
            assert os.path.exists(chapter_path), "missing split PDF file"
            assert _get_pdf_len(chapters[0]) == 1, "wrong length for ch " + str(
                chapters[0]
            )
            assert _get_pdf_len(chapters[1]) == 1, "wrong length for ch " + str(
                chapters[1]
            )
            assert _get_pdf_len(chapters[2]) == 2, "wrong length for ch " + str(
                chapters[2]
            )
            assert _get_pdf_len(chapters[3]) == 206, "wrong length for ch " + str(
                chapters[3]
            )
            assert _get_pdf_len(chapters[4]) == 9, "wrong length for ch " + str(
                chapters[4]
            )
            assert _get_pdf_len(chapters[5]) == 9, "wrong length for ch " + str(
                chapters[5]
            )
            # print('assert _get_pdf_len(chapters[]) ==', str(_get_pdf_len(chapter))+', \'wrong length for ch \' + str(chapters[])')


# Chapters and subchapters
################################################################################


def test_get_toc_subchapters(doc1_with_toc_path, downloads_dir):
    with PDFParser(doc1_with_toc_path, directory=downloads_dir) as pdfparser:
        chapters_toc = pdfparser.get_toc(subchapters=True)
        for chapter_dict in chapters_toc:
            if "children" in chapter_dict and chapter_dict["children"]:
                for subchapter_dict in chapter_dict["children"]:
                    _check_pagerange_matches_title_len(subchapter_dict)
            else:
                _check_pagerange_matches_title_len(chapter_dict)


def test_split_subchapters(doc1_with_toc_path, downloads_dir):
    with PDFParser(doc1_with_toc_path, directory=downloads_dir) as pdfparser:
        chapters = pdfparser.split_subchapters()
        # pprint(chapters)
        for ch in chapters[0:4]:
            assert "children" not in ch, "first four chapters have no subchapters..."
        assert _get_pdf_len(chapters[0]) == 1, "wrong num pages in " + str(chapters[0])
        assert _get_pdf_len(chapters[1]) == 1, "wrong num pages in " + str(chapters[1])
        assert _get_pdf_len(chapters[2]) == 2, "wrong num pages in " + str(chapters[2])
        assert _get_pdf_len(chapters[3]) == 3, "wrong num pages in " + str(chapters[3])

        ch4 = chapters[4]
        assert "children" in ch4, "no children"
        assert len(ch4["children"]) == 2
        assert _get_pdf_len(ch4["children"][0]) == 1, "wrong num pages in " + str(
            ch4["children"][0]
        )
        assert _get_pdf_len(ch4["children"][1]) == 1, "wrong num pages in " + str(
            ch4["children"][1]
        )

        ch5 = chapters[5]
        assert "children" in ch5, "no children"
        assert len(ch5["children"]) == 3
        assert _get_pdf_len(ch5["children"][0]) == 1, "wrong num pages in " + str(
            ch5["children"][0]
        )
        assert _get_pdf_len(ch5["children"][1]) == 1, "wrong num pages in " + str(
            ch5["children"][1]
        )
        assert _get_pdf_len(ch5["children"][2]) == 1, "wrong num pages in " + str(
            ch5["children"][2]
        )


def test_split_subchapters3(doc3_with_toc_path, downloads_dir):
    with PDFParser(doc3_with_toc_path, directory=downloads_dir) as pdfparser:
        chapters = pdfparser.split_subchapters()
        ch3 = chapters[3]
        assert "children" in ch3, "no subchapters found in  ch3"
        assert len(ch3["children"]) == 17, "wrong number of subchapters"
        subchs = ch3["children"]
        assert _get_pdf_len(subchs[0]) == 6, "wrong length for subch " + str(subchs[0])
        assert _get_pdf_len(subchs[1]) == 8, "wrong length for subch " + str(subchs[1])
        assert _get_pdf_len(subchs[2]) == 14, "wrong length for subch " + str(subchs[2])
        assert _get_pdf_len(subchs[3]) == 14, "wrong length for subch " + str(subchs[3])
        assert _get_pdf_len(subchs[4]) == 11, "wrong length for subch " + str(subchs[4])
        assert _get_pdf_len(subchs[5]) == 13, "wrong length for subch " + str(subchs[5])
        assert _get_pdf_len(subchs[6]) == 13, "wrong length for subch " + str(subchs[6])
        assert _get_pdf_len(subchs[7]) == 10, "wrong length for subch " + str(subchs[7])
        assert _get_pdf_len(subchs[8]) == 13, "wrong length for subch " + str(subchs[8])
        assert _get_pdf_len(subchs[9]) == 15, "wrong length for subch " + str(subchs[9])
        assert _get_pdf_len(subchs[10]) == 16, "wrong length for subch " + str(
            subchs[10]
        )
        assert _get_pdf_len(subchs[11]) == 7, "wrong length for subch " + str(
            subchs[11]
        )
        assert _get_pdf_len(subchs[12]) == 18, "wrong length for subch " + str(
            subchs[12]
        )
        assert _get_pdf_len(subchs[13]) == 20, "wrong length for subch " + str(
            subchs[13]
        )
        assert _get_pdf_len(subchs[14]) == 15, "wrong length for subch " + str(
            subchs[14]
        )
        assert _get_pdf_len(subchs[15]) == 8, "wrong length for subch " + str(
            subchs[15]
        )
        assert _get_pdf_len(subchs[16]) == 5, "wrong length for subch " + str(
            subchs[16]
        )


# Test helpers
################################################################################


def _get_pdf_len(str_or_dict_with_path_attr):
    if isinstance(str_or_dict_with_path_attr, str):
        path = str_or_dict_with_path_attr
    else:
        path = str_or_dict_with_path_attr["path"]
    with open(path, "rb") as pdffile:
        pdf = PdfReader(pdffile)
        return len(pdf.pages)


def _check_pagerange_matches_title_len(pagerange):
    # print(chapter_dict)
    title = pagerange["title"]
    m = re.search(r"\(len=(?P<len>\d*)\)", title)
    assert m, "no len=?? found in title"
    len_expected = int(m.groupdict()["len"])
    len_observed = pagerange["page_end"] - pagerange["page_start"]
    assert len_observed == len_expected, "Wrong page_range len detected in " + str(
        pagerange
    )


def _check_path_matches_title_len(chapter_dict):
    # print(chapter_dict)
    title = chapter_dict["title"]
    m = re.search(r"\(len=(?P<len>\d*)\)", title)
    assert m, "no len=?? found in title"
    len_expected = int(m.groupdict()["len"])
    len_observed = _get_pdf_len(chapter_dict["path"])
    assert len_observed == len_expected, "Wrong len detected in " + str(chapter_dict)
