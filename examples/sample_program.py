#!/usr/bin/env python

from enum import Enum
import json
import os
from os.path import join
import re

from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, questions, files
from ricecooker.classes.licenses import get_license
from ricecooker.exceptions import UnknownContentKindError, UnknownFileTypeError, UnknownQuestionTypeError, InvalidFormatException, raise_for_invalid_channel
from le_utils.constants import content_kinds,file_formats, format_presets, licenses, exercises, languages
from pressurecooker.encodings import get_base64_encoding


# CHANNEL SETTINGS
SOURCE_DOMAIN = "<yourdomain.org>"                 # content provider's domain
SOURCE_ID = "<yourid>"                             # an alphanumeric channel ID
CHANNEL_TITLE = "Testing Ricecooker Channel"       # a humand-readbale title
CHANNEL_LANGUAGE = "en"                            # language code of channel


# LOCAL DIRS
EXAMPLES_DIR = os.path.dirname(os.path.realpath(__file__))
DATA_DIR = os.path.join(EXAMPLES_DIR, 'data')
CONTENT_DIR = os.path.join(EXAMPLES_DIR, 'content')
#
# A utility function to manage absolute paths that allows us to refer to files
# in the CONTENT_DIR (subdirectory `content/' in current directory) using content://
def get_abspath(path, content_dir=CONTENT_DIR):
    """
    Replaces `content://` with absolute path of `content_dir`.
    By default looks for content in subdirectory `content` in current directory.
    """
    if path:
        file = re.search('content://(.+)', path)
        if file:
            return os.path.join(content_dir, file.group(1))
    return path



class FileTypes(Enum):
    """ Enum containing all file types Ricecooker can have

        Steps:
            AUDIO_FILE: mp3 files
            THUMBNAIL: png, jpg, or jpeg files
            DOCUMENT_FILE: pdf files
    """
    AUDIO_FILE = 0
    THUMBNAIL = 1
    DOCUMENT_FILE = 2
    VIDEO_FILE = 3
    YOUTUBE_VIDEO_FILE = 4
    VECTORIZED_VIDEO_FILE = 5
    VIDEO_THUMBNAIL = 6
    YOUTUBE_VIDEO_THUMBNAIL_FILE = 7
    HTML_ZIP_FILE = 8
    SUBTITLE_FILE = 9
    TILED_THUMBNAIL_FILE = 10
    UNIVERSAL_SUBS_SUBTITLE_FILE = 11
    BASE64_FILE = 12
    WEB_VIDEO_FILE = 13
    H5P_FILE = 14


FILE_TYPE_MAPPING = {
    content_kinds.AUDIO : {
        file_formats.MP3 : FileTypes.AUDIO_FILE,
        file_formats.PNG : FileTypes.THUMBNAIL,
        file_formats.JPG : FileTypes.THUMBNAIL,
        file_formats.JPEG : FileTypes.THUMBNAIL,
    },
    content_kinds.DOCUMENT : {
        file_formats.PDF : FileTypes.DOCUMENT_FILE,
        file_formats.PNG : FileTypes.THUMBNAIL,
        file_formats.JPG : FileTypes.THUMBNAIL,
        file_formats.JPEG : FileTypes.THUMBNAIL,
    },
    content_kinds.HTML5 : {
        file_formats.HTML5 : FileTypes.HTML_ZIP_FILE,
        file_formats.PNG : FileTypes.THUMBNAIL,
        file_formats.JPG : FileTypes.THUMBNAIL,
        file_formats.JPEG : FileTypes.THUMBNAIL,
    },
    content_kinds.H5P : {
        file_formats.H5P : FileTypes.H5P_FILE,
        file_formats.PNG : FileTypes.THUMBNAIL,
        file_formats.JPG : FileTypes.THUMBNAIL,
        file_formats.JPEG : FileTypes.THUMBNAIL,
    },
    content_kinds.VIDEO : {
        file_formats.MP4 : FileTypes.VIDEO_FILE,
        file_formats.VTT : FileTypes.SUBTITLE_FILE,
        file_formats.PNG : FileTypes.THUMBNAIL,
        file_formats.JPG : FileTypes.THUMBNAIL,
        file_formats.JPEG : FileTypes.THUMBNAIL,
    },
    content_kinds.EXERCISE : {
        file_formats.PNG : FileTypes.THUMBNAIL,
        file_formats.JPG : FileTypes.THUMBNAIL,
        file_formats.JPEG : FileTypes.THUMBNAIL,
    },
}



def guess_file_type(kind, filepath=None, youtube_id=None, web_url=None, encoding=None):
    """ guess_file_class: determines what file the content is
        Args:
            filepath (str): filepath of file to check
        Returns: string indicating file's class
    """
    if youtube_id:
        return FileTypes.YOUTUBE_VIDEO_FILE
    elif web_url:
        return FileTypes.WEB_VIDEO_FILE
    elif encoding:
        return FileTypes.BASE64_FILE
    else:
        ext = os.path.splitext(filepath)[1][1:].lower()
        if kind in FILE_TYPE_MAPPING and ext in FILE_TYPE_MAPPING[kind]:
            return FILE_TYPE_MAPPING[kind][ext]
    return None

def guess_content_kind(path=None, web_video_data=None, questions=None):
    """ guess_content_kind: determines what kind the content is
        Args:
            files (str or list): files associated with content
        Returns: string indicating node's kind
    """
    # If there are any questions, return exercise
    if questions and len(questions) > 0:
        return content_kinds.EXERCISE

    # See if any files match a content kind
    if path:
        ext = os.path.splitext(path)[1][1:].lower()
        if ext in content_kinds.MAPPING:
            return content_kinds.MAPPING[ext]
        raise InvalidFormatException("Invalid file type: Allowed formats are {0}".format([key for key, value in content_kinds.MAPPING.items()]))
    elif web_video_data:
        return content_kinds.VIDEO
    else:
        return content_kinds.TOPIC



# LOAD sample_tree.json (as dict)
with open(join(DATA_DIR,'sample_tree.json'),'r') as json_file:
    SAMPLE_TREE = json.load(json_file)

# LOAD JSON DATA (as string) FOR PERSEUS QUESTIONS
SAMPLE_PERSEUS_1_JSON = open(join(DATA_DIR,'sample_perseus01.json'),'r').read()
# SAMPLE_PERSEUS_2_JSON = open(join(DATA_DIR,'sample_perseus02.json'),'r').read()

# ADD EXERCISES
EXERCISES_NODES = [
    {
        "title": "Rice Cookers",
        "id": "d98752",
        "description": "Start cooking rice today!",
        "children": [
            {
                "title": "Rice Chef",
                "id": "6cafe2",
                "author": "Revision 3",
                "description": "Become a master rice cooker",
                "file": "https://ia600209.us.archive.org/27/items/RiceChef/Rice Chef.mp4",
                "license": licenses.CC_BY_NC_SA,
                "copyright_holder": "Learning Equality",
                "files": [
                    {
                        "path": "https://ia600209.us.archive.org/27/items/RiceChef/Rice Chef.mp4",
                    },
                    {
                        "encoding": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAABGdBTUEAALGPC/xhBQAAAAFzUkdCAK7OHOkAAAAgY0hSTQAAeiYAAICEAAD6AAAAgOgAAHUwAADqYAAAOpgAABdwnLpRPAAAAmFQTFRF////wN/2I0FiNFFuAAAAxdvsN1RxV3KMnrPFFi9PAB1CVG+KXHaQI0NjttLrEjVchIF4AyNGZXB5V087UUw/EzBMpqWeb2thbmpgpqOceXVsERgfTWeADg8QCAEApKGZBAYIop+XCQkIhZ+2T2mEg5mtnK/AobPDkKO2YXqTAAAAJkBetMraZH2VprjIz9zm4enw7/T47fP3wc7ae5GnAAAAN1BsSmSApLfI1ODq2OHp5Orv8PL09vb38fb5wM/bbISbrL/PfZSpxNPgzdnj2+Pr5evw6+/z6e3w3ePp2OPsma2/ABM5Q197ABk4jKG1yNfjytfh1uDo3eXs4unv1t/nztrjqbzMTmmEXneRES1Ji6CzxtXixdPfztrk1N/n1+Dp1d/oz9vlxdPeq73NVG+KYnyUAAAddIuhwtPhvMzaxtTgytfiy9jjwtHewtHenbDCHT1fS2eCRV52qr7PvM3cucrYv87cv8/cvMzavc3bucvacoyl////ByE8WnKKscXWv9Hguszbu8zbvc7dtcnaiJqrcHZ4f4SHEh0nEitFTWZ+hJqumrDDm7HDj6W5dI2lYGJfmZeQl5SNAAAADRciAAATHjdSOVNsPlhyLklmKCYjW1lUlpOLlZKLFSAqWXSOBQAADA0NAAAAHh0bWlhSk5CIk5CIBAYJDRQbERcdDBAUBgkMAAAEDg4NAAAAHBsZWFZQkY6GAAAAAAAABQUEHBsZAAAAGxoYVlROko+GBAQDZ2RdAAAAGhkYcW9oAgICAAAAExMSDQwLjouDjYuDioiAiIV9hoN7VlRO////Z2DcYwAAAMR0Uk5TAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACRKrJyrZlBQECaNXCsKaqypMGAUDcu7Gpn5mf03gDo8+4saiipKq3xRMBH83Eu7OsqbG61DkDMdbFvrizsbK3wNs9Ax/VysS/vLq/zNwfArDhxMfExMXE3pMCMe7byMjIzd33ZgYGQtnz6+zooeJXBQMFD1yHejZ1+l8FBgEELlOR+GgFCQ0SGxoBGFKg+m0BBwEMR6v+hAEDM6nRASWURVuYQQ4AAAABYktHRACIBR1IAAAACXBIWXMAAAjLAAAIywGEuOmJAAABCklEQVQY02NgUGZUUVVT19DUYtBmYmZhYdBh1dXTNzA0MjYxZTFjAwqwm1tYWlnb2NrZO3A4cgIFGJycXVzd3D08vbx9uHyBAn7+AYFBwSEhoWHhEdyRQIGo6JjYuPiExKTklFSeNKBAekZmVnZObk5efkEhbxFQgK+4pLSsvKKyqrqGoZZfgIVBsK6+obGpuaW1rV2oQ1hEgKFTtKu7p7evf8LEI5PEJotLMEyZyjJt+oyZsxhmzzk6V3KeFIO01vwFMrJyCxctXrL02DL55QwsClorVq5avWbtuvUbNh7fpMjAwsKyWWvLFJatStu279h5YhdIAAJ2s+zZu+/kfoQAy4HNLAcPHQYA5YtSi+k2/WkAAAAldEVYdGRhdGU6Y3JlYXRlADIwMTMtMTAtMDRUMTk6Mzk6MjEtMDQ6MDAwU1uYAAAAJXRFWHRkYXRlOm1vZGlmeQAyMDEzLTEwLTA0VDE5OjM5OjIxLTA0OjAwQQ7jJAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAAAASUVORK5CYII=",
                    },
                ],
            },
            {
                "title": "Rice Exercise",
                "id": "6cafe3",
                "description": "Test how well you know your rice",
                "license": licenses.CC_BY_NC_SA,
                "copyright_holder": "Learning Equality",
                "mastery_model": exercises.DO_ALL,
                "files": [
                    {
                        "path": "http://www.publicdomainpictures.net/pictures/110000/nahled/bowl-of-rice.jpg",
                    }
                ],
                "questions": [
                    {
                        "id": "eeeee",
                        "question": "Which rice is your favorite? \\_\\_\\_ ![](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAABGdBTUEAALGPC/xhBQAAAAFzUkdCAK7OHOkAAAAgY0hSTQAAeiYAAICEAAD6AAAAgOgAAHUwAADqYAAAOpgAABdwnLpRPAAAAmFQTFRF////wN/2I0FiNFFuAAAAxdvsN1RxV3KMnrPFFi9PAB1CVG+KXHaQI0NjttLrEjVchIF4AyNGZXB5V087UUw/EzBMpqWeb2thbmpgpqOceXVsERgfTWeADg8QCAEApKGZBAYIop+XCQkIhZ+2T2mEg5mtnK/AobPDkKO2YXqTAAAAJkBetMraZH2VprjIz9zm4enw7/T47fP3wc7ae5GnAAAAN1BsSmSApLfI1ODq2OHp5Orv8PL09vb38fb5wM/bbISbrL/PfZSpxNPgzdnj2+Pr5evw6+/z6e3w3ePp2OPsma2/ABM5Q197ABk4jKG1yNfjytfh1uDo3eXs4unv1t/nztrjqbzMTmmEXneRES1Ji6CzxtXixdPfztrk1N/n1+Dp1d/oz9vlxdPeq73NVG+KYnyUAAAddIuhwtPhvMzaxtTgytfiy9jjwtHewtHenbDCHT1fS2eCRV52qr7PvM3cucrYv87cv8/cvMzavc3bucvacoyl////ByE8WnKKscXWv9Hguszbu8zbvc7dtcnaiJqrcHZ4f4SHEh0nEitFTWZ+hJqumrDDm7HDj6W5dI2lYGJfmZeQl5SNAAAADRciAAATHjdSOVNsPlhyLklmKCYjW1lUlpOLlZKLFSAqWXSOBQAADA0NAAAAHh0bWlhSk5CIk5CIBAYJDRQbERcdDBAUBgkMAAAEDg4NAAAAHBsZWFZQkY6GAAAAAAAABQUEHBsZAAAAGxoYVlROko+GBAQDZ2RdAAAAGhkYcW9oAgICAAAAExMSDQwLjouDjYuDioiAiIV9hoN7VlRO////Z2DcYwAAAMR0Uk5TAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACRKrJyrZlBQECaNXCsKaqypMGAUDcu7Gpn5mf03gDo8+4saiipKq3xRMBH83Eu7OsqbG61DkDMdbFvrizsbK3wNs9Ax/VysS/vLq/zNwfArDhxMfExMXE3pMCMe7byMjIzd33ZgYGQtnz6+zooeJXBQMFD1yHejZ1+l8FBgEELlOR+GgFCQ0SGxoBGFKg+m0BBwEMR6v+hAEDM6nRASWURVuYQQ4AAAABYktHRACIBR1IAAAACXBIWXMAAAjLAAAIywGEuOmJAAABCklEQVQY02NgUGZUUVVT19DUYtBmYmZhYdBh1dXTNzA0MjYxZTFjAwqwm1tYWlnb2NrZO3A4cgIFGJycXVzd3D08vbx9uHyBAn7+AYFBwSEhoWHhEdyRQIGo6JjYuPiExKTklFSeNKBAekZmVnZObk5efkEhbxFQgK+4pLSsvKKyqrqGoZZfgIVBsK6+obGpuaW1rV2oQ1hEgKFTtKu7p7evf8LEI5PEJotLMEyZyjJt+oyZsxhmzzk6V3KeFIO01vwFMrJyCxctXrL02DL55QwsClorVq5avWbtuvUbNh7fpMjAwsKyWWvLFJatStu279h5YhdIAAJ2s+zZu+/kfoQAy4HNLAcPHQYA5YtSi+k2/WkAAAAldEVYdGRhdGU6Y3JlYXRlADIwMTMtMTAtMDRUMTk6Mzk6MjEtMDQ6MDAwU1uYAAAAJXRFWHRkYXRlOm1vZGlmeQAyMDEzLTEwLTA0VDE5OjM5OjIxLTA0OjAwQQ7jJAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAAAASUVORK5CYII=)",
                        "type":exercises.MULTIPLE_SELECTION,
                        "correct_answers": ["White rice", "Brown rice", "Sushi rice <p>abc</p>"],
                        "all_answers": ["White rice", "Quinoa","Brown rice", "<"],
                    },
                    {
                        "id": "bbbbb",
                        "question": "Which rice is the crunchiest?",
                        "type":exercises.SINGLE_SELECTION,
                        "correct_answer": "Rice Krispies \n![](https://upload.wikimedia.org/wikipedia/commons/c/cd/RKTsquares.jpg)",
                        "all_answers": [
                            "White rice",
                            "Brown rice \n![](https://c2.staticflickr.com/4/3159/2889140143_b99fd8dd4c_z.jpg?zz=1)",
                            "Rice Krispies \n![](https://upload.wikimedia.org/wikipedia/commons/c/cd/RKTsquares.jpg)"
                        ],
                        "hints": "It's delicious",
                    },
                    {

                        "id": "aaaaa",
                        "question": "How many minutes does it take to cook rice? <img src='https://upload.wikimedia.org/wikipedia/commons/5/5e/Jeera-rice.JPG'>",
                        "type":exercises.INPUT_QUESTION,
                        "answers": ["20", "25", "15"],
                        "hints": ["Takes roughly same amount of time to install kolibri on Windows machine", "Does this help?\n![](http://www.aroma-housewares.com/images/rice101/delay_timer_1.jpg)"],
                    },
                    {
                        "id": "ddddd",
                        "type":exercises.PERSEUS_QUESTION,
                        "item_data":SAMPLE_PERSEUS_1_JSON,
                    },
                ],
            },
            {
                "title": "Rice Exercise 2",
                "id": "6cafe4",
                "description": "Test how well you know your rice",
                "license": licenses.CC_BY_NC_SA,
                "copyright_holder": "Learning Equality",
                "mastery_model": exercises.M_OF_N,
                "files": [
                    {
                        "path": "https://c1.staticflickr.com/5/4021/4302326650_b11f0f0aaf_b.jpg",
                    }
                ],
                "questions": [
                    {
                        "id": "11111",
                        "question": "<h3 id=\"rainbow\" style=\"font-weight:bold\">RICE COOKING!!!</h3><script type='text/javascript'><!-- setInterval(function() {$('#rainbow').css('color', '#'+((1<<24)*Math.random()|0).toString(16));}, 300); --></script>",
                        "type":exercises.SINGLE_SELECTION,
                        "all_answers": ["Answer"],
                        "correct_answer": "Answer",
                    },
                    {
                        "id": "121212",
                        "question": '<math> <mrow> <msup><mi> a </mi><mn>2</mn></msup> <mo> + </mo> <msup><mi> b </mi><mn>2</mn></msup> <mo> = </mo> <msup><mi> c </mi><mn>2</mn></msup> </mrow> </math>',
                        "type":exercises.SINGLE_SELECTION,
                        "all_answers": ["Answer"],
                        "correct_answer": "Answer",
                    },
                ],
            },
            {
                "title": "HTML Sample",
                "id": "abcdef",
                "description": "An example of how html can be imported from the ricecooker",
                "license": licenses.PUBLIC_DOMAIN,
                "files": [
                    {
                        "path": "content://htmltest.zip",
                    }
                ]
            },
            {
                "title": "Rice Exercise 3",
                "id": "6cafe5",
                "description": "Test how well you know your rice",
                "license": licenses.CC_BY_NC_SA,
                "copyright_holder": "Learning Equality",
                "mastery_model": exercises.M_OF_N,
                "files": [
                    {
                        "path": "https://upload.wikimedia.org/wikipedia/commons/b/b7/Rice_p1160004.jpg",
                    }
                ],
                "questions": [
                    {
                        "id": "123456",
                        "question": "Solve: $$(111^{x+1}\\times111^\\frac14)\div111^\\frac12=111^3$$",
                        "type":exercises.SINGLE_SELECTION,
                        "all_answers": ["Yes", "No", "Rice!"],
                        "correct_answer": "Rice!",
                    },
                ],
            },
        ]
    },
]
SAMPLE_TREE.extend(EXERCISES_NODES)


class SampleChef(SushiChef):
    """
    The chef class that takes care of uploading channel to the content curation server.

    We'll call its `main()` method from the command line script.
    """
    channel_info = {    #
        'CHANNEL_SOURCE_DOMAIN': SOURCE_DOMAIN,       # who is providing the content (e.g. learningequality.org)
        'CHANNEL_SOURCE_ID': SOURCE_ID,                   # channel's unique id
        'CHANNEL_TITLE': CHANNEL_TITLE,
        'CHANNEL_LANGUAGE': CHANNEL_LANGUAGE,
        'CHANNEL_THUMBNAIL': 'https://upload.wikimedia.org/wikipedia/commons/thumb/5/50/Banaue_Philippines_Banaue-Rice-Terraces-01.jpg/640px-Banaue_Philippines_Banaue-Rice-Terraces-01.jpg', # (optional) local path or url to image file
        'CHANNEL_DESCRIPTION': 'A sample sushi chef to demo content types.',      # (optional) description of the channel (optional)
    }

    def construct_channel(self, *args, **kwargs):
        """
        Create ChannelNode and build topic tree.
        """
        channel = self.get_channel(*args, **kwargs)   # creates ChannelNode from data in self.channel_info
        _build_tree(channel, SAMPLE_TREE)
        raise_for_invalid_channel(channel)

        return channel


def _build_tree(node, sourcetree):
    """
    Parse nodes given in `sourcetree` and add as children of `node`.
    """
    for child_source_node in sourcetree:
        try:
            main_file = child_source_node['files'][0] if 'files' in child_source_node else {}
            kind = guess_content_kind(path=main_file.get('path'), web_video_data=main_file.get('youtube_id') or main_file.get('web_url'), questions=child_source_node.get("questions"))
        except UnknownContentKindError:
            continue

        if kind == content_kinds.TOPIC:
            child_node = nodes.TopicNode(
                source_id=child_source_node["id"],
                title=child_source_node["title"],
                author=child_source_node.get("author"),
                description=child_source_node.get("description"),
                thumbnail=child_source_node.get("thumbnail"),
            )
            node.add_child(child_node)

            source_tree_children = child_source_node.get("children", [])

            _build_tree(child_node, source_tree_children)

        elif kind == content_kinds.VIDEO:
            child_node = nodes.VideoNode(
                source_id=child_source_node["id"],
                title=child_source_node["title"],
                license=get_license(child_source_node.get("license"), description="Description of license", copyright_holder=child_source_node.get('copyright_holder')),
                author=child_source_node.get("author"),
                description=child_source_node.get("description"),
                derive_thumbnail=True, # video-specific data
                thumbnail=child_source_node.get('thumbnail'),
            )
            add_files(child_node, child_source_node.get("files") or [])
            node.add_child(child_node)

        elif kind == content_kinds.AUDIO:
            child_node = nodes.AudioNode(
                source_id=child_source_node["id"],
                title=child_source_node["title"],
                license=child_source_node.get("license"),
                author=child_source_node.get("author"),
                description=child_source_node.get("description"),
                thumbnail=child_source_node.get("thumbnail"),
                copyright_holder=child_source_node.get("copyright_holder"),
            )
            add_files(child_node, child_source_node.get("files") or [])
            node.add_child(child_node)

        elif kind == content_kinds.DOCUMENT:
            child_node = nodes.DocumentNode(
                source_id=child_source_node["id"],
                title=child_source_node["title"],
                license=child_source_node.get("license"),
                author=child_source_node.get("author"),
                description=child_source_node.get("description"),
                thumbnail=child_source_node.get("thumbnail"),
                copyright_holder=child_source_node.get("copyright_holder"),
            )
            add_files(child_node, child_source_node.get("files") or [])
            node.add_child(child_node)

        elif kind == content_kinds.EXERCISE:
            mastery_model = (child_source_node.get('mastery_model') and {"mastery_model": child_source_node['mastery_model']}) or {}
            child_node = nodes.ExerciseNode(
                source_id=child_source_node["id"],
                title=child_source_node["title"],
                license=child_source_node.get("license"),
                author=child_source_node.get("author"),
                description=child_source_node.get("description"),
                exercise_data=mastery_model,
                thumbnail=child_source_node.get("thumbnail"),
                copyright_holder=child_source_node.get("copyright_holder"),
            )
            add_files(child_node, child_source_node.get("files") or [])
            for q in child_source_node.get("questions"):
                question = create_question(q)
                child_node.add_question(question)
            node.add_child(child_node)

        elif kind == content_kinds.HTML5:
            child_node = nodes.HTML5AppNode(
                source_id=child_source_node["id"],
                title=child_source_node["title"],
                license=child_source_node.get("license"),
                author=child_source_node.get("author"),
                description=child_source_node.get("description"),
                thumbnail=child_source_node.get("thumbnail"),
                copyright_holder=child_source_node.get("copyright_holder"),
            )
            add_files(child_node, child_source_node.get("files") or [])
            node.add_child(child_node)

        elif kind == content_kinds.H5P:
            child_node = nodes.H5PAppNode(
                source_id=child_source_node["id"],
                title=child_source_node["title"],
                license=child_source_node.get("license"),
                author=child_source_node.get("author"),
                description=child_source_node.get("description"),
                thumbnail=child_source_node.get("thumbnail"),
                copyright_holder=child_source_node.get("copyright_holder"),
            )
            add_files(child_node, child_source_node.get("files") or [])
            node.add_child(child_node)

        else:                   # unknown content file format
            continue

    return node

def add_files(node, file_list):
    for f in file_list:

        path = f.get('path')
        if path is not None:
            abspath = get_abspath(path)      # NEW: expand  content://  -->  ./content/  in file paths
        else:
            abspath = None

        file_type = guess_file_type(node.kind, filepath=abspath, youtube_id=f.get('youtube_id'), web_url=f.get('web_url'), encoding=f.get('encoding'))

        if file_type == FileTypes.AUDIO_FILE:
            node.add_file(files.AudioFile(path=abspath, language=f.get('language')))
        elif file_type == FileTypes.THUMBNAIL:
            node.add_file(files.ThumbnailFile(path=abspath))
        elif file_type == FileTypes.DOCUMENT_FILE:
            node.add_file(files.DocumentFile(path=abspath, language=f.get('language')))
        elif file_type == FileTypes.HTML_ZIP_FILE:
            node.add_file(files.HTMLZipFile(path=abspath, language=f.get('language')))
        elif file_type == FileTypes.H5P_FILE:
            node.add_file(files.H5PFile(path=abspath, language=f.get('language')))
        elif file_type == FileTypes.VIDEO_FILE:
            node.add_file(files.VideoFile(path=abspath, language=f.get('language'), ffmpeg_settings=f.get('ffmpeg_settings')))
        elif file_type == FileTypes.SUBTITLE_FILE:
            node.add_file(files.SubtitleFile(path=abspath, language=f['language']))
        elif file_type == FileTypes.BASE64_FILE:
            node.add_file(files.Base64ImageFile(encoding=f['encoding']))
        elif file_type == FileTypes.WEB_VIDEO_FILE:
            node.add_file(files.WebVideoFile(web_url=f['web_url'], high_resolution=f.get('high_resolution')))
        elif file_type == FileTypes.YOUTUBE_VIDEO_FILE:
            node.add_file(files.YouTubeVideoFile(youtube_id=f['youtube_id'], high_resolution=f.get('high_resolution')))
            node.add_file(files.YouTubeSubtitleFile(youtube_id=f['youtube_id'], language='en'))
        else:
            raise UnknownFileTypeError("Unrecognized file type '{0}'".format(f['path']))

def create_question(raw_question):
    question = parse_images(raw_question.get('question'))
    hints = raw_question.get('hints')
    hints = parse_images(hints) if isinstance(hints, str) else [parse_images(hint) for hint in hints or []]

    if raw_question["type"] == exercises.MULTIPLE_SELECTION:
        return questions.MultipleSelectQuestion(
            id=raw_question["id"],
            question=question,
            correct_answers=[parse_images(answer) for answer in raw_question['correct_answers']],
            all_answers=[parse_images(answer) for answer in raw_question['all_answers']],
            hints=hints,
        )
    if raw_question["type"] == exercises.SINGLE_SELECTION:
        return questions.SingleSelectQuestion(
            id=raw_question["id"],
            question=question,
            correct_answer=parse_images(raw_question['correct_answer']),
            all_answers=[parse_images(answer) for answer in raw_question['all_answers']],
            hints=hints,
        )
    if raw_question["type"] == exercises.INPUT_QUESTION:
        return questions.InputQuestion(
            id=raw_question["id"],
            question=question,
            answers=[parse_images(answer) for answer in raw_question['answers']],
            hints=hints,
        )
    if raw_question["type"] == exercises.PERSEUS_QUESTION:
        return questions.PerseusQuestion(
            id=raw_question["id"],
            raw_data=parse_images(raw_question.get('item_data')),
            source_url="https://www.google.com/",
        )
    else:
        raise UnknownQuestionTypeError("Unrecognized question type '{0}': accepted types are {1}".format(raw_question["type"], [key for key, value in exercises.question_choices]))

def parse_images(content):
    if content:
        reg = re.compile(questions.MARKDOWN_IMAGE_REGEX, flags=re.IGNORECASE)
        matches = reg.findall(content)
        for match in matches:
            path = match[1]
            graphie = re.search(questions.WEB_GRAPHIE_URL_REGEX, path)
            if graphie:
                path = graphie.group(1)
            content = content.replace(path, get_abspath(path).replace('\\', '\\\\'))
    return content



if __name__ == '__main__':
    """
    This code will run when the sushi chef is called from the command line.
    """

    chef = SampleChef()
    chef.main()
