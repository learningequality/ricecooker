Migrating chefs from ricecooker 0.7 and 0.8
===========================================


Removed and changed APIs
------------------------
- `ChannelNode(channel_id=...)` is removed; a `get_channel` override that passes it raises
  `TypeError`.
- `channel_info["CHANNEL_ID"]` is rejected with a usage error; see [ids](developer/ids.md).
- `--resume` and `--step` are removed; see [chefops](chefops.md) for the current options.
- `ricecooker.utils.downloader` is removed; pass the page URL as `ContentNode(uri=...)`.
  See [downloader](downloader.md).
- A content node takes one primary file; see [content nodes](nodes.md#content-nodes).
- `PerseusQuestion` requires `ka_language`; see [exercise nodes](nodes.md#exercise-nodes).
- `Node.validate_tree()` is removed; the tree is validated before files are processed.
  See [upload process](developer/uploadprocess.md).
- `SlideshowNode` and `SlideImageFile` are removed, with no replacement; a json tree with a
  `slideshow` node or a `slideshow_image` file entry raises `NotImplementedError`.


Pass node arguments by keyword
------------------------------
These positional arguments bind to different parameters than in 0.7:

- `ContentNode`, `AudioNode`, `DocumentNode`, `HTML5AppNode`, `H5PAppNode`, `CustomNavigationNode`:
  4th `license_description` → `uri`, 5th `copyright_holder` → `pipeline`.
- `ExerciseNode`, `PracticeQuizNode`: 4th `questions` → `uri`, 5th `exercise_data` → `pipeline`.
- `TopicNode`: 6th onward, from `tags` → `copyright_holder`; each later argument moves three places.
- `ChannelNode`, `CustomNavigationChannelNode`: 3rd `tagline` → `title`, 4th `channel_id` → `tagline`.

Pass everything after `source_id` and `title` by keyword:

    TopicNode(source_id="t1", title="Topic", tags=["science"])
    ContentNode(source_id="c1", title="Page", license=my_license, uri="https://example.org/page")
    ExerciseNode(source_id="e1", title="Quiz", license=my_license, questions=[...])


`ricecooker.utils.utils` was split
----------------------------------
Import its helpers from their new modules:

- `is_valid_url`, `is_valid_uuid_string`: `ricecooker.utils.validators`
- `extract_path_ext`, `make_dir_if_needed`: `ricecooker.utils.paths`
- `get_hash`, `copy_file_to_storage`: `ricecooker.utils.storage`
- `VideoURLFormatError`: `ricecooker.utils.youtube`
