Supported content types
=======================

Audio
-----
The `AudioNode` and `AudioFile` are used to store mp3 files.


Videos
------
The `VideoNode` and `VideoFile` are used to store videos.


Documents
---------
The `DocumentNode` and `DocumentFile` are used to store PDF documents.


HTML5Apps
---------
The most versatile and extensible option for importing content into Kolibri is to
package the content as HTML5App nodes. The HTML5 content type on Kolibri, consists
of a zip file with web content inside it. The Kolibri application serves the file
`index.html` from the root of the zip folder inside an iframe. It is possible to
package any web content in this manner: text, images, CSS, fonts, and JavaScript code.
The `iframe` rendering the content in Kolibri is sandbox so no plugins are allowed (no swf/flash).
In addition, it is expected that oh web resources are stored within the zip file,
and referenced using relative paths. This is what enables Kolibri to used in offline settings.  


Here are some samples:

  - [Sample Vue.js App](https://github.com/learningequality/sample-channels/tree/master/contentnodes/html5_vuejs):
    Proof of concept of minimal webapp based on the vue.js framework.
    Note the [shell script](https://github.com/learningequality/sample-channels/blob/master/contentnodes/html5_vuejs/update.sh#L22)
    tweaks the output to make references relative paths.

  - [Sample React App](https://github.com/learningequality/sample-channels/tree/master/contentnodes/html5_react):
    Proof of concept of minimal webapp based on the React framework.
    Note the [shell script](https://github.com/learningequality/sample-channels/blob/master/contentnodes/html5_react/update.sh#L24)
    tweaks required to make paths relative.



Exercises
---------
Kolibri exercises are based on the `perseus` exercise framework developed by Khan Academy.
Perseus provides a free-form interface for questions based on various "widgets" buttons,
draggables, expressions, etc. This is the native format for exercises on Kolibri.
An exercise question item is represented as a giant json file, with the main question
field stored as Markdown. Widgets are included in the "main" through a unique-Unicode
character and then widget metadata is stored separately as part of the json data.

Exercises can be created programmatically or interactively using the perseus editor through the web: [http://khan.github.io/perseus/](http://khan.github.io/perseus/)
(try adding different widgets in the Question area and then click the JSON Mode
checkbox to "view source" for the exercise.

You can then copy-paste the results as a .json file and import into Kolibri using ricecooker library (Python).

Sample: [https://github.com/learningequality/sample-channels/blob/master/contentnodes/exercise/sample_perseus04.json](https://github.com/learningequality/sample-channels/blob/master/contentnodes/exercise/sample_perseus04.json)  


Kolibri Studio provides helper classes for creating single/multiple-select questions, and numeric input questions:
[https://github.com/learningequality/ricecooker/blob/master/docs/exercises.md](https://github.com/learningequality/ricecooker/blob/master/docs/exercises.md)

A simple multiple choice (single select) question can be created as follows:

    SingleSelectQuestion(
        question = "What was the main idea in the passage you just read?",
        correct_answer = "The right answer",
        all_answers = ["The right answer", "Another option", "Nope, not this"]
        ...

Exercise activities allow student answers to be logged and enable progress reports
for teachers and coaches. Exercises can also be used as part of individual assignments
(playlist-like thing with a mix of content and exercises), group assignments, and exams.




Extending Kolibri
-----------------
New content types and presentation modalities will become available and supported
natively by future versions of Kolibri. The Kolibri software architecture is based
around the plug-in system that is easy to extend. All currently supported content
type renderers are based on this plug-in architecture. It might be possible to create
a Kolibri plugin for rendering specific content in custom ways.

