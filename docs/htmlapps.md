HTML5App nodes and HTML5Zip files
=================================

Kolibri supports rendering of generic HTML content through the use of `HTML5Apps`
nodes, which correspond to `HTML5Zip` files. The Kolibri application serves the
contents of `index.html` in the root of the zip file inside an iframe.
All `href`s and img `src` attributes must be relative links to resources within
the zip file.



Example of HTML5App nodes
-------------------------

* [simple example](http://mitblossoms-demo.learningequality.org/learn/#/recommended/caddd1df7a7b5849a444074408e31655)
  * Note links are disabled (removed blue link) because A) external links are disable in iframe and B) because wouldn't have access offline
  * If link is to a PDF, IMG, or other useful resource than can be included in zip file then keep link but change to relative path
* [medium complexity example](http://tessa-demo.learningequality.org/learn/#/45605d184d985e74960015190a6f4e4f/recommended/ecb158bff182511db6327be6f8a91891)
  * Download all parts of a multi-part lesson into a single HTML5Zip file
  * Original source didn't have a "table of contents" so added manually (really bad CSS I need to fix in final version)
* [complex example](http://kolibridemo.learningequality.org/learn/#/topics/c/d165c4fbc3bd5bbeaf3e51360965af29)
  * Full javascript application packaged as a zip file
  * Source: [sushi-chef-phet](https://github.com/learningequality/sushi-chef-phet/blob/master/chef.py#L104)



Usability guidelines
--------------------

- There _must_ be an index.html file at the topmost level of the zip file, otherwise no app will be shown
- Text should be legible (high contrast, reasonable font size)
- Responsive: text should reflow to fit screens of different sizes. You can preview on a mobile device (or use Chrome’s mobile emulation mode) and ensure that the text fits in the viewport and doesn’t require horizontal scrolling (a maximum width is OK but minimum widths can cause trouble).
- Ensure navigation within HTML5App is easy to use:
    - consistent use of navigation links (e.g. side menu with sections)
    - consistent use of prev/next links
- Ensure links to external websites are disabled (remove `<a></a>` tag), and instead show the `href` in brackets next to the link text (so that potentially users could access URL by other means)
    - e.g., "some other text  link text (http://link.url)  and more text continues"



Links and navigation
--------------------
It's currently not possible to have navigation links between different HTML5App nodes,
but relative links within the same zip file work (since they are rendered in same iframe).
It's important to "cut" the source websites content into appropriately sized chunks:

  - As small as possible so that resources are individually trackable, assignable, and reusable in multiple places
  -  But not too small, e.g. if a lesson contains three parts intended to be followed one after the other, then all three parts should be included in a single HTML5App with internal links
  - Use nested folder structure to represent complex sources.
    Whenever an HTML page that acts as a "container" with links to other pages
    and PDFs we try to turn it into a Folder and put content items inside it.
    Nested folders is main way of representing structured content.




The `HTMLWriter` utility class
------------------------------
The class `HTMLWriter` in `ricecooker.utils.html_writer` provides a basic helper
methods for creating files within a zip file to be used as `HTML5Zip` files
added to `HTML5App` nodes.

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

See the source code for more details:
[ricecooker/utils/html_writer.py](https://github.com/learningequality/ricecooker/blob/master/ricecooker/utils/html_writer.py)




Static assets download utility
------------------------------
We have a handy function for fetching all of a webpage's static assets (JS, CSS, images, etc.),
so that, in theory, you could scrape a webpage and display it in Kolibri exactly
as you see it in the website itself in your browser.

See:
- the source: [`ricecooker.utils.downloader.download_static_assets()`](https://github.com/learningequality/ricecooker/blob/428bfde98e0f76310eccd367886aebe62cd9ae5a/ricecooker/utils/downloader.py#L129)
- [example usage in a simple app: MEET chef](https://github.com/learningequality/sushi-chef-MEET/blob/425327ad552f9f25f582a2057048f6d4475382c1/chef.py#L205), which comprises articles with text and images
- [example usage in a complex app: Blockly Games chef](https://github.com/learningequality/sushi-chef-blockly-games/blob/270e8bc620be0ed883f40e2739878db54f7243b7/chef.py#L193), an interactive JS game with images and sounds




Starter template
----------------
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

The bottom line is ensure the content meets the guidelines layed out above—legible,
responsive, easy to navigate, and "look good" (you define "good" :P).
Fulfilling that, use your judgement on whatever approach makes sense and that you can use effectively!

