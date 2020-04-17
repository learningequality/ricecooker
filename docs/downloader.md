Downloading web content
=======================
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


