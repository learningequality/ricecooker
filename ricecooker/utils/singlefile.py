import logging
import os
import subprocess

LOGGER = logging.getLogger("SingleFile")
LOGGER.setLevel(logging.DEBUG)

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
    timeout=120,
):
    """Render ``url`` into ``output_dir`` with the ``single-file`` binary.

    The entry page is written to ``<output_dir>/index.html``; when
    ``crawl_max_depth > 1`` additional pages are followed and written alongside
    it. Returns the entry path. Raises :class:`SingleFileRenderError` on a
    non-zero exit, a missing binary, a timeout, or if no ``index.html`` is
    produced.
    """
    index_path = os.path.join(output_dir, "index.html")

    # Keep all flag names/values and output naming in this single block so a
    # correction against the real binary is a one-spot change (see Task 6).
    command = ["single-file", url]
    if crawl_max_depth > 1:
        command.append("--crawl-links=true")
        command.append("--crawl-max-depth={}".format(crawl_max_depth))
        command.append(
            "--crawl-inner-links-only={}".format(
                "true" if crawl_inner_links_only else "false"
            )
        )
    if crawl_rewrite_rule:
        command.append("--crawl-rewrite-rule={}".format(crawl_rewrite_rule))
    if browser_executable_path:
        command.append("--browser-executable-path={}".format(browser_executable_path))
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
