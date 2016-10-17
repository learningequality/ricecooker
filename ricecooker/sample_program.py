from ricecooker.classes.nodes import Channel, Video, Audio, Document, Topic, Exercise, guess_content_kind
from ricecooker.classes.questions import PerseusQuestion, MultipleSelectQuestion, SingleSelectQuestion, FreeResponseQuestion, InputQuestion
from ricecooker.exceptions import UnknownContentKindError, UnknownQuestionTypeError, raise_for_invalid_channel
from le_utils.constants import content_kinds,file_formats, format_presets, licenses, exercises

SAMPLE_PERSEUS = '{"answerArea":{"chi2Table":false,"periodicTable":false,"tTable":false,"zTable":false,"calculator":false},' + \
'"hints":[{"widgets":{},"images":{},"content":"Hint #1","replace":false},{"widgets":{},"images":{},"content":"Hint #2","replace":false}],' +\
'"question":{"widgets":{"radio 1":{"type":"radio","alignment":"default","graded":true,"static":false,' +\
'"options":{"deselectEnabled":false,"multipleSelect":false,"choices":[{"correct":true,"content":"Yes"},{"correct":false,"content":"No"}],' +\
'"displayCount":null,"hasNoneOfTheAbove":false,"randomize":false,"onePerLine":true},"version":{"minor":0,"major":1}}},"images":{},' +\
'"content":"Do you like rice?\\n\\n![](web+graphie:file:///C:/Users/Jordan/contentcuration-dump/test)\\n\\n[[\\u2603 radio 1]]"},"itemDataVersion":{"minor":1,"major":0}}'

SAMPLE_TREE = [
    {
        "title": "Western Philosophy",
        "id": "abd115",
        "description": "Philosophy materials for the budding mind.",
        "children": [
            {
                "title": "Nicomachean Ethics",
                "id": "ffda92",
                "author": "Aristotle",
                "description": "The Nicomachean Ethics is the name normally given to ...",
                "file": ["https://archive.org/download/petersethics00arisrich/petersethics00arisrich.pdf"],
                "license": licenses.PUBLIC_DOMAIN,
            },
            {

                "title": "The Critique of Pure Reason",
                "id": "6ef99c",
                "description": "Kant saw the Critique of Pure Reason as an attempt to bridge the gap...",
                "children": [
                    {
                        "title": "01 - The Critique of Pure Reason",
                        "id": "8326cc",
                        "related_to": ["aaaa4d"],
                        "file": "https://archive.org/download/critique_pure_reason_0709_librivox/critique_of_pure_reason_01_kant.mp3",
                        # "subtitle": "https://archive.org/download/critique_pure_reason_0709_librivox/critique_of_pure_reason_01_kant.vtt",
                        "author": "Immanuel Kant",
                        "license": licenses.PUBLIC_DOMAIN,
                    },
                    {
                        "title": "02 - Preface to the Second Edition",
                        "id": "aaaa4d",
                        "author": "Immanuel Kant",
                        "file": "https://ia801406.us.archive.org/13/items/alice_in_wonderland_librivox/wonderland_ch_01.mp3",
                        "author": "Immanuel Kant",
                        "license": licenses.PUBLIC_DOMAIN,
                    }
                ]
            },
        ]
    },
    {
        "title": "Recipes",
        "id": "d98752",
        "description": "Recipes for various dishes.",
        "children": [
            {
                "title": "Smoked Brisket Recipe",
                "id": "418799",
                "author": "Bradley Smoker",
                "file": "https://archive.org/download/SmokedBrisketRecipe/smokedbrisketrecipebybradleysmoker.mp4",
                "subtitle": "something.vtt",
                "license": licenses.CC_BY,
                "thumbnail" : "https://www.kingsford.com/wp-content/uploads/2014/12/kfd-howtosmokebrisket-Brisket5_0267-1024x621.jpg",
            },
            {
                "title": "Food Mob Bites 10: Garlic Bread",
                "id": "6cafe2",
                "author": "Revision 3",
                "description": "Basic garlic bread recipe.",
                "file": "file:///C:/Users/Jordan/Documents/Documents/College/199 RESEARCH/Winter 2015/Fostering Improved Learning in Math.pdf",
                "license": licenses.CC_BY_NC_SA,
                "thumbnail":"https://cdn.kastatic.org/googleusercontent/4hbrDZGnw8OZKYo17pK-cA00doPXlaO_P_Gj8XGBZ5wYZZ6krD-4STwQ1b0nwY6jpLKB5dDBJEt2brKXdNW0dT0I",
            },
            {
                "title": "Recipe Exercise",
                "id": "6cafe1",
                "description": "Test how well you know your recipes",
                "license": licenses.CC_BY_NC_SA,
                "mastery_model": exercises.M_OF_N,
                "thumbnail":"https://cdn.kastatic.org/googleusercontent/4hbrDZGnw8OZKYo17pK-cA00doPXlaO_P_Gj8XGBZ5wYZZ6krD-4STwQ1b0nwY6jpLKB5dDBJEt2brKXdNW0dT0I",
                "questions": [
                    {
                        "id": "eeeee",
                        "question": "Which rice is your favorite? ![](file:///C:/Users/Jordan/Pictures/11881000_10207589179957262_1956307727_n.jpg)\n![](http://discovermagazine.com/~/media/Images/Issues/2014/JanFeb/golden-rice.jpg)",
                        "type":exercises.MULTIPLE_SELECTION,
                        "correct_answers": ["White rice ![](http://i2.cdn.turner.com/cnnnext/dam/assets/150327114100-06-rice-stock-super-169.jpg)", "Brown rice", "Sushi rice"],
                        "all_answers": ["White rice ![](http://i2.cdn.turner.com/cnnnext/dam/assets/150327114100-06-rice-stock-super-169.jpg)", "Quinoa","Brown rice"],
                    },
                    {
                        "id": "bbbbb",
                        "question": "Which rice is the crunchiest?![](http://www.riceoutlook.com/wp-content/uploads/2016/07/Taiwan-rice.jpg)",
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
                ],
            },
        ]
    },
]

def construct_channel(args):

    channel = Channel(
        domain="learningequality.org",
        channel_id="sample-channel",
        title="Sample channel",
        thumbnail="https://s.graphiq.com/sites/default/files/stories/t4/15_Tiniest_Dog_Breeds_1718_3083.jpg",
    )
    _build_tree(channel, SAMPLE_TREE)
    raise_for_invalid_channel(channel)

    # import pickle
    # with open('./ricecooker/KA_tree.pickle', 'rb') as handler:
    #     channel = pickle.loads(handler.read())
    #     channel.children = channel.children[0].children
    #     channel.children = channel.children[0].children
    #     print(channel.size())

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