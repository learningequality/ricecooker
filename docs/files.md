
Files
=====


Base classes

    class File(object)
    class NodeFile(File)
    class DownloadFile(File)


Audio

    class AudioFile(DownloadFile)

PDFs

    class DocumentFile(DownloadFile)


HTML + CSS + JS in a zip file

    class HTMLZipFile(DownloadFile)


Videos

    class VideoFile(DownloadFile)
    class WebVideoFile(File)
    class YouTubeVideoFile(WebVideoFile)
    class SubtitleFile(DownloadFile)
    class YouTubeSubtitleFile(File)

Thumbs

    class ThumbnailFile(ThumbnailPresetMixin, DownloadFile)
    class TiledThumbnailFile(ThumbnailPresetMixin, File)
    class ExtractedVideoThumbnailFile(ThumbnailFile)

Images (supporting classes for Exercises)

    class Base64ImageFile(ThumbnailPresetMixin, File)
    class _ExerciseBase64ImageFile(Base64ImageFile)
    class _ExerciseImageFile(DownloadFile)
    class _ExerciseGraphieFile(DownloadFile)
