ricecooker
==========

The `ricecooker` library is a framework for automating the conversion of educational content into
Kolibri content channels and uploading them to [Kolibri Studio](https://studio.learningequality.org/), 
which is the central content server for [Kolibri](http://learningequality.org/kolibri/).

## Overview

`ricecooker` is used to take openly licensed educational content available on the
web and convert it into an offline-friendly package that can be imported into Kolibri.

The basic process of getting new content into Kolibri is as follows:

1. Create and upload a new Kolibri Channel using either `ricecooker` integration
   script or by manually uploading content through the Kolibri Studio web interface.
2. Publish the new channel using Kolibri Studio to make it accessible to Kolibri.
3. Copy the channel's token in Kolibri Studio, and paste it into Kolibri's import screen 
   to import the channel.

The diagram below illustrates the three steps of this process:

![The Kolibri Content Pipeline](https://raw.githubusercontent.com/learningequality/ricecooker/master/docs/figures/content_pipeline_diagram.png)


## Key Concepts

Before we go any further, let us provide more details on some key concepts in the
Kolibri Content Pipeline.

### Kolibri Channel

  - A **Kolibri Channel** is a tree-like data structure that consists of the following types of content:
    - Topics (folders)
    - Content of a type supported by Kolibri, including:
      - Document (ePub and PDF files)
      - Audio (mp3 files)
      - Video (mp4 files)
      - HTML5App zip files (generic container for web content: HTML+JS+CSS)
      - SlidesShow (jpg and png slide images)
      - Exercises, which contain different types of questions:
        - SingleSelectQuestion (multiple choice)
        - MultipleSelectQuestion (multiple choice with multiple correct answers)
        - InputQuestion (good for numeric inputs)
        - PerseusQuestion (a rich exercise question format developed at Khan Academy)

### ContentNode

A **ContentNode** is a technical term used to describe a piece of content in Kolibri, along with
the metadata associated with it, such as the licensing, description, and thumbnail. A Kolibri Channel
contains a content tree (i.e. table of contents) made up of `ContentNodes`.

### Content Integration Script (aka SushiChef)

The content integration scripts that use the `ricecooker` library to generate Kolibri Channels
are commonly referred to as **SushiChef** scripts. The responsibility of a `SushiChef` is to download the source
content, perform any necessary format or structure conversions to create a content tree viewable
in Kolibri, then to upload the output of this process to Kolibri Studio for review and publishing.

Conceptually, `SushiChef` scripts are very similar to web scrapers, but with specialized functions
for optimizing the content for Kolibri's data structures and capabilities.

### Content Pipeline

The combination of software tools and procedures that content moves through from
starting as an external content source to becoming a Kolibri Channel available
for use in the Kolibri Learning Platform. The `ricecooker` framework is the
"main actor" in the first part of the content pipeline, and touches all aspects
of the pipeline within the region highlighted in blue in the above diagram.


## Installation

We'll assume you have a Python 3 installation on your computer and are familiar
with best practices for working with Python codes (e.g. `virtualenv` or `pipenv`).
If this is not the case, you can consult the Kolibri developer docs as a guide for
[setting up a Python virtualenv](http://kolibri-dev.readthedocs.io/en/latest/start/getting_started.html#virtual-environment).

The `ricecooker` library is a standard Python library distributed through PyPI:
  - Run `pip install ricecooker` to install `ricecooker` and all Python dependencies.
  - Some of the utility functions in `ricecooker.utils` require additional software:
     - The multimedia command line tool [ffmpeg](https://ffmpeg.org/)
     - The `imagemagick` (version 6) image manipulation tools
     - The `poppler` library for PDF utilities

For details about the installation steps, see [docs/installation.md](https://github.com/learningequality/ricecooker/blob/master/docs/installation.md).

In order to upload your `ricecooker` generated channels to Kolibri Studio and make them importable
into Kolibri, you will also need to create an account on Kolibri Studio. To do so, visit
[Kolibri Studio](https://studio.learningequality.org) and click the "Create an Account" link.
The instructions below assume you have already completed this step.


## Creating Your First Content Integration Script

Below is code for a simple sushi chef script that uses the `ricecooker` library to create a Kolibri
channel with a single topic node (Folder), and puts a single PDF content node inside that folder.

To get started, create a new project folder and save the following code in a file called `sushichef.py`:

**Important Note** Be sure to give unique values for the `CHANNEL_SOURCE_DOMAIN` and `CHANNEL_SOURCE_ID`,
as these values are used to determine your channel's ID and using duplicate values will lead
to an error when trying to upload.

```
#!/usr/bin/env python
from ricecooker.chefs import SushiChef
from ricecooker.classes.nodes import ChannelNode, TopicNode, DocumentNode
from ricecooker.classes.files import DocumentFile
from ricecooker.classes.licenses import get_license


class SimpleChef(SushiChef):
    channel_info = {
        'CHANNEL_TITLE': 'Potatoes info channel',
        'CHANNEL_SOURCE_DOMAIN': '<domain.org>',         # where you got the content (change me!!)
        'CHANNEL_SOURCE_ID': '<unique id for channel>',  # channel's unique id (change me!!)
        'CHANNEL_LANGUAGE': 'en',                        # le_utils language code
        'CHANNEL_THUMBNAIL': 'https://upload.wikimedia.org/wikipedia/commons/b/b7/A_Grande_Batata.jpg', # (optional)
        'CHANNEL_DESCRIPTION': 'What is this channel about?',      # (optional)
    }

    def construct_channel(self, **kwargs):
        channel = self.get_channel(**kwargs)
        potato_topic = TopicNode(title="Potatoes!", source_id="<potatos_id>")
        channel.add_child(potato_topic)
        doc_node = DocumentNode(
            title='Growing potatoes',
            description='An article about growing potatoes on your rooftop.',
            source_id='pubs/mafri-potatoe',
            license=get_license('CC BY', copyright_holder='University of Alberta'),
            language='en',
            files=[DocumentFile(path='https://www.gov.mb.ca/inr/pdf/pubs/mafri-potatoe.pdf',
                                language='en')],
        )
        potato_topic.add_child(doc_node)
        return channel


if __name__ == '__main__':
    """
    Run this script on the command line using:
        python sushichef.py -v --reset --token=YOURTOKENHERE9139139f3a23232
    """
    simple_chef = SimpleChef()
    simple_chef.main()
```

You can run the chef script by passing the appropriate command line arguments:

    python sushichef.py --reset --token=YOURTOKENHERE9139139f3a23232

The most important argument when running a chef script is `--token`, which is used
to pass in the Studio Access Token used to allow upload access. You can find this token
by going to the [settings page](http://studio.learningequality.org/settings/tokens) of
the account you created earlier and copying the token it displays.

The flag `--reset` is generally useful in development. It ensures the chef script
starts the upload process from scratch every time you run the script
(otherwise the script will prompt you to resume from the last saved checkpoint).

To see all the `ricecooker` command line options, run `python sushichef.py -h`.
For more details about running chef scripts see [the chefops page](https://github.com/learningequality/ricecooker/blob/master/docs/chefops.md).

If you get an error when running the chef, make sure you've replaced
`YOURTOKENHERE9139139f3a23232` by the token you obtained from Studio.
Also make sure you've changed the value of `channel_info['CHANNEL_SOURCE_DOMAIN']`
and `channel_info['CHANNEL_SOURCE_ID']` instead of using the default values.


## Next Steps

The Kolibri Content Pipeline is a collaborative effort between educational experts and software
developers. As such, we have provided some getting docs of particular relevance for each role
in the process:

  - **Content specialists and Administrators** can read the non-technical part
    of the documentation to learn about how content works in the Kolibri platform.
    - The best place to start is the [Kolibri Platform overview](https://github.com/learningequality/ricecooker/blob/master/docs/platform/introduction.md).
    - The page on [content workflows](https://ricecooker.readthedocs.io/en/latest/platform/content_workflows.html)
      also has a useful overview of the steps of the process.
    - You can read about the supported [content types here](https://github.com/learningequality/ricecooker/blob/master/docs/platform/content_types.md).
    - The page on [Reviewing Channel](https://ricecooker.readthedocs.io/en/latest/platform/reviewing_channels.html)
      provides more information about the possible content issues to watch out for.

  - **Chef authors** can read the remainder of this README, and get started using
    the `ricecooker` library by following these first steps:
      - [Quickstart](https://github.com/learningequality/ricecooker/blob/master/docs/tutorial/quickstart.ipynb), which will introduce you to
        the steps needed to create a sushi chef script.
      - After the quickstart, you should be ready to take things into your own
        hands, and complete all steps in the [ricecooker tutorial](https://gist.github.com/jayoshih/6678546d2a2fa3e7f04fc9090d81aff6).
      - The next step after that is to read the [ricecooker usage docs](https://github.com/learningequality/ricecooker/blob/master/docs/usage.md),
        which is also available Jupyter notebooks under [docs/tutorial/](https://github.com/learningequality/ricecooker/blob/master/docs/tutorial/).
    More detailed technical documentation is available on the following topics:
      - [Installation](https://github.com/learningequality/ricecooker/blob/master/docs/installation.md)
      - [Content Nodes](https://github.com/learningequality/ricecooker/blob/master/docs/nodes.md)
      - [File types](https://github.com/learningequality/ricecooker/blob/master/docs/files.md)
      - [Exercises](https://github.com/learningequality/ricecooker/blob/master/docs/exercises.md)
      - [HTML5 apps](https://github.com/learningequality/ricecooker/blob/master/docs/htmlapps.md)
      - [Parsing HTML](https://github.com/learningequality/ricecooker/blob/master/docs/parsing_html.md)
      - [Running chef scripts](https://github.com/learningequality/ricecooker/blob/master/docs/chefops.md) to learn about the command line args,
        for controlling chef operation, managing caches, and other options.
      - [Sushi chef style guide](https://docs.google.com/document/d/1_Wh7IxPmFScQSuIb9k58XXMbXeSM0ZQLkoXFnzKyi_s/edit)

  - **Ricecooker developers** should read all the documentation for chef authors,
    and also consult the docs in the [developer/](https://github.com/learningequality/ricecooker/blob/master/docs/developer) folder for
    additional information info about the "behind the scenes" work needed to
    support the Kolibri content pipeline:
    - [Running chef scripts](chefops.md), also known as **chefops**.
    - [Running chef scripts in daemon mode](https://github.com/learningequality/ricecooker/blob/master/docs/developer/daemonization.md)
    - [Managing the content pipeline](https://github.com/learningequality/ricecooker/blob/master/docs/developer/sushops.md), also known as **sushops**.

## Further reading

  - Read the [Kolibri Studio docs](http://kolibri-studio.readthedocs.io/en/latest/)
    to learn more about the Kolibri Studio features
  - Read the [Kolibri user guide](http://kolibri.readthedocs.io/en/latest/) to learn
    how to install Kolibri on your machine (useful for testing channels)
  - Read the [Kolibri developer docs](http://kolibri-dev.readthedocs.io/en/latest/)
    to learn about the inner workings of Kolibri.
