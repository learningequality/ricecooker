from fle_utils import constants
from ricecooker.commands import createchannel
from ricecooker.exceptions import InvalidUsageException, InvalidCommandException
import sys

commands = ["createchannel"]

if len(sys.argv) < 3 :
    raise InvalidUsageException("Invalid format: python -m ricecooker createchannel <channel name> <description> <thumbnail.jpg> [--private]")

if sys.argv[1] not in commands:
    raise InvalidCommandException("Invalid format: (commands are {0})".format(commands))

channel_metadata= {
        "domain" : "learningequality.org",
        "channel_id" : "sample-channel",
        "title" : sys.argv[2],
        "description": sys.argv[3] if len(sys.argv) >= 4 else None,
        "thumbnail": sys.argv[4] if len(sys.argv) >= 5 else None,
    }

content_metadata = [
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
                "license": constants.L_PD,
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
                        "subtitle": "https://archive.org/download/critique_pure_reason_0709_librivox/critique_of_pure_reason_01_kant.vtt",
                        "author": "Immanuel Kant",
                        "license": constants.L_PD,
                    },
                    {
                        "title": "02 - Preface to the Second Edition",
                        "id": "aaaa4d",
                        "author": "Immanuel Kant",
                        "file": "http://www.wavsource.com/snds_2016-08-21_1204101428963685/movies/aladdin/aladdin_cant_believe.wav",
                        "author": "Immanuel Kant",
                        "license": constants.L_PD,
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
                "license": constants.L_CC_BY,
            },
            {
                "title": "Food Mob Bites 10: Garlic Bread",
                "id": "6cafe2",
                "author": "Revision 3",
                "description": "Basic garlic bread recipe.",
                "file": "https://archive.org/download/Food_Mob_Bites_10/foodmob--bites--0010--garlicbread--hd720p30.h264.mp4",
                "license": constants.L_CC_BY_NC_SA,
            },
        ]
    },
]

if sys.argv[1] == "createchannel":
    createchannel(channel_metadata, content_metadata)
