# Node models to represent channel's tree
import json
import re
import uuid

from le_utils.constants import content_kinds
from le_utils.constants import exercises
from le_utils.constants import format_presets
from le_utils.constants import languages
from le_utils.constants import roles
from le_utils.constants.labels import accessibility_categories
from le_utils.constants.labels import learning_activities
from le_utils.constants.labels import levels
from le_utils.constants.labels import needs
from le_utils.constants.labels import resource_type
from le_utils.constants.labels import subjects

from .. import __version__
from .. import config
from ..exceptions import InvalidNodeException
from ..utils.utils import is_valid_uuid_string
from .files import ExtractedEPubThumbnailFile
from .files import ExtractedHTMLZipThumbnailFile
from .files import ExtractedPdfThumbnailFile
from .files import File
from .files import SubtitleFile
from .files import YouTubeSubtitleFile
from .licenses import License
from ricecooker.utils.pipeline.exceptions import ExpectedFileException
from ricecooker.utils.pipeline.exceptions import InvalidFileException

MASTERY_MODELS = [id for id, name in exercises.MASTERY_MODELS]
ROLES = [id for id, name in roles.choices]
PRESET_LOOKUP = {p.id: p for p in format_presets.PRESETLIST}


# Used to map content kind to learning activity when a list of learning_activiies is not provided
kind_activity_map = {
    content_kinds.EXERCISE: learning_activities.PRACTICE,
    content_kinds.VIDEO: learning_activities.WATCH,
    content_kinds.AUDIO: learning_activities.LISTEN,
    content_kinds.DOCUMENT: learning_activities.READ,
    content_kinds.HTML5: learning_activities.EXPLORE,
    content_kinds.H5P: learning_activities.EXPLORE,
}


inheritable_simple_value_fields = {
    "language",
    "license",
    "author",
    "aggregator",
    "provider",
}


inheritable_metadata_label_fields = [
    "grade_levels",
    "resource_types",
    "categories",
    "learner_needs",
]


class Node(object):
    """Node: model to represent all nodes in the tree"""

    kind = None
    license = None
    language = None
    kind = None
    valid = False

    def __init__(
        self,
        source_id,
        title,
        author="",
        aggregator="",
        provider="",
        copyright_holder="",
        license=None,
        license_description=None,
        tags=None,
        domain_ns=None,
        grade_levels=None,
        resource_types=None,
        learning_activities=None,
        accessibility_labels=None,
        categories=None,
        learner_needs=None,
        role=roles.LEARNER,
        language=None,
        description=None,
        thumbnail=None,
        files=None,
        derive_thumbnail=False,
        node_modifications={},
        extra_fields=None,
        suggested_duration=None,
    ):
        assert isinstance(source_id, str), "source_id must be a string"
        self.source_id = source_id

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

        self.author = author or ""
        self.aggregator = aggregator or ""
        self.provider = provider or ""
        self.tags = tags or []
        self.domain_ns = domain_ns
        self.suggested_duration = suggested_duration
        self.questions = (
            self.questions if hasattr(self, "questions") else []
        )  # Needed for to_dict method

        self.grade_levels = grade_levels or []
        self.resource_types = resource_types or []
        self.learning_activities = learning_activities or []
        self.accessibility_labels = accessibility_labels or []
        self.categories = categories or []
        self.learner_needs = learner_needs or []
        self.role = role

        self.set_license(
            license, copyright_holder=copyright_holder, description=license_description
        )

    def set_language(self, language):
        """Set self.language to internal lang. repr. code from str or Language object."""
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
        metadata = "{0} {1}".format(
            count, "descendant" if count == 1 else "descendants"
        )
        return "{title} ({kind}) ({source_id}): {metadata}".format(
            title=self.title,
            kind=self.__class__.__name__,
            source_id=self.source_id,
            metadata=metadata,
        )

    def __repr__(self):
        return self.__str__()

    def truncate_fields(self):
        if len(self.title) > config.MAX_TITLE_LENGTH:
            config.print_truncate("title", self.source_id, self.title, kind=self.kind)
            self.title = self.title[: config.MAX_TITLE_LENGTH]

        if self.source_id and len(self.source_id) > config.MAX_SOURCE_ID_LENGTH:
            config.print_truncate(
                "source_id", self.source_id, self.source_id, kind=self.kind
            )
            self.source_id = self.source_id[: config.MAX_SOURCE_ID_LENGTH]

        for f in self.files:
            f.truncate_fields()

    def to_dict(self):
        """to_dict: puts data in format CC expects
        Args: None
        Returns: dict of channel data
        """

    def add_child(self, node):
        """add_child: Adds child node to node
        Args: node to add as child
        Returns: None
        """
        assert isinstance(node, Node), "Child node must be a subclass of Node"
        node.parent = self
        self.children += [node]

    def add_file(self, file_to_add):
        """add_file: Add to node's associated files
        Args: file_to_add (File): file model to add to node
        Returns: None
        """
        from .files import File

        assert isinstance(
            file_to_add, File
        ), "Files being added must be instances of a subclass of File class"
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
        """set_thumbnail: Set node's thumbnail
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
        try:
            preset = next(
                filter(
                    lambda x: x.thumbnail and x.kind == self.kind,
                    format_presets.PRESETLIST,
                )
            )
            return preset.id
        except StopIteration:
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
        """count: get number of nodes in tree
        Args: None
        Returns: int
        """
        total = len(self.children)
        for child in self.children:
            total += child.count()
        return total

    def get_topic_count(self):
        """get_topic_count: get number of topics in tree
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
        """print_tree: prints out structure of tree
        Args: indent (int): What level of indentation at which to start printing
        Returns: None
        """
        config.LOGGER.info(
            "{indent}{data}".format(indent="   " * indent, data=str(self))
        )
        for child in self.children:
            child.print_tree(indent + 1)

    def get_json_tree(self):
        tree = self.to_dict()
        if len(self.children) > 0:
            tree["children"] = []
            for child in self.children:
                tree["children"].append(child.get_json_tree())

        return tree

    def save_channel_children_to_csv(self, metadata_csv, structure_string=""):
        # Not including channel title in topic structure
        is_channel = isinstance(self, ChannelNode)
        if not is_channel:
            # Build out tag string
            tags_string = ",".join(self.tags)
            new_title = self.node_modifications.get("New Title") or ""
            new_description = self.node_modifications.get("New Description") or ""
            new_tags = self.node_modifications.get("New Tags") or ""
            # New Tags is being saved as a list. Check if list and if so, join to correctly write it to csv
            if isinstance(new_tags, list):
                new_tags = ",".join(new_tags)

            record = [
                self.source_id,
                structure_string,
                self.title,
                new_title,  # New Title
                self.description,
                new_description,  # New Description
                tags_string,
                new_tags,  # New Tags
                "",  # Last Modified
            ]
            metadata_csv.writerow(record)

            # add current level to structure_string_list
            if structure_string == "":
                structure_string = self.title
            else:
                structure_string += "/" + self.title
        for child in self.children:
            child.save_channel_children_to_csv(metadata_csv, structure_string)

    def _validate_values(self, assertion, error_message):
        if assertion:
            raise InvalidNodeException(f"{self}: {error_message}")

    def infer_learning_activities(self):
        # learning_activities can be set to a default based on the kind if not provided directly
        if not self.learning_activities and self.kind in kind_activity_map:
            self.learning_activities = [kind_activity_map[self.kind]]

    def set_license(self, license, copyright_holder=None, description=None):
        # Add license (create model if it's just a path)
        if isinstance(license, str):
            from .licenses import get_license

            license = get_license(
                license, copyright_holder=copyright_holder, description=description
            )
        self.license = license

    def _validate(self):  # noqa: C901
        """validate: Makes sure node is valid
        Args: None
        Returns: boolean indicating if node is valid
        """
        self._validate_values(self.source_id is None, "Must have a source_id")

        if self.__class__.kind is not None:
            self._validate_values(
                self.kind != self.__class__.kind,
                f"{self.__class__.__name__} must have kind {self.__class__.kind}",
            )
            if self.kind != content_kinds.EXERCISE:
                self._validate_values(
                    bool(self.questions), f"{self.kind} should not have questions"
                )

        self._validate_values(not isinstance(self.title, str), "Title is not a string")
        self._validate_values(len(self.title.strip()) == 0, "Title cannot be empty")
        self._validate_values(
            not (isinstance(self.description, str) or self.description is None),
            "Description is not a string",
        )
        self._validate_values(
            not isinstance(self.children, list), "Children is not a list"
        )

        for f in self.files:
            self._validate_values(not isinstance(f, File), "Files must be file class")
            f.validate()

        source_ids = [c.source_id for c in self.children]
        duplicates = set([x for x in source_ids if source_ids.count(x) > 1])
        self._validate_values(
            len(duplicates) > 0,
            f"Must have unique source id among siblings ({duplicates} appears multiple times)",
        )

        self.infer_learning_activities()
        self._validate_values(
            not isinstance(self.author, str), "Author is not a string"
        )
        self._validate_values(
            not isinstance(self.aggregator, str), "Aggregator is not a string"
        )
        self._validate_values(
            not isinstance(self.provider, str), "Provider is not a string"
        )
        self._validate_values(not isinstance(self.files, list), "Files is not a list")
        self._validate_values(
            not isinstance(self.questions, list), "Questions is not a list"
        )
        self._validate_values(
            not isinstance(self.extra_fields, dict), "Extra fields is not a dict"
        )
        self._validate_values(not isinstance(self.tags, list), "Tags is not a list")

        for tag in self.tags:
            self._validate_values(not isinstance(tag, str), "Tag is not a string")
            self._validate_values(
                len(tag) > 30,
                f"Tag '{tag}' is too long. Tags should be 30 chars or less.",
            )

        if self.license is not None:
            self._validate_values(
                not isinstance(self.license, License), "License is not a license object"
            )
            try:
                self.license.validate()
            except AssertionError as e:
                self._validate_values(True, str(e))

        self._validate_values(
            self.role not in ROLES, f"Role must be one of the following: {ROLES}"
        )

        if self.grade_levels is not None:
            for grade in self.grade_levels:
                self._validate_values(
                    grade not in levels.LEVELSLIST,
                    f"Grade levels must be one of the following: {levels.LEVELSLIST}",
                )

        if self.resource_types is not None:
            for res_type in self.resource_types:
                self._validate_values(
                    res_type not in resource_type.RESOURCETYPELIST,
                    f"Resource types must be one of the following: {resource_type.RESOURCETYPELIST}",
                )

        if self.learning_activities is not None:
            self._validate_values(
                not isinstance(self.learning_activities, list),
                "Learning activities must be list",
            )
            for learn_act in self.learning_activities:
                self._validate_values(
                    learn_act not in learning_activities.LEARNINGACTIVITIESLIST,
                    f"Learning activities must be one of the following: {learning_activities.LEARNINGACTIVITIESLIST}",
                )

        if self.accessibility_labels is not None:
            self._validate_values(
                not isinstance(self.accessibility_labels, list),
                "Accessibility label must be list",
            )
            for access_label in self.accessibility_labels:
                self._validate_values(
                    access_label
                    not in accessibility_categories.ACCESSIBILITYCATEGORIESLIST,
                    f"Accessibility label must be one of the following: {accessibility_categories.ACCESSIBILITYCATEGORIESLIST}",
                )

        if self.categories is not None:
            self._validate_values(
                not isinstance(self.categories, list), "Categories must be list"
            )
            for category in self.categories:
                self._validate_values(
                    category not in subjects.SUBJECTSLIST,
                    f"Categories must be one of the following: {subjects.SUBJECTSLIST}",
                )

        if self.learner_needs is not None:
            self._validate_values(
                not isinstance(self.learner_needs, list), "Learner needs must be list"
            )
            for learner_need in self.learner_needs:
                self._validate_values(
                    learner_need not in needs.NEEDSLIST,
                    f"Learner needs must be one of the following: {needs.NEEDSLIST}",
                )

        return True

    def validate(self):
        self.valid = False
        self.valid = self._validate()
        return self.valid

    def get_metadata_dict(self, metadata: dict[str, any]) -> dict[str, any]:
        """
        Supplements the metadata in the metadata dict argument with metadata from the node.
        """
        for field in inheritable_simple_value_fields:
            # These fields, if not set, will be either None or empty string
            value = getattr(self, field)
            if value is not None and value != "":
                metadata[field] = value
        for field in inheritable_metadata_label_fields:
            # These fields, if not set, will be empty list
            ancestor_values = metadata.get(field, [])
            node_values = getattr(self, field)
            final_values = set()
            # Get a list of all keys in reverse order of length so we can remove any less specific values
            all_values = sorted(
                set(ancestor_values).union(set(node_values)), key=len, reverse=True
            )
            for value in all_values:
                if not any(k != value and k.startswith(value) for k in final_values):
                    final_values.add(value)
            if final_values:
                metadata[field] = list(final_values)
        return metadata

    def gather_ancestor_metadata(self):
        return self.get_metadata_dict({})


class ChannelNode(Node):
    """Model representing the channel you are creating

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

    def __init__(self, source_id, source_domain, title, tagline=None, **kwargs):
        # Map parameters to model variables
        self.source_domain = source_domain
        self.tagline = tagline

        super(ChannelNode, self).__init__(source_id, title, **kwargs)

    def get_domain_namespace(self):
        return uuid.uuid5(uuid.NAMESPACE_DNS, self.source_domain)

    def get_content_id(self):
        return uuid.uuid5(self.get_domain_namespace(), self.get_node_id().hex)

    def get_node_id(self):
        return uuid.uuid5(self.get_domain_namespace(), self.source_id)

    def truncate_fields(self):
        if self.description and len(self.description) > config.MAX_DESCRIPTION_LENGTH:
            config.print_truncate(
                "description", self.source_id, self.description, kind=self.kind
            )
            self.description = self.description[: config.MAX_DESCRIPTION_LENGTH]
        if self.tagline and len(self.tagline) > config.MAX_TAGLINE_LENGTH:
            config.print_truncate(
                "tagline", self.source_id, self.tagline, kind=self.kind
            )
            self.tagline = self.tagline[: config.MAX_TAGLINE_LENGTH]
        super(ChannelNode, self).truncate_fields()

    def to_dict(self):
        """to_dict: puts channel data into the format that Kolibri Studio expects
        Args: None
        Returns: dict of channel data
        """
        return {
            "id": self.get_node_id().hex,
            "name": self.title,
            "thumbnail": self.thumbnail.filename if self.thumbnail else None,
            "language": self.language,
            "description": self.description or "",
            "tagline": self.tagline or "",
            "license": self.license.license_id if self.license else None,
            "source_domain": self.source_domain,
            "source_id": self.source_id,
            "ricecooker_version": __version__,
            "extra_fields": json.dumps(self.extra_fields),
            "files": [
                f.to_dict()
                for f in self.files
                if f
                and f.filename
                and not (self.thumbnail and self.thumbnail.filename is f.filename)
            ],
        }

    def _validate(self):
        """validate: Makes sure channel is valid
        Args: None
        Returns: boolean indicating if channel is valid
        """
        self._validate_values(
            not isinstance(self.source_domain, str), "Channel domain must be a string"
        )
        self._validate_values(self.language is None, "Channel must have a language")
        return super(ChannelNode, self)._validate()


class TreeNode(Node):
    """Model representing the content nodes in the channel's tree

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

    def get_domain_namespace(self):
        if not self.domain_ns:
            self.domain_ns = self.parent.get_domain_namespace()
        return self.domain_ns

    def get_content_id(self):
        if not self.content_id:
            self.content_id = uuid.uuid5(self.get_domain_namespace(), self.source_id)
        return self.content_id

    def get_node_id(self):
        assert (
            self.parent
        ), "Parent not found: node id must be calculated based on parent"
        if not self.node_id:
            self.node_id = uuid.uuid5(
                self.parent.get_node_id(), self.get_content_id().hex
            )
        return self.node_id

    def truncate_fields(self):
        if self.author and len(self.author) > config.MAX_AUTHOR_LENGTH:
            config.print_truncate("author", self.source_id, self.author, kind=self.kind)
            self.author = self.author[: config.MAX_AUTHOR_LENGTH]

        if self.aggregator and len(self.aggregator) > config.MAX_AGGREGATOR_LENGTH:
            config.print_truncate(
                "aggregator", self.source_id, self.aggregator, kind=self.kind
            )
            self.aggregator = self.aggregator[: config.MAX_AGGREGATOR_LENGTH]

        if self.provider and len(self.provider) > config.MAX_PROVIDER_LENGTH:
            config.print_truncate(
                "provider", self.source_id, self.provider, kind=self.kind
            )
            self.provider = self.provider[: config.MAX_PROVIDER_LENGTH]

        self.license and self.license.truncate_fields()

        super(TreeNode, self).truncate_fields()

    def sort_children(self, key=None, reverse=False):
        """
        Sort children of TreeNode
        :param key: A Function to execute to decide the order. Default None
        :param reverse: A Boolean. False will sort ascending, True will sort descending. False by default
        """
        # default natural sorting
        if not key:

            def convert(text):
                return int(text) if text.isdigit() else text.lower()

            def key(key):
                return [
                    convert(re.sub(r"[^A-Za-z0-9]+", "", c.replace("&", "and")))
                    for c in re.split("([0-9]+)", key.title)
                ]

        self.children = sorted(self.children, key=key, reverse=reverse)
        return self.children

    def to_dict(self):
        """to_dict: puts Topic or Content node data into the format that Kolibri Studio expects
        Args: None
        Returns: dict of channel data
        """
        return {
            "title": self.node_modifications.get("New Title") or self.title,
            "language": self.language,
            "description": self.node_modifications.get("New Description")
            or self.description,
            "node_id": self.get_node_id().hex,
            "content_id": self.get_content_id().hex,
            "source_domain": self.domain_ns.hex,
            "source_id": self.source_id,
            "author": self.author,
            "aggregator": self.aggregator,
            "provider": self.provider,
            "files": [
                f.to_dict() for f in self.files if f and f.filename
            ],  # Filter out failed downloads
            "tags": self.node_modifications.get("New Tags") or self.tags,
            "kind": self.kind,
            "license": None,
            "license_description": None,
            "copyright_holder": "",
            "questions": [],
            "extra_fields": json.dumps(self.extra_fields),
            "grade_levels": self.grade_levels,
            "resource_types": self.resource_types,
            "learning_activities": self.learning_activities,
            "accessibility_labels": self.accessibility_labels,
            "categories": self.categories,
            "learner_needs": self.learner_needs,
            "role": self.role,
        }

    def gather_ancestor_metadata(self):
        if not self.parent:
            raise InvalidNodeException(
                "Parent not found: cannot gather ancestor metadata if no parent exists"
            )
        metadata = self.parent.gather_ancestor_metadata()
        return self.get_metadata_dict(metadata)


class TopicNode(TreeNode):
    """Model representing channel topics

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


class ContentNode(TreeNode):
    """Model representing the content nodes in the channel's tree

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
        uri (str): A URI for the main file for this content node
        pipeline (FilePipeline): A FilePipeline instance for handling uri processing
    """

    required_presets = tuple()

    def __init__(self, source_id, title, license, uri=None, pipeline=None, **kwargs):
        self.uri = uri
        self._pipeline = pipeline
        # Flag here to say that files haven't been processed.
        # Until files have been processed we can't be sure that the files are actually valid
        # for example, once we download a file we may discover it doesn't exist, that it's
        # actually a video not a PDF etc.
        self._files_processed = False
        super(ContentNode, self).__init__(source_id, title, license=license, **kwargs)

    @property
    def pipeline(self):
        if self._pipeline is None:
            return config.FILE_PIPELINE
        return self._pipeline

    def __str__(self):
        metadata = "{0} {1}".format(
            len(self.files), "file" if len(self.files) == 1 else "files"
        )
        return "{title} ({kind}): {metadata}".format(
            title=self.title, kind=self.__class__.__name__, metadata=metadata
        )

    def _validate_uri(self):
        try:
            should_handle = self.pipeline.should_handle(self.uri)
        except InvalidFileException:
            should_handle = False
        if not should_handle:
            raise InvalidNodeException(
                "Invalid node: pipeline cannot handle uri {}".format(self.uri)
            )

    def _validate(self):
        """validate: Makes sure content node is valid
        Args: None
        Returns: boolean indicating if content node is valid
        """
        self._validate_values(self.license is None, "ContentNode must have a license")
        if self._files_processed:
            self._validate_values(self.kind is None, "No kind has been set")
            if self.required_presets:
                num_required_presets = 0
                for f in self.files:
                    num_required_presets += (
                        1
                        if (
                            any(
                                f.filename and f.get_preset() == preset
                                for preset in self.required_presets
                            )
                        )
                        else 0
                    )
                self._validate_values(
                    num_required_presets == 0,
                    f"No required format preset found out of {self.required_presets}",
                )
                self._validate_values(
                    num_required_presets > 1,
                    f"Multiple ({num_required_presets}) required presets found out of {self.required_presets}",
                )
            # We don't need files if we have questions
            if not self.questions:
                has_default_file = False
                for f in self.files:
                    # If files have failed to process, they will not have a filename set.
                    if not f.filename:
                        continue
                    preset = f.get_preset()
                    preset_obj = PRESET_LOOKUP[preset]
                    has_default_file = has_default_file or not preset_obj.supplementary
                self._validate_values(not has_default_file, "No default file")
        if self.uri:
            self._validate_uri()
        return super(ContentNode, self)._validate()

    def _process_uri(self):
        try:
            file_metadata_list = self.pipeline.execute(
                self.uri, skip_cache=config.UPDATE
            )
        except (InvalidFileException, ExpectedFileException) as e:
            config.LOGGER.error(f"Error processing path: {self.uri} with error: {e}")
            return None
        content_metadata = {}
        for file_metadata in file_metadata_list:
            metadata_dict = file_metadata.to_dict()
            if "content_node_metadata" in metadata_dict:
                content_metadata.update(metadata_dict.pop("content_node_metadata"))
            # Remove path from metadata_dict as it is not needed for the File object
            metadata_dict.pop("path", None)
            file_obj = File(**metadata_dict)
            self.add_file(file_obj)
        for key, value in content_metadata.items():
            if key == "extra_fields":
                self.extra_fields.update(value)
            else:
                if key == "kind" and self.kind is not None and self.kind != value:
                    raise InvalidNodeException(
                        "Inferred kind is different from content node class kind."
                    )
                setattr(self, key, value)

    def process_files(self):
        if self.uri:
            self._process_uri()
        filenames = super().process_files()
        # Now that we have set all the metadata, and files, we validate the node
        # again to ensure that the metadata is valid
        self._files_processed = True
        self.validate()
        return filenames

    def to_dict(self):
        """to_dict: puts data in format CC expects
        Args: None
        Returns: dict of channel data
        """
        return {
            "title": self.node_modifications.get("New Title") or self.title,
            "language": self.language,
            "description": self.node_modifications.get("New Description")
            or self.description,
            "node_id": self.get_node_id().hex,
            "content_id": self.get_content_id().hex,
            "source_domain": self.domain_ns.hex,
            "source_id": self.source_id,
            "author": self.author,
            "aggregator": self.aggregator,
            "provider": self.provider,
            "files": [
                f.to_dict() for f in filter(lambda x: x and x.filename, self.files)
            ],  # Filter out failed downloads
            "tags": self.node_modifications.get("New Tags") or self.tags,
            "kind": self.kind,
            "license": self.license.license_id,
            "license_description": self.license.description,
            "copyright_holder": self.license.copyright_holder,
            "questions": [question.to_dict() for question in self.questions],
            "extra_fields": json.dumps(self.extra_fields),
            "role": self.role,
            "suggested_duration": self.suggested_duration,
            "grade_levels": self.grade_levels,
            "resource_types": self.resource_types,
            "learning_activities": self.learning_activities,
            "accessibility_labels": self.accessibility_labels,
            "categories": self.categories,
            "learner_needs": self.learner_needs,
        }

    def set_metadata_from_ancestors(self):
        metadata = self.gather_ancestor_metadata()
        for field in metadata:
            setattr(self, field, metadata[field])


class VideoNode(ContentNode):
    """Model representing videos in channel

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
    required_presets = (format_presets.VIDEO_HIGH_RES, format_presets.VIDEO_LOW_RES)

    def __init__(self, source_id, title, license, **kwargs):
        super(VideoNode, self).__init__(source_id, title, license, **kwargs)

    def generate_thumbnail(self):
        from .files import VideoFile, WebVideoFile, ExtractedVideoThumbnailFile

        video_files = [
            f
            for f in self.files
            if isinstance(f, VideoFile) or isinstance(f, WebVideoFile)
        ]
        if video_files:
            video_file = video_files[0]
            if video_file.filename and not video_file.error:
                storage_path = config.get_storage_path(video_file.filename)
                return ExtractedVideoThumbnailFile(storage_path)
        return None

    def _validate(self):
        """validate: Makes sure video is valid
        Args: None
        Returns: boolean indicating if video is valid
        """

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
                    file_info = file.path if hasattr(file, "path") else file.youtube_url
                    config.LOGGER.warning(
                        "Skipping duplicate subs for "
                        + language_code
                        + " from "
                        + file_info
                    )
            else:
                new_files.append(file)
        self.files = new_files
        return super(VideoNode, self)._validate()


class AudioNode(ContentNode):
    """Model representing audio content in channel

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
    required_presets = (format_presets.AUDIO,)


class DocumentNode(ContentNode):
    """Model representing documents in channel

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
    required_presets = (
        format_presets.DOCUMENT,
        format_presets.EPUB,
        format_presets.BLOOMPUB,
    )

    def generate_thumbnail(self):
        pdf_files = [f for f in self.files if f.get_preset() == format_presets.DOCUMENT]
        epub_files = [f for f in self.files if f.get_preset() == format_presets.EPUB]
        if pdf_files:
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


def _set_entrypoint(entrypoint, kwargs):
    if entrypoint:
        kwargs["extra_fields"] = kwargs.get("extra_fields", {})
        kwargs["extra_fields"]["options"] = kwargs["extra_fields"].get("options", {})
        kwargs["extra_fields"]["options"].update({"entry": entrypoint})
    return kwargs


class HTML5AppNode(ContentNode):
    """Model representing a zipped HTML5 application

    The zip file must either contain a file called index.html, which will be the first page loaded,
    or pass an entrypoint kwarg.
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
    required_presets = (format_presets.HTML5_ZIP,)

    def __init__(self, *args, entrypoint=None, **kwargs):
        kwargs = _set_entrypoint(entrypoint, kwargs)
        super().__init__(*args, **kwargs)

    def generate_thumbnail(self):

        html5_files = [
            f for f in self.files if f.get_preset() == format_presets.HTML5_ZIP
        ]
        if html5_files:
            html_file = html5_files[0]
            if html_file.filename and not html_file.error:
                storage_path = config.get_storage_path(html_file.filename)
                return ExtractedHTMLZipThumbnailFile(storage_path)
        else:
            return None


class H5PAppNode(ContentNode):
    """Model representing a H5P content nodes

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
    required_presets = (format_presets.H5P_ZIP,)


class ExerciseNode(ContentNode):
    """Model representing exercises in channel

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

    def __init__(
        self, source_id, title, license, questions=None, exercise_data=None, **kwargs
    ):
        self.questions = questions or []

        # Set mastery model defaults if none provided
        if not exercise_data:
            exercise_data = {}
        if isinstance(exercise_data, str):
            exercise_data = {"mastery_model": exercise_data}

        exercise_data.update(
            {
                "mastery_model": exercise_data.get("mastery_model", exercises.M_OF_N),
                "randomize": exercise_data.get("randomize", True),
            }
        )

        super(ExerciseNode, self).__init__(
            source_id, title, license, extra_fields=exercise_data, **kwargs
        )

    def __str__(self):
        metadata = "{0} {1}".format(
            len(self.questions), "question" if len(self.questions) == 1 else "questions"
        )
        return "{title} ({kind}): {metadata}".format(
            title=self.title, kind=self.__class__.__name__, metadata=metadata
        )

    def add_question(self, question):
        """add_question: adds question to question list
        Args: question to add to list
        Returns: None
        """
        self.questions += [question]

    def process_files(self):
        """Goes through question fields and replaces image strings
        Returns: content-hash based filenames of all the required image files
        """
        config.LOGGER.info(
            "\t*** Processing images for exercise: {}".format(self.title)
        )
        downloaded = super(ExerciseNode, self).process_files()
        for question in self.questions:
            downloaded += question.process_question()

        self.process_exercise_data()

        config.LOGGER.info("\t*** Images for {} have been processed".format(self.title))
        return downloaded

    def process_exercise_data(self):
        mastery_model = self.extra_fields["mastery_model"]

        # Keep original m/n values or other n/m values if specified
        m_value = self.extra_fields.get("m") or self.extra_fields.get("n")
        n_value = self.extra_fields.get("n") or self.extra_fields.get("m")

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

        self.extra_fields.update({"m": m_value})
        self.extra_fields.update({"n": n_value})

    def _validate(self):
        """validate: Makes sure exercise is valid
        Args: None
        Returns: boolean indicating if exercise is valid
        """

        # Check if questions are correct
        self._validate_values(
            not self.questions, "Exercise does not have any questions"
        )
        self._validate_values(
            any(not q.validate() for q in self.questions),
            "Exercise has invalid question",
        )
        self._validate_values(
            self.extra_fields["mastery_model"] not in MASTERY_MODELS,
            "Unrecognized mastery model {}".format(self.extra_fields["mastery_model"]),
        )
        if self.extra_fields["mastery_model"] == exercises.M_OF_N:
            self._validate_values(
                "m" not in self.extra_fields, "M of N mastery model is missing M value"
            )
            self._validate_values(
                "n" not in self.extra_fields, "M of N mastery model is missing N value"
            )
            try:
                int(self.extra_fields["m"])
            except ValueError:
                self._validate_values(
                    True,
                    "M must be an integer coerceable value",
                )
            try:
                int(self.extra_fields["n"])
            except ValueError:
                self._validate_values(
                    True,
                    "N must be an integer coerceable value",
                )

        self.process_exercise_data()

        return super(ExerciseNode, self)._validate()

    def truncate_fields(self):
        for q in self.questions:
            q.truncate_fields()

        super(ExerciseNode, self).truncate_fields()


class SlideshowNode(ContentNode):
    """Model representing Slideshows

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
            extra_fields = {"slideshow_data": slideshow_data}
        else:
            extra_fields = {"slideshow_data": []}
        # THe Node base class' __init__ method has:
        #       for f in files or []:
        #           self.add_file(f)
        super(SlideshowNode, self).__init__(
            source_id, title, license, extra_fields=extra_fields, **kwargs
        )

    def add_file(self, file_to_add):
        """
        Add a the SlideImageFile to the node's files and append slideshow metadata
        to extra_fields['slideshow_data'] (list).
        Args: file (SlideshowNode or ThumbnailFile): file model to add to node
        Returns: None
        """
        from .files import ThumbnailFile, SlideImageFile

        assert isinstance(file_to_add, ThumbnailFile) or isinstance(
            file_to_add, SlideImageFile
        ), "Files being added must be instances of a subclass of File class"

        if file_to_add not in self.files:
            filename = file_to_add.get_filename()
            if filename:
                checksum, ext = filename.split(".")  # <md5sum(contents)>.[png|jpg|jpeg]
            else:
                raise ValueError("filename not available")

            #
            # Appending to extra_fields is only necessary for SlideImageFile instances
            if isinstance(file_to_add, SlideImageFile):
                #
                # Find the idx of sort_order.next()
                slideshow_image_files = [
                    f for f in self.files if isinstance(f, SlideImageFile)
                ]
                idx = len(
                    slideshow_image_files
                )  # next available index, assuming added in desired order
                #
                # Add slideshow data to extra_fields['slideshow_data'] (aka manifest)
                slideshow_data = self.extra_fields["slideshow_data"]
                slideshow_data.append(
                    {
                        "caption": file_to_add.caption,
                        "descriptive_text": file_to_add.descriptive_text,
                        "sort_order": idx,
                        "checksum": checksum,
                        "extension": ext,
                    }
                )
                self.extra_fields["slideshow_data"] = slideshow_data

            #
            # Add node->file link
            file_to_add.node = self
            self.files.append(file_to_add)


class CustomNavigationNode(ContentNode):
    kind = content_kinds.TOPIC
    required_presets = (format_presets.HTML5_ZIP,)

    def __init__(self, *args, entrypoint=None, **kwargs):
        kwargs = _set_entrypoint(entrypoint, kwargs)
        kwargs["extra_fields"] = kwargs.get("extra_fields", {})
        kwargs["extra_fields"]["options"] = kwargs["extra_fields"].get("options", {})
        # TODO: update le-utils version and use a constant value here
        kwargs["extra_fields"]["options"].update({"modality": "CUSTOM_NAVIGATION"})
        super(CustomNavigationNode, self).__init__(*args, **kwargs)

    def generate_thumbnail(self):
        html5_files = [
            f for f in self.files if f.get_preset() == format_presets.HTML5_ZIP
        ]
        if html5_files:
            html_file = html5_files[0]
            if html_file.filename and not html_file.error:
                storage_path = config.get_storage_path(html_file.filename)
                return ExtractedHTMLZipThumbnailFile(storage_path)
        else:
            return None


class CustomNavigationChannelNode(ChannelNode):
    required_presets = (format_presets.HTML5_ZIP,)

    def __init__(self, *args, entrypoint=None, **kwargs):
        kwargs = _set_entrypoint(entrypoint, kwargs)
        kwargs["extra_fields"] = kwargs.get("extra_fields", {})
        kwargs["extra_fields"]["options"] = kwargs["extra_fields"].get("options", {})
        # TODO: update le-utils version and use a constant value here
        kwargs["extra_fields"]["options"].update({"modality": "CUSTOM_NAVIGATION"})
        super(CustomNavigationChannelNode, self).__init__(*args, **kwargs)


class PracticeQuizNode(ExerciseNode):
    """
    Node class for creating Practice Quizzes that are exercises under the hood but
    are displayed as Practice Quizzes in Kolibri.
    """

    def __init__(self, *args, **kwargs):
        kwargs["exercise_data"] = kwargs.get("exercise_data", {})
        kwargs["exercise_data"]["options"] = kwargs["exercise_data"].get("options", {})
        # TODO: update le-utils version and use a constant value here
        kwargs["exercise_data"]["options"].update({"modality": "QUIZ"})
        super(PracticeQuizNode, self).__init__(*args, **kwargs)


class StudioContentNode(TreeNode):
    """
    Node class for creating content nodes in the channel that are imported from
    existing nodes in another channel on Studio.

    Notes:
    - Your account must have read permissions for the target node.
    - You must specify the source_channel_id, and at least one of source_node_id or source_content_id.
    - If you specify both source_node_id and source_content_id, the source_node_id will be used,
      and it will fallback to looking up by source_content_id if source_node_id is not found.
    """

    kind = "remotecontent"

    ALLOWED_OVERRIDES = [
        "title",
        "description",
        "aggregator",
        "provider",
        "tags",
        "grade_levels",
        "resource_types",
        "learning_activities",
        "accessibility_labels",
        "categories",
        "learner_needs",
        "role",
        "thumbnail",
        "extra_fields",
        "suggested_duration",
    ]

    def __init__(
        self, source_channel_id, source_node_id=None, source_content_id=None, **kwargs
    ):
        self.source_channel_id = (
            source_channel_id if is_valid_uuid_string(source_channel_id) else None
        )
        self.source_node_id = (
            source_node_id if is_valid_uuid_string(source_node_id) else None
        )
        self.source_content_id = (
            source_content_id if is_valid_uuid_string(source_content_id) else None
        )
        self.overrides = kwargs.copy()
        overriden_title = kwargs.pop("title", "<title from remote>")
        super(StudioContentNode, self).__init__(
            source_node_id or source_content_id, overriden_title, **kwargs
        )

    def _validate(self):
        if not self.source_channel_id:
            raise InvalidNodeException(
                "Invalid node: source_channel_id must be specified, and be a valid UUID string."
            )
        if not self.source_node_id and not self.source_content_id:
            raise InvalidNodeException(
                "Invalid node: at least one of source_node_id or source_content_id must be specified, and be a valid UUID string."
            )
        for key in self.overrides:
            if key not in self.ALLOWED_OVERRIDES:
                raise InvalidNodeException(
                    "Invalid node: '{}' cannot be overriden on a StudioContentNode.".format(
                        key
                    )
                )
        return super(StudioContentNode, self)._validate()

    def to_dict(self):
        data = {
            "node_id": self.get_node_id().hex if self.parent else "",
            "source_channel_id": self.source_channel_id,
            "source_node_id": self.source_node_id,
            "source_content_id": self.source_content_id,
        }
        if "thumbnail" in self.overrides:
            self.overrides["files"] = [
                f.to_dict() for f in self.files if f and f.filename
            ]
            del self.overrides["thumbnail"]
        data.update(self.overrides)
        return data


# add alias for back-compatibility
RemoteContentNode = StudioContentNode
