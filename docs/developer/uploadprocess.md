Ricecooker content upload process
=================================
This page describes the "behind the scenes" operation of the `ricecooker` framework.
The goal is to give an overview of the processing steps that take place every
time you run a sushichef script. The goal of this page to help developers know
which parts of the code to look at when debugging ricecooker issues, adding
support for new content kinds and file types, or when implement performance optimizations.

Each section below describes one of the steps in this process.


Build tree
----------
The ricecooker tree consists of `Node` and `File` objects organized into a tree
data structure. The chef script must implement the `construct_channel` method,
which gets called by the ricecooker framework:

```python
    channel = chef.construct_channel(**kwargs)
```


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
Ricecooker then sends the list of filenames (using the content-hash based names)
to Studio to check which files are already present. 

```python
    get_file_diff(tree, files_to_diff)
        tree.get_file_diff(files_to_diff)
            config.SESSION.post(config.file_diff_url())
```

See [`managers/tree.py`](https://github.com/learningequality/ricecooker/blob/master/ricecooker/managers/tree.py)
for the code details. Any files that have been previously uploaded to Studio do
not need to be (re)uploaded, since Studio already has those files in storage.
Studio will reply with the "file difference" list of files that Studio does not have
and need to be uploaded, as described in the next section.


File upload
-----------
Guess what happens in this step?

```python
    upload_files(tree, file_diff)
        tree.upload_files(file_diff)
        tree.reattempt_upload_fails()
```

At the end of this process all the files from the local `storage/` directory will
also exist in the Studio's storage directory. You can verify this by trying to
access one of the files at `https://studio.learningequality.org/content/storage/c/0/c0ntetha5h0fdaf1le0a0e.ext`
with `c0ntetha5h0fdaf1le0a0e.ext` replaced by one of the filenames you find in
your local `storage/` directory. Note path prefix `c/0/` is used for filenames
starting with `c0`.

See [managers/tree.py](https://github.com/learningequality/ricecooker/blob/master/ricecooker/managers/tree.py) for details.



Structure upload
----------------
The final step happens in the function `tree.upload_tree()`, which repeatedly
calls the `add_nodes` method to upload the json metadata to Kolibri Studio,
and finally calls the `commit_channel` to finalize the process.

At the end of this chef step the complete channel (files, tree structure, and metadata)
is now on Studio. By default, the content is uploaded to a `staging` tree of the
channel, which is something like a "draft version" of the channel that is hidden
from Studio channel viewers but visible to channel editors.
The purpose of the staging tree is to allow channel editors can to review the
proposed changes in the "draft version" in the Studio web interface for changes
like nodes modified/added/removed and the total storage space requirements.


Deploying the channel (optional)
-------------------------------- 
Studio channel editors can use the `DEPLOY` button in the Studio web interface
to activate the "draft copy" and make it visible to all Studio users.
This is implemented by replacing the channel's `main` tree with the `staging` tree.
During [this step](https://github.com/learningequality/studio/blob/5564c1fc540d8a936fc2907c9d65bf0fb2bacb14/contentcuration/contentcuration/api.py#L103-L105), a "backup copy" of channel is saved, called the `previous_tree`.


Publish channel (optional)
--------------------------
The `PUBLISH` channel button on Studio is used to save and export a new version of the channel.
The PUBLISH action exports all the channel metadata to a sqlite3 DB file served 
by Studio at the URL `/content/{{channel_id}}.sqlite3` and ensure the associated
files exist in `/content/storage/` which is served by a CDN. 
This step is a prerequisite for getting the channel out of Studio and into Kolibri.
The combination of `{{channel_id}}.sqlite3` file and the files in `/content/storage`
define the Kolibri Channels content format. This is what gets exported to the folder
`KOLIBRI_DATA` on sdcard or external drives when you use the `EXPORT` action in Kolibri.






