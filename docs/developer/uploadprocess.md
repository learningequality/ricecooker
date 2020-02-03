Ricecooker content upload process
=================================
This page describes the "behind the scenes" operation of the ricecooker library.
The goal is to give an overview of the processing steps that to help developers
know which parts of the code to look at to add new content kinds, file types, or
implement performance optimizations.


Build tree
----------
The ricececooker tree consists of `Node` and `File` objects organized into a tree
data structure. The chef script must implement the `construct_channel` method,
which gets called by the ricecooker framework:

    channel = chef.construct_channel(**kwargs)



Validation logic
----------------
Every ricecooker `Node` has a `validate` method that performs basic checks to
make sure the node's metadata is set correctly and necessary files are provided.
Each `File` subclass comes turn has it's own validation logic to ensure the file
provided has the appropriate extension.

The tree validation logic is initiated [here](https://github.com/learningequality/ricecooker/blob/master/ricecooker/managers/tree.py#L19-L24) when the channel's `validate_tree` method is called.

Note: the files have not been processed at this point, so the node and file
`validate` methods cannot do "deep checks" on the file contents yet.


File processing
---------------
The next step of the ricecooker run occurs when we call the `process_files`
method on each node object. The file processing is initiated [here](https://github.com/learningequality/ricecooker/blob/master/ricecooker/managers/tree.py#L26-L48) and proceeds recursively through the tree.

### Node.process_files

Each `Node` subclass implements the `process_files` method which includes the
following steps:
  - call `process_file` on all files associated with the node (described below)
  - if the node has children, `process_files` is called on all child nodes
  - call the node's `generate_thumbnail` method if it doesn't have a thumbnail
    already, and the node has `derive_thumbnail` set to True, or if the global
    command line argument `--thumbnail` (config.THUMBNAILS) is set to True.
    See notes section "Node.generate_thumbnail".

The result of the `node.process_file()` is a list of processed filenames, that
reference files in the content-addressable storage directory `/content/storage/`.

The list of files names can contain `None` values, which indicate that some the
file processing for a certain files has failed. These None values are filtered
out [here](https://github.com/learningequality/ricecooker/blob/master/ricecooker/managers/tree.py#L35)
before the list is passed onto the file diff and file upload steps.


### File.process_file
Each `File` subclass implements the `process_file` method that takes care of:
  - downloading the `path` (a web URL or a local filepath) and possibly,
    possibly performing format conversions (e.g. for videos and subtitles)
  - saves the file to the content-hash based filesystem in `/storage` and keeping
    track of the file saved in `.ricecookerfilecache`
  - optionally runs video compression on video file and records the output
    compressed version in `/storage` and `.ricecookerfilecache`


### Node.generate_thumbnail
Content Node subclasses can implement a the `generate_thumbnail` method that can
be used to automatically generate a thumbnail based on the node content.
The `generate_thumbnail` will return a `Thumbnail` object if the thumbnail
generation worked and the thumbnail will be added to the Node during inside the
`Node.process_files` method.

The actual thumbnail generation happens using one of the `pressurcooker` helper
functions that currently support PDF, ePub, HTML5, mp3 files, and videos.




File diff
---------

    get_file_diff(tree, files_to_diff)
        tree.get_file_diff(files_to_diff)
            config.SESSION.post(config.file_diff_url()

See [managers/tree.py](https://github.com/learningequality/ricecooker/blob/master/ricecooker/managers/tree.py) for details.


File upload
-----------

    upload_files(tree, file_diff)
        tree.upload_files(file_diff)
        tree.reattempt_upload_fails()

See [managers/tree.py](https://github.com/learningequality/ricecooker/blob/master/ricecooker/managers/tree.py) for details.


Structure upload
----------------
The final step happens in the function `tree.upload_tree()`, which repeatedly
calls the `add_nodes` method to upload the json metadata to Kolibri Studio.



Deploy and publish channel (optional)
-------------------------------------
At the end of the chef run the new content is uploaded to the stage channel
, there is optional deploy stage that

`tree.publish(channel_id)

