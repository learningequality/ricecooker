=======
History
=======


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

