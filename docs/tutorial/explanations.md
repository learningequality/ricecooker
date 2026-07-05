Explanations
============
This page provides more details about the code structure and the metadata needs,
which we glossed over in the [getting started](gettingstarted.html) page.

Feel free to skip these explanations if you're in a hurry, but remember to come
back here and learn the code and metadata technical details, as this knowledge
will be very helpful when you try to create larger, more complicated channels.


How does a chef script work?
----------------------------
Let's look at the chef code we used in the [getting started](gettingstarted.html)
tutorial and walk through and comment on the most important parts of the code.

<!-- TODOC: convert this file to .rst and using include with linenumbers -->

```python
#!/usr/bin/env python
from ricecooker.chefs import SushiChef
from ricecooker.classes.nodes import TopicNode, ContentNode
from ricecooker.classes.licenses import get_license

class SimpleChef(SushiChef):                                                 # (1)
    channel_info = {                                                         # (2)
        'CHANNEL_TITLE': 'Potatoes info channel',
        'CHANNEL_SOURCE_DOMAIN': 'gov.mb.ca',                          # change me!
        'CHANNEL_SOURCE_ID': 'website_docs',                           # change me!
        'CHANNEL_LANGUAGE': 'en',
        'CHANNEL_THUMBNAIL': 'https://upload.wikimedia.org/wikipedia/commons/b/b7/A_Grande_Batata.jpg',
        'CHANNEL_DESCRIPTION': 'A channel about potatoes.',
    }

    def construct_channel(self, **kwargs):
        channel = self.get_channel(**kwargs)                                 # (3)
        potato_topic = TopicNode(title="Potatoes!", source_id="patates")     # (4)
        channel.add_child(potato_topic)                                      # (5)
        doc_node = ContentNode(                                              # (6)
            title='Growing potatoes',
            description='An article about growing potatoes on your rooftop.',
            source_id='inr/pdf/pubs/mafri-potatoe.pdf',
            license=get_license('CC BY', copyright_holder='U. of Alberta'),  # (7)
            language='en',                                                   # (8)
            uri='https://www.gov.mb.ca/inr/pdf/pubs/mafri-potatoe.pdf',      # (9)
        )
        potato_topic.add_child(doc_node)
        return channel

if __name__ == '__main__':                                                   # (10)
    """
    Run this script on the command line using:
        python simple_chef.py  --token=YOURTOKENHERE9139139f3a23232
    """
    simple_chef = SimpleChef()
    simple_chef.main()                                                       # (11)

```


### Ricecooker Chef API
To use the `ricecooker` library, you create a **sushi chef** scripts that define
a subclass of the base class `ricecooker.chefs.SushiChef`, as shown at (1) in the code.
By extending `SushiChef`, your chef class will inherit all the standard functionality
provided by the `ricecooker` framework.


### Channel metadata
A chef class should have the attribute `channel_info` (dict), which contains the
metadata for the channel, as shows on line (2). Define the `channel_info` as follows:

```python
    channel_info = {
        'CHANNEL_TITLE': 'Channel name shown in UI',
        'CHANNEL_SOURCE_DOMAIN': '<sourcedomain.org>',
        'CHANNEL_SOURCE_ID': '<some unique identifier>',     #
        'CHANNEL_LANGUAGE': 'en',                            # use language codes from le_utils
        'CHANNEL_THUMBNAIL': 'http://yourdomain.org/img/logo.jpg', # (optional) local path or url to a thumbnail image
        'CHANNEL_DESCRIPTION': 'What is this channel about?',      # (optional) longer description of the channel
    }
```
The `CHANNEL_SOURCE_DOMAIN` identifies the domain name of the organization that
produced or is hosting the content (e.g. `khanacademy.org` or `youtube.com`).
The `CHANNEL_SOURCE_ID` must be set to some unique identifier for this channel
within the domain (e.g. `KA-en` for the Khan Academy English channel).
The combination of `CHANNEL_SOURCE_DOMAIN` and `CHANNEL_SOURCE_ID` is used to
compute the `channel_id` for the Kolibri channel you're creating.


### Construct channel
The code responsible for building the structure of the channel your channel by
adding `TopicNode`s, `ContentNodes`s, files, and exercises questions lives here.
This is where most of the work of writing a chef script happens.

You chef class should have a method with the signature:
```python
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
You can use topic nodes to build arbitrary hierarchies based on subject,
language, grade levels, or any other organizational structure that is best suited
for the specific content source. Reach out to the Learning Equality content team
if you're not sure how to structure your channel. We've got experience with both
technical and curriculum aspects of creating channels and will be able to guide
you to a structure that best first the needs of learners and teachers.


### Content nodes
The canonical way to add a content item is `ContentNode(source_id, title, license, uri=...)`.
Passing a local path or URL as `uri` downloads the resource and infers its kind, format
preset, and underlying file object automatically — see
[concepts/introduction.md](../concepts/introduction.md#supported-content-kinds) for how
this inference works. You don't need to construct a file object yourself for the vast
majority of content.

Line (6) shows how to create a `ContentNode` to store the metadata for a pdf file.
The `title` and `description` attributes are set, and `source_id` is set to a unique
identifier for this document.

Line (7) shows how we set the `license` attribute to the appropriate instance of
`ricecooker.classes.licenses.License`. All non-topic nodes must be assigned a
license upon initialization. You can obtain the appropriate license object using
the helper function `get_license` defined in `ricecooker.classes.licenses`.
Use the predefined license ids given in `le_utils.constants.licenses` as the
first argument to the `get_license` helper function.

On (8), we set the `language` attribute to the internal language code `en`, to indicate
the content node is in English. The Python package `le-utils` defines the internal
language codes used throughout the Kolibri platform (e.g. `en`, `es-MX`, and `zul`).
To find the internal language code for a given language, you can locate it in the
[lookup table](https://github.com/learningequality/le-utils/blob/main/le_utils/resources/languagelookup.json),
or use one of the language lookup helper functions defined in `le_utils.constants.languages`.
This `language` is also inherited by the file the pipeline builds from `uri` — you
don't need to set it again on a file object.

Line (9) shows the `uri` attribute — the path or URL to the actual pdf file. `uri` can be
either a local filesystem path or a web URL (as in the above example); URLs are downloaded
automatically when the chef runs and cached locally. Note the default ricecooker behaviour
is to cache downloaded files forever. Use the `--update` argument to bypass the cache and
re-download all files. The `--update` must be used whenever files are modified but the path
stays the same.

The only cases `uri` alone can't express are exercises (`ExerciseNode` + questions) and
video subtitles (`SubtitleFile`, which requires an explicit `language`) — see
[Legacy / advanced node classes](../nodes.md#legacy-advanced-node-classes) and
[Subtitle files](../files.md#subtitle-files).



### Command line interface
You can run your chef script by passing the appropriate command line arguments:

    ./sushichef.py --token=YOURTOKENHERE9139139f3a23232

The most important argument when running a chef script is `--token` which is used
to pass in the Studio Access Token obtained in Step 1.

To see the full list of `ricecooker` command line options, run `./sushichef.py -h`.
For more details about running chef scripts see the [chefops page](../chefops.md).

<!-- TODOC: link to the steps of the upload process page -->




Deploying the channel
---------------------
At the end of the chef run the complete channel (files and metadata) will be
uploaded to "draft version" of the channel called a "`staging` tree".
The purpose of the staging tree is to allow channel editors can to review the
changes in the "draft version" as compared to the current version of the channel.
Use the **DEPLOY** button in the Studio web interface to activate the "draft copy"
and make it visible to all Studio users.


Publishing the channel
----------------------
The **PUBLISH** button on Studio is used to save and export a new version of the channel.
The **PUBLISH** action exports all the channel metadata to a sqlite3 DB file served
by Studio at the URL `/content/{{channel_id}}.sqlite3` and ensure the associated
files exist in `/content/storage/` which is served by a CDN.
This step is a prerequisite for getting the channel out of Studio and into Kolibri.


Next steps
----------
After these tutorial and explanations, you are ready to take things into your own hands and learn about:

  - [Content Nodes](../nodes.md)
  - [File types](../files.md)
  - [Exercises](../exercises.md)
  - [Parsing HTML](../parsing_html.md) and creating [HTML5 apps](../htmlapps.md)
  - [Command line arguments](../chefops.md) for controlling chef operation, managing caches, and other options
  - See also the [Cheffing techniques doc](https://docs.google.com/document/d/18Gwip2a1nzjeFT8PT6hQpVeu9DAhmolCRNbrohPSxPM/edit#)
    which provides links to tips and code examples for handling various special cases and content sources.
