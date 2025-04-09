import pytest

from ricecooker.utils.pipeline.transfer import (
    get_filename_from_content_disposition_header,
)


content_disposition_filename_cases = [
    ('Content-Disposition: attachment; filename="example.jpg"', "example.jpg"),
    (
        "Content-Disposition: attachment; filename*=UTF-8''%E4%BE%8B%E5%AD%90.jpg",
        "例子.jpg",
    ),
    ('Content-Disposition: inline; filename="document.pdf"', "document.pdf"),
    ("Content-Disposition: attachment; filename=plainfile.txt", "plainfile.txt"),
    (
        "Content-Disposition: attachment; filename*=UTF-8''%C3%A9l%C3%A9phant.jpg",
        "éléphant.jpg",
    ),
    ("Content-Disposition: attachment", None),
    (
        "Content-Disposition: attachment; filename=\"\"; filename*=UTF-8''%F0%9F%98%82.jpg",
        "😂.jpg",
    ),
    (
        "Content-Disposition: attachment; filename=\"EURO rates\"; filename*=utf-8''%E2%82%AC%20rates.txt",
        "€ rates.txt",
    ),
]


@pytest.mark.parametrize(
    "content_disposition, expected", content_disposition_filename_cases
)
def test_get_filename_from_content_disposition_header(content_disposition, expected):
    result = get_filename_from_content_disposition_header(content_disposition)
    assert (
        result == expected
    ), f"Failed on {content_disposition}: expected {expected}, got {result}"
