import uuid
import hashlib
import base64
import requests
import validators
import json
import tempfile
import shutil
import os
from io import BytesIO
from PIL import Image
from ricecooker import config
from le_utils.constants import content_kinds,file_formats, format_presets, licenses, exercises

def download_image(path):
    filename, original_filename, path, file_size = download_file(path, '.{}'.format(file_formats.PNG))
    return '![]' + exercises.IMG_FORMAT.format(filename), filename, original_filename, path, file_size

def download_file(path, extension=None):
    """ download_file: downloads files to local storage
        @param files (list of files to download)
        @return list of file hashes and extensions
    """
    hash = hashlib.md5()

    # Write file to temporary file
    with tempfile.TemporaryFile() as tempf:
        r = config.SESSION.get(path, stream=True)
        r.raise_for_status()
        for chunk in r:
            hash.update(chunk)
            tempf.write(chunk)

        # Get file metadata (hashed filename, original filename, size)
        hashstring = hash.hexdigest()
        original_filename = path.split("/")[-1].split(".")[0]
        filename = '{0}{ext}'.format(hashstring, ext=os.path.splitext(path)[-1] if extension is None else extension)
        file_size = tempf.tell()
        tempf.seek(0)

        # Write file to local storage
        with open(config.get_storage_path(filename), 'wb') as destf:
            shutil.copyfileobj(tempf, destf)

    return filename, original_filename, path, file_size

def guess_content_kind(files, questions=None):
    """ guess_content_kind: determines what kind the content is
        Args:
            files (str or list): files associated with content
        Returns: string indicating node's kind
    """
    files = [files] if isinstance(files, str) else files
    questions=[questions] if isinstance(questions, str) else questions
    if files is not None and len(files) > 0:
        for f in files:
            ext = f.rsplit('/', 1)[-1].split(".")[-1].lower()
            if ext in content_kinds.MAPPING:
                return content_kinds.MAPPING[ext]
        raise InvalidFormatException("Invalid file type: Allowed formats are {0}".format([key for key, value in content_kinds.MAPPING.items()]))
    elif questions is not None and len(questions) > 0:
        return content_kinds.EXERCISE
    else:
        return content_kinds.TOPIC

""" TreeModel: model to handle structure of channel """
class TreeModel:
    def __init__(self):
        self.children = []

    """ to_dict: formats data to what CC expects
        @return dict of model's data
    """
    def to_dict(self):
        pass

    """ add_child: adds children to root node
        @param node (node to add to children)
    """
    def add_child(self, node):
        self.children += [node]

    def count(self):
        total = len(self.children)
        for child in self.children:
            total += child.count()
        return total

    def print_tree(self, indent=1):
        print("{indent}{title} ({kind}): {count} descendants".format(indent="   " * indent, title=self.title, kind=self.__class__.__name__, count=self.count()))
        for child in self.children:
            child.print_tree(indent + 1)


class Channel(TreeModel):
    """ Model representing the channel you are creating

        Used to store metadata on channel that is being created

        Attributes:
            channel_id (str): channel's unique id
            domain (str): who is providing the content (e.g. learningequality.org)
            title (str): name of channel
            thumbnail (str): file path or url of channel's thumbnail
            description (str): description of the channel
    """
    def __init__(self, channel_id, domain=None, title=None, thumbnail=None, description=None):
        self.domain = domain
        self.id = uuid.uuid3(uuid.NAMESPACE_DNS, uuid.uuid5(uuid.NAMESPACE_DNS, channel_id).hex)
        self.title = title
        self.thumbnail = self.encode_thumbnail(thumbnail)
        self.description = description

        # Add data to be used in next steps
        self._internal_domain = uuid.uuid5(uuid.NAMESPACE_DNS, self.domain)
        self.content_id = uuid.uuid5(self._internal_domain, self.id.hex)
        self.node_id = uuid.uuid5(self.id, self.content_id.hex)
        super(Channel, self).__init__()


    def to_dict(self):
        """ to_dict: puts data in format CC expects
            Args: None
            Returns: dict of channel data
        """
        return {
            "id": self.id.hex,
            "name": self.title,
            "has_changed": True,
            "thumbnail": self.thumbnail,
            "description": self.description if self.description is not None else "",
            "children": [child_node.to_dict() for child_node in self.children],
        }


    def encode_thumbnail(self, thumbnail):
        """ encode_thumbnail: gets base64 encoding of thumbnail
            Args:
                thumbnail (str): file path or url to channel's thumbnail
            Returns: base64 encoding of thumbnail
        """
        if thumbnail is None:
            return None
        else:
            if validators.url(thumbnail):
                r = requests.get(thumbnail, stream=True)
                if r.status_code == 200:
                    thumbnail = tempfile.TemporaryFile()
                    for chunk in r:
                        thumbnail.write(chunk)

            img = Image.open(thumbnail)
            width = 200
            height = int((float(img.size[1])*float(width/float(img.size[0]))))
            img.thumbnail((width,height), Image.ANTIALIAS)
            bufferstream = BytesIO()
            img.save(bufferstream, format="PNG")
            return "data:image/png;base64," + base64.b64encode(bufferstream.getvalue()).decode('utf-8')



class Node(TreeModel):
    """ Model representing the nodes in the channel's tree

        Base model for different content node kinds (topic, video, exercise, etc.)

        Attributes:
            id (str): content's original id
            title (str): content's title
            description (str): description of content
            author (str): who created the content
            license (str): content's license (using constants from fle_utils)
            files (str or list): content's associated file(s)
    """
    def __init__(self, *args, **kwargs):
        self.id = args[0]
        self.title = args[1]
        self.description = "" if 'description' not in kwargs else kwargs['description']
        self.author = kwargs['author']
        self.license = None if 'license' not in kwargs else kwargs['license']

        files = [] if 'files' not in kwargs else kwargs['files']
        self.files = [files] if isinstance(files, str) else files
        if 'thumbnail' in kwargs and kwargs['thumbnail'] is not None:
            self.files.append(kwargs['thumbnail'])

        self.questions = [] if 'questions' not in kwargs else kwargs['questions']
        self.extra_fields = {} if 'extra_fields' not in kwargs else kwargs['extra_fields']

        super(Node, self).__init__()


    def to_dict(self):
        """ to_dict: puts data in format CC expects
            Args: None
            Returns: dict of node's data
        """
        return {
            "title": self.title,
            "description": self.description if self.description is not None else "",
            "node_id": self.node_id.hex,
            "content_id": self.content_id.hex,
            "author": self.author if self.author is not None else "",
            "children": [child_node.to_dict() for child_node in self.children],
            "files" : self.files,
            "kind": self.kind,
            "license": self.license,
            "questions": self.questions,
            "extra_fields": json.dumps(self.extra_fields),
        }

    def set_ids(self, domain, parent_id):
        """ set_ids: sets ids to be used in building tree
            Args:
                domain (uuid): uuid of channel domain
                parent_id (uuid): parent node's node_id
            Returns: None
        """
        self.content_id = uuid.uuid5(domain, self.id)
        self.node_id = uuid.uuid5(parent_id, self.content_id.hex)



class Topic(Node):
    """ Model representing channel topics

        Topic nodes are used to add organization to the channel's content

        Attributes:
            id (str): content's original id
            title (str): content's title
            description (str): description of content
            author (str): who created the content
    """
    def __init__(self, id, title, description="", author=None):
        self.kind = content_kinds.TOPIC
        super(Topic, self).__init__(id, title, description=description, author=author)



class Video(Node):
    """ Model representing videos in channel

        Videos must be mp4 format

        Attributes:
            id (str): content's original id
            title (str): content's title
            author (str): who created the content
            description (str): description of content
            transcode_to_lower_resolutions (bool): indicates whether to extract lower resolution
            derive_thumbnail (bool): indicates whether to derive thumbnail from video
            preset (str): default preset for files
            subtitle (str): path or url to file's subtitles
            license (str): content's license (using constants from fle_utils)
            files (str or list): content's associated file(s)
    """
    default_preset = format_presets.VIDEO_HIGH_RES
    def __init__(self, id, title, author=None, description=None, transcode_to_lower_resolutions=False, derive_thumbnail=False, license=None, subtitle=None, files=None, preset=None, thumbnail=None):
        if preset is not None:
            self.default_preset = preset
        if transcode_to_lower_resolutions:
            self.transcode_to_lower_resolutions()
        if derive_thumbnail:
            thumbnail = self.derive_thumbnail()
        self.kind = content_kinds.VIDEO
        super(Video, self).__init__(id, title, description=description, author=author, license=license, files=files, thumbnail=thumbnail)

    def derive_thumbnail(self):
        """ derive_thumbnail: derive video's thumbnail
            Args: None
            Returns: None
        """
        pass

    def transcode_to_lower_resolutions(self):
        """ transcode_to_lower_resolutions: transcode video to lower resolution
            Args: None
            Returns: None
        """
        pass



class Audio(Node):
    """ Model representing audio content in channel

        Audio can be in either mp3 or wav format

        Attributes:
            id (str): content's original id
            title (str): content's title
            author (str): who created the content
            description (str): description of content
            subtitle (str): path or url to file's subtitles
            license (str): content's license (using constants from fle_utils)
            files (str or list): content's associated file(s)
    """
    default_preset = format_presets.AUDIO
    def __init__(self, id, title, author=None, description="", license=None, subtitle=None, files=None, thumbnail=None):
        self.kind = content_kinds.AUDIO
        super(Audio, self).__init__(id, title, description=description, author=author, license=license, files=files, thumbnail=thumbnail)



class Document(Node):
    """ Model representing documents in channel

        Documents must be pdf format

        Attributes:
            id (str): content's original id
            title (str): content's title
            author (str): who created the content
            description (str): description of content
            license (str): content's license (using constants from fle_utils)
            files (str or list): content's associated file(s)
    """
    default_preset = format_presets.DOCUMENT
    def __init__(self, id, title, author=None, description=None, license=None, files=None, thumbnail=None):
        self.kind = content_kinds.DOCUMENT
        super(Document, self).__init__(id, title, description=description, author=author, license=license, files=files, thumbnail=thumbnail)



class Exercise(Node):
    """ Model representing exercises in channel

        Exercises are sets of questions to assess learners'
        understanding of the content

        Attributes:
            id (str): content's original id
            title (str): content's title
            author (str): who created the content
            description (str): description of content
            license (str): content's license (using constants from fle_utils)
            files (str or list): content's associated file(s)
    """
    default_preset = format_presets.EXERCISE
    def __init__(self, id, title, author=None, description=None, license=None, files=None, exercise_data=None, thumbnail=None):
        self.kind = content_kinds.EXERCISE
        self.questions = []

        files = [] if files is None else files
        exercise_data = {} if exercise_data is None else exercise_data
        super(Exercise, self).__init__(id, title, description=description, author=author, license=license, files=files, questions=self.questions, extra_fields=exercise_data,thumbnail=thumbnail)

    def add_question(self, question):
        self.questions += [question]

    def get_all_files(self):
        files = {}
        file_list = []
        for question in self.questions:
            files.update(question._file_mapping)
            file_list += question.files
        return files, file_list

    def to_dict(self):
        """ to_dict: puts data in format CC expects
            Args: None
            Returns: dict of node's data
        """
        return {
            "title": self.title,
            "description": self.description if self.description is not None else "",
            "node_id": self.node_id.hex,
            "content_id": self.content_id.hex,
            "author": self.author if self.author is not None else "",
            "children": [child_node.to_dict() for child_node in self.children],
            "files" : self.get_all_files()[1],
            "kind": self.kind,
            "license": self.license,
            "questions": [question.to_dict() for question in self.questions],
            "extra_fields": json.dumps(self.extra_fields),
        }