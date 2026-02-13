"""
Tests for ricecooker.utils.url_utils — shared URL extraction and rewriting.

All tests operate on plain strings. No HTTP, no filesystem, no archives.
"""

import json

from ricecooker.utils.url_utils import (
    derive_local_filename,
    extract_urls_from_css,
    extract_urls_from_h5p_json,
    extract_urls_from_html,
    is_external_url,
    rewrite_urls_in_css,
    rewrite_urls_in_h5p_json,
    rewrite_urls_in_html,
)


# ---------------------------------------------------------------------------
# is_external_url tests
# ---------------------------------------------------------------------------


class TestIsExternalURL:
    def test_http_url(self):
        assert is_external_url("http://example.com/file.js") is True

    def test_https_url(self):
        assert is_external_url("https://example.com/file.js") is True

    def test_relative_path(self):
        assert is_external_url("images/photo.jpg") is False

    def test_data_uri(self):
        assert is_external_url("data:image/png;base64,abc123") is False

    def test_fragment_only(self):
        assert is_external_url("#section") is False

    def test_empty_string(self):
        assert is_external_url("") is False

    def test_protocol_relative(self):
        # //cdn.example.com/file.js — no scheme, so not classified as external
        assert is_external_url("//cdn.example.com/file.js") is False

    def test_mailto(self):
        assert is_external_url("mailto:user@example.com") is False

    def test_javascript_uri(self):
        assert is_external_url("javascript:void(0)") is False


# ---------------------------------------------------------------------------
# derive_local_filename tests
# ---------------------------------------------------------------------------


class TestDeriveLocalFilename:
    def test_simple_url(self):
        result = derive_local_filename("https://cdn.example.com/image.png")
        assert result == "_external/cdn.example.com/image.png"

    def test_url_with_subdirs(self):
        result = derive_local_filename(
            "https://fonts.example.com/v1/fonts/roboto.woff2"
        )
        assert result == "_external/fonts.example.com/v1/fonts/roboto.woff2"

    def test_url_with_query(self):
        result = derive_local_filename(
            "https://fonts.googleapis.com/css?family=Roboto"
        )
        assert result == "_external/fonts.googleapis.com/css?family=Roboto"

    def test_url_root_path(self):
        result = derive_local_filename("https://example.com/")
        assert result == "_external/example.com/"

    def test_starts_with_external_prefix(self):
        result = derive_local_filename("https://example.com/anything")
        assert result.startswith("_external/")

    def test_path_traversal_stripped(self):
        result = derive_local_filename("https://evil.com/../../../etc/passwd")
        assert ".." not in result
        assert result.startswith("_external/")
        assert "etc/passwd" in result

    def test_path_traversal_deep(self):
        result = derive_local_filename(
            "https://evil.com/a/../../b/../../../etc/passwd"
        )
        assert ".." not in result
        assert result.startswith("_external/")


# ---------------------------------------------------------------------------
# extract_urls_from_css tests
# ---------------------------------------------------------------------------


class TestExtractUrlsFromCSS:
    def test_extract_css_url_single_quotes(self):
        css = "body { background: url('https://example.com/bg.png') }"
        urls = extract_urls_from_css(css, "style.css")
        assert len(urls) == 1
        assert urls[0].url == "https://example.com/bg.png"
        assert urls[0].context == "css_url"
        assert urls[0].source_file == "style.css"

    def test_extract_css_url_double_quotes(self):
        css = 'body { background: url("https://example.com/bg.png") }'
        urls = extract_urls_from_css(css, "style.css")
        assert len(urls) == 1
        assert urls[0].url == "https://example.com/bg.png"

    def test_extract_css_url_no_quotes(self):
        css = "body { background: url(https://example.com/bg.png) }"
        urls = extract_urls_from_css(css, "style.css")
        assert len(urls) == 1
        assert urls[0].url == "https://example.com/bg.png"

    def test_extract_css_import_bare_string_single_quotes(self):
        css = "@import 'https://fonts.googleapis.com/css?family=Roboto';"
        urls = extract_urls_from_css(css, "style.css")
        assert len(urls) == 1
        assert urls[0].url == "https://fonts.googleapis.com/css?family=Roboto"
        assert urls[0].context == "css_import"

    def test_extract_css_import_bare_string_double_quotes(self):
        css = '@import "https://fonts.googleapis.com/css?family=Roboto";'
        urls = extract_urls_from_css(css, "style.css")
        assert len(urls) == 1
        assert urls[0].url == "https://fonts.googleapis.com/css?family=Roboto"

    def test_extract_css_import_url_form(self):
        """@import url('...') should be caught by the url() regex."""
        css = "@import url('https://fonts.googleapis.com/css');"
        urls = extract_urls_from_css(css, "style.css")
        assert len(urls) == 1
        assert urls[0].url == "https://fonts.googleapis.com/css"
        assert urls[0].context == "css_url"

    def test_extract_css_font_face(self):
        css = """
        @font-face {
            font-family: 'Roboto';
            src: url('https://fonts.example.com/roboto.woff2') format('woff2');
        }
        """
        urls = extract_urls_from_css(css, "style.css")
        assert len(urls) == 1
        assert urls[0].url == "https://fonts.example.com/roboto.woff2"

    def test_css_data_urls_ignored(self):
        css = "body { background: url(data:image/png;base64,abc123) }"
        urls = extract_urls_from_css(css, "style.css")
        assert len(urls) == 0

    def test_css_relative_urls_ignored(self):
        css = "body { background: url('../images/bg.png') }"
        urls = extract_urls_from_css(css, "style.css")
        assert len(urls) == 0

    def test_multiple_urls(self):
        css = """
        body { background: url('https://example.com/bg1.png') }
        .header { background: url('https://example.com/bg2.png') }
        """
        urls = extract_urls_from_css(css, "style.css")
        assert len(urls) == 2
        extracted_urls = {u.url for u in urls}
        assert "https://example.com/bg1.png" in extracted_urls
        assert "https://example.com/bg2.png" in extracted_urls

    def test_empty_css(self):
        urls = extract_urls_from_css("", "style.css")
        assert len(urls) == 0

    def test_no_duplicate_for_import_url_form(self):
        """@import url('...') should not produce duplicates from both regexes."""
        css = "@import url('https://fonts.googleapis.com/css');"
        urls = extract_urls_from_css(css, "style.css")
        assert len(urls) == 1


# ---------------------------------------------------------------------------
# extract_urls_from_html tests
# ---------------------------------------------------------------------------


class TestExtractUrlsFromHTML:
    def test_extract_img_src(self):
        html = '<img src="https://cdn.example.com/photo.jpg">'
        urls = extract_urls_from_html(html, "index.html")
        assert len(urls) == 1
        assert urls[0].url == "https://cdn.example.com/photo.jpg"
        assert urls[0].context == "html_attr"
        assert urls[0].tag == "img"
        assert urls[0].attr == "src"
        assert urls[0].source_file == "index.html"

    def test_extract_img_srcset(self):
        html = '<img srcset="https://cdn.example.com/img-300.jpg 300w, https://cdn.example.com/img-600.jpg 600w">'
        urls = extract_urls_from_html(html, "index.html")
        srcset_urls = [u for u in urls if u.context == "html_srcset"]
        assert len(srcset_urls) == 2
        extracted = {u.url for u in srcset_urls}
        assert "https://cdn.example.com/img-300.jpg" in extracted
        assert "https://cdn.example.com/img-600.jpg" in extracted

    def test_extract_img_srcset_mixed_relative_external(self):
        html = '<img srcset="img-300.jpg 300w, https://cdn.example.com/img-600.jpg 600w">'
        urls = extract_urls_from_html(html, "index.html")
        srcset_urls = [u for u in urls if u.context == "html_srcset"]
        assert len(srcset_urls) == 1
        assert srcset_urls[0].url == "https://cdn.example.com/img-600.jpg"

    def test_extract_link_stylesheet(self):
        html = '<link rel="stylesheet" href="https://fonts.googleapis.com/css">'
        urls = extract_urls_from_html(html, "index.html")
        assert len(urls) == 1
        assert urls[0].url == "https://fonts.googleapis.com/css"
        assert urls[0].tag == "link"
        assert urls[0].attr == "href"

    def test_extract_link_non_stylesheet_ignored(self):
        html = '<link rel="icon" href="https://example.com/favicon.ico">'
        urls = extract_urls_from_html(html, "index.html")
        assert len(urls) == 0

    def test_extract_script_src(self):
        html = '<script src="https://cdn.example.com/lib.js"></script>'
        urls = extract_urls_from_html(html, "index.html")
        assert len(urls) == 1
        assert urls[0].url == "https://cdn.example.com/lib.js"
        assert urls[0].tag == "script"

    def test_extract_source_src(self):
        html = '<source src="https://example.com/video.mp4" type="video/mp4">'
        urls = extract_urls_from_html(html, "index.html")
        assert len(urls) == 1
        assert urls[0].url == "https://example.com/video.mp4"
        assert urls[0].tag == "source"

    def test_extract_source_srcset(self):
        html = '<source srcset="https://example.com/img-lg.jpg 1024w">'
        urls = extract_urls_from_html(html, "index.html")
        srcset_urls = [u for u in urls if u.context == "html_srcset"]
        assert len(srcset_urls) == 1
        assert srcset_urls[0].url == "https://example.com/img-lg.jpg"

    def test_extract_background_image(self):
        html = """<div style="background-image: url('https://example.com/bg.png')">text</div>"""
        urls = extract_urls_from_html(html, "index.html")
        css_urls = [u for u in urls if u.context == "css_url"]
        assert len(css_urls) == 1
        assert css_urls[0].url == "https://example.com/bg.png"

    def test_extract_style_block(self):
        html = """
        <html><head>
        <style>body { background: url('https://example.com/bg.png') }</style>
        </head><body></body></html>
        """
        urls = extract_urls_from_html(html, "index.html")
        assert len(urls) == 1
        assert urls[0].url == "https://example.com/bg.png"

    def test_relative_urls_ignored(self):
        html = '<img src="images/photo.jpg"><script src="js/app.js"></script>'
        urls = extract_urls_from_html(html, "index.html")
        assert len(urls) == 0

    def test_data_urls_ignored(self):
        html = '<img src="data:image/png;base64,abc123">'
        urls = extract_urls_from_html(html, "index.html")
        assert len(urls) == 0

    def test_empty_html(self):
        urls = extract_urls_from_html("", "index.html")
        assert len(urls) == 0

    def test_minimal_html(self):
        urls = extract_urls_from_html("<html><body></body></html>", "index.html")
        assert len(urls) == 0

    def test_multiple_elements(self):
        html = """
        <html><body>
        <img src="https://cdn.example.com/img1.jpg">
        <img src="https://cdn.example.com/img2.jpg">
        <script src="https://cdn.example.com/app.js"></script>
        </body></html>
        """
        urls = extract_urls_from_html(html, "index.html")
        assert len(urls) == 3
        extracted = {u.url for u in urls}
        assert "https://cdn.example.com/img1.jpg" in extracted
        assert "https://cdn.example.com/img2.jpg" in extracted
        assert "https://cdn.example.com/app.js" in extracted


# ---------------------------------------------------------------------------
# extract_urls_from_h5p_json tests
# ---------------------------------------------------------------------------


class TestExtractUrlsFromH5PJSON:
    def test_extract_external_path(self):
        data = json.dumps(
            {
                "video": {
                    "files": [
                        {"path": "https://h5p.org/sites/default/files/h5p/iv.mp4"}
                    ]
                }
            }
        )
        urls = extract_urls_from_h5p_json(data, "content.json")
        assert len(urls) == 1
        assert urls[0].url == "https://h5p.org/sites/default/files/h5p/iv.mp4"
        assert urls[0].context == "h5p_json"
        assert urls[0].source_file == "content.json"

    def test_relative_path_ignored(self):
        data = json.dumps({"image": {"path": "images/photo.jpg"}})
        urls = extract_urls_from_h5p_json(data, "content.json")
        assert len(urls) == 0

    def test_deeply_nested(self):
        data = json.dumps(
            {
                "level1": {
                    "level2": {
                        "level3": [
                            {
                                "path": "https://cdn.example.com/deep/resource.mp4"
                            }
                        ]
                    }
                }
            }
        )
        urls = extract_urls_from_h5p_json(data, "content.json")
        assert len(urls) == 1
        assert urls[0].url == "https://cdn.example.com/deep/resource.mp4"

    def test_multiple_paths(self):
        data = json.dumps(
            {
                "video": {"path": "https://example.com/video.mp4"},
                "image": {"path": "https://example.com/image.jpg"},
                "local": {"path": "images/local.jpg"},
            }
        )
        urls = extract_urls_from_h5p_json(data, "content.json")
        assert len(urls) == 2
        extracted = {u.url for u in urls}
        assert "https://example.com/video.mp4" in extracted
        assert "https://example.com/image.jpg" in extracted

    def test_empty_json(self):
        urls = extract_urls_from_h5p_json("{}", "content.json")
        assert len(urls) == 0

    def test_non_string_path_ignored(self):
        data = json.dumps({"path": 42})
        urls = extract_urls_from_h5p_json(data, "content.json")
        assert len(urls) == 0


# ---------------------------------------------------------------------------
# rewrite_urls_in_css tests
# ---------------------------------------------------------------------------


class TestRewriteUrlsInCSS:
    def test_rewrite_url(self):
        css = "body { background: url('https://example.com/bg.png') }"
        url_map = {"https://example.com/bg.png": "_external/example.com/bg.png"}
        result = rewrite_urls_in_css(css, url_map)
        assert "url('_external/example.com/bg.png')" in result
        assert "https://example.com/bg.png" not in result

    def test_rewrite_import(self):
        css = "@import 'https://fonts.googleapis.com/css?family=Roboto';"
        url_map = {
            "https://fonts.googleapis.com/css?family=Roboto": "_external/fonts.googleapis.com/css"
        }
        result = rewrite_urls_in_css(css, url_map)
        assert "_external/fonts.googleapis.com/css" in result
        assert "https://fonts.googleapis.com/css?family=Roboto" not in result

    def test_rewrite_preserves_unmapped(self):
        css = """
        body { background: url('https://example.com/bg.png') }
        .other { background: url('https://other.com/bg.png') }
        """
        url_map = {"https://example.com/bg.png": "_external/example.com/bg.png"}
        result = rewrite_urls_in_css(css, url_map)
        assert "_external/example.com/bg.png" in result
        assert "https://other.com/bg.png" in result

    def test_rewrite_url_no_quotes(self):
        css = "body { background: url(https://example.com/bg.png) }"
        url_map = {"https://example.com/bg.png": "_external/example.com/bg.png"}
        result = rewrite_urls_in_css(css, url_map)
        assert "_external/example.com/bg.png" in result

    def test_empty_map(self):
        css = "body { background: url('https://example.com/bg.png') }"
        result = rewrite_urls_in_css(css, {})
        assert "https://example.com/bg.png" in result


# ---------------------------------------------------------------------------
# rewrite_urls_in_html tests
# ---------------------------------------------------------------------------


class TestRewriteUrlsInHTML:
    def test_rewrite_img_src(self):
        html = '<img src="https://cdn.example.com/photo.jpg">'
        url_map = {
            "https://cdn.example.com/photo.jpg": "_external/cdn.example.com/photo.jpg"
        }
        result = rewrite_urls_in_html(html, url_map)
        assert "_external/cdn.example.com/photo.jpg" in result
        assert "https://cdn.example.com/photo.jpg" not in result

    def test_rewrite_srcset(self):
        html = '<img srcset="https://cdn.example.com/img-300.jpg 300w, https://cdn.example.com/img-600.jpg 600w">'
        url_map = {
            "https://cdn.example.com/img-300.jpg": "_external/cdn.example.com/img-300.jpg",
            "https://cdn.example.com/img-600.jpg": "_external/cdn.example.com/img-600.jpg",
        }
        result = rewrite_urls_in_html(html, url_map)
        assert "_external/cdn.example.com/img-300.jpg" in result
        assert "_external/cdn.example.com/img-600.jpg" in result

    def test_rewrite_style_block(self):
        html = "<style>body { background: url('https://example.com/bg.png') }</style>"
        url_map = {"https://example.com/bg.png": "_external/example.com/bg.png"}
        result = rewrite_urls_in_html(html, url_map)
        assert "_external/example.com/bg.png" in result
        assert "https://example.com/bg.png" not in result

    def test_rewrite_inline_style(self):
        html = """<div style="background-image: url('https://example.com/bg.png')">text</div>"""
        url_map = {"https://example.com/bg.png": "_external/example.com/bg.png"}
        result = rewrite_urls_in_html(html, url_map)
        assert "_external/example.com/bg.png" in result

    def test_rewrite_preserves_unmapped(self):
        html = """
        <img src="https://cdn.example.com/img1.jpg">
        <img src="https://cdn.example.com/img2.jpg">
        """
        url_map = {
            "https://cdn.example.com/img1.jpg": "_external/cdn.example.com/img1.jpg"
        }
        result = rewrite_urls_in_html(html, url_map)
        assert "_external/cdn.example.com/img1.jpg" in result
        assert "https://cdn.example.com/img2.jpg" in result

    def test_rewrite_link_href(self):
        html = '<link rel="stylesheet" href="https://fonts.googleapis.com/css">'
        url_map = {
            "https://fonts.googleapis.com/css": "_external/fonts.googleapis.com/css"
        }
        result = rewrite_urls_in_html(html, url_map)
        assert "_external/fonts.googleapis.com/css" in result

    def test_rewrite_script_src(self):
        html = '<script src="https://cdn.example.com/lib.js"></script>'
        url_map = {
            "https://cdn.example.com/lib.js": "_external/cdn.example.com/lib.js"
        }
        result = rewrite_urls_in_html(html, url_map)
        assert "_external/cdn.example.com/lib.js" in result


# ---------------------------------------------------------------------------
# rewrite_urls_in_h5p_json tests
# ---------------------------------------------------------------------------


class TestRewriteUrlsInH5PJSON:
    def test_rewrite_path(self):
        data = json.dumps(
            {"video": {"path": "https://h5p.org/sites/default/files/h5p/iv.mp4"}}
        )
        url_map = {
            "https://h5p.org/sites/default/files/h5p/iv.mp4": "_external/h5p.org/sites/default/files/h5p/iv.mp4"
        }
        result = rewrite_urls_in_h5p_json(data, url_map)
        parsed = json.loads(result)
        assert (
            parsed["video"]["path"]
            == "_external/h5p.org/sites/default/files/h5p/iv.mp4"
        )

    def test_rewrite_preserves_unmapped(self):
        data = json.dumps(
            {
                "video": {"path": "https://example.com/video.mp4"},
                "image": {"path": "https://other.com/image.jpg"},
            }
        )
        url_map = {
            "https://example.com/video.mp4": "_external/example.com/video.mp4"
        }
        result = rewrite_urls_in_h5p_json(data, url_map)
        parsed = json.loads(result)
        assert parsed["video"]["path"] == "_external/example.com/video.mp4"
        assert parsed["image"]["path"] == "https://other.com/image.jpg"

    def test_rewrite_deeply_nested(self):
        data = json.dumps(
            {
                "a": {
                    "b": [{"path": "https://example.com/deep.mp4"}]
                }
            }
        )
        url_map = {
            "https://example.com/deep.mp4": "_external/example.com/deep.mp4"
        }
        result = rewrite_urls_in_h5p_json(data, url_map)
        parsed = json.loads(result)
        assert parsed["a"]["b"][0]["path"] == "_external/example.com/deep.mp4"

    def test_rewrite_relative_path_unchanged(self):
        data = json.dumps({"image": {"path": "images/photo.jpg"}})
        url_map = {
            "https://example.com/video.mp4": "_external/example.com/video.mp4"
        }
        result = rewrite_urls_in_h5p_json(data, url_map)
        parsed = json.loads(result)
        assert parsed["image"]["path"] == "images/photo.jpg"

    def test_empty_map(self):
        data = json.dumps({"video": {"path": "https://example.com/video.mp4"}})
        result = rewrite_urls_in_h5p_json(data, {})
        parsed = json.loads(result)
        assert parsed["video"]["path"] == "https://example.com/video.mp4"
