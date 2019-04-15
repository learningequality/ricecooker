There are some utilities useful to people writing chefs in this directory.

# Browser Preview
`ricecooker.utils.browser.preview_in_browser(directory, filename=”index.html”, port=8282)`
Creates a local HTTP server to serve the specified directory, starting with filename

# File Download
`ricecooker.utils.html.download_file(url, destpath, filename=None, baseurl=None, subpath=None, middleware_callbacks=None, middleware_kwargs=None, request_fn=sess.get)`
Download a file from url, into the destpath folder, using filename as the name of the file.
If `baseurl` is specified, the file will be put into subdirectory of destpath per the url's path relative to the baseurl.
If `subpath` is specified, it will be appended to destpath before deciding where to write the file.
middleware_callbacks are called in turn with arguments from middleware_kwargs.

# Path Utilities
`ricecooker.utils.paths.file_exists(filepath)`
`ricecooker.utils.paths.dir_exists(filepath)`
Does the relevant file or directory exist?

`ricecooker.utils.paths.get_name_from_url(url)`
Get the filename from a URL -- i.e. the bit after the final slash, but before query parameters.
I’d consider using `urllib.parse.urlparse(url).path.split('/')[-1]`

`ricecooker.utils.paths.get_name_from_url_no_ext(url)`
As above, but also removes extension

`ricecooker.utils.paths.build_path(levels)`
Create nested folders for each level, if necessary

# Zip Utilities

`ricecooker.utils.html_writer.HTMLWriter(write_to_path, mode='w')`
Create a zipfile at write_to_path
`….open()`
`….close()`
`….contains(filename)`
`….write_contents(filename, contents, directory=None)`
Write contents into the zipfile at directory/filename
`….write_file(filepath, filename=None, directory=None)`
Add the file at filepath to the zipfile at directory/filename
`….write_url(url, filename, directory=None)`
Add the file at url to the zipfile at directory/filename
`….write_index_contents(contents)`
Write contents into the zipfile at index.html

`ricecooker.utils.zip.create_predictable_zip(path)`
Make zip from directory deterministically

# PDF Splitter
`ricecooker.utils.pdf.PDFParser(sourcepath, directory=”downloads”)`
Split PDF file into smaller files along chapter or subchapter lines
`….open(update=False)`
`….close()`
`….get_toc(subchapters=False)`
Find pageranges for chapters or subchapters
`….write_pagerange(pagerange, prefix='')`
Write pagerange to a different PDF to the target directory with filename prefix prefix.
`….split_subchapters(jsondata=None)`
`….split_chapters(jsondata=None, prefix='')`
Automate whole process -- can customise jsondata output from `get_toc` if fine-tuning is required.

# Node Creation
`ricecooker.utils.nodes.create_node(file_class, url, filename, title, license, copyright_holder, description)`
Create a content node from either a URL or filename.
Which content node is determined by:
  * the `file_class` explicitly passed (e.g. VideoFile class)
  * guessing from downloaded mimetype, file extension or magic bytes (see `guess_type` function)
You can set `ricecooker.utils.nodes.metadata` to automatically fille in licence and copyright details as a dictionary.

# Transcoding
`ricecooker.utils.transcode.transcode_video(source_filename, target_filename=None)`
Transcodes video to h264 using ffmpeg; returns filename of transcoded video.

`ricecooker.utils.transcode.transcode_audio(source_filename, target_filename=None)`
