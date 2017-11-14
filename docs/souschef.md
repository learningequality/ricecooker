# Writing a SousChef

Kolibri is an open source educational platform to distribute content to areas with
little or no internet connectivity. Educational content is created and edited on [Kolibri Studio](https://studio.learningequality.org),
which is a platform for organizing content to import from the Kolibri applications. The purpose
of this project is to create a *chef*, or a program that scrapes a content source and puts it
into a format that can be imported into Kolibri Studio. This project will read a
given source's content and parse and organize that content into a folder + csv structure,
which will then be imported into Kolibri Studio.



## Installation

* Install [Python 3](https://www.python.org/downloads/) if you don't have it already.

* Install [pip](https://pypi.python.org/pypi/pip) if you don't have it already.

* Create a Python virtual environment for this project (optional, but recommended):
   * Install the virtualenv package: `pip install virtualenv`
   * The next steps depends if you're using UNIX (Mac/Linux) or Windows:
      * For UNIX systems:
         * Create a virtual env called `venv` in the current directory using the
           following command: `virtualenv -p python3  venv`
         * Activate the virtualenv called `venv` by running: `source venv/bin/activate`.
           Your command prompt will change to indicate you're working inside `venv`.
      * For Windows systems:
         * Create a virtual env called `venv` in the current directory using the
           following command: `virtualenv -p C:/Python36/python.exe venv`.
           You may need to adjust the `-p` argument depending on where your version
           of Python is located.
         * Activate the virtualenv called `venv` by running: `.\venv\Scripts\activate`

* Run `pip install -r requirements.txt` to install the required python libraries.


## Description

A sous chef is responsible for scraping content from a source and putting it into a folder
and csv structure.


## Getting started

Here are some notes and sample code to help you get started.


### Downloader

The Ricecooker script `utils/downloader.py` has a `read` function that can read from both
urls and file paths. To use:

```
from ricecooker.utils.downloader import read

local_file_content = read('/path/to/local/file.pdf')            # Load local file
web_content = read('https://example.com/page')                  # Load web page contents
js_content = read('https://example.com/loadpage', loadjs=True)  # Load js before getting contents

```

The `loadjs` option will run the JavaScript code on the webpage before reading
the contents of the page, which can be useful for scraping certain websites that
depend on JavaScript to build the page DOM tree.

If you need to use a custom session, you can also use the `session` option. This can
be useful for sites that require login information.


### HTML parsing using BeautifulSoup

BeautifulSoup is an HTML parsing library that allows to select various DOM elements,
and extract their attributes and text contents. Here is some sample code for getting
the text of the LE mission statement.

```
from bs4 import BeautifulSoup
from ricecooker.utils.downloader import read

url = 'https://learningequality.org/'
html = read(url)
page = BeautifulSoup(html, 'html.parser')

main_div = page.find('div', {'id': 'body-content'})
mission_el = main_div.find('h3', class_='mission-state')
mission = mission_el.get_text().strip()
print(mission)
```

The most commonly used parts of the BeautifulSoup API are:
  - `.find(tag_name,  <spec>)`: find the next occurrence of the tag `tag_name` that
     has attributes specified in `<spec>` (given as a dictionary), or can use the
     shortcut options `id` and `class_` (note extra underscore).
  - `.find_all(tag_name, <spec>)`: same as above but returns a list of all matching
     elements. Use the optional keyword argument `recursive=False` to select only
     immediate child nodes (instead of including children of children, etc.).
  - `.next_sibling`: find the next element (for badly formatted pages with no useful selectors)
  - `.get_text()` extracts the text contents of the node. See also helper method
    called `get_text` that performs additional cleanup of newlines and spaces.
  - `.extract()`: to remove a element from the DOM tree (useful to remove labels, and extra stuff)

For more info about BeautifulSoup, see [the docs](https://www.crummy.com/software/BeautifulSoup/bs4/doc/).



## Using the DataWriter

The DataWriter (`ricecooker.utils.data_writer.DataWriter`) is a tool for creating channel
`.zip` files in a standardized format. This includes creating folders, files,
and `CSV` metadata files that will be used to create the channel on Kolibri Studio.



### Step 1: Open a DataWriter

The `DataWriter` class is meant to be used as a context manager. To use it, add
the following to your code:
```
from ricecooker.utils.data_writer import DataWriter
with DataWriter() as writer:
    # Add your code here
```

You can also pass the argument `write_to_path` to control where the `DataWriter`
will generate a zip file.



### Step 2: Create a Channel

Next, you will need to create a channel. Channels need the following arguments:
  - `title` (str): Name of channel
  - `source_id` (str): Channel's unique id
  - `domain` (str): Who is providing the content
  - `language` (str): Language of channel
  - `description` (str): Description of the channel (optional)
  - `thumbnail` (str): Path in zipfile to find thumbnail (optional)

To create a channel, call the `add_channel` method from DataWriter

```
from ricecooker.utils.data_writer import DataWriter

CHANNEL_NAME = "Channel name shown in UI"
CHANNEL_SOURCE_ID = "<some unique identifier>"
CHANNEL_DOMAIN = "<yourdomain.org>"
CHANNEL_LANGUAGE = "en"
CHANNEL_DESCRIPTION = "What is this channel about?"

with DataWriter() as writer:
    writer.add_channel(CHANNEL_NAME, CHANNEL_SOURCE_ID, CHANNEL_DOMAIN, CHANNEL_LANGUAGE, description=CHANNEL_DESCRIPTION)
```

To add a channel thumbnail, you must write the file to the zip folder
```
thumbnail = writer.add_file(CHANNEL_NAME, "Channel Thumbnail", CHANNEL_THUMBNAIL, write_data=False)
writer.add_channel(CHANNEL_NAME, CHANNEL_SOURCE_ID, CHANNEL_DOMAIN, CHANNEL_LANGUAGE, description=CHANNEL_DESCRIPTION, thumbnail=thumbnail)
```

The DataWriter's `add_file` method returns a filepath to the downloaded thumbnail.
This method will be covered more in-depth in Step 4.

Every channel must have language code specified (a string, e.g., `'en'`, `'fr'`).
To check if a language code exists, you can use the helper function `getlang`,
or lookup the language by name using `getlang_by_name` or `getlang_by_native_name`:
```
from le_utils.constants.languages import getlang, getlang_by_name, getlang_by_native_name
getlang('fr').code                       # = 'fr'
getlang_by_name('French').code           # = 'fr'
getlang_by_native_name('Français').code  # = 'fr'
```
The same language codes can optionally be applied to folders and files if they
differ from the channel language (otherwise assumed to be the same as channel).


### Step 3: Add a Folder

In order to add subdirectories, you will need to use the `add_folder` method
from the DataWriter class. The method `add_folder` accepts the following arguments:
  - `path` (str): Path in zip file to find folder
  - `title` (str): Content's title
  - `source_id` (str): Content's original ID (optional)
  - `language` (str): Language of content (optional)
  - `description` (str): Description of the content (optional)
  - `thumbnail` (str): Path in zipfile to find thumbnail (optional)

Here is an example of how to add a folder:
```
# Assume writer is a DataWriter object
TOPIC_NAME = "topic"
writer.add_folder(CHANNEL_NAME + "/" + TOPIC_NAME, TOPIC_NAME)
```


### Step 4: Add a File

Finally, you will need to add files to the channel as learning resources.
This can be accomplished using the `add_file` method, which accepts these arguments:
  - `path` (str): Path in zip file to find folder
  - `title` (str): Content's title
  - `download_url` (str): Url or local path of file to download
  - `license` (str): Content's license (use le_utils.constants.licenses)
  - `license_description` (str): Description for content's license
  - `copyright_holder` (str): Who owns the license to this content?
  - `source_id` (str): Content's original ID (optional)
  - `description` (str): Description of the content (optional)
  - `author` (str): Author of content
  - `language` (str): Language of content (optional)
  - `thumbnail` (str): Path in zipfile to find thumbnail (optional)
  - `write_data` (boolean): Indicate whether to make a node (optional)

For instance:

```
from le_utils.constants import licenses

# Assume writer is a DataWriter object
PATH = CHANNEL_NAME + "/" + TOPIC_NAME + "/filename.pdf"
writer.add_file(PATH, "Example PDF", "url/or/link/to/file.pdf", license=licenses.CC_BY, copyright_holder="Somebody")
```

The `write_data` argument determines whether or not to make the file a node.
This is espcially helpful for adding supplementary files such as thumbnails
without making them separate resources. For example, adding a thumbnail to a
folder might look like the following:

```
# Assume writer is a DataWriter object
TOPIC_PATH = CHANNEL_NAME + "/" + TOPIC_NAME
PATH = TOPIC_PATH + "/thumbnail.png"
thumbnail = writer.add_file(PATH, "Thumbnail", "url/or/link/to/thumbnail.png", write_data=False)
writer.add_folder(TOPIC_PATH, TOPIC_NAME, thumbnail=thumbnail)
```

**Every content node must have a `license` and `copyright_holder`**, otherwise
the later stages of the content pipeline will reject. You can see the full list
of allowed license codes by running `print(le_utils.constants.licenses.choices)`.
Use the ALL_CAPS constants to obtain the appropriate string code for a license.
For example, to set a file's license to the Creative Commons CC BY-NC-SA, get
get the code from `licenses.CC_BY_NC_SA`.

Note: Files with `licenses.PUBLIC_DOMAIN` do not require a `copyright_holder`.


## Extra Tools

### PathBuilder (ricecooker.utils.path_builder.py)

The `PathBuilder` clas is a tool for tracking folder and file paths to write to
the zip file. To initialize a PathBuilder object, you need to specify a channel name:

```
from ricecooker.utils.path_builder import PathBuilder

CHANNEL_NAME = "Channel"
PATH = PathBuilder(channel_name=CHANNEL_NAME)
```

You can now build this path using `open_folder`, which will append another item to the path:

```
...
PATH.open_folder('Topic')         # str(PATH): 'Channel/Topic'
```

You can also set a path from the root directory:
```
...
PATH.open_folder('Topic')         # str(PATH): 'Channel/Topic'
PATH.set('Topic 2', 'Topic 3')    # str(PATH): 'Channel/Topic 2/Topic 3'
```


If you'd like to go back one step back in the path:
```
...
PATH.set('Topic 1', 'Topic 2')    # str(PATH): 'Channel/Topic 1/Topic 2'
PATH.go_to_parent_folder()        # str(PATH): 'Channel/Topic 1'
PATH.go_to_parent_folder()        # str(PATH): 'Channel'
PATH.go_to_parent_folder()        # str(PATH): 'Channel' (Can't go past root level)
```

To clear the path:
```
...
PATH.set('Topic 1', 'Topic 2')    # str(PATH): 'Channel/Topic 1/Topic 2'
PATH.reset()                      # str(PATH): 'Channel'
```



### Downloader (ricecooker.utils.downloader.py)

`downloader.py` has a `read` function that can read from both urls and file paths.
To use:

```
from ricecooker.utils.downloader import read

local_file_content = read('/path/to/local/file.pdf')            # Load local file
web_content = read('https://example.com/page')                  # Load web page contents
js_content = read('https://example.com/loadpage', loadjs=True)  # Load js before getting contents

```

 The `loadjs` option will load any scripts before reading the contents of the page,
 which can be useful for web scraping.

If you need to use a custom session, you can also use the `session` option. This can
be useful for sites that require login information.



### HTMLWriter (ricecooker.utils.html_writer.py)

The HTMLWriter is a tool for generating zip files to be uploaded to Kolibri Studio

First, open an HTMLWriter context:

```
from ricecooker.utils.html_writer import HTMLWriter
with HTMLWriter('./myzipfile.zip') as zipper:
    # Add your code here
```

To write the main file, you will need to use the `write_index_contents` method

```
contents = "<html><head></head><body>Hello, World!</body></html>"
zipper.write_index_contents(contents)
```

You can also add other files (images, stylesheets, etc.) using `write_file`, `write_contents` and `write_url`:
```
# Returns path to file "styles/style.css"
css_path = zipper.write_contents("style.css", "body{padding:30px}", directory="styles")
extra_head = "<link href='{}' rel='stylesheet'></link>".format(css_path)         # Can be inserted into <head>

img_path = zipper.write_file("path/to/img.png")                                  # Note: file must be local
img_tag = "<img src='{}'>...".format(img_path)                                   # Can be inserted as image

script_path = zipper.write_url("src.js", "http://example.com/src.js", directory="src")
script = "<script src='{}' type='text/javascript'></script>".format(script_path) # Can be inserted into html
```

If you need to check if a file exists in the zipfile, you can use the `contains` method:
```
# Zipfile has "index.html" file
zipper.contains('index.html')     # Returns True
zipper.contains('css/style.css')  # Returns False
```


(See above example on BeautifulSoup on how to parse html)
