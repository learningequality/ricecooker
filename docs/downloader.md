Archiving web pages
===================

Give a `ContentNode` a web page URL as its `uri` and ricecooker archives the page
as an offline HTML5 zip. During the DOWNLOAD stage, a URL that serves HTML is
rendered with [single-file-cli](https://github.com/gildas-lormeau/single-file-cli)
and Chromium, and the page's assets are packed into the zip. Any other URL
downloads as-is.

Rendering needs single-file-cli and Chromium; see [installation](installation.md).

```python
from ricecooker.classes.licenses import get_license
from ricecooker.classes.nodes import ContentNode

page_node = ContentNode(
    source_id="todomvc-react",
    title="TodoMVC (React)",
    license=get_license("Public Domain"),
    language="en",
    uri="https://todomvc.com/examples/react/dist/",
    context={"crawl_max_depth": 1, "crawl_inner_links_only": True},
)
```

See the [page-archiving example](https://github.com/learningequality/ricecooker/tree/main/examples/pagearchive)
for a complete chef.


### Rendering options

Pass these in the node's `context`:

- `crawl_max_depth`: crawl depth, counting the page itself. The default, `1`, archives only the page.
- `crawl_inner_links_only`: follow only links on the same domain. Default `True`.
- `crawl_rewrite_rule`: passed to single-file's `--crawl-rewrite-rule`.
- `browser_executable_path`: Chromium or Chrome, if it is not on `PATH`.
- `browser_cookies_file`: cookies for pages behind a login.
- `http_headers`: a `{name: value}` dict of extra request headers.

For pages behind a login, see
[Authenticating login-walled sites](https://github.com/learningequality/ricecooker/tree/main/examples/pagearchive#authenticating-login-walled-sites).


### Migrating from `ArchiveDownloader`

`ArchiveDownloader` and `downloader.read` have been removed.

- `get_page` + `export_page_as_zip` → `ContentNode(uri=url)`.
- `link_policy` → `crawl_max_depth` and `crawl_inner_links_only`.
- `run_js` → always on.
- `refresh` → the `--update` command-line option.
- `create_zip_dir_for_page`, to edit files before zipping → build the zip yourself
  with `ricecooker.utils.zip.create_predictable_zip` (see [Zipping a folder](htmlapps.md#zipping-a-folder))
  and pass its path as `uri`.
- Custom `requests` session, archived pages → `browser_cookies_file` or `http_headers`.
- Custom `requests` session, other downloads → `DOMAIN_AUTH_HEADERS` on your chef
  or `ricecooker.config.DOWNLOAD_SESSION`.


### Reading file contents

`read` replaces `downloader.read`:

```python
from ricecooker.utils.pipeline.transfer import read

pdf_bytes = read("/path/to/local/file.pdf")
pdf_bytes = read("https://example.com/file.pdf")
```

An HTML URL passed to `read` is rendered by single-file-cli and returns the zip.
To parse a page's HTML, fetch it with `requests`; see [Parsing HTML](parsing_html.md).


### Caching

Downloaded and archived files are cached in `.ricecookerfilecache` in the chef's
working directory. Run with `--update` to fetch them again.
