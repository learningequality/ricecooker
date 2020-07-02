Files
=====
Each `ricecooker` content node is associated with one or more files stored in a
content-addressable file storage system. For example, to store the file `sample.pdf`
we first compute `md5` hash of its contents (say `abcdef00000000000000000000000000`)
then store the file at the path `storage/a/b/abcdef00000000000000000000000000.pdf`.
The same storage mechanism is used on Kolibri Studio and Kolibri applications.


File objects
------------
The following file classes are defined in the module `ricecooker.classes.files`:

    AudioFile             # .mp3
    DocumentFile          # .pdf
    EPubFile              # .epub
    HTMLZipFile           # .zip containing HTML,JS,CSS
    H5PFile               # .h5p
    VideoFile             # .mp4 (`path` is local file system or url)
      WebVideoFile        # .mp4 (downloaded from `web_url`)
      YouTubeVideoFile    # .mp4 (downloaded from youtube based on `youtube_id`)
      SubtitleFile        # .vtt (`path` is local file system or url)
      YouTubeSubtitleFile # .vtt (downloaded from youtube based on `youtube_id` and `language`)
    SlideImageFile        # .png/.jpg an image that is part of a SlideshowNode
    ThumbnailFile         # .png/.jpg/.jpeg  (`path` is local file system or url)



Base classes
------------
The file classes extent the base classes `File(object)` and `DownloadFile(File)`.
When creating a file object, you must specify the following attributes:
  - `path` (str): this can be either local path like `dir/subdir/file.ext`, or
    a URL like 'http://site.org/dir/file.ext'.
  - `language` (str or `le_utils` language object): what is the language is the
    file contents.



### Path
The `path` attribute can be either a path on the local filesystem relative to the
current working directory of the chef script, or the URL of a web resource.

### Language
The Python package `le-utils` defines the internal language codes used throughout
the Kolibri platform (e.g. `en`, `es-MX`, and `zul`). To find the internal language
code for a given language, you can locate it in the [lookup table](https://github.com/learningequality/le-utils/blob/master/le_utils/resources/languagelookup.json),
or use one of the language lookup helper functions defined in `le_utils.constants.languages`:
  - `getlang(<code>) --> lang_obj`: basic lookup used to ensure `<code>` is a valid
    internal language code (otherwise returns `None`).
  - `getlang_by_name(<Language name in English>) --> lang_obj`: lookup by name, e.g. `French`
  - `getlang_by_native_name(<Language autonym>) --> lang_obj`: lookup by native name, e.g., `français`
  - `getlang_by_alpha2(<two-letter ISO 639-1 code>) --> lang_obj`: lookup by standard two-letter code, e.g `fr`

You can either pass `lang_obj` as the `language` attribute when creating nodes and files,
or pass the internal language code (str) obtained from the property `lang_obj.code`.
See [languages][./languages.md] to read more about language codes.



Audio files
-----------
Use the `AudioFile(DownloadFile)` class to store `mp3` files.


    audio_file = AudioFile(
        path='dir/subdir/lecture_recording.mp3',
        language=getlang('en').code
    )


Document files
--------------
Use the `DocumentFile` class to add PDF documents:

    document_file = DocumentFile(
        path='dir/subdir/lecture_slides.mp4',
        language=getlang('en').code
    )

Use the `EPubFile` class to add ePub documents:

    document_file = EPubFile(
        path='dir/subdir/lecture_slides.epub',
        language=getlang('en').code
    )



HTML files
-------------
The `HTML5ZipFile` class is a generic zip container for web content like HTML, CSS,
and JavaScript. To be a valid `HTML5ZipFile` file, the file must have a `index.html`
in its root. The file `index.html` will be loaded within a sandboxed iframe when
this content item is accessed on Kolibri.

Chef authors are responsible for scraping the HTML and all the related JS, CSS,
and images required to render the web content, and creating the zip file.
Creating a `HTML5ZipFile` is then done using

    document_file = HTML5ZipFile(
        path='/tmp/interactive_js_simulation.zip',
        language=getlang('en').code
    )


Use the `H5PFile` class to add [H5P](https://h5p.org/) files:

    h5p_file = H5PFile(
        path='dir/subdir/presentation.h5p',
        language=getlang('en').code
    )



Videos files
------------
The following file classes can be added to the `VideoNode`s:

    class VideoFile(DownloadFile)
    class WebVideoFile(File)
    class YouTubeVideoFile(WebVideoFile)
    class SubtitleFile(DownloadFile)
    class YouTubeSubtitleFile(File)


To create `VideoFile`, you need the code

    video_file = VideoFile(
        path='dir/subdir/lecture_video_recording.mp4',
        language=getlang('en').code
    )


VideoFiles can also be initialized with __ffmpeg_settings__ (dict),
which will be used to determine compression settings for the video file.
```
video_file = VideoFile(
    path = "file:///path/to/file.mp4",
    ffmpeg_settings = {"max_height": 480, "crf": 28},
    language=getlang('en').code
)
```

WebVideoFiles must be given a __web_url__ (str) to a video on YouTube or Vimeo,
and YouTubeVideoFiles must be given a __youtube_id__ (str).

```
video_file2 = WebVideoFile(
    web_url = "https://vimeo.com/video-id",
    language=getlang('en').code,
)

video_file3 = YouTubeVideoFile(
    youtube_id = "abcdef",
    language=getlang('en').code,
)
```

WebVideoFiles and YouTubeVideoFiles can also take in __download_settings__ (dict)
to determine how the video will be downloaded and __high_resolution__ (boolean)
to determine what resolution to download.


Subtitle files can be created using
```
subs_file = SubtitleFile(
    path = "file:///path/to/file.vtt",
    language = languages.getlang('en').code,
)
```
Kolibri uses the `.vtt` subtitle format internally, but the following formats can
be automatically converted: `.srt`, `.ttml`, `.scc`, `.dfxp`, and `.sami`.
The subtitle format is inferred from the file extension of the `path` argument.
Use the `subtitlesformat` keyword argument in cases where the path does not end
on a format extension:
```
subs_file = SubtitleFile(
    path = "http:/srtsubs.org/subs/29323923",
    subtitlesformat = 'srt',                 # specify format because not in URL
    language = languages.getlang('en').code,
)
```

You can also get subtitles using `YouTubeSubtitleFile` which takes a `youtube_id`
and youtube `language` code (may be different from internal language codes).
Use the helper method `is_youtube_subtitle_file_supported_language` to test if
a given youtube language code is supported by `YouTubeSubtitleFile` and skip the
ones that are not currently supported. Please let the LE content team know when
you run into language codes that are not supported so we can add them.



Thumbnail files
---------------
The class `ThumbnailFile` defined thumbnails that can be added to channel,
topic nodes, and content nodes. The extensions `.png`, `.jpg`, and `.jpeg` and supported.

The recommended size for thumbnail images is 400px by 225px (aspect ratio 16:9).


SlideImageFile files
--------------------
The `SlideImageFile` class is used in conjunction with the `SlideshowNode` class
to create powerpoint-like slideshow presentations.

    slide_image_file = SlideImageFile(
        path='some/local/path/firstslide.png',
        caption="The caption text to be displayed below the slide image",
        descriptive_text="Description of the slide for users that cannot see the image",
        language=getlang('en').code,
    )

Use the `caption` field to provide the text that will be displayed under the slide
image as part of the presentation. Use the `descriptive_text` field to provide
the "alt text" the image contents for visually impaired users.



File size limits
----------------
Kolibri Studio does not impose any max-size limits for files uploaded, but chef
authors need to keep in mind that content channels will often be downloaded over
slow internet connections and viewed on devices with limited storage.

Below are some general guidelines for handling video files:
  - Short videos (5-10 mins long) should be roughly less than 15MB
  - Longer video lectures (1 hour long) should not be larger than 200MB
  - High-resolution videos should be converted to lower resolution formats:
    Here are some recommended choices for video vertical resolution:
      - Use max height of `480` for videos that work well in low resolution (most videos)
      - Use max height of `720` for high resolution videos (lectures with writing on board)
  - Ricecooker can handle the video compression for you if you specify the
    `--compress` command line argument, or by setting the `ffmpeg_settings` property
    when creating `VideoFile`s. The default values for `ffmpeg_settings` are as follows:
    ```
    ffmpeg_settings = {'crf':32, 'max_height':480 }
    ```
  - The `ffmpeg` setting `crf` stands for Constant Rate Factor and is very useful
    for controlling overall video quality. Setting `crf=24` produces high quality
    video (and possibly large file size), `crf=28` is a mid-range quality, and
    values of `crf` above 30 produce highly-compressed videos with small size.

PDF files are usually not large, but PDFs with many pages (more than 50 pages)
can be difficult to views and browse on devices with small screens, so we
recommend that long PDF documents be split into separate parts.

Note: Kolibri Studio imposes a file storage quota on a per-user basis. By default
the storage limit for new accounts is 500MB. Please get in touch with the content
team by email (`content@le...`) if you need a quota increase.

