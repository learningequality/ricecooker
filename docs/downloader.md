Downloading web content
=======================

### The ArchiveDownloader class

**New in 0.7**

#### Overview
The `ArchiveDownloader` class encapsulates the functionality of
downloading URLs, their related resources, and rewriting page links
to point to their downloaded location.

All the downloaded content becomes part of an archive, which can be
saved and reused on future runs of the script. After the download completes,
the script could even be run offline.

This enables many things, including the ability to update and re-run scripts even
if the original content was removed, easily and automatically create a dependency
zip of content shared by various pages in the archive, and create HTML5 zips for
pages that correctly include all necessary resources without extra code.

#### Using ArchiveDownloader

`ArchiveDownloader` has the following general workflow:

- Create an `ArchiveDownloader` instance before downloading any web content.
- Call `get_page` on that instance passing in full URLs to pages you wish to download.
- Once content has been downloaded, you need to create an HTML5 zip of the content.
  * If the content does not need to be modified, call `export_page_as_zip` and use the
    zip created as a file for an HTML5 app node.
  * If you need to make modifications, call `create_zip_dir_for_page`, then modify
    the files in the directory it returns as needed. (Not modifying the original
     sources allows you to keep a clean copy at all times.) Finally, create a ZIP by
    calling `ricecooker.utils.create_predictable_zip` and use the zip created
    as a file for an HTML5 app node.

Usage example:

```python
    from ricecooker.utils.downloader import ArchiveDownloader

    sushi_url = 'https://en.wikipedia.org/wiki/Sushi'

    archive = ArchiveDownloader("downloads/archive_1")
    # Download and store page in the archive
    archive.get_page(sushi_url)
    # Convert page into a Kolibri-friendly HTML5 zip file
    zip_file = archive.export_page_as_zip(sushi_url)
    # ... code to add zip_file to an HTML5AppNode ...
```

Example scripts:

The [COVID 19 Simulations sushi chef](https://github.com/learningequality/sushi-chef-covid19-sim/blob/master/sushichef.py)
 provides a relatively small and simple example of how to use `ArchiveDownloader`.

#### Using `get_page`

By default, `get_page` will download the page and all its related resources, including
CSS, image, and JS files. You can also pass a few optional arguments to modify its
behavior:

`refresh` [True | False]:
If `True`, this will re-download the page, even if it is already in the archive.

`run_js` [True | False]:
If `True`, the page will be loaded using `pyppeteer` and wait until page load handlers
have run before downloading the content. If `False` (default), it will use `requests`
to download the content.

`link_policy` [Dict or None]:
Defines how to handle scraping of page links. The default, `None`, indicates no scraping.
If a dictionary is passed, it may contain the following keys:

* `levels` [Integer]: (Required) Number of levels deep to scrape links.
* `scope` [String]: (Optional) Defaults to "internal", which only scrapes links on the
same domain. Change to "all" to scrape links from external domains as well.
* `whitelist` [List]: (Optional) A list of strings containing URLs to be whitelisted.
They will be compared against complete URLs, so the strings can be as complete as desired.
e.g. `www.mydomain.com/subdir/subdir2/` can be used to match against only URLs in that
particular subdir.
* `blacklist` [List]: (Optional) A list of strings containing URLs to be blacklisted.
URLs can be specified using the same rules as the `whitelist` argument.

### downloader.py Functions

The Ricecooker module `utils/downloader.py` provides a `read` function that can
be used to read the file contents from both urls and local file paths.

Usage examples:

```python
from ricecooker.utils.downloader import read

local_file_content = read('/path/to/local/file.pdf')              # Load local file
web_content = read('https://example.com/page')                    # Load web page contents
web_content2 = read('https://example.com/loadpage', loadjs=True)  # Load js before getting contents
```

The `loadjs` option will run the JavaScript code on the webpage before reading
the contents of the page, which can be useful for scraping certain websites that
depend on JavaScript to build the page DOM tree.

If you need to use a custom session, you can also use the `session` option.
This can be useful for sites that require login.
See the [sushi-chef-firki code](https://github.com/learningequality/sushi-chef-firki/blob/master/client.py#L20-L31)
for an example of this.


Caching
-------
Requests made with the `read` method are cached by default, and the cache doesn't
have an expiration date. The cached files are stored the folder `.webcache` in
the chef repository. You must manually delete this folder when the source website changes.

    rm -rf .webcache

This [sample code](https://github.com/learningequality/sushi-chef-pradigi/blob/master/sushichef.py#L64-L70)
shows how to setup requests session caching that expires after one day.



Further reading
---------------

  - Tutorial on the Python [requests module](https://stackabuse.com/the-python-requests-module/).


