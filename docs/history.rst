=======
History
=======

0.6.46 (2020-09-21)
-------------------
* Add ``ricecooker.utils.youtube``, containing utilities for handling and caching YouTube videos and playlists.
* Improve validation of ``m`` and ``n`` mastery model values in ``ExerciseNode``.


0.6.45 (2020-07-25)
-------------------
* Remove SushiBar remote monitoring and remote command functionality


0.6.44 (2020-07-16)
-------------------
* Documentation overhaul and refresh, see `ricecooker.readthedocs.io <https://ricecooker.readthedocs.io/>`__
* Add support for specifying a Channel tagline
* Ensure we send ``extra_fields`` data for all node types
* Make ``--reset`` behavior the default
* Remove legacy code around ``compatibiliry_mode`` and BaseChef class
* Improved caching logic (no caching for thumbnails and local paths, always cache youtube downloads)
* Ensure chefs clean up after run (automatic temp files removal)
* Added ``save_channel_tree_as_json`` full channel metadata as part of every run.
* Added support for web content archiving
* Further improvements to logging
* Bugfix: deep deterministic cache keys for nested dicts values in ``ffmpeg_settings``


0.6.42 (2020-04-10)
-------------------
* Added ``--sample N`` command line option. Run script with ``--sample 10`` to
  produce a test version of the channel with 10 randomly selected nodes from
  the full channel. Use this to check transformations are working as expected.
* Added ``dryrun`` command. Use the command ``./sushichef.py dryrun`` to run the
  chef as normal but skip the step where the files get uploaded to Studio.
* Added HTTP proxy functionality for YouTubeVideoFile and YouTubeSubtitleFile
  Set the ``PROXY_LIST`` env variable to a ``;``-separated list of ``{ip}:{port}``.
  Ricecooker will detect the presence of the ``PROXY_LIST`` and use it when
  accessing resources via YoutubeDL. Alternatively, set ``USEPROXY`` env var
  to use a list of free proxy servers, which are very slow and not reliable.
* Improved colored logging functionality and customizability of logging output.


0.6.40 (2020-02-07)
-------------------
* Changed default behaviour to upload the staging tree instead of the main tree
* Added ``--deploy`` flag to reproduce old bahavior (upload to main tree)
* Added thumbnail generating methods for audio, HTML5, PDF, and ePub nodes.
  Set the ``derive_thumbnail=True`` when creating the Node instance, or pass the
  command line argument ``--thumbnails`` to generate thumbnails for all nodes.
  Note: automatic thumbnail generation will only work if ``thumbnail`` is None.


0.6.38 (2019-12-27)
-------------------
* Added support the ``h5p`` content kind and ``h5p`` file type
* Removed monkey-patching of ``localStorage`` and ``document.cookie``
  in the helper method ``download_static_assets``
* Added validation logic for tags
* Improved error reporting


0.6.36 (2019-09-25)
-------------------
* Added support for tags using the ``JsonChef`` workflow
* Added validation step to ensure subtitles file are unique for each language code
* Document new ``SlidesShow`` content kind coming in Kolibri 0.13
* Added docs with detailed instruction for content upload and update workflows
* Bugfixes to file extension logic and improved error handling around subtitles


0.6.32 (2019-08-01)
-------------------
* Updated documentation to use top-level headings
* Removed support for Python 3.4
* Removed support for the "sous chef" workflow


0.6.31 (2019-07-01)
-------------------
* Handle more subtitle convertible formats: ``SRT``, ``TTML``, ``SCC``, ``DFXP``, and ``SAMI``


0.6.30 (2019-05-01)
-------------------
* Updated docs build scripts to make ricecooker docs available on read the docs
* Added ``corrections`` command line script for making bulk edits to content metadata
* Added ``StudioApi`` client to support CRUD (created, read, update, delete) Studio actions
* Added pdf-splitting helper methods (see ``ricecooker/utils/pdf.py``)


0.6.23 (2018-11-08)
-------------------
* Updated ``le-utils`` and ``pressurcooker`` dependencies to latest version
* Added support for ePub files (``EPubFile`` s can be added of ``DocumentNode`` s)
* Added tag support
* Changed default value for ``STUDIO_URL`` to ``api.studio.learningequality.org``
* Added ``aggregator`` and ``provider`` fields for content nodes
* Various bugfixes to image processing in exercises
* Changed validation logic to use ``self.filename`` to check file format is in ``self.allowed_formats``
* Added ``is_youtube_subtitle_file_supported_language`` helper function to support importing youtube subs
* Added ``srt2vtt`` subtitles conversion
* Added static assets downloader helper method in ``utils.downloader.download_static_assets``
* Added LineCook chef functions to ``--generate`` CSV from directory structure
* Fixed the always ``randomize=True`` bug
* Docs: general content node metadata guidelines
* Docs: video compression instructions and helper scripts ``convertvideo.bat`` and ``convertvideo.sh``


0.6.17 (2018-04-20)
-------------------
* Added support for ``role`` attribute on ConentNodes (currently ``coach`` || ``learner``)
* Update pressurecooker dependency (to catch compression errors)
* Docs improvements, see https://github.com/learningequality/ricecooker/tree/master/docs


0.6.15 (2018-03-06)
-------------------
* Added support for non-mp4 video files, with auto-conversion using ffmpeg. See ``git diff b1d15fa 87f2528``
* Added CSV exercises workflow support to ``LineCook`` chef class
* Added --nomonitor CLI argument to disable sushibar functionality
* Defined new ENV variables:
  * PHANTOMJS_PATH: set this to a phantomjs binary (instead of assuming one in node_modules)
  * STUDIO_URL (alias CONTENTWORKSHOP_URL): set to URL of Kolibri Studio server where to upload files
* Various fixes to support sushi chefs
* Removed ``minimize_html_css_js`` utility function from ``ricecooker/utils/html.py``
  to remove dependency on ``css_html_js_minify`` and support Py3.4 fully.


0.6.9 (2017-11-14)
------------------
* Changed default logging level to --verbose
* Added support for cronjobs scripts via `--cmdsock` (see docs/daemonization.md)
* Added tools for creating HTML5Zip files in utils/html_writer.py
* Added utility for downloading HTML with optional js support in utils/downloader.py
* Added utils/path_builder.py and utils/data_writer.py for creating souschef archives
  (zip archive that contains files in a folder hierarchy + Channel.csv + Content.csv)


0.6.7 (2017-10-04)
------------------
* Sibling content nodes are now required to have unique source_id
* The field `copyright_holder` is required for all licenses other than public domain


0.6.7 (2017-10-04)
------------------
* Sibling content nodes are now required to have unique source_id
* The field `copyright_holder` is required for all licenses other than public domain


0.6.6 (2017-09-29)
------------------
* Added `JsonTreeChef` class for creating channels from ricecooker json trees
* Added `LineCook` chef class to support souschef-based channel workflows


0.6.4 (2017-08-31)
------------------
* Added `language` attribute for `ContentNode` (string key in internal repr. defined in le-utils)
* Made `language` a required attribute for ChannelNode
* Enabled sushibar.learningequality.org progress monitoring by default
  Set SUSHIBAR_URL env. var to control where progress is reported (e.g. http://localhost:8001)
* Updated le-utils and pressurecooker dependencies to latest


0.6.2 (2017-07-07)
------------------
* Clarify ricecooker is Python3 only (for now)
* Use https:// and wss:// for SuhiBar reporting


0.6.0 (2017-06-28)
------------------
* Remote progress reporting and logging to SushiBar (MVP version)
* New API based on the SuchiChef classes
* Support existing old-API chefs in compatibility mode



0.5.13 (2017-06-15)
-------------------
* Last stable release before SushiBar functionality was added
* Renamed --do-not-activate argument to --stage



0.1.0 (2016-09-30)
------------------
* First release on PyPI.

