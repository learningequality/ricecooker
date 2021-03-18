# Node models to represent channel's tree

import json
import uuid
import os
import csv

from le_utils.constants import content_kinds, exercises, file_formats, format_presets, languages, roles

from .licenses import License
from .. import config, __version__
from ..exceptions import InvalidNodeException

MASTERY_MODELS = [id for id, name in exercises.MASTERY_MODELS]
ROLES = [id for id, name in roles.choices]

class Node(object):
    """ Node: model to represent all nodes in the tree """
    license = None
    language = None

    def __init__(self, title, language=None, description=None, thumbnail=None, files=None, derive_thumbnail=False, node_modifications = {}, extra_fields=None):
        self.files = []
        self.children = []
        self.descendants = []
        self.parent = None
        self.node_id = None
        self.content_id = None
        self.title = title
        self.set_language(language)
        self.description = description or ""
        self.derive_thumbnail = derive_thumbnail
        self.extra_fields = extra_fields or {}

        for f in files or []:
            self.add_file(f)

        self.set_thumbnail(thumbnail)
        # save modifications passed in by csv
        self.node_modifications = node_modifications

    def set_language(self, language):
        """ Set self.language to internal lang. repr. code from str or Language object. """
        if isinstance(language, str):
            language_obj = languages.getlang(language)
            if language_obj:
                self.language = language_obj.code
            else:
                raise TypeError("Language code {} not found".format(language))
        if isinstance(language, languages.Language):
            self.language = language.code

    def __str__(self):
        count = self.count()
        metadata = "{0} {1}".format(count, "descendant" if count == 1 else "descendants")
        return "{title} ({kind}): {metadata}".format(title=self.title, kind=self.__class__.__name__, metadata=metadata)

    def truncate_fields(self):
        if len(self.title) > config.MAX_TITLE_LENGTH:
            config.print_truncate("title", self.source_id, self.title, kind=self.kind)
            self.title = self.title[:config.MAX_TITLE_LENGTH]

        if self.source_id and len(self.source_id) > config.MAX_SOURCE_ID_LENGTH:
            config.print_truncate("source_id", self.source_id, self.source_id, kind=self.kind)
            self.source_id = self.source_id[:config.MAX_SOURCE_ID_LENGTH]

        for f in self.files:
            f.truncate_fields()

    def to_dict(self):
        """ to_dict: puts data in format CC expects
            Args: None
            Returns: dict of channel data
        """
        pass

    def add_child(self, node):
        """ add_child: Adds child node to node
            Args: node to add as child
            Returns: None
        """
        assert isinstance(node, Node), "Child node must be a subclass of Node"
        node.parent = self
        self.children += [node]

    def add_file(self, file_to_add):
        """ add_file: Add to node's associated files
            Args: file_to_add (File): file model to add to node
            Returns: None
        """
        from .files import File
        assert isinstance(file_to_add, File), "Files being added must be instances of a subclass of File class"
        file_to_add.node = self
        if file_to_add not in self.files:
            self.files.append(file_to_add)

    def generate_thumbnail(self):
        """Each node subclass implements its own thumbnail generation logic.

        Returns:
            A Thumbnail object (unprocessed) or None.
        """
        return None

    def has_thumbnail(self):
        from .files import ThumbnailFile
        return any(f for f in self.files if isinstance(f, ThumbnailFile))
        # TODO deep check: f.process_file() and check f.filename is not None

    def set_thumbnail(self, thumbnail):
        """ set_thumbnail: Set node's thumbnail
            Args: thumbnail (ThumbnailFile): file model to add to node
            Returns: None
        """
        self.thumbnail = thumbnail
        if isinstance(self.thumbnail, str):
            from .files import ThumbnailFile
            self.thumbnail = ThumbnailFile(path=self.thumbnail)

        if self.thumbnail:
            self.add_file(self.thumbnail)

    def get_thumbnail_preset(self):
        """
        Returns the format preset corresponding to this Node's type,
        or None if the node doesn't have a format preset.
        """
        if isinstance(self, ChannelNode):
            return format_presets.CHANNEL_THUMBNAIL
        elif isinstance(self, TopicNode):
            return format_presets.TOPIC_THUMBNAIL
        elif isinstance(self, VideoNode):
            return format_presets.VIDEO_THUMBNAIL
        elif isinstance(self, AudioNode):
            return format_presets.AUDIO_THUMBNAIL
        elif isinstance(self, DocumentNode):
            return format_presets.DOCUMENT_THUMBNAIL
        elif isinstance(self, ExerciseNode):
            return format_presets.EXERCISE_THUMBNAIL
        elif isinstance(self, HTML5AppNode):
            return format_presets.HTML5_THUMBNAIL
        else:
            return None

    def process_files(self):
        """Processes all the files associated with this Node, including:
        - download files if not present in the local storage
        - convert and compress video files
        - (optionally) generate thumbnail file from the node's content
        Returns: content-hash based filenames of all the files for this node
        """
        filenames = []
        for file in self.files:
            filenames.append(file.process_file())

        # Auto-generation of thumbnails happens here if derive_thumbnail or config.THUMBNAILS is set
        if not self.has_thumbnail() and (config.THUMBNAILS or self.derive_thumbnail):
            thumbnail_file = self.generate_thumbnail()
            if thumbnail_file:
                thumbnail_filename = thumbnail_file.process_file()
                if thumbnail_filename:
                    self.set_thumbnail(thumbnail_file)
                    filenames.append(thumbnail_filename)
                else:
                    pass  # failed to generate thumbnail
            else:
                pass  # method generate_thumbnail is not implemented or no suitable source file found

        return filenames

    def count(self):
        """ count: get number of nodes in tree
            Args: None
            Returns: int
        """
        total = len(self.children)
        for child in self.children:
            total += child.count()
        return total

    def get_topic_count(self):
        """ get_topic_count: get number of topics in tree
            Args: None
            Returns: int
        """
        total = 0
        if self.kind == content_kinds.TOPIC or self.kind == "Channel":
            total = 1
            for child in self.children:
                total += child.get_topic_count()
        return total

    def get_non_topic_descendants(self):
        if len(self.descendants) == 0:
            for child_node in self.children:
                if child_node.kind == content_kinds.TOPIC:
                    self.descendants += child_node.get_non_topic_descendants()
                elif child_node not in self.descendants:
                    self.descendants.append(child_node)
        return self.descendants

    def print_tree(self, indent=2):
        """ print_tree: prints out structure of tree
            Args: indent (int): What level of indentation at which to start printing
            Returns: None
        """
        config.LOGGER.info("{indent}{data}".format(indent="   " * indent, data=str(self)))
        for child in self.children:
            child.print_tree(indent + 1)

    def get_json_tree(self):
        tree = self.to_dict()
        if len(self.children) > 0:
            tree['children'] = []
            for child in self.children:
                tree['children'].append(child.get_json_tree())

        return tree


    def save_channel_children_to_csv(self, metadata_csv, structure_string = ''):
        # Not including channel title in topic structure
        is_channel = isinstance(self, ChannelNode)
        if not is_channel:
            # Build out tag string
            tags_string = ','.join(self.tags)
            new_title = self.node_modifications.get('New Title') or ''
            new_description = self.node_modifications.get('New Description') or ''
            new_tags = self.node_modifications.get('New Tags') or ''
            # New Tags is being saved as a list. Check if list and if so, join to correctly write it to csv
            if isinstance(new_tags, list):
                new_tags = ','.join(new_tags)

            record = [
                self.source_id,
                structure_string,
                self.title,
                new_title,        # New Title
                self.description,
                new_description,  # New Description
                tags_string,
                new_tags,         # New Tags
                ''                # Last Modified
            ]
            metadata_csv.writerow(record)

            current_level = self.title
            # add current level to structure_string_list
            if structure_string == '':
                structure_string = self.title
            else:
                structure_string += '/' + self.title
            print(self.title)
            print(structure_string)
        for child in self.children:
            child.save_channel_children_to_csv(metadata_csv, structure_string)


    def validate_tree(self):
        """
        Validate all nodes in this tree recusively.
          Args: None
          Returns: boolean indicating if tree is valid
        """
        self.validate()
        for child in self.children:
            assert child.validate_tree()
        return True

    def validate(self):
        """ validate: Makes sure node is valid
            Args: None
            Returns: boolean indicating if node is valid
        """
        from .files import File

        assert self.source_id is not None, "Assumption Failed: Node must have a source_id"
        assert isinstance(self.title, str), "Assumption Failed: Node title is not a string"
        assert len(self.title.strip()) > 0, "Assumption Failed: Node title cannot be empty"
        assert isinstance(self.description, str) or self.description is None, "Assumption Failed: Node description is not a string"
        assert isinstance(self.children, list), "Assumption Failed: Node children is not a list"
        for f in self.files:
            assert isinstance(f, File), "Assumption Failed: files must be file class"
            f.validate()

        source_ids = [c.source_id for c in self.children]
        duplicates = set([x for x in source_ids if source_ids.count(x) > 1])
        assert len(duplicates) == 0, "Assumption Failed: Node must have unique source id among siblings ({} appears multiple times)".format(duplicates)
        return True


class ChannelNode(Node):
    """ Model representing the channel you are creating

        Used to store metadata on channel that is being created

        Attributes:
            source_id (str): channel's unique id
            source_domain (str): who is providing the content (e.g. learningequality.org)
            title (str): name of channel
            description (str): description of the channel (optional)
            thumbnail (str): file path or url of channel's thumbnail (optional)
            files ([<File>]): list of file objects for node (optional)
    """
    kind = "Channel"
    def __init__(self, source_id, source_domain, tagline=None, channel_id=None, *args, **kwargs):
        # Map parameters to model variables
        self.channel_id = channel_id
        self.source_domain = source_domain
        self.source_id = source_id
        self.tagline = tagline

        super(ChannelNode, self).__init__(*args, **kwargs)

    def get_domain_namespace(self):
        return uuid.uuid5(uuid.NAMESPACE_DNS, self.source_domain)

    def get_content_id(self):
        return uuid.uuid5(self.get_domain_namespace(), self.get_node_id().hex)

    def get_node_id(self):
        return uuid.uuid5(self.get_domain_namespace(), self.source_id)

    def truncate_fields(self):
        if self.description and len(self.description) > config.MAX_DESCRIPTION_LENGTH:
            config.print_truncate("description", self.source_id, self.description, kind=self.kind)
            self.description = self.description[:config.MAX_DESCRIPTION_LENGTH]
        if self.tagline and len(self.tagline) > config.MAX_TAGLINE_LENGTH:
            config.print_truncate("tagline", self.source_id, self.tagline, kind=self.kind)
            self.tagline = self.tagline[:config.MAX_TAGLINE_LENGTH]
        super(ChannelNode, self).truncate_fields()

    def to_dict(self):
        """ to_dict: puts channel data into the format that Kolibri Studio expects
            Args: None
            Returns: dict of channel data
        """
        return {
            "id": self.channel_id or self.get_node_id().hex,
            "name": self.title,
            "thumbnail": self.thumbnail.filename if self.thumbnail else None,
            "language" : self.language,
            "description": self.description or "",
            "tagline": self.tagline or "",
            "license": self.license,
            "source_domain": self.source_domain,
            "source_id": self.source_id,
            "ricecooker_version": __version__,
            "extra_fields": json.dumps(self.extra_fields),
            "files": [f.to_dict() for f in self.files if f and f.filename and not (self.thumbnail and self.thumbnail.filename is f.filename)],
        }

    def validate(self):
        """ validate: Makes sure channel is valid
            Args: None
            Returns: boolean indicating if channel is valid
        """
        try:
            assert isinstance(self.source_domain, str), "Channel domain must be a string"
            assert self.language, "Channel must have a language"
            return super(ChannelNode, self).validate()
        except AssertionError as ae:
            raise InvalidNodeException("Invalid channel ({}): {} - {}".format(ae.args[0], self.title, self.__dict__))


class TreeNode(Node):
    """ Model representing the content nodes in the channel's tree

        Base model for different content node kinds (topic, video, exercise, etc.)

        Attributes:
            source_id (str): content's original id
            title (str): content's title
            license (str or <License>): content's license
            description (str): description of content (optional)
            author (str): who created the content (optional)
            aggregator (str): website or org hosting the content collection but not necessarily the creator or copyright holder (optional)
            provider (str): organization that commissioned or is distributing the content (optional)
            thumbnail (str): local path or url to thumbnail image (optional)
            files ([<File>]): list of file objects for node (optional)
            tags ([str]): list of tags for node (optional)
            extra_fields (dict): any additional data needed for node (optional)
            domain_ns (str): who is providing the content (e.g. learningequality.org) (optional)
    """
    def __init__(self, source_id, title, author="", aggregator="", provider="", tags=None, domain_ns=None, **kwargs):
        # Map parameters to model variables
        assert isinstance(source_id, str), "source_id must be a string"
        self.source_id = source_id
        self.author = author or ""
        self.aggregator = aggregator or ""
        self.provider = provider or ""
        self.tags = tags or []
        self.domain_ns = domain_ns
        self.questions = self.questions if hasattr(self, 'questions') else [] # Needed for to_dict method

        super(TreeNode, self).__init__(title, **kwargs)

    def get_domain_namespace(self):
        if not self.domain_ns:
            self.domain_ns = self.parent.get_domain_namespace()
        return self.domain_ns

    def get_content_id(self):
        if not self.content_id:
            self.content_id = uuid.uuid5(self.get_domain_namespace(), self.source_id)
        return self.content_id

    def get_node_id(self):
        assert self.parent, "Parent not found: node id must be calculated based on parent"
        if not self.node_id:
            self.node_id = uuid.uuid5(self.parent.get_node_id(), self.get_content_id().hex)
        return self.node_id


    def truncate_fields(self):
        if self.author and len(self.author) > config.MAX_AUTHOR_LENGTH:
            config.print_truncate("author", self.source_id, self.author, kind=self.kind)
            self.author = self.author[:config.MAX_AUTHOR_LENGTH]

        if self.aggregator and len(self.aggregator) > config.MAX_AGGREGATOR_LENGTH:
            config.print_truncate("aggregator", self.source_id, self.aggregator, kind=self.kind)
            self.aggregator = self.aggregator[:config.MAX_AGGREGATOR_LENGTH]

        if self.provider and len(self.provider) > config.MAX_PROVIDER_LENGTH:
            config.print_truncate("provider", self.source_id, self.provider, kind=self.kind)
            self.provider = self.provider[:config.MAX_PROVIDER_LENGTH]

        self.license and self.license.truncate_fields()

        super(TreeNode, self).truncate_fields()


    def to_dict(self):
        """ to_dict: puts Topic or Content node data into the format that Kolibri Studio expects
            Args: None
            Returns: dict of channel data
        """
        return {
            "title": self.node_modifications.get('New Title') or self.title,
            "language" : self.language,
            "description": self.node_modifications.get('New Description') or self.description,
            "node_id": self.get_node_id().hex,
            "content_id": self.get_content_id().hex,
            "source_domain": self.domain_ns.hex,
            "source_id": self.source_id,
            "author": self.author,
            "aggregator": self.aggregator,
            "provider": self.provider,
            "files" : [f.to_dict() for f in self.files if f and f.filename], # Filter out failed downloads
            "tags": self.node_modifications.get('New Tags') or self.tags,
            "kind": self.kind,
            "license": None,
            "license_description": None,
            "copyright_holder": "",
            "questions": [],
            "extra_fields": json.dumps(self.extra_fields),
        }

    def validate(self):
        """ validate: Makes sure content node is valid
            Args: None
            Returns: boolean indicating if content node is valid
        """
        assert isinstance(self.author, str) , "Assumption Failed: Author is not a string"
        assert isinstance(self.aggregator, str) , "Assumption Failed: Aggregator is not a string"
        assert isinstance(self.provider, str) , "Assumption Failed: Provider is not a string"
        assert isinstance(self.files, list), "Assumption Failed: Files is not a list"
        assert isinstance(self.questions, list), "Assumption Failed: Questions is not a list"
        assert isinstance(self.extra_fields, dict), "Assumption Failed: Extra fields is not a dict"
        assert isinstance(self.tags, list), "Assumption Failed: Tags is not a list"
        for tag in self.tags:
            assert isinstance(tag, str) , "Assumption Failed: Tag is not a string"
            assert len(tag) <= 50, "ERROR: tag " + tag + " is too long. Tags should be 50 chars or less."
        return super(TreeNode, self).validate()


class TopicNode(TreeNode):
    """ Model representing channel topics

        Topic nodes are used to add organization to the channel's content

        Attributes:
            source_id (str): content's original id
            title (str): content's title
            description (str): description of content (optional)
            thumbnail (str): local path or url to thumbnail image (optional)
            derive_thumbnail (bool): set to generate tiled thumbnail from children (optional)
    """
    kind = content_kinds.TOPIC

    def generate_thumbnail(self):
        """Generate a ``TiledThumbnailFile`` based on the descendants.
        Returns: a Thumbnail file or None.
        """
        from .files import TiledThumbnailFile
        return TiledThumbnailFile(self.get_non_topic_descendants())

    def validate(self):
        """ validate: Makes sure topic is valid
            Args: None
            Returns: boolean indicating if topic is valid
        """
        try:
            assert self.kind == content_kinds.TOPIC, "Assumption Failed: Node is supposed to be a topic"
            return super(TopicNode, self).validate()
        except AssertionError as ae:
            raise InvalidNodeException("Invalid node ({}): {} - {}".format(ae.args[0], self.title, self.__dict__))


class ContentNode(TreeNode):
    """ Model representing the content nodes in the channel's tree

        Base model for different content node kinds (topic, video, exercise, etc.)

        Attributes:
            source_id (str): content's original id
            title (str): content's title
            license (str or <License>): content's license
            description (str): description of content (optional)
            author (str): who created the content (optional)
            aggregator (str): website or org hosting the content collection but not necessarily the creator or copyright holder (optional)
            provider (str): organization that commissioned or is distributing the content (optional)
            role (str): set to roles.COACH for teacher-facing materials (default roles.LEARNER)
            thumbnail (str): local path or url to thumbnail image (optional)
            derive_thumbnail (bool): set to generate thumbnail from content (optional)
            files ([<File>]): list of file objects for node (optional)
            extra_fields (dict): any additional data needed for node (optional)
            domain_ns (str): who is providing the content (e.g. learningequality.org) (optional)
    """
    required_file_format = None

    def __init__(self, source_id, title, license, role=roles.LEARNER, license_description=None, copyright_holder=None, **kwargs):
        self.role = role
        self.set_license(license, copyright_holder=copyright_holder, description=license_description)
        super(ContentNode, self).__init__(source_id, title, **kwargs)

    def __str__(self):
        metadata = "{0} {1}".format(len(self.files), "file" if len(self.files) == 1 else "files")
        return "{title} ({kind}): {metadata}".format(title=self.title, kind=self.__class__.__name__, metadata=metadata)

    def set_license(self, license, copyright_holder=None, description=None):
        # Add license (create model if it's just a path)
        if isinstance(license, str):
            from .licenses import get_license
            license = get_license(license, copyright_holder=copyright_holder, description=description)
        self.license = license

    def validate(self):
        """ validate: Makes sure content node is valid
            Args: None
            Returns: boolean indicating if content node is valid
        """
        assert self.role in ROLES, "Assumption Failed: Role must be one of the following {}".format(ROLES)
        assert isinstance(self.license, str) or isinstance(self.license, License), "Assumption Failed: License is not a string or license object"
        self.license.validate()
        # if self.required_file_format:
        #     files_valid = False
        #     #not any(f for f in self.files if isinstance(f, DownloadFile))
        #     for f in self.files:
        #         files_valid = files_valid or (f.path.endswith(self.required_file_format)
        #     assert files_valid , "Assumption Failed: Node should have at least one {} file".format(self.required_file_format)
        return super(ContentNode, self).validate()

    def to_dict(self):
        """ to_dict: puts data in format CC expects
            Args: None
            Returns: dict of channel data
        """
        return {
            "title": self.node_modifications.get('New Title') or self.title,
            "language" : self.language,
            "description": self.node_modifications.get('New Description') or self.description,
            "node_id": self.get_node_id().hex,
            "content_id": self.get_content_id().hex,
            "source_domain": self.domain_ns.hex,
            "source_id": self.source_id,
            "author": self.author,
            "aggregator": self.aggregator,
            "provider": self.provider,
            "files" : [f.to_dict() for f in filter(lambda x: x and x.filename, self.files)], # Filter out failed downloads
            "tags": self.node_modifications.get('New Tags') or self.tags,
            "kind": self.kind,
            "license": self.license.license_id,
            "license_description": self.license.description,
            "copyright_holder": self.license.copyright_holder,
            "questions": [question.to_dict() for question in self.questions],
            "extra_fields": json.dumps(self.extra_fields),
            "role": self.role,
        }


class VideoNode(ContentNode):
    """ Model representing videos in channel

        Videos must be mp4 or webm format

        Attributes:
            source_id (str): content's original id
            title (str): content's title
            license (str or <License>): content's license
            author (str): who created the content (optional)
            aggregator (str): website or org hosting the content collection but not necessarily the creator or copyright holder (optional)
            provider (str): organization that commissioned or is distributing the content (optional)
            description (str): description of content (optional)
            derive_thumbnail (bool): set to generate thumbnail from video (optional)
            thumbnail (str): local path or url to thumbnail image (optional)
            extra_fields (dict): any additional data needed for node (optional)
            domain_ns (str): who is providing the content (e.g. learningequality.org) (optional)
            files ([<File>]): list of file objects for node (optional)
    """
    kind = content_kinds.VIDEO
    required_file_format = (file_formats.MP4, file_formats.WEBM)

    def __init__(self, source_id, title, license, **kwargs):
        super(VideoNode, self).__init__(source_id, title, license, **kwargs)

    def generate_thumbnail(self):
        from .files import VideoFile, WebVideoFile, ExtractedVideoThumbnailFile
        video_files = [f for f in self.files if isinstance(f, VideoFile) or isinstance(f, WebVideoFile)]
        if video_files:
            video_file = video_files[0]
            if video_file.filename and not video_file.error:
                storage_path = config.get_storage_path(video_file.filename)
                return ExtractedVideoThumbnailFile(storage_path)
        return None

    def validate(self):
        """ validate: Makes sure video is valid
            Args: None
            Returns: boolean indicating if video is valid
        """
        from .files import VideoFile, WebVideoFile, SubtitleFile, YouTubeSubtitleFile
        try:
            assert self.kind == content_kinds.VIDEO, "Assumption Failed: Node should be a video"
            assert self.questions == [], "Assumption Failed: Video should not have questions"
            assert len(self.files) > 0, "Assumption Failed: Video must have at least one video file"

            # Check if there are any .mp4 files if there are video files (other video types don't have paths)
            assert any(f for f in self.files if isinstance(f, VideoFile) or isinstance(f, WebVideoFile)), "Assumption Failed: Video node should have at least one video file"

            # Ensure that there is only one subtitle file per language code
            new_files = []
            language_codes_seen = set()
            for file in self.files:
                if isinstance(file, SubtitleFile) or isinstance(file, YouTubeSubtitleFile):
                    language_code = file.language
                    if language_code not in language_codes_seen:
                        new_files.append(file)
                        language_codes_seen.add(language_code)
                    else:
                        file_info = file.path if hasattr(file, 'path') else file.youtube_url
                        config.LOGGER.warning('Skipping duplicate subs for ' + language_code + ' from ' + file_info)
                else:
                    new_files.append(file)
            self.files = new_files

            return super(VideoNode, self).validate()

        except AssertionError as ae:
            raise InvalidNodeException("Invalid node ({}): {} - {}".format(ae.args[0], self.title, self.__dict__))


class AudioNode(ContentNode):
    """ Model representing audio content in channel

        Audio must be in mp3 format

        Attributes:
            source_id (str): content's original id
            title (str): content's title
            license (str or <License>): content's license
            author (str): who created the content (optional)
            aggregator (str): website or org hosting the content collection but not necessarily the creator or copyright holder (optional)
            provider (str): organization that commissioned or is distributing the content (optional)
            description (str): description of content (optional)
            thumbnail (str): local path or url to thumbnail image (optional)
            derive_thumbnail (bool): set to generate waveform thumbnail (optional)
            extra_fields (dict): any additional data needed for node (optional)
            domain_ns (str): who is providing the content (e.g. learningequality.org) (optional)
            files ([<File>]): list of file objects for node (optional)
    """
    kind = content_kinds.AUDIO
    required_file_format = file_formats.MP3

    def generate_thumbnail(self):
        from .files import AudioFile, ExtractedAudioThumbnailFile
        audio_files = [f for f in self.files if isinstance(f, AudioFile)]
        if audio_files:
            audio_file = audio_files[0]
            if audio_file.filename and not audio_file.error:
                storage_path = config.get_storage_path(audio_file.filename)
                return ExtractedAudioThumbnailFile(storage_path)
        return None


    def validate(self):
        """ validate: Makes sure audio is valid
            Args: None
            Returns: boolean indicating if audio is valid
        """
        from .files import AudioFile
        try:
            assert self.kind == content_kinds.AUDIO, "Assumption Failed: Node should be audio"
            assert self.questions == [], "Assumption Failed: Audio should not have questions"
            assert len(self.files) > 0, "Assumption Failed: Audio should have at least one file"
            assert [f for f in self.files if isinstance(f, AudioFile)], "Assumption Failed: Audio should have at least one audio file"
            return super(AudioNode, self).validate()
        except AssertionError as ae:
            raise InvalidNodeException("Invalid node ({}): {} - {}".format(ae.args[0], self.title, self.__dict__))


class DocumentNode(ContentNode):
    """ Model representing documents in channel

        Documents must be in PDF or ePub format

        Attributes:
            source_id (str): content's original id
            title (str): content's title
            license (str or <License>): content's license
            author (str): who created the content (optional)
            aggregator (str): website or org hosting the content collection but not necessarily the creator or copyright holder (optional)
            provider (str): organization that commissioned or is distributing the content (optional)
            description (str): description of content (optional)
            thumbnail (str): local path or url to thumbnail image (optional)
            derive_thumbnail (bool): automatically generate thumbnail (optional)
            extra_fields (dict): any additional data needed for node (optional)
            domain_ns (str): who is providing the content (e.g. learningequality.org) (optional)
            files ([<File>]): list of file objects for node (optional)
    """
    kind = content_kinds.DOCUMENT
    required_file_format = file_formats.PDF # TODO(ivan) change ro allowed_formats

    def validate(self):
        """ validate: Makes sure document node contains at least one EPUB or PDF
            Args: None
            Returns: boolean indicating if document is valid
        """
        from .files import DocumentFile, EPubFile
        try:
            assert self.kind == content_kinds.DOCUMENT, "Assumption Failed: Node should be a document"
            assert self.questions == [], "Assumption Failed: Document should not have questions"
            assert len(self.files) > 0, "Assumption Failed: Document should have at least one file"
            assert [f for f in self.files if isinstance(f, DocumentFile) or isinstance(f, EPubFile)], \
                "Assumption Failed: Document should have at least one document file"
            return super(DocumentNode, self).validate()
        except AssertionError as ae:
            raise InvalidNodeException("Invalid node ({}): {} - {}".format(ae.args[0], self.title, self.__dict__))

    def generate_thumbnail(self):
        from .files import DocumentFile, EPubFile, ExtractedPdfThumbnailFile, ExtractedEPubThumbnailFile
        pdf_files = [f for f in self.files if isinstance(f, DocumentFile)]
        epub_files = [f for f in self.files if isinstance(f, EPubFile)]
        if pdf_files and epub_files:
            raise InvalidNodeException("Invalid node (both PDF and ePub provided): {} - {}".format(self.title, self.__dict__))
        elif pdf_files:
            pdf_file = pdf_files[0]
            if pdf_file.filename and not pdf_file.error:
                storage_path = config.get_storage_path(pdf_file.filename)
                return ExtractedPdfThumbnailFile(storage_path)
        elif epub_files:
            epub_file = epub_files[0]
            if epub_file.filename and not epub_file.error:
                storage_path = config.get_storage_path(epub_file.filename)
                return ExtractedEPubThumbnailFile(storage_path)
        return None


class HTML5AppNode(ContentNode):
    """ Model representing a zipped HTML5 application

        The zip file must contain a file called index.html, which will be the first page loaded.
        All links (e.g. href and src) must be relative URLs, pointing to other files in the zip.

        Attributes:
            source_id (str): content's original id
            title (str): content's title
            license (str or <License>): content's license
            author (str): who created the content (optional)
            aggregator (str): website or org hosting the content collection but not necessarily the creator or copyright holder (optional)
            provider (str): organization that commissioned or is distributing the content (optional)
            description (str): description of content (optional)
            thumbnail (str): local path or url to thumbnail image (optional)
            derive_thumbnail (bool): generate thumbnail from largest image inside zip (optional)
            extra_fields (dict): any additional data needed for node (optional)
            domain_ns (str): who is providing the content (e.g. learningequality.org) (optional)
            files ([<File>]): list of file objects for node (optional)
    """
    kind = content_kinds.HTML5
    required_file_format = file_formats.HTML5

    def generate_thumbnail(self):
        from .files import HTMLZipFile, ExtractedHTMLZipThumbnailFile
        html5_files = [f for f in self.files if isinstance(f, HTMLZipFile)]
        if html5_files:
            html_file = html5_files[0]
            if html_file.filename and not html_file.error:
                storage_path = config.get_storage_path(html_file.filename)
                return ExtractedHTMLZipThumbnailFile(storage_path)
        else:
            return None

    def validate(self):
        """ validate: Makes sure HTML5 app is valid
            Args: None
            Returns: boolean indicating if HTML5 app is valid
        """
        from .files import HTMLZipFile
        try:
            assert self.kind == content_kinds.HTML5, "Assumption Failed: Node should be an HTML5 app"
            assert self.questions == [], "Assumption Failed: HTML should not have questions"
            assert [f for f in self.files if isinstance(f, HTMLZipFile)], "Assumption Failed: HTML should have at least one html file"
            return super(HTML5AppNode, self).validate()
        except AssertionError as ae:
            raise InvalidNodeException("Invalid node ({}): {} - {}".format(ae.args[0], self.title, self.__dict__))


class H5PAppNode(ContentNode):
    """ Model representing a H5P content nodes

        The .h5p file is self-contained and inlcuding media and javascript libs.

        Attributes:
            source_id (str): content's original id
            title (str): content's title
            license (str or <License>): content's license
            author (str): who created the content (optional)
            aggregator (str): website or org hosting the content collection but not necessarily the creator or copyright holder (optional)
            provider (str): organization that commissioned or is distributing the content (optional)
            description (str): description of content (optional)
            thumbnail (str): local path or url to thumbnail image (optional)
            extra_fields (dict): any additional data needed for node (optional)
            domain_ns (str): who is providing the content (e.g. learningequality.org) (optional)
            files ([<File>]): list of file objects for node (optional)
    """
    kind = content_kinds.H5P
    required_file_format = file_formats.H5P

    def validate(self):
        """ validate: Makes sure H5P app is valid
            Args: None
            Returns: boolean indicating if H5P app is valid
        """
        from .files import H5PFile
        try:
            assert self.kind == content_kinds.H5P, "Assumption Failed: Node should be an H5P app"
            assert self.questions == [], "Assumption Failed: HTML should not have questions"
            assert [f for f in self.files if isinstance(f, H5PFile)], "Assumption Failed: H5PAppNode should have at least one h5p file"
            return super(H5PAppNode, self).validate()
        except AssertionError as ae:
            raise InvalidNodeException("Invalid node ({}): {} - {}".format(ae.args[0], self.title, self.__dict__))


class ExerciseNode(ContentNode):
    """ Model representing exercises in channel

        Exercises are sets of questions to assess learners'
        understanding of the content

        Attributes:
            source_id (str): content's original id
            title (str): content's title
            license (str or <License>): content's license
            author (str): who created the content (optional)
            aggregator (str): website or org hosting the content collection but not necessarily the creator or copyright holder (optional)
            provider (str): organization that commissioned or is distributing the content (optional)
            description (str): description of content (optional)
            exercise_data ({mastery_model:str, randomize:bool, m:int, n:int}): data on mastery requirements (optional)
            thumbnail (str): local path or url to thumbnail image (optional)
            extra_fields (dict): any additional data needed for node (optional)
            domain_ns (str): who is providing the content (e.g. learningequality.org) (optional)
            questions ([<Question>]): list of question objects for node (optional)
    """
    kind = content_kinds.EXERCISE

    def __init__(self, source_id, title, license, questions=None, exercise_data=None, **kwargs):
        self.questions = questions or []

        # Set mastery model defaults if none provided
        if not exercise_data:
            exercise_data = {}
        if isinstance(exercise_data, str):
            exercise_data = {"mastery_model": exercise_data}

        exercise_data.update({
            'mastery_model': exercise_data.get('mastery_model', exercises.M_OF_N),
            'randomize': exercise_data.get('randomize', True),
        })

        super(ExerciseNode, self).__init__(source_id, title, license, extra_fields=exercise_data, **kwargs)

    def __str__(self):
        metadata = "{0} {1}".format(len(self.questions), "question" if len(self.questions) == 1 else "questions")
        return "{title} ({kind}): {metadata}".format(title=self.title, kind=self.__class__.__name__, metadata=metadata)

    def add_question(self, question):
        """ add_question: adds question to question list
            Args: question to add to list
            Returns: None
        """
        self.questions += [question]

    def process_files(self):
        """Goes through question fields and replaces image strings
        Returns: content-hash based filenames of all the required image files
        """
        config.LOGGER.info("\t*** Processing images for exercise: {}".format(self.title))
        downloaded = super(ExerciseNode, self).process_files()
        for question in self.questions:
            downloaded += question.process_question()

        self.process_exercise_data()

        config.LOGGER.info("\t*** Images for {} have been processed".format(self.title))
        return downloaded

    def process_exercise_data(self):
        mastery_model = self.extra_fields['mastery_model']

        # Keep original m/n values or other n/m values if specified
        m_value = self.extra_fields.get('m') or self.extra_fields.get('n')
        n_value = self.extra_fields.get('n') or self.extra_fields.get('m')

        if m_value:
            m_value = int(m_value)
        if n_value:
            n_value = int(n_value)

        # Update mastery model if parameters were not provided
        if mastery_model == exercises.M_OF_N:
            m_value = m_value or max(min(5, len(self.questions)), 1)
            n_value = n_value or max(min(5, len(self.questions)), 1)
        elif mastery_model == exercises.DO_ALL:
            m_value = n_value = max(len(self.questions), 1)
        elif mastery_model == exercises.NUM_CORRECT_IN_A_ROW_10:
            m_value = n_value = 10
        elif mastery_model == exercises.NUM_CORRECT_IN_A_ROW_5:
            m_value = n_value = 5
        elif mastery_model == exercises.NUM_CORRECT_IN_A_ROW_3:
            m_value = n_value = 3
        elif mastery_model == exercises.NUM_CORRECT_IN_A_ROW_2:
            m_value = n_value = 2
        elif mastery_model == exercises.SKILL_CHECK:
            m_value = n_value = 1

        self.extra_fields.update({'m': m_value})
        self.extra_fields.update({'n': n_value})

    def validate(self):
        """ validate: Makes sure exercise is valid
            Args: None
            Returns: boolean indicating if exercise is valid
        """

        try:
            self.process_exercise_data()

            assert self.kind == content_kinds.EXERCISE, "Assumption Failed: Node should be an exercise"

            # Check if questions are correct
            assert any(self.questions), "Assumption Failed: Exercise does not have a question"
            assert all([q.validate() for q in self.questions]), "Assumption Failed: Exercise has invalid question"
            assert self.extra_fields['mastery_model'] in MASTERY_MODELS, \
                "Assumption Failed: Unrecognized mastery model {}".format(self.extra_fields['mastery_model'])
            if self.extra_fields['mastery_model'] == exercises.M_OF_N:
                assert 'm' in self.extra_fields and 'n' in self.extra_fields, "Assumption failed: M of N mastery model is missing M and/or N values"
                assert isinstance(self.extra_fields['m'], int), "Assumption failed: M must be an integer value"
                assert isinstance(self.extra_fields['m'], int), "Assumption failed: N must be an integer value"

            return super(ExerciseNode, self).validate()
        except (AssertionError, ValueError) as ae:
            raise InvalidNodeException("Invalid node ({}): {} - {}".format(ae.args[0], self.title, self.__dict__))


    def truncate_fields(self):
        for q in self.questions:
            q.truncate_fields()

        super(ExerciseNode, self).truncate_fields()

class SlideshowNode(ContentNode):
    """ Model representing Slideshows

        Slideshows are sequences of "Slides", a combination of an image and caption.
        Slides are shown in a specified sequential order.

        Attributes:
            source_id (str): content's original id
            title (str): content's title
            license (str or <License>): content's license
            author (str): who created the content (optional)
            aggregator (str): website or org hosting the content collection but not necessarily the creator or copyright holder (optional)
            provider (str): organization that commissioned or is distributing the content (optional)
            description (str): description of content (optional)
            files ([<SlideImageFile>]): images associated with slides
            thumbnail (str): local path or url to thumbnail image (optional)
            extra_fields (dict): any additional data needed for node (optional)
            domain_ns (str): who is providing the content (e.g. learningequality.org) (optional)
    """
    kind = content_kinds.SLIDESHOW

    def __init__(self, source_id, title, license, slideshow_data=None, **kwargs):
        if slideshow_data:
            extra_fields = {'slideshow_data': slideshow_data}
        else:
            extra_fields = {'slideshow_data':[]}
        # THe Node base class' __init__ method has:
        #       for f in files or []:
        #           self.add_file(f)
        super(SlideshowNode, self).__init__(source_id, title, license, extra_fields=extra_fields, **kwargs)

    def add_file(self, file_to_add):
        """
        Add a the SlideImageFile to the node's files and append slideshow metadata
        to extra_fields['slideshow_data'] (list).
        Args: file (SlideshowNode or ThumbnailFile): file model to add to node
        Returns: None
        """
        from .files import ThumbnailFile, SlideImageFile
        assert isinstance(file_to_add, ThumbnailFile) or isinstance(file_to_add, SlideImageFile), "Files being added must be instances of a subclass of File class"

        if file_to_add not in self.files:
            filename = file_to_add.get_filename()
            if filename:
                checksum, ext = filename.split('.')  # <md5sum(contents)>.[png|jpg|jpeg]
            else:
                raise ValueError('filename not available')

            #
            # Appending to extra_fields is only necessary for SlideImageFile instances
            if isinstance(file_to_add, SlideImageFile):
                #
                # Find the idx of sort_order.next()
                slideshow_image_files = [f for f in self.files if isinstance(f,SlideImageFile)]
                idx = len(slideshow_image_files)  # next available index, assuming added in desired order
                #
                # Add slideshow data to extra_fields['slideshow_data'] (aka manifest)
                slideshow_data = self.extra_fields['slideshow_data']
                slideshow_data.append(
                    {
                        'caption': file_to_add.caption,
                        'descriptive_text': file_to_add.descriptive_text,
                        'sort_order': idx,
                        'checksum': checksum,
                        'extension': ext
                    }
                )
                self.extra_fields['slideshow_data'] = slideshow_data

            #
            # Add node->file link
            file_to_add.node = self
            self.files.append(file_to_add)

    def validate(self):
        from .files import SlideImageFile, ThumbnailFile
        try:
            assert [f for f in self.files if isinstance(f, SlideImageFile)], \
                "Assumption Failed: SlideshowNode must have at least one SlideImageFile file."
            assert all([isinstance(f, SlideImageFile) or isinstance(f, ThumbnailFile) for f in self.files]), \
                   "Assumption Failed: SlideshowNode files must be of type SlideImageFile or ThumbnailFile."
        except AssertionError as ae:
            raise InvalidNodeException("Invalid node ({}): {} - {}".format(ae.args[0], self.title, self.__dict__))
        super(SlideshowNode, self).validate()


class CustomNavigationNode(ContentNode):
    kind = content_kinds.TOPIC
    required_file_format = file_formats.HTML5

    def __init__(self, *args, **kwargs):
        kwargs["extra_fields"] = {'modality': "CUSTOM_NAVIGATION"}
        super(CustomNavigationNode, self).__init__(*args, **kwargs)

    def generate_thumbnail(self):
        from .files import HTMLZipFile, ExtractedHTMLZipThumbnailFile
        html5_files = [f for f in self.files if isinstance(f, HTMLZipFile)]
        if html5_files:
            html_file = html5_files[0]
            if html_file.filename and not html_file.error:
                storage_path = config.get_storage_path(html_file.filename)
                return ExtractedHTMLZipThumbnailFile(storage_path)
        else:
            return None

    def validate(self):
        """ validate: Makes sure Custom Navigation app is valid
            Args: None
            Returns: boolean indicating if Custom Navigation app is valid
        """
        from .files import HTMLZipFile
        try:
            assert self.kind == content_kinds.TOPIC, "Assumption Failed: Node should be a Topic Node"
            assert self.questions == [], "Assumption Failed: Custom Navigation should not have questions"
            assert any(f for f in self.files if isinstance(f, HTMLZipFile)), "Assumption Failed: Custom Navigation should have at least one html file"
            return super(CustomNavigationNode, self).validate()
        except AssertionError as ae:
            raise InvalidNodeException("Invalid node ({}): {} - {}".format(ae.args[0], self.title, self.__dict__))


class CustomNavigationChannelNode(ChannelNode):
    required_file_format = file_formats.HTML5

    def __init__(self, *args, **kwargs):
        kwargs["extra_fields"] = {'modality': "CUSTOM_NAVIGATION"}
        super(CustomNavigationChannelNode, self).__init__(*args, **kwargs)

    def validate(self):
        """ validate: Makes sure Custom Navigation app is valid
            Args: None
            Returns: boolean indicating if Custom Navigation app is valid
        """
        from .files import HTMLZipFile
        try:
            assert self.kind == "Channel", "Assumption Failed: Node should be a Topic Node"
            assert any(f for f in self.files if isinstance(f, HTMLZipFile)), "Assumption Failed: Custom Navigation should have at least one html file"
            return super(CustomNavigationChannelNode, self).validate()
        except AssertionError as ae:
            raise InvalidNodeException("Invalid node ({}): {} - {}".format(ae.args[0], self.title, self.__dict__))
