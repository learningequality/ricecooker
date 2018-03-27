# Using the `ricecooker` library

The `ricecooker` library is used to transform various educational content types
into Kolibri-compatible formats and upload content to Kolibri Studio.
The following steps will guide you through the creation of a sushi chef script
that uses all the features of the `ricecooker` library.



## Step 1: Obtain a Studio Authorization Token

You will need a Studio Authorization Token to create a channel on Kolibri Studio.
In order to obtain such a token:
1. Create an account on [Kolibri Studio](https://studio.learningequality.org/).
2. Navigate to the Tokens tab under your Settings page.
3. Copy the given authorization token to a safe place.

You must pass the token on the command line as `--token=<your-auth-token>` when
calling your chef script. Alternatively, you can create a file to store your token
and pass in the command line argument `--token="path/to/file.txt"`.



## Step 2: Create a Sushi Chef script

We'll use following simple chef script as an the running example in this section.
You can copy-paste this code into a file `mychef.py` and use it as a starting point
for the chef script you're working on.

```
#!/usr/bin/env python
from ricecooker.chefs import SushiChef
from ricecooker.classes.nodes import TopicNode, DocumentNode
from ricecooker.classes.files import DocumentFile
from ricecooker.classes.licenses import get_license

class SimpleChef(SushiChef):                                                      # (1)
    channel_info = {                                                              # (2)
        'CHANNEL_TITLE': 'Potatoes info channel',
        'CHANNEL_SOURCE_DOMAIN': 'gov.mb.ca',                                     # change me!!!
        'CHANNEL_SOURCE_ID': 'website_docs',                                      # change me!!!
        'CHANNEL_LANGUAGE': 'en',
        'CHANNEL_THUMBNAIL': 'https://upload.wikimedia.org/wikipedia/commons/b/b7/A_Grande_Batata.jpg',
        'CHANNEL_DESCRIPTION': 'A channel about potatoes.',
    }

    def construct_channel(self, **kwargs):
        channel = self.get_channel(**kwargs)                                      # (3)  
        potato_topic = TopicNode(title="Potatoes!", source_id="les_patates")      # (4)
        channel.add_child(potato_topic)                                           # (5)
        doc_node = DocumentNode(                                                  # (6)
            title='Growing potatoes',
            description='An article about growing potatoes on your rooftop.',
            source_id='inr/pdf/pubs/mafri-potatoe.pdf',
            author=None,
            language='en',                                                        # (7)
            license=get_license('CC BY', copyright_holder='U. of Alberta'),       # (8)
            files=[
                DocumentFile(                                                     # (9)
                    path='https://www.gov.mb.ca/inr/pdf/pubs/mafri-potatoe.pdf',  # (10)
                    language='en',                                                # (11)
                )
            ],
        )
        potato_topic.add_child(doc_node)
        return channel

if __name__ == '__main__':                                                        # (12)
    """
    Run this script on the command line using:
        python simple_chef.py -v --reset --token=YOURTOKENHERE9139139f3a23232
    """
    simple_chef = SimpleChef()
    simple_chef.main()                                                            # (13)

```


### Ricecooker Chef API
To use the `ricecooker` library, you create a **sushi chef** scripts that define
a subclass of the base class `ricecooker.chefs.SushiChef`, as shown at (1) in the code.
By extending `SushiChef`, your chef class will inherit the following methods:
  - `run`, which performs all the work of uploading your channel to the Kolibri Studio.
    A sushi chef run consists of multiple steps, the most important one being
    when the we call the chef class' `construct_channel` method.
  - `main`, which your is the function that runs when the sushi chef script is 
     called on the command line.


### Chef class attributes
A chef class should have the attribute `channel_info` (dict), which contains the
metadata for the channel, as shows on line (2). Define the `channel_info` as follows:

    channel_info = {
        'CHANNEL_TITLE': 'Channel name shown in UI',
        'CHANNEL_SOURCE_DOMAIN': '<sourcedomain.org>',       # who is providing the content (e.g. learningequality.org)
        'CHANNEL_SOURCE_ID': '<some unique identifier>',     # an unique identifier for this channel within the domain 
        'CHANNEL_LANGUAGE': 'en',                            # use language codes from le_utils
        'CHANNEL_THUMBNAIL': 'http://yourdomain.org/img/logo.jpg', # (optional) local path or url to a thumbnail image
        'CHANNEL_DESCRIPTION': 'What is this channel about?',      # (optional) longer description of the channel
    }

Note: make sure you change the values of `CHANNEL_SOURCE_DOMAIN` and `CHANNEL_SOURCE_ID`
before you try running this script. The combination of these two values is used
to compute the `channel_id` for the Kolibri channel you're creating. If you keep
the lines above unchanged, you'll get an error because the channel with source
domain 'gov.mb.ca' and source id 'website_docs' already exists on Kolibri Studio.


### Construct channel
The code responsible for building the structure of the channel your channel by
adding `TopicNode`s, `ContentNodes`s, files, and exercises questions lives here.
This is where most of the work of writing a chef script happens.

You chef class should have a method with the signature:
```
def construct_channel(self, **kwargs) -> ChannelNode:
    ...
```

To write the `construct_channel` method of your chef class, start by getting the
`ChannelNode` for this channel by calling `self.get_channel(**kwargs)`.
An instance of the `ChannelNode` will be constructed for you, from the metadata
provided in `self.channel_info`. Once you have the `ChannelNode` instance, the
rest of your chef's `construct_channel` method is responsible for constructing
the channel by adding various `Node`s objects to the channel using `add_child`.


### Topic nodes
Topic nodes are folder-like containers that are used to organize the channel's content.
Line (4) shows how to create a `TopicNode` (folder) instance titled "Potatoes!".
Line (5) shows how to add the newly created topic node to the channel.


### Content nodes
The `ricecooker` library provides classes like `DocumentNode`, `VideoNode`,
`AudioNode`, etc., to store the metadata associate with media content items.
Each content node also has one or more files associated with it,
`DocumentFile`, `VideoFile`, `AudioFile`, `ThumbnailFile`, etc.

Line (6) shows how to create a `DocumentNode` to store the metadata for a pdf file.
The `title` and `description` attributes are set. We also set the `source_id`
attribute to a unique identifier for this document on the source domain `gov.mb.ca`.
The document does not specify authors, so we set the `author` attribute to `None`.

On (7), we set `language` attribute to the internal language code `en`, to indicate
the content node is in English. We use the same language code later on line (11)
to indicate the file contents are in English. The Python package `le-utils` defines
the internal language codes used throughout the Kolibri platform (e.g. `en`, `es-MX`, and `zul`).
To find the internal language code for a given language, you can locate it in the
[lookup table](https://github.com/learningequality/le-utils/blob/master/le_utils/resources/languagelookup.json),
or use one of the language lookup helper functions defined in `le_utils.constants.languages`.

Line (8) shows how we set the `license` attribute to the appropriate instance of 
`ricecooker.classes.licenses.License`. All non-topic nodes must be assigned a
license upon initialization. You can obtain the appropriate license object using
the helper function `get_license` defined in `ricecooker.classes.licenses`.
Use the predefined license ids given in `le_utils.constants.licenses` as the
first argument to the `get_license` helper function.


### Files
On lines (9, 10, and 11), we create a `DocumentFile` instance and set the appropriate
`path` and `language` attributes. Note that `path` can be a web URL as in the above example,
or a local filesystem path.


### Command line interface
You can run your chef script by passing the appropriate command line arguments:

    python mychef.py -v --reset --token=YOURTOKENHERE9139139f3a23232

The most important argument when running a chef script is `--token` which is used
to pass in the Studio Access Token obtained in Step 1.

The flags `-v` (verbose) and `--reset` are generally useful in development.
These make sure the chef script will start the process from scratch and displays
useful debugging information on the command line.

To see the full list of `ricecooker` command line options, run `./mychef.py -h`.
For more details about running chef scripts see [the chefops page](./chefops.md).

If you get an error when running the chef, make sure you've replaced 
`YOURTOKENHERE9139139f3a23232` by the token you obtained from Studio.
Also make sure you've changed the value of `channel_info['CHANNEL_SOURCE_DOMAIN']`
and `channel_info['CHANNEL_SOURCE_ID']` instead of using the default values.

If the channel run was successful, you should be able to see your single-topic
channel on Kolibri Studio server. The topic node "Potatoes!" is nice to look at,
but it feels kind of empty. Let's add more nodes to it!






## Step 3: Add more content nodes and files

Once your channel is created, you can start adding nodes. To do this, you need
to convert your data to `ricecooker` objects. Here are the classes that are
available to you (import from `ricecooker.classes.nodes`):

  - __TopicNode__: folders to organize to the channel's content
  - __AudioNode__: content containing mp3 file
  - __DocumentNode__: content containing pdf file
  - __HTML5AppNode__: content containing zip of html files (html, js, css, etc.)
  - __VideoNode__: content containing mp4 file
  - __ExerciseNode__: assessment-based content with questions

Once you have created the node, add it to a parent node with `parent_node.add_child(child_node)`

To read more about the different nodes, read the [nodes page](./nodes.md).


To add a file to your node, you must start by creating a file object from `ricecooker.classes.files`.
Your sushi chef is responsible for determining which file object to create.
Here are the available file models:

  - __AudioFile__: mp3 file
  - __DocumentFile__: pdf file
  - __HTMLZipFile__: zip of html files (must have `index.html` file at topmost level)
  - __VideoFile__: mp4 file (can be high resolution or low resolution)
  - __WebVideoFile__: video downloaded from site such as YouTube or Vimeo
  - __YouTubeVideoFile__: video downloaded from YouTube using a youtube video id
  - __SubtitleFile__: .vtt subtitle files to be used with VideoFiles
  - __YouTubeSubtitleFile__: subtitles downloaded based on youtube video id and language code
  - __ThumbnailFile__: png or jpg thumbnail files to add to any kind of node

Each file class can be passed a __preset__ and __language__ at initialization
(SubtitleFiles must have a language set at initialization).
A preset determines what kind of file the object is (e.g. high resolution video vs. low resolution video).
A list of available presets can be found at `le_utils.constants.format_presets`.

ThumbnailFiles, AudioFiles, DocumentFiles, HTMLZipFiles, VideoFiles, and SubtitleFiles
must be initialized with a __path__ (str). This path can be a url or a local path to a file.

To read more about the different nodes, read the [nodes files](./files.md).




## Step 4: Adding exercises

See the [exercises page](./exercises.md).

