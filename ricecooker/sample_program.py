import os
from enum import Enum
from ricecooker.classes import nodes, questions, files
from ricecooker.classes.licenses import get_license
from ricecooker.exceptions import UnknownContentKindError, UnknownFileTypeError, UnknownQuestionTypeError, raise_for_invalid_channel
from le_utils.constants import content_kinds,file_formats, format_presets, licenses, exercises, languages
from pressurecooker.encodings import get_base64_encoding

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
        ext = path.rsplit('/', 1)[-1].split(".")[-1].lower()
        if ext in content_kinds.MAPPING:
            return content_kinds.MAPPING[ext]
        raise InvalidFormatException("Invalid file type: Allowed formats are {0}".format([key for key, value in content_kinds.MAPPING.items()]))
    elif web_video_data:
        return content_kinds.VIDEO
    else:
        return content_kinds.TOPIC

SAMPLE_PERSEUS = '{"answerArea":{"chi2Table":false,"periodicTable":false,"tTable":false,"zTable":false,"calculator":false},' + \
'"hints":[{"widgets":{},"images":{"web+graphie:C:/users/jordan/contentcuration-dump/0a0c0f1a1a40226d8d227a07dd143f8c08a4b8a5": {}},"content":"Hint #1","replace":false},{"widgets":{},"images":{},"content":"Hint #2","replace":false}],' +\
'"question":{"widgets":{"radio 1":{"type":"radio","alignment":"default","graded":true,"static":false,' +\
'"options":{"deselectEnabled":false,"multipleSelect":false,"choices":[{"correct":true,"content":"Yes"},{"correct":false,"content":"No"}],' +\
'"displayCount":null,"hasNoneOfTheAbove":false,"randomize":false,"onePerLine":true},"version":{"minor":0,"major":1}}},"images":{"web+graphie:C:/users/jordan/contentcuration-dump/0a0c0f1a1a40226d8d227a07dd143f8c08a4b8a5": {}},' +\
'"content":"Do you like rice?\\\"\\n\\n![](web+graphie:file:///C:/users/jordan/contentcuration-dump/0a0c0f1a1a40226d8d227a07dd143f8c08a4b8a5)\\n\\n[[\\u2603 radio 1]]"},"itemDataVersion":{"minor":1,"major":0}}'

SAMPLE_PERSEUS_2 = '{"hints":[{"replace":false,"content":"Numbers are equivalent when they are located at the same point on the number line.\\n\\nLet\'s ' +\
'see what fraction is at the same location as $\\\\tealD{\\\\dfrac48}$ on the number line.\\n","widgets":{},"images":{"web+graphie:file:///C:/Users/Jordan/contentcuration-dump/ddb3feb4c8e3740ca4f10c2ebad70b5797f60ebd":' +\
'{"width":460,"height":120}}},{"replace":false,"content":"![](web+graphie:file:///home/ralphie/Desktop/ka-sushi-chef-sw/build/a61/a61ac6f4038cb3e2c3bd6e69f6e75da10632a3d4\\n)\\n\\n $\\\\purpleC{\\\\dfrac24}$ is at the same location on the ' +\
'number line as  $\\\\tealD{\\\\dfrac48}$.\\n","widgets":{},"images":{}},{"replace":false,"content":" $\\\\purpleC{\\\\dfrac24}$ is equivalent to $\\\\tealD{\\\\dfrac48}$.\\n\\n![]( web+graphie:file:///home/ralphie/Desktop/ka-sushi-chef-sw/' +\
'build/e84/e84b6d5fa1410f002ef8f9446a999d4a09266edd)","widgets":{},"images":{"web+graphie:file:///home/ralphie/Desktop/ka-sushi-chef-sw/build/6a1/6a1bf04c8df3d217c846362e8902008d84d10ff4":{"width":460,"height":120}}}],"question":{"content"' +\
':"![](web+graphie:file:///home/ralphie/Desktop/ka-sushi-chef-sw/build/749/749d2d16db0cfc94e8685f3eb7302394448d8c8c)\\n\\n**Move the dot to a fraction equivalent to $\\\\tealD{\\\\dfrac48}$ on the number line.**\\n\\n\\n[[\\u2603 number-line ' +\
'1]]\\n","widgets":{"number-line 1":{"type":"number-line","static":false,"options":{"initialX":null,"labelRange":[null,null],"divisionRange":[null,null],"correctX":0.5,"labelStyle":"non-reduced","labelTicks":true,"snapDivisions":2,"correctRel":' +\
'"eq","static":false,"numDivisions":null,"range":[null,null],"tickStep":0.25},"graded":true,"version":{"minor":0,"major":0},"alignment":"default"}},"images":{}},"itemDataVersion":{"minor":1,"major":0},"answerArea":{"periodicTable":false,"zTable":' +\
'false,"chi2Table":false,"calculator":false,"tTable":false}}'

SAMPLE_TREE = [
    {
        "title": "Video Tests",
        "id": "abd116",
        "description": "Tests for different videos",
        "children": [
            {
                "title": "TEST COMPRESSION",
                "id": "6cafe7",
                "author": "Revision 3",
                "description": "Compression Test",
                "license": licenses.CC_BY_NC_SA,
                "files": [
                    {
                        "path": "C:/users/jordan/contentcuration-dump/high resolution.mp4",
                        "ffmpeg_settings": {"max_width": 480, "crf": 20},
                    }
                ],
                "thumbnail": "https://cdn.kastatic.org/googleusercontent/5QUfMdnHfeSlnm4mI-2T1cnyn7xLC8hL_Ye9sSVufVma8FLQOrJ55nCkeRG50jp6lNiY_aCvVEzMPqDmxR6ccncqfA"
            },
            {
                "title": "TEST SUBTITLES",
                "id": "7cafe6",
                "author": "Revision 3",
                "description": "Subtitle Test",
                "license": licenses.CC_BY_NC_SA,
                "files": [
                    {
                        "path": "https://ia600209.us.archive.org/27/items/RiceChef/Rice Chef.mp4",
                    },
                    {
                        "path": "C:/users/jordan/Videos/testfolder/captions.vtt",
                        "language": languages.getlang('en').code,
                    }
                    ,
                    {
                        "path": "C:/users/jordan/Videos/testfolder/captions.vtt",
                        "language": languages.getlang('es').code,
                    }
                ],
            },
            {
                "title": "TEST YOUTUBE",
                "id": "6cafe8",
                "description": "Youtube Test",
                "license": licenses.CC_BY_NC_SA,
                "files": [
                    {
                        "youtube_id": "kpCJyQ2usJ4",
                        "high_resolution": False,
                    }
                ],
            },
            {
                "title": "TEST VIMEO",
                "id": "6cafe9",
                "description": "Vimeo Test",
                "license": licenses.CC_BY_NC_SA,
                "files": [
                    {
                        "web_url": "https://vimeo.com/188609325",
                    }
                ],
            },
        ],
    },
    {
        "title": "Rice 101",
        "id": "abd115",
        "description": "Learn about how rice",
        "children": [
            {
                "title": "Rice Distribution",
                "id": "aaaa4d",
                "files": [
                    {
                        "path" : "https://ia801407.us.archive.org/21/items/ah_Rice/Rice.mp3",
                    },
                ],
                "thumbnail": "https://upload.wikimedia.org/wikipedia/commons/b/ba/Rice_grains_(IRRI)",
                "description": "Get online updates regarding world's leading long grain rice distributors, broken rice distributors, rice suppliers, parboiled rice exporter on our online B2B marketplace TradeBanq.",
                "license": licenses.PUBLIC_DOMAIN,
            },
            {
                "title": "Rice History",
                "id": "6ef99c",
                "description": "Discover the history of rice",
                "children": [
                    {
                        "title": "The History of Japanese Rice",
                        "id": "418799",
                        "author": "Sandra Lopez-Richter",
                        "license": licenses.CC_BY_NC_SA,
                        "files":[
                            {
                                "path" : "https://ia601301.us.archive.org/31/items/The_History_of_Japanese_Rice_Lopez-Richter/The_History_of_Japanese_Rice_Lopez-Richter.pdf",
                            },
                            {
                                "path" : "http://res.freestockphotos.biz/pictures/17/17321-a-bowl-of-rice-with-chopsticks-pv.jpg",
                            },
                        ],
                        "license": licenses.CC_BY,
                    },
                ]
            },
        ]
    },
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
                "mastery_model": exercises.M_OF_N,
                "files": [
                    {
                        "path": "http://www.publicdomainpictures.net/pictures/110000/nahled/bowl-of-rice.jpg",
                        # "language": languages.get("english")
                    }
                ],
                "questions": [
                    {
                        "id": "eeeee",
                        "question": "Which rice is your favorite? ![](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAABGdBTUEAALGPC/xhBQAAAAFzUkdCAK7OHOkAAAAgY0hSTQAAeiYAAICEAAD6AAAAgOgAAHUwAADqYAAAOpgAABdwnLpRPAAAAmFQTFRF////wN/2I0FiNFFuAAAAxdvsN1RxV3KMnrPFFi9PAB1CVG+KXHaQI0NjttLrEjVchIF4AyNGZXB5V087UUw/EzBMpqWeb2thbmpgpqOceXVsERgfTWeADg8QCAEApKGZBAYIop+XCQkIhZ+2T2mEg5mtnK/AobPDkKO2YXqTAAAAJkBetMraZH2VprjIz9zm4enw7/T47fP3wc7ae5GnAAAAN1BsSmSApLfI1ODq2OHp5Orv8PL09vb38fb5wM/bbISbrL/PfZSpxNPgzdnj2+Pr5evw6+/z6e3w3ePp2OPsma2/ABM5Q197ABk4jKG1yNfjytfh1uDo3eXs4unv1t/nztrjqbzMTmmEXneRES1Ji6CzxtXixdPfztrk1N/n1+Dp1d/oz9vlxdPeq73NVG+KYnyUAAAddIuhwtPhvMzaxtTgytfiy9jjwtHewtHenbDCHT1fS2eCRV52qr7PvM3cucrYv87cv8/cvMzavc3bucvacoyl////ByE8WnKKscXWv9Hguszbu8zbvc7dtcnaiJqrcHZ4f4SHEh0nEitFTWZ+hJqumrDDm7HDj6W5dI2lYGJfmZeQl5SNAAAADRciAAATHjdSOVNsPlhyLklmKCYjW1lUlpOLlZKLFSAqWXSOBQAADA0NAAAAHh0bWlhSk5CIk5CIBAYJDRQbERcdDBAUBgkMAAAEDg4NAAAAHBsZWFZQkY6GAAAAAAAABQUEHBsZAAAAGxoYVlROko+GBAQDZ2RdAAAAGhkYcW9oAgICAAAAExMSDQwLjouDjYuDioiAiIV9hoN7VlRO////Z2DcYwAAAMR0Uk5TAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACRKrJyrZlBQECaNXCsKaqypMGAUDcu7Gpn5mf03gDo8+4saiipKq3xRMBH83Eu7OsqbG61DkDMdbFvrizsbK3wNs9Ax/VysS/vLq/zNwfArDhxMfExMXE3pMCMe7byMjIzd33ZgYGQtnz6+zooeJXBQMFD1yHejZ1+l8FBgEELlOR+GgFCQ0SGxoBGFKg+m0BBwEMR6v+hAEDM6nRASWURVuYQQ4AAAABYktHRACIBR1IAAAACXBIWXMAAAjLAAAIywGEuOmJAAABCklEQVQY02NgUGZUUVVT19DUYtBmYmZhYdBh1dXTNzA0MjYxZTFjAwqwm1tYWlnb2NrZO3A4cgIFGJycXVzd3D08vbx9uHyBAn7+AYFBwSEhoWHhEdyRQIGo6JjYuPiExKTklFSeNKBAekZmVnZObk5efkEhbxFQgK+4pLSsvKKyqrqGoZZfgIVBsK6+obGpuaW1rV2oQ1hEgKFTtKu7p7evf8LEI5PEJotLMEyZyjJt+oyZsxhmzzk6V3KeFIO01vwFMrJyCxctXrL02DL55QwsClorVq5avWbtuvUbNh7fpMjAwsKyWWvLFJatStu279h5YhdIAAJ2s+zZu+/kfoQAy4HNLAcPHQYA5YtSi+k2/WkAAAAldEVYdGRhdGU6Y3JlYXRlADIwMTMtMTAtMDRUMTk6Mzk6MjEtMDQ6MDAwU1uYAAAAJXRFWHRkYXRlOm1vZGlmeQAyMDEzLTEwLTA0VDE5OjM5OjIxLTA0OjAwQQ7jJAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAAAASUVORK5CYII=)",
                        "type":exercises.MULTIPLE_SELECTION,
                        "correct_answers": ["White rice", "Brown rice", "Sushi rice"],
                        "all_answers": ["White rice", "Quinoa","Brown rice"],
                    },
                    {
                        "id": "bbbbb",
                        "question": "Which rice is the crunchiest?",
                        "type":exercises.SINGLE_SELECTION,
                        "correct_answer": "Rice Krispies \n![](https://upload.wikimedia.org/wikipedia/commons/c/cd/RKTsquares.jpg)",
                        "all_answers": [
                            "White rice \n![](web+graphie:file:///C:/users/jordan/contentcuration-dump/0a0c0f1a1a40226d8d227a07dd143f8c08a4b8a5)![](web+graphie:file:///C:/users/jordan/contentcuration-dump/0a0c0f1a1a40226d8d227a07dd143f8c08a4b8a5 - Copy)![](web+graphie:file:///C:/users/jordan/contentcuration-dump/0a0c0f1a1a40226d8d227a07dd143f8c08a4b8a5)",
                            "Brown rice \n![](https://c2.staticflickr.com/4/3159/2889140143_b99fd8dd4c_z.jpg?zz=1)",
                            "Rice Krispies \n![](https://upload.wikimedia.org/wikipedia/commons/c/cd/RKTsquares.jpg)"
                        ],
                        "hints": "It's delicious",
                    },
                    {
                        "id": "ccccc",
                        "question": "Why a rice cooker? ![bb8](https://media.giphy.com/media/9fbYYzdf6BbQA/giphy.gif)",
                        "type":exercises.FREE_RESPONSE,
                        "answers": [],
                        "images": None,
                    },
                    {
                        "id": "aaaaa",
                        "question": "How many minutes does it take to cook rice? ![](https://upload.wikimedia.org/wikipedia/commons/5/5e/Jeera-rice.JPG)",
                        "type":exercises.INPUT_QUESTION,
                        "answers": ["20", "25", "15"],
                        "hints": ["Takes roughly same amount of time to install kolibri on Windows machine", "Does this help?\n![](http://www.aroma-housewares.com/images/rice101/delay_timer_1.jpg)"],
                    },
                    {
                        "id": "ddddd",
                        "type":exercises.PERSEUS_QUESTION,
                        "item_data":SAMPLE_PERSEUS,
                    },
                ],
            },
            {
                "title": "Rice Exercise 2",
                "id": "6cafe4",
                "description": "Test how well you know your rice",
                "license": licenses.CC_BY_NC_SA,
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
                        "path": "C:/users/jordan/Videos/testfolder/htmltest.zip",
                    }
                ]
            },
            {
                "title": "Rice Exercise 3",
                "id": "6cafe5",
                "description": "Test how well you know your rice",
                "license": licenses.CC_BY_NC_SA,
                "mastery_model": exercises.M_OF_N,
                "files": [
                    {
                        "path": "https://upload.wikimedia.org/wikipedia/commons/b/b7/Rice_p1160004.jpg",
                    }
                ],
                "questions": [
                    {
                        "id": "ccccc",
                        "question": "<p><img align=\"middle\" alt=\"C o n s i d e r space t h e space f o l l o w i n g space f i g u r e space o f space l i n e space top enclose M N end enclose. space S a y space w h e t h e r space f o l l o w i n g space\r\ns t a t e m e n t s space a r e space t r u e space o r space f a l s e space i n space c o n t e x t space o f space t h e space g i v e n space f i g u r e.\r\n\" class=\"Wirisformula\" data-mathml=\"«math xmlns=¨http://www.w3.org/1998/Math/MathML¨»«mi»C«/mi»«mi»o«/mi»«mi»n«/mi»«mi»s«/mi»«mi»i«/mi»«mi»d«/mi»«mi»e«/mi»«mi»r«/mi»«mo»§#160;«/mo»«mi»t«/mi»«mi»h«/mi»«mi»e«/mi»«mo»§#160;«/mo»«mi»f«/mi»«mi»o«/mi»«mi»l«/mi»«mi»l«/mi»«mi»o«/mi»«mi»w«/mi»«mi»i«/mi»«mi»n«/mi»«mi»g«/mi»«mo»§#160;«/mo»«mi»f«/mi»«mi»i«/mi»«mi»g«/mi»«mi»u«/mi»«mi»r«/mi»«mi»e«/mi»«mo»§#160;«/mo»«mi»o«/mi»«mi»f«/mi»«mo»§#160;«/mo»«mi»l«/mi»«mi»i«/mi»«mi»n«/mi»«mi»e«/mi»«mo»§#160;«/mo»«menclose notation=¨top¨»«mi»M«/mi»«mi»N«/mi»«/menclose»«mo».«/mo»«mo»§#160;«/mo»«mi»S«/mi»«mi»a«/mi»«mi»y«/mi»«mo»§#160;«/mo»«mi»w«/mi»«mi»h«/mi»«mi»e«/mi»«mi»t«/mi»«mi»h«/mi»«mi»e«/mi»«mi»r«/mi»«mo»§#160;«/mo»«mi»f«/mi»«mi»o«/mi»«mi»l«/mi»«mi»l«/mi»«mi»o«/mi»«mi»w«/mi»«mi»i«/mi»«mi»n«/mi»«mi»g«/mi»«mo»§#160;«/mo»«mspace linebreak=¨newline¨/»«mi»s«/mi»«mi»t«/mi»«mi»a«/mi»«mi»t«/mi»«mi»e«/mi»«mi»m«/mi»«mi»e«/mi»«mi»n«/mi»«mi»t«/mi»«mi»s«/mi»«mo»§#160;«/mo»«mi»a«/mi»«mi»r«/mi»«mi»e«/mi»«mo»§#160;«/mo»«mi»t«/mi»«mi»r«/mi»«mi»u«/mi»«mi»e«/mi»«mo»§#160;«/mo»«mi»o«/mi»«mi»r«/mi»«mo»§#160;«/mo»«mi»f«/mi»«mi»a«/mi»«mi»l«/mi»«mi»s«/mi»«mi»e«/mi»«mo»§#160;«/mo»«mi»i«/mi»«mi»n«/mi»«mo»§#160;«/mo»«mi»c«/mi»«mi»o«/mi»«mi»n«/mi»«mi»t«/mi»«mi»e«/mi»«mi»x«/mi»«mi»t«/mi»«mo»§#160;«/mo»«mi»o«/mi»«mi»f«/mi»«mo»§#160;«/mo»«mi»t«/mi»«mi»h«/mi»«mi»e«/mi»«mo»§#160;«/mo»«mi»g«/mi»«mi»i«/mi»«mi»v«/mi»«mi»e«/mi»«mi»n«/mi»«mo»§#160;«/mo»«mi»f«/mi»«mi»i«/mi»«mi»g«/mi»«mi»u«/mi»«mi»r«/mi»«mi»e«/mi»«mo».«/mo»«mspace linebreak=¨newline¨/»«/math»\" src=\"http://www.magogenie.com/assets/tinymce/jscripts/tiny_mce/plugins/tiny_mce_wiris/integration/showimage.php?formula=5ae94c3870f7867b485830ce79504b42.png\"><img src=\"data:image/jpeg;base64,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\"></p><p><img src=\"http://www.magogenie.com/assets/tinymce/jscripts/tiny_mce/plugins/tiny_mce_wiris/integration/showimage.php?formula=f56752af6b14e80159ccc7de1100cb5b.png\" data-mathml=\"«math xmlns=¨http://www.w3.org/1998/Math/MathML¨»«mi»M«/mi»«mo»§#160;«/mo»«mi»i«/mi»«mi»s«/mi»«mo»§#160;«/mo»«mi»p«/mi»«mi»o«/mi»«mi»i«/mi»«mi»n«/mi»«mi»t«/mi»«mo»§#160;«/mo»«mi»o«/mi»«mi»n«/mi»«mo»§#160;«/mo»«mi»r«/mi»«mi»a«/mi»«mi»y«/mi»«mo»§#160;«/mo»«menclose notation=¨top¨»«mi»O«/mi»«mi»P«/mi»«/menclose»«/math»\" class=\"Wirisformula\" alt=\"M space i s space p o i n t space o n space r a y space top enclose O P end enclose\" align=\"middle\"><br></p>",
                        "type":exercises.SINGLE_SELECTION,
                        "all_answers": ["Yes", "No", "Rice!"],
                        "correct_answer": "Rice!",
                    },
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

def construct_channel(**kwargs):

    channel = nodes.ChannelNode(
        source_domain="learningequality.org",
        source_id="testing-ricecooker-channel",
        title="Testing Ricecooker Channel",
        thumbnail="https://upload.wikimedia.org/wikipedia/commons/thumb/5/50/Banaue_Philippines_Banaue-Rice-Terraces-01.jpg/640px-Banaue_Philippines_Banaue-Rice-Terraces-01.jpg",
    )

    _build_tree(channel, SAMPLE_TREE)
    raise_for_invalid_channel(channel)

    return channel


def _build_tree(node, sourcetree):

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
                license=child_source_node.get("license"),
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
            )
            add_files(child_node, child_source_node.get("files") or [])
            node.add_child(child_node)

        elif kind == content_kinds.EXERCISE:
            child_node = nodes.ExerciseNode(
                source_id=child_source_node["id"],
                title=child_source_node["title"],
                license=child_source_node.get("license"),
                author=child_source_node.get("author"),
                description=child_source_node.get("description"),
                exercise_data={}, # Just set to default
                thumbnail=child_source_node.get("thumbnail"),
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
            )
            add_files(child_node, child_source_node.get("files") or [])
            node.add_child(child_node)

        else:                   # unknown content file format
            continue

    return node

def add_files(node, file_list):
    for f in file_list:
        file_type = guess_file_type(node.kind, filepath=f.get('path'), youtube_id=f.get('youtube_id'), web_url=f.get('web_url'), encoding=f.get('encoding'))

        if file_type == FileTypes.AUDIO_FILE:
            node.add_file(files.AudioFile(path=f['path'], language=f.get('language')))
        elif file_type == FileTypes.THUMBNAIL:
            node.add_file(files.ThumbnailFile(path=f['path']))
        elif file_type == FileTypes.DOCUMENT_FILE:
            node.add_file(files.DocumentFile(path=f['path'], language=f.get('language')))
        elif file_type == FileTypes.HTML_ZIP_FILE:
            node.add_file(files.HTMLZipFile(path=f['path'], language=f.get('language')))
        elif file_type == FileTypes.VIDEO_FILE:
            node.add_file(files.VideoFile(path=f['path'], language=f.get('language'), ffmpeg_settings=f.get('ffmpeg_settings')))
        elif file_type == FileTypes.SUBTITLE_FILE:
            node.add_file(files.SubtitleFile(path=f['path'], language=f['language']))
        elif file_type == FileTypes.BASE64_FILE:
            node.add_file(files.Base64ImageFile(encoding=f['encoding']))
        elif file_type == FileTypes.WEB_VIDEO_FILE:
            node.add_file(files.WebVideoFile(web_url=f['web_url'], high_resolution=f.get('high_resolution')))
        elif file_type == FileTypes.YOUTUBE_VIDEO_FILE:
            node.add_file(files.YouTubeVideoFile(youtube_id=f['youtube_id'], high_resolution=f.get('high_resolution')))
        else:
            raise UnknownFileTypeError("Unrecognized file type '{0}'".format(f['path']))

def create_question(raw_question):

    if raw_question["type"] == exercises.MULTIPLE_SELECTION:
        return questions.MultipleSelectQuestion(
            id=raw_question["id"],
            question=raw_question["question"],
            correct_answers=raw_question["correct_answers"],
            all_answers=raw_question["all_answers"],
            hints=raw_question.get("hints"),
        )
    if raw_question["type"] == exercises.SINGLE_SELECTION:
        return questions.SingleSelectQuestion(
            id=raw_question["id"],
            question=raw_question["question"],
            correct_answer=raw_question["correct_answer"],
            all_answers=raw_question["all_answers"],
            hints=raw_question.get("hints"),
        )
    if raw_question["type"] == exercises.INPUT_QUESTION:
        return questions.InputQuestion(
            id=raw_question["id"],
            question=raw_question["question"],
            answers=raw_question["answers"],
            hints=raw_question.get("hints"),
        )
    if raw_question["type"] == exercises.FREE_RESPONSE:
        return questions.FreeResponseQuestion(
            id=raw_question["id"],
            question=raw_question["question"],
            hints=raw_question.get("hints"),
        )
    if raw_question["type"] == exercises.PERSEUS_QUESTION:
        return questions.PerseusQuestion(
            id=raw_question["id"],
            raw_data=raw_question["item_data"],
            source_url="https://www.google.com/",
        )
    else:
        raise UnknownQuestionTypeError("Unrecognized question type '{0}': accepted types are {1}".format(raw_question["type"], [key for key, value in exercises.question_choices]))
