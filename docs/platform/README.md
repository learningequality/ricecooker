Kolibri content platform
========================
Educational content in the Kolibri platform is organized into **content channels**.
The `ricecooker` library is used for creating content channels and uploading them
to [Kolibri Studio](https://studio.learningequality.org/), which is the central
content server that [Kolibri](http://learningequality.org/kolibri/) applications
talk to when importing their content.

The Kolibri content pipeline is pictured below:

![The Kolibri Content Pipeline](../figures/content_pipeline_diagram.png)

This `ricecooker` framework is the "main actor" in the first part of the content
pipeline, and touches all aspects of the pipeline within the region highlighted
in blue in the above diagram.


Supported Content types
-----------------------
Kolibri channels are tree-like data structures that consist of the following types
of nodes:

  - Topic nodes (folders)
  - Content types:
    - Document (PDF files)
    - Audio (mp3 files)
    - Video (mp4 files)
    - HTML5App zip files (generic container for web content: HTML+JS+CSS)
    - Exercises, which contain different types of questions:
      - SingleSelectQuestion (multiple choice)
      - MultipleSelectQuestion (multiple choice with multiple correct answers)
      - InputQuestion (good for numeric inputs)
      - PerseusQuestion (a rich exercise question format developed at Khan Academy)

You can learn more about the content types supported by the Kolibri ecosystem
[here](./content_types.md).



Content import workflows
------------------------
The following options are available for importing content into Kolibri Studio.


### Kolibri Studio web interface
You can use the [Kolibri Studio](https://studio.learningequality.org/) web interface
to upload various content types and organize them into channels. Kolibri Studio
allows you to explore pre-organized libraries of open educational resources,
and reuse them in your channels. You can also add tags, re-order, re-mix content,
and create exercises to support student's learning process.

To learn more about Studio, we recommend reading the following pages in the
[Kolibri Studio User Guide](http://kolibri-studio.readthedocs.io/en/latest/):
  - [Accessing Studio](http://kolibri-studio.readthedocs.io/en/latest/access_studio.html)
  - [Working with channels](http://kolibri-studio.readthedocs.io/en/latest/working_channels.html)
  - [Adding content to channels](http://kolibri-studio.readthedocs.io/en/latest/add_content.html)

When creating large channels (50+ content items) or channels that need will be
updated regularly, you should consider using one of the bulk-import options below.



### Bulk-importing content programatically
The [`ricecooker`](https://github.com/learningequality/ricecooker) library is a
tool that programmers can use to upload content to Kolibri Studio in an automated
fashion. We refer to these import scripts as **sushi chefs**, because their job
is to chop-up the source material (e.g. an educational website) and package the
content items into tasty morsels (content items) with all the associated metadata.

Using the bulk import option requires the a content developer (sushi chef author)
to prepare the content, content metadata, and run the chef script to perform the
upload to Kolibri Studio.

Educators and content specialists can assist the developers by preparing a **spec sheet**
for the content source (usually a shared google doc), which provides detailed
instructions for how content should be structured and organized within the channel.

Consult [this document](https://docs.google.com/document/d/1slwoNT90Wqu0Rr8MJMAEsA-9LWLRvSeOgdg9u7HrZB8/edit?usp=sharing)
for more info about writing spec sheets.



### CSV metadata workflow
In addition to the web interface and the Python interface (`ricecooker`), there
exists a third option for creating Kolibri channels by:
  - Organizing content items (documents, videos, mp3 files) into a folder hierarchy
    on the local file system
  - Specifying metadata in the form of CSV files
    
The CSV-based workflow is a good fit for non-technical users since it doesn't 
require writing any code, but instead can use Excel to provide all the metadata.

  - [CSV-based workflow README](https://github.com/learningequality/sample-channels/tree/master/channels/csv_channel)
  - [Example content folder](https://github.com/learningequality/sample-channels/tree/master/channels/csv_exercises/content)
  - [Example Channel.csv metadata file](https://github.com/learningequality/sample-channels/blob/master/channels/csv_channel/content/Channel.csv)
  - [Example Content.csv metadata file](https://github.com/learningequality/sample-channels/blob/master/channels/csv_channel/content/Content.csv)
  - [CSV-based exercises info](https://github.com/learningequality/sample-channels/tree/master/channels/csv_exercises)

Organizing the content into folders and creating the CSV metadata files is most
of the work, and can be done by non-programmers.
The generic sushi chef script (`LineCook`) is then used to upload the channel.




Further reading
---------------

  - [Kolibri Studio User Guide](http://kolibri-studio.readthedocs.io/en/latest/index.html)
  - [Sample channels](https://github.com/learningequality/sample-channels)

