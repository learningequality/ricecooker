HTML5 Apps
==========

Kolibri supports web content through the use of `HTML5AppNode`, which renders
the contents of a `HTMLZipFile` in a sandboxed iframe. The Kolibri
[HTML5 viewer](https://github.com/learningequality/kolibri/tree/develop/kolibri/plugins/html5_viewer)
will load the `index.html` file which is assumed to be in the root of the zip file.
All `href`s and other `src` attributes must be relative links to resources within
the zip file. The `iframe` rendering of the content in Kolibri is sandbox so
there are some limitations about use of plugins and parts of the web API.





Technical specifications
------------------------
- An `HTMLZipFile` _must_ have an `index.html` file at the root of the zip file.
- A web application packaged as a `HTMLZipFile` _must_ not depend on network calls
  for it to work (cannot load resources references via http/https links)
- A web application packaged as a `HTMLZipFile` _should_ not make unnecessary network calls
  (analytics scripts, social sharing functionality, tracking pixels).
  In an offline setting none of these functions would work so it is considered
  best practices to "clean up" the web apps as part of packaging for offline use.
- The web application _must_ not use plugins like swf/flash.





HTML5AppNode examples
---------------------

* A [raw HTML example](https://kolibridemo.learningequality.org/en/learn/#/topics/c/8d7b9bbfc5c75c12bcd72fcd46d88d98)
  that consists of basic unstyled HTML content taken from the "Additional Online Resources"
  section of [this source page](https://blossoms.mit.edu/videos/lessons/meet_family_investigating_primate_relationships).
  Note links are disabled (removed blue link, and replaced by display of target URL.
  If the links were to useful resources (documents, worksheets, sound clips), they
  could be included in the zip file (deep scraping) with link changed to a relative path.
  By modern cheffing standards, this HTML node would be flagged as "deficient"
  since it lacks basic styled and readability.
  See the recommended approach to basic HTML styling in the next example.
* A basic [styled HTML example](http://kolibridemo-ar.learningequality.org/en/learn/#/topics/c/d24dbf172ed1587782843bfe44b71e50).
  The [code](https://github.com/learningequality/sushi-chef-kamkalima/blob/master/sushichef.py#L195-L244)
  uses a [basic template](https://github.com/learningequality/sushi-chef-kamkalima/blob/master/chefdata/html5app_template/index.template.html)
  which was copy-pasted from [html-app-starter](https://github.com/learningequality/html-app-starter).
  This presentation applies basic fonts, margins, and layout to make HTML content more readable.
  See the section "Usability guidelines" below for more details.
* An example of an [interactive app](http://kolibridemo.learningequality.org/learn/#/topics/c/d165c4fbc3bd5bbeaf3e51360965af29).
  Complete javascript interactive application packaged as a zip file.
  Source: [sushi-chef-phet](https://github.com/learningequality/sushi-chef-phet/blob/master/chef.py#L104).
* A [flipbook reader](https://kolibridemo.learningequality.org/en/learn/#/topics/c/3cc04619379e5296907210c3cdfa63b1)
  application that is built by [this code](https://github.com/learningequality/sushi-chef-african-storybook/blob/master/chef.py#L179-L237).
* A section from a [math textbook](https://kolibridemo.learningequality.org/en/learn/#/topics/c/f1e3fbcf8ecc554082eb0ed1d07635aa)
  that includes text, images, and scripts for rendering math equations.
* A [interactive training activity](https://kolibridemo.learningequality.org/en/learn/#/topics/c/c26acfb92d5a584db81e4ce08e4376a8).
  The [code](https://github.com/learningequality/sushi-chef-hplife/blob/master/transform.py#L297-L404)
  for packaging this HTML app ensures all js, css, and media assets are included in the .zip file.
* Proof of concept of a [Vue.js App](https://github.com/learningequality/sample-channels/tree/master/contentnodes/html5_vuejs).
  This is a minimal webapp example based on the vue.js framework.
  Note the [shell script](https://github.com/learningequality/sample-channels/blob/master/contentnodes/html5_vuejs/update.sh#L22)
  used to tweak the links inside index.html and build.js to make references relative paths.
* Proof of concept [React App](https://github.com/learningequality/sample-channels/tree/master/contentnodes/html5_react):
  A minimal webapp example based on the React framework.
  Note the [shell script](https://github.com/learningequality/sample-channels/blob/master/contentnodes/html5_react/update.sh#L24)
  tweaks required to make paths relative.
* A complete task-oriented [coding environment](https://kolibridemo.learningequality.org/en/learn/#/topics/c/d77c0debaa9d58c688b9e14e24f176d8)
  which is obtained by taking the [source page](https://blockly.games/maze) content
  and [packaging it](https://github.com/learningequality/sushi-chef-blockly-games/blob/master/chef.py#L182-L233)
  for offline use.
* A [powerpoint sideshow presentation](https://kolibridemo.learningequality.org/en/learn/#/topics/c/6d0d779669b244078f1a51e751e003ff)
  packaged as a standalone zip with PREV/NEXT buttons.








Extracting Web Content
----------------------
Most content integration scripts for web content require some combination of *crawling*
(visiting web pages on the source website to extract the structure),
and *scraping* (extracting the metadata and files from detail pages).

The two standard tools for these tasks in the Python community are the
[`requests` library](https://requests.readthedocs.io/en/master/) for making HTTP
requests, and the [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/bs4/doc/) library.

The page [Parsing HTML](parsing_html.md) contains some basic info and code examples
that will allow you to get started with crawling and scraping.
You can also watch this [cheffing video tutorial](http://35.196.115.213/en/learn/#/topics/c/73470ad1a3015769ace455fbfdf17d48)
that will show the basic steps of using `requests` and `BeautifulSoup` for crawling a website.
See the [sushi-chef-shls code repo](https://github.com/learningequality/sushi-chef-shls/blob/master/sushichef.py#L226-L340)
for the final version of the web crawling code that was used for this content source.


### Static assets download utility
We have a handy function for fetching all of a webpage's static assets (JS, CSS, images, etc.),
so that, in theory, you could scrape a webpage and display it in Kolibri exactly
as you see it in the website itself in your browser.

See the source in [`utils/downloader.py`](https://github.com/learningequality/ricecooker/blob/master/ricecooker/utils/downloader.py#L129-L247),
[example usage in a simple app: MEET chef](https://github.com/learningequality/sushi-chef-MEET/blob/425327ad552f9f25f582a2057048f6d4475382c1/chef.py#L205),
which comprises articles with text and images, and [another example in a complex app: Blockly Games chef](https://github.com/learningequality/sushi-chef-blockly-games/blob/270e8bc620be0ed883f40e2739878db54f7243b7/chef.py#L193), an interactive JS game with images and sounds.








Usability guidelines
--------------------
- Text should be legible (high contrast, reasonable font size)

- Responsive: text should reflow to fit screens of different sizes.
  You can preview on a mobile device (or use Chrome’s mobile emulation mode) and
  ensure that the text fits in the viewport and doesn’t require horizontal scrolling
  (a maximum width is OK but minimum widths can cause trouble).

- Ensure navigation within HTML5App is easy to use:
    - consistent use of navigation links (e.g. side menu with sections)
    - consistent use of previous/next links

- Ensure links to external websites are disabled (remove `<a></a>` tag), and
  instead show the `href` in brackets next to the link text (so that users could
  potentially access the URL by some other means).
  For example "some other text **link text**(http://link.url) and more text continues"


### Links and navigation
It's currently not possible to have navigation links between different HTML5App nodes,
but relative links within the same zip file work (since they are rendered in same iframe).

### Packaging considerations
It's important to "cut" the source websites content into appropriately sized chunks:

  - As small as possible so that resources are individually trackable, assignable,
    remixable, and reusable accross channels and in lessons.
  - But not too small, e.g., if a lesson contains three parts intended to be
    followed one after the other, then all three parts should be included in a
    same HTML5App with internal links.
  - Use nested folder structure to represent complex sources.
    Whenever an HTML page that acts as a "container" with links to other pages
    and PDFs, turn it into a TopicNode (Folder) and put content items inside it.

### Starter template
We also have a [starter template](https://github.com/learningequality/html-app-starter)
for apps, particularly helpful for displaying content that's mostly text and images,
such as articles. It applies some default styling on text to ensure readability,
consistency, and mobile responsiveness.

It also includes a sidebar for those apps where you may want internal navigation.
However, consider if it would be more appropriate to turn each page into its own
content item and grouping them together into a single folder (topic).

How to decide between the static assets downloader (above) and this starter template?
Prefer the static assets downloader if it makes sense to keep the source styling or JS,
such as in the case of an interactive app
(e.g. [Blockly Games](https://github.com/learningequality/sushi-chef-blockly-games))
or an app-like reader
(e.g. [African Storybook](https://github.com/learningequality/sushi-chef-african-storybook)).
If the source is mostly a text blob or an article -- and particularly if the
source styling is not readable or appealing—using the template could make sense,
especially given that the template is designed for readability.

The bottom line is ensure the content meets the usability guidelines above:
legible, responsive, easy to navigate, and "look good" (you define "good" :P).
Fulfilling that, use your judgment on whatever approach makes sense and that you can use effectively!





Using Local Kolibri Preview
---------------------------
The [kolibripreview.py](developer/kolibripreview.md) script can be used to test
the contents of `webroot/` in a local installation of Kolibri without needing to
go through the whole content pipeline.






Creating a HTMLZipFile
----------------------
No special technique is required to create HTMLZipFile files—as long as the .zip
file contain the index.html in it's root (not in a subfolder), it can be used
as a `HTMLZipFile` and added as a file to an `HTML5AppNode`.

Since creating the zip files is such a common task of the cheffing process, we
provide two helpers to save you time: the `create_predictable_zip` method and
the `HTMLWriter` class.


### Zipping a folder

The function [`create_predictable_zip`](https://github.com/learningequality/ricecooker/blob/master/ricecooker/utils/zip.py#L9-L39)
can be used to create a zip file from a given directory. This is the recommended
approach for creating zip files since it strips out file timestamps to ensure
that the content hash will not change every time the chef script runs.

Here is some sample code that show how to use this function:
```python
# 1. Create a temporary directory
webroot = tempfile.mkdtemp()

# 2. Create the index.html file inside the temporary directory
indexhtmlpath = os.path.join(webroot, 'index.html')
with open(indexhtmlpath, 'w') as indexfile:
    indexfile.write("<html><head></head><body>Hello, World!</body></html>")
# add images the webroot dir
# add css files the webroot dir
# add js files to the webroot dir
# ...

# 3. Zip it!                      (see https://youtu.be/BODSCrj9FHQ for a laugh)
zippath = create_predictable_zip(webroot)
```
You can then use this zippath as follows `zipfile = HTMLZipFile(path=zippath, ...)`
and add the `zipfile` to a `HTML5AppNode` object using its `add_file` method.
See [here](https://github.com/learningequality/sushi-chef-hplife/blob/550597c211dcaa325a5265c99dc7fbfc71d0b321/transform.py#L43-L72)
for a full code sample.



### The `HTMLWriter` utility class
The class `HTMLWriter` in `ricecooker.utils.html_writer` provides a basic helper
methods for creating zip files directly in compressed form, without the need for
creating a temporary directory first.

To use the `HTMLWriter` class, you must enter the `HTMLWriter` context:
```python
from ricecooker.utils.html_writer import HTMLWriter
with HTMLWriter('./myzipfile.zip') as zipper:
    # Add your code here
```

To write the main file (`index.html` in the root of the zip file), use the 
`write_index_contents` method:
```python
contents = "<html><head></head><body>Hello, World!</body></html>"
zipper.write_index_contents(contents)
```

You can also add other files (images, stylesheets, etc.) using `write_file`,
`write_contents`, and `write_url` methods:
```python
# Returns path to file "styles/style.css"
css_path = zipper.write_contents("style.css", "body{padding:30px}", directory="styles")
extra_head = "<link href='{}' rel='stylesheet'></link>".format(css_path)         # Can be inserted into <head>

img_path = zipper.write_file("path/to/img.png")                                  # Note: file must be local
img_tag = "<img src='{}'>...".format(img_path)                                   # Can be inserted as image

script_path = zipper.write_url("src.js", "http://example.com/src.js", directory="src")
script = "<script src='{}' type='text/javascript'></script>".format(script_path) # Can be inserted into html
```

To check if a file exists in the zipfile, use the `contains` method:
```python
# Zipfile has "index.html" file
zipper.contains('index.html')     # Returns True
zipper.contains('css/style.css')  # Returns False
```
You can then call `zipfile = HTMLZipFile(path=''./myzipfile.zip', ...)` and add
the `zipfile` to a `HTML5AppNode` object using its `add_file` method.

See the source code for more details:
[ricecooker/utils/html_writer.py](https://github.com/learningequality/ricecooker/blob/master/ricecooker/utils/html_writer.py).




Further reading
---------------
 - Conceptually, we could say that `.epub` files are a subkind of the `.zip`
   file format, but Kolibri handles them differently, using `EPubFile`.
 - The new H5P content format (experimental support) is also conceptually similar
   but contains much more structure and metadata about the javascript libraries
   that are used. See `H5PAppNode` and the `H5PFile` for more info.

