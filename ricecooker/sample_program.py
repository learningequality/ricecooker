from ricecooker.classes.nodes import Channel, Video, Audio, Document, Topic, Exercise, guess_content_kind
from ricecooker.classes.questions import PerseusQuestion, MultipleSelectQuestion, SingleSelectQuestion, FreeResponseQuestion, InputQuestion
from ricecooker.exceptions import UnknownContentKindError, UnknownQuestionTypeError, raise_for_invalid_channel
from le_utils.constants import content_kinds,file_formats, format_presets, licenses, exercises

SAMPLE_PERSEUS = '{"answerArea":{"chi2Table":false,"periodicTable":false,"tTable":false,"zTable":false,"calculator":false},' + \
'"hints":[{"widgets":{},"images":{"web+graphie:storage/a330b1eb4dad1cedebaa7b2e61f026c2": {}},"content":"Hint #1","replace":false},{"widgets":{},"images":{},"content":"Hint #2","replace":false}],' +\
'"question":{"widgets":{"radio 1":{"type":"radio","alignment":"default","graded":true,"static":false,' +\
'"options":{"deselectEnabled":false,"multipleSelect":false,"choices":[{"correct":true,"content":"Yes"},{"correct":false,"content":"No"}],' +\
'"displayCount":null,"hasNoneOfTheAbove":false,"randomize":false,"onePerLine":true},"version":{"minor":0,"major":1}}},"images":{"web+graphie:storage/a330b1eb4dad1cedebaa7b2e61f026c2": {}},' +\
'"content":"Do you like rice?\\n\\n![](web+graphie:storage/a330b1eb4dad1cedebaa7b2e61f026c2)\\n\\n[[\\u2603 radio 1]]"},"itemDataVersion":{"minor":1,"major":0}}'

SAMPLE_TREE = [
    {
        "title": "Rice 101",
        "id": "abd115",
        "description": "Learn about how rice",
        "children": [
            {
                "title": "Rice Distribution",
                "id": "aaaa4d",
                "file": "https://ia801407.us.archive.org/21/items/ah_Rice/Rice.mp3",
                "description": "Get online updates regarding world's leading long grain rice distributors, broken rice distributors, rice suppliers, parboiled rice exporter on our online B2B marketplace TradeBanq.",
                "license": licenses.PUBLIC_DOMAIN,
            },
            {

                "title": "Rice History",
                "id": "6ef99c",
                "description": "Discover the history of rice",
                "children": [
                    {
                        "title": "Rice Farming",
                        "id": "418799",
                        "author": "Public Media, inc",
                        "file": "https://ia802601.us.archive.org/11/items/ricefarmersinthailand/ricefarmersinthailand.mp4",
                        "license": licenses.CC_BY,
                        "thumbnail" : "http://res.freestockphotos.biz/pictures/17/17321-a-bowl-of-rice-with-chopsticks-pv.jpg",
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
                "thumbnail":"https://pixabay.com/static/uploads/photo/2015/05/29/21/35/sushi-789820_960_720.jpg",
            },
            {
                "title": "Rice Exercise",
                "id": "6cafe1",
                "description": "Test how well you know your rice",
                "license": licenses.CC_BY_NC_SA,
                "mastery_model": exercises.M_OF_N,
                "thumbnail":"http://www.publicdomainpictures.net/pictures/110000/nahled/bowl-of-rice.jpg",
                "questions": [
                    {
                        "id": "eeeee",
                        "question": "Which rice is your favorite? ![](http://discovermagazine.com/~/media/Images/Issues/2014/JanFeb/golden-rice.jpg)",
                        "type":exercises.MULTIPLE_SELECTION,
                        "correct_answers": ["White rice", "Brown rice", "Sushi rice"],
                        "all_answers": ["White rice", "Quinoa","Brown rice"],
                    },
                    {
                        "id": "bbbbb",
                        "question": "Which rice is the crunchiest?",
                        "type":exercises.SINGLE_SELECTION,
                        "correct_answer": "Rice Krispies",
                        "all_answers": ["White rice", "Brown rice", "Rice Krispies"],
                        "hints": "Has rice in it",
                    },
                    {
                        "id": "ccccc",
                        "question": "Why a rice cooker?",
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
                    {
                        "id": "11111",
                        "question": "<h3 id='rainbow'><b>RICE COOKING!!!</b></h3><script type='text/javascript'><!-- setInterval(function() {$('#rainbow').css('color', '#'+((1<<24)*Math.random()|0).toString(16));}, 300); --></script>",
                        "type":exercises.FREE_RESPONSE,
                        # "hints": ["You've been hit <script type='text/javascript'><!-- alert(\"IT'S A TRAP!\"); --></script>"],
                    },
                ],
            },
            {
                "title": "Rice Exercise 2",
                "id": "6cafe1",
                "description": "Test how well you know your rice",
                "license": licenses.CC_BY_NC_SA,
                "mastery_model": exercises.M_OF_N,
                "thumbnail":"http://www.publicdomainpictures.net/pictures/110000/nahled/bowl-of-rice.jpg",
                "questions": [
                    {
                        "id": "ccccc",
                        "question": "What makes rice so good?",
                        "type":exercises.FREE_RESPONSE,
                        "answers": [],
                        "images": None,
                    },
                ],
            },
        ]
    },
]

def construct_channel(**kwargs):

    channel = Channel(
        domain="learningequality.org",
        channel_id="sample-rice-channel",
        title="Sample Ricecooker Channel",
        thumbnail="https://upload.wikimedia.org/wikipedia/commons/4/48/Electronic_rice_cooker_with_scoop.jpg",
    )
    _build_tree(channel, SAMPLE_TREE)
    raise_for_invalid_channel(channel)

    return channel


def _build_tree(node, sourcetree):

    for child_source_node in sourcetree:
        try:
            kind = guess_content_kind(child_source_node.get("file"), child_source_node.get("questions"))
        except UnknownContentKindError:
            continue

        if kind == content_kinds.TOPIC:
            child_node = Topic(
                id=child_source_node["id"],
                title=child_source_node["title"],
                author=child_source_node.get("author"),
                description=child_source_node.get("description"),
            )
            node.add_child(child_node)

            source_tree_children = child_source_node.get("children", [])

            _build_tree(child_node, source_tree_children)

        elif kind == content_kinds.VIDEO:

            child_node = Video(
                id=child_source_node["id"],
                title=child_source_node["title"],
                author=child_source_node.get("author"),
                description=child_source_node.get("description"),
                files=child_source_node.get("file"),
                license=child_source_node.get("license"),

                # video-specific data
                preset=format_presets.VIDEO_HIGH_RES,
                transcode_to_lower_resolutions=True,
                derive_thumbnail=False,

                # audio and video shared data
                subtitle=child_source_node.get("subtitle"),
                thumbnail=child_source_node.get("thumbnail"),
            )
            node.add_child(child_node)

        elif kind == content_kinds.AUDIO:
            child_node = Audio(
                id=child_source_node["id"],
                title=child_source_node["title"],
                author=child_source_node.get("author"),
                description=child_source_node.get("description"),
                files=child_source_node.get("file"),
                license=child_source_node.get("license"),

                # audio and video shared data
                subtitle=child_source_node.get("subtitle"),
                thumbnail=child_source_node.get("thumbnail"),
            )
            node.add_child(child_node)

        elif kind == content_kinds.DOCUMENT:
            child_node = Document(
                id=child_source_node["id"],
                title=child_source_node["title"],
                author=child_source_node.get("author"),
                description=child_source_node.get("description"),
                files=child_source_node.get("file"),
                license=child_source_node.get("license"),
                thumbnail=child_source_node.get("thumbnail"),
            )
            node.add_child(child_node)

        elif kind == content_kinds.EXERCISE:
            child_node = Exercise(
                id=child_source_node["id"],
                title=child_source_node["title"],
                author=child_source_node.get("author"),
                description=child_source_node.get("description"),
                files=child_source_node.get("file"),
                exercise_data={'mastery_model': child_source_node.get("mastery_model"), 'randomize': True, 'm': 3, 'n': 5},
                license=child_source_node.get("license"),
                thumbnail=child_source_node.get("thumbnail"),
            )
            for q in child_source_node.get("questions"):
                question = create_question(q)
                child_node.add_question(question)
            node.add_child(child_node)

        else:                   # unknown content file format
            continue

    return node

def create_question(raw_question):

    if raw_question["type"] == exercises.MULTIPLE_SELECTION:
        return MultipleSelectQuestion(
            id=raw_question["id"],
            question=raw_question["question"],
            correct_answers=raw_question["correct_answers"],
            all_answers=raw_question["all_answers"],
            hints=raw_question.get("hints"),
        )
    if raw_question["type"] == exercises.SINGLE_SELECTION:
        return SingleSelectQuestion(
            id=raw_question["id"],
            question=raw_question["question"],
            correct_answer=raw_question["correct_answer"],
            all_answers=raw_question["all_answers"],
            hints=raw_question.get("hints"),
        )
    if raw_question["type"] == exercises.INPUT_QUESTION:
        return InputQuestion(
            id=raw_question["id"],
            question=raw_question["question"],
            answers=raw_question["answers"],
            hints=raw_question.get("hints"),
        )
    if raw_question["type"] == exercises.FREE_RESPONSE:
        return FreeResponseQuestion(
            id=raw_question["id"],
            question=raw_question["question"],
            hints=raw_question.get("hints"),
        )
    if raw_question["type"] == exercises.PERSEUS_QUESTION:
        return PerseusQuestion(
            id=raw_question["id"],
            raw_data=raw_question["item_data"],
        )
    else:
        raise UnknownQuestionTypeError("Unrecognized question type '{0}': accepted types are {1}".format(raw_question["type"], [key for key, value in exercises.question_choices]))