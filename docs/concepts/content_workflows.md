Content integration methods
===========================

There are two methods that you can use to create Kolibri channels:

  * **Manual content upload**:
    This method is suitable for content that is saved on your local computer such as files or folders.
    You can directly upload your content through the Kolibri Studio web interface.
    This method is appropriate for small and medium content sets.
    See the [Kolibri Studio User Guide](https://kolibri-studio.readthedocs.io/en/latest/) for more information.

  * **Uploading content using a content integration script**:
    You can use a content integration script (a.k.a. sushichef script) to
    integrate content from websites, content repositories, APIs, or other external sources.
    A content integration script is a Python program.


More information about each of these methods provided below.


## Manual content upload
You can use the [Kolibri Studio](https://studio.learningequality.org/) web interface
to upload various content types and organize them into channels. Kolibri Studio
allows you to explore pre-organized libraries of open educational resources,
and reuse them in your channels. You can also add tags, re-order, re-mix content,
and create exercises to support student's learning process.

To learn more about Studio, we recommend reading the following pages in the
[Kolibri Studio User Guide](https://kolibri-studio.readthedocs.io/en/latest/):
  - [Accessing Studio](https://kolibri-studio.readthedocs.io/en/latest/access_studio.html)
  - [Working with channels](https://kolibri-studio.readthedocs.io/en/latest/working_channels.html)
  - [Adding content to channels](https://kolibri-studio.readthedocs.io/en/latest/add_content.html)

When creating large channels (100+ content items) or channels that need to be
updated regularly, you should consider using a content integration script,
as described below.




## Content integration scripts

The [`ricecooker`](https://github.com/learningequality/ricecooker) framework is a
tool that programmers can use to upload content to Kolibri Studio in an automated
fashion. We refer to these import scripts as **sushi chefs**, because their job
is to chop-up the source material (e.g. an educational website) and package the
content items into tasty morsels (content items) with all the associated metadata.

Using the bulk import option requires the a content developer (sushi chef author)
to prepare the content, content metadata, and run the chef script to perform the
upload to Kolibri Studio.

Educators and content specialists can assist the developers by preparing a **spec sheet**
for the content source that provides detailed guidance for how content should be
structured and organized within the channel. The content specialist also plays a role
during the channel [review process](reviewing_channels.md).



The following alternative options are available for specifying the metadata for
content nodes that can be used in special circumstances.

### CSV metadata workflow
In addition to the web interface and the Python interface (`ricecooker`), there
exists an option for creating Kolibri channels by:
  - Organizing content items (documents, videos, mp3 files) into a folder hierarchy on the local file system
  - Specifying metadata in the form of CSV files created using Excel

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
