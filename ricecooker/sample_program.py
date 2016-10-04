from ricecooker.classes import Channel, Video, Audio, Document, Topic, guess_content_kind
from ricecooker.exceptions import UnknownContentKindError, UnknownQuestionTypeError, raise_for_invalid_channel
from le_utils.constants import content_kinds,file_formats, format_presets, licenses, exercises

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
                # "file": ["https://archive.org/download/petersethics00arisrich/petersethics00arisrich.pdf"],
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
                        # "file": "https://ia801406.us.archive.org/13/items/alice_in_wonderland_librivox/wonderland_ch_01.mp3",
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
                # "file": "https://archive.org/download/SmokedBrisketRecipe/smokedbrisketrecipebybradleysmoker.mp4",
                "subtitle": "something.vtt",
                "license": licenses.CC_BY,
            },
            {
                "title": "Food Mob Bites 10: Garlic Bread",
                "id": "6cafe2",
                "author": "Revision 3",
                "description": "Basic garlic bread recipe.",
                # "file": "https://archive.org/download/Food_Mob_Bites_10/foodmob--bites--0010--garlicbread--hd720p30.h264.mp4",
                "license": licenses.CC_BY_NC_SA,
            },
            {
                "title": "Recipe Exercise",
                "id": "6cafe1",
                "description": "Test how well you know your recipes",
                "license": licenses.CC_BY_NC_SA,
                "mastery_model": exercises.SKILL_CHECK,
                "questions": [
                    {
                        "id": "eeeee",
                        "question": "Which rice is your favorite?",
                        "type":exercises.MULTIPLE_SELECTION,
                        "correct_answers": ["White rice", "Brown rice", "Sushi rice"],
                        "all_answers": ["White rice", "Quinoa","Brown rice"],
                        "hint": "",
                        "images": ["file://blah/somewhere.jpg"],
                    },
                    {
                        "id": "bbbbb",
                        "question": "Which rice is the crunchiest?",
                        "type":exercises.SINGLE_SELECTION,
                        "correct_answer": "Rice Krispies",
                        "all_answers": ["White rice", "Brown rice", "Rice Krispies"],
                        "hint": "Has rice in it",
                        "images": [],
                    },
                    {
                        "id": "ccccc",
                        "question": "Why a rice cooker?",
                        "type":exercises.FREE_RESPONSE,
                        "answers": [],
                        "hint": "",
                        "images": [],
                    },
                    {
                        "id": "aaaaa",
                        "question": "How many minutes does it take to cook rice?",
                        "type":exercises.INPUT_QUESTION,
                        "answers": [20, "20.5", 19.5],
                        "hint": "Takes roughly same amount of time to install kolibri on Windows machine",
                        "images": [],
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
                derive_thumbnail=True,

                # audio and video shared data
                subtitle=child_source_node.get("subtitle"),
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
            )
            node.add_child(child_node)

        elif kind == content_kinds.EXERCISE:
            child_node = Exercise(
                id=child_source_node["id"],
                title=child_source_node["title"],
                author=child_source_node.get("author"),
                description=child_source_node.get("description"),
                files=child_source_node.get("file"),
                exercise_data={'mastery_model': child_source_node.get("mastery_model"), 'randomize': True},
                license=child_source_node.get("license"),
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
            hint=raw_question["hint"],
            images=raw_question["images"],
        )
    if raw_question["type"] == exercises.SINGLE_SELECTION:
        return SingleSelectQuestion(
            id=raw_question["id"],
            question=raw_question["question"],
            correct_answer=raw_question["correct_answer"],
            all_answers=raw_question["all_answers"],
            hint=raw_question["hint"],
            images=raw_question["images"],
        )
    if raw_question["type"] == exercises.INPUT_QUESTION:
        return InputQuestion(
            id=raw_question["id"],
            question=raw_question["question"],
            answers=raw_question["answers"],
            hint=raw_question["hint"],
            images=raw_question["images"],
        )
    if raw_question["type"] == exercises.FREE_RESPONSE:
        return FreeResponseQuestion(
            id=raw_question["id"],
            question=raw_question["question"],
            hint=raw_question["hint"],
            images=raw_question["images"],
        )
    else:
        raise UnknownQuestionTypeError("Unrecognized question type '{0}': accepted types are {1}".format(raw_question["type"], [key for key, value in exercises.question_choices]))