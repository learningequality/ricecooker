import os
import subprocess

INSTALL_HINT = (
    "single-file binary not found. Install it with "
    "`npm install -g single-file-cli` and ensure Chromium is available; "
    "see docs/installation.md"
)


class SingleFileRenderError(Exception):
    """Raised when the ``single-file`` binary fails to render a page."""


def render_page(
    url,
    output_dir,
    *,
    crawl_max_depth=1,
    crawl_inner_links_only=True,
    crawl_rewrite_rule=None,
    browser_executable_path=None,
    browser_cookies_file=None,
    http_headers=None,
    timeout=120,
):
    """Render ``url`` into ``output_dir`` with the ``single-file`` binary.

    The entry page is written to ``<output_dir>/index.html``; when
    ``crawl_max_depth > 1`` additional pages are followed and written alongside
    it. Returns the entry path. Raises :class:`SingleFileRenderError` on a
    non-zero exit, a missing binary, a timeout, or if no ``index.html`` is
    produced.

    To capture pages behind a login wall, pass ``browser_cookies_file`` (a
    cookies file in Netscape or JSON format exported from an authenticated
    session) and/or ``http_headers`` (a ``{name: value}`` mapping, e.g. an
    ``Authorization`` bearer token). These map to single-file's
    ``--browser-cookies-file`` / ``--http-header`` options.
    """
    index_path = os.path.join(output_dir, "index.html")

    # Flag names/values isolated here so a correction against the real binary
    # (unavailable in CI) is a one-spot change.
    command = ["single-file", url]
    if crawl_max_depth > 1:
        command += [
            "--crawl-links=true",
            "--crawl-max-depth={}".format(crawl_max_depth),
            "--crawl-inner-links-only={}".format(str(crawl_inner_links_only).lower()),
        ]
    if crawl_rewrite_rule:
        command.append("--crawl-rewrite-rule={}".format(crawl_rewrite_rule))
    if browser_executable_path:
        command.append("--browser-executable-path={}".format(browser_executable_path))
    if browser_cookies_file:
        command.append("--browser-cookies-file={}".format(browser_cookies_file))
    for name, value in (http_headers or {}).items():
        command.append("--http-header={}: {}".format(name, value))
    # Single-page [output] positional guarantees a top-level index.html.
    command.append(index_path)

    try:
        subprocess.check_output(command, stderr=subprocess.STDOUT, timeout=timeout)
    except FileNotFoundError:
        raise SingleFileRenderError(INSTALL_HINT)
    except subprocess.CalledProcessError as e:
        raise SingleFileRenderError("{}: {}".format(e, e.output))
    except subprocess.TimeoutExpired as e:
        raise SingleFileRenderError(str(e))

    if not os.path.exists(index_path):
        raise SingleFileRenderError(
            "single-file produced no index.html in {}".format(output_dir)
        )
    return index_path
