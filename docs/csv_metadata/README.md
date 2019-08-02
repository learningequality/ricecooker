CSV Metadata Workflow
=====================

It is possible to create Kolibri channels by:
  - Organizing content items (documents, videos, mp3 files) into a folder hierarchy
    on the local file system
  - Specifying metadata in the form of CSV files


The CSV-based workflow is a good fit for non-technical users since it doesn't
require writing any code, but instead can use the Excel to provide all the metadata.

  - [CSV-based workflow README](https://github.com/learningequality/sample-channels/tree/master/channels/csv_channel)
  - [Example content folder](https://github.com/learningequality/sample-channels/tree/master/channels/csv_exercises/content)
  - [Example Channel.csv metadata file](https://github.com/learningequality/sample-channels/blob/master/channels/csv_channel/content/Channel.csv)
  - [Example Content.csv metadata file](https://github.com/learningequality/sample-channels/blob/master/channels/csv_channel/content/Content.csv)

Organizing the content into folders and creating the CSV metadata files is most
of the work, and can be done by non-programmers.
The generic sushi chef script (`LineCook`) is then used to upload the channel.


CSV Exercises
-------------
You can also use the CSV metadata workflow to upload simple exercises to Kolibri Studio.
See [this doc](./csv_exercises.md) for the technical details about creating exercises.
