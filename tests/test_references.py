"""Unit tests for ricecooker.utils.references.

Pure-function reference detection/rewriting over HTML and CSS strings — no
HTTP, no filesystem — so the pipeline's archive processor can reuse one
detector (supersedes #303; replaces the deleted downloader.py scraper tests).
"""

import unittest

from ricecooker.utils import references


class ReferencesExternalUrlAndCssTest(unittest.TestCase):
    """Task 1: pure-function URL filter + CSS extraction/rewriting utilities.

    These live in ricecooker.utils.references so the pipeline can reuse the
    detection logic without a live HTTP session (supersedes #303).
    """

    def test_is_external_url(self):
        self.assertTrue(references.is_external_url("https://x/a.png"))
        self.assertTrue(references.is_external_url("http://x/a.png"))
        self.assertTrue(references.is_external_url("//cdn/x.js"))
        self.assertFalse(references.is_external_url("images/a.png"))
        self.assertFalse(references.is_external_url("../a.css"))
        self.assertFalse(references.is_external_url("data:image/png;base64,AA"))
        self.assertFalse(references.is_external_url("#frag"))
        self.assertFalse(references.is_external_url(""))

    def test_extract_css_urls(self):
        css = "a{background:url('bg.png')} @import 'fonts/f.css'; b{src:url(https://h/x.woff2)}"
        self.assertEqual(
            references.CSSMapper().extract(css),
            ["bg.png", "fonts/f.css", "https://h/x.woff2"],
        )

    def test_rewrite_css_urls(self):
        css = "a{background:url('bg.png')} @import 'fonts/f.css'; b{src:url(https://h/x.woff2)}"
        rewritten = references.CSSMapper().rewrite(css, {"bg.png": "_static/1.png"})
        # The mapped url() now points at the local copy...
        self.assertIn("_static/1.png", rewritten)
        self.assertNotIn("bg.png", rewritten)
        # ...and the unmapped @import and remote url() are left untouched.
        self.assertIn("fonts/f.css", rewritten)
        self.assertIn("https://h/x.woff2", rewritten)


class ReferencesHtmlTest(unittest.TestCase):
    """Pure-function HTML extraction/rewriting utilities.

    Detects ``src`` (any element), stylesheet ``link[href]``, ``srcset``, inline
    ``style`` and ``<style>`` blocks — the same resource references kolibri-zip's
    ``DOMMapper`` does — but excludes the navigation ``<a href>`` / ``<iframe
    src>`` references, which are page links, not offline resources.
    """

    HTML = (
        "<html><head>"
        '<link rel="stylesheet" href="s.css">'
        '<link rel="canonical" href="https://site/page">'
        "<style>@import 'f.css';</style>"
        "</head><body>"
        '<img src="a.png">'
        '<img srcset="x-1.png 1x, x-2.png 2x">'
        '<script src="https://cdn/l.js"></script>'
        "<div style=\"background:url('bg.png')\"></div>"
        "</body></html>"
    )

    def test_extract_html_urls(self):
        urls = references.HTMLMapper().extract(self.HTML)
        # Exactly the resource references, canonical href omitted.
        self.assertIn("a.png", urls)
        self.assertIn("x-1.png", urls)
        self.assertIn("x-2.png", urls)
        self.assertIn("https://cdn/l.js", urls)
        self.assertIn("s.css", urls)
        self.assertIn("bg.png", urls)
        self.assertIn("f.css", urls)
        self.assertNotIn("https://site/page", urls)

    def test_rewrite_html_urls(self):
        rewritten = references.HTMLMapper().rewrite(
            self.HTML, {"a.png": "_static/a.png", "x-1.png": "_static/x1.png"}
        )
        # The two mapped refs point at the local copies...
        self.assertIn("_static/a.png", rewritten)
        self.assertIn("_static/x1.png", rewritten)
        # ...the srcset descriptor for the rewritten entry is preserved...
        self.assertIn("_static/x1.png 1x", rewritten)
        # ...and the untouched refs survive intact.
        self.assertIn("x-2.png 2x", rewritten)
        self.assertIn("https://cdn/l.js", rewritten)
        self.assertIn("s.css", rewritten)
        self.assertIn("https://site/page", rewritten)

    def test_rewrite_is_surgical(self):
        """Only matched reference spans change; everything else is byte-identical.

        Rewriting must not round-trip the document through a parser (which reflows
        whitespace, normalizes void/self-closing tags and re-encodes inline
        scripts, corrupting third-party HTML5 apps). It splices replacements over
        the matched spans and leaves every other byte untouched.
        """
        html = (
            "<!DOCTYPE html>\n"
            "<HTML><head>\n"
            '  <meta charset="utf-8">\n'
            '  <script>if (a<b && c>d) { x["k"]=1; }</script>\n'
            "</head><body>\n"
            '  <IMG src="https://ex.com/a.png" data-src="keep">\n'
            '  <a href="https://ex.com/page">nav</a>\n'
            "  <br>\n"
            "</body></HTML>\n"
        )
        rewritten = references.HTMLMapper().rewrite(
            html, {"https://ex.com/a.png": "a.png"}
        )
        # Only the img src changed.
        self.assertIn('src="a.png"', rewritten)
        self.assertNotIn("https://ex.com/a.png", rewritten)
        # Inline JS with <, >, &, " is preserved verbatim (a parser round-trip
        # would entity-encode it); so are void tags, tag casing, the data-src
        # attribute and the (navigation) <a href>, which must not be rewritten.
        self.assertIn('<script>if (a<b && c>d) { x["k"]=1; }</script>', rewritten)
        self.assertIn("<br>\n", rewritten)
        self.assertIn("<IMG ", rewritten)
        self.assertIn('data-src="keep"', rewritten)
        self.assertIn('href="https://ex.com/page"', rewritten)
        # The whole document is byte-identical except for the single ref.
        self.assertEqual(rewritten, html.replace("https://ex.com/a.png", "a.png"))


class StyleSanitizerTest(unittest.TestCase):
    """Surgical CSS style sanitizer: strip ``<style>`` blocks, allowlist ``style=``."""

    ALLOWLIST = {"text-align", "color", "background-color"}

    def test_strip_style_block(self):
        html = "<html><head><style>p{color:red}</style></head><body><p>Hi</p></body></html>"
        out, removed = references.sanitize_style_css(html, self.ALLOWLIST)
        self.assertNotIn("<style", out)
        self.assertNotIn("p{color:red", out)
        self.assertIn("<style> block", removed)

    def test_allowlisted_style_survives(self):
        html = '<p style="text-align: center">x</p>'
        out, removed = references.sanitize_style_css(html, self.ALLOWLIST)
        self.assertIn("text-align: center", out)
        self.assertEqual(removed, [])

    def test_disallowed_style_dropped(self):
        html = '<p style="position: absolute">x</p>'
        out, removed = references.sanitize_style_css(html, self.ALLOWLIST)
        self.assertNotIn("position", out)
        self.assertIn("style property 'position'", removed)

    def test_mixed_style_keeps_allowlisted(self):
        html = '<p style="color: red; position: absolute; text-align: left">x</p>'
        out, removed = references.sanitize_style_css(html, self.ALLOWLIST)
        self.assertIn("color: red", out)
        self.assertIn("text-align: left", out)
        self.assertNotIn("position", out)
        self.assertIn("style property 'position'", removed)

    def test_no_change_returns_empty_removed(self):
        html = "<p>plain</p>"
        out, removed = references.sanitize_style_css(html, self.ALLOWLIST)
        self.assertEqual(removed, [])
        self.assertEqual(out, html)

    def test_filter_css_declarations(self):
        self.assertEqual(
            references._filter_css_declarations("color: red; margin: 0", {"color"}),
            ("color: red", ["margin"]),
        )
