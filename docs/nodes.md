Nodes
=====

Kolibri channels are tree-like structures that consist of different types of topic
nodes (folders) and various content nodes (document, audio, video, html, exercise).
The module `ricecooker.classes.nodes` defines helper classes to represent each of
these supported content types and provide validation logic to check channel content
is valid before uploading it to Kolibri Studio.

The purpose of the Node classes is to represent the channel tree structure and
store metadata necessary for each type of content item, while the actual content
data is stored in file objects (defined in `ricecooker.classes.files`) and exercise
questions object (defined in `ricecooker.classes.questions`) which are created separately.



Overview
--------
The following diagram lists all the node classes defined in `ricecooker.classes.nodes`
and shows the associated file and question classes that content nodes can contain.

          ricecooker.classes.nodes
          |
          |                                               ricecooker.classes.files
    class Node(object)                                    |
        class ChannelNode(Node)                           |
        class TreeNode(Node)                              |
            class TopicNode(TreeNode)                     |
            class ContentNode(TreeNode)                   |
                class AudioNode(ContentNode)     files = [AudioFile]
                class DocumentNode(ContentNode)  files = [DocumentFile, EPubFile]
                class HTML5AppNode(ContentNode)  files = [HTMLZipFile]
                class H5PAppNode(ContentNode)    files = [H5PFile]
                class SlideshowNode(ContentNode) files = [SlideImageFile]
                class VideoNode(ContentNode)     files = [VideoFile, WebVideoFile, YouTubeVideoFile,
                                                          SubtitleFile, YouTubeSubtitleFile]
                class ExerciseNode(ContentNode)  questions = [SingleSelectQuestion,
                                                              MultipleSelectQuestion,
                                                              InputQuestion,
                                                              PerseusQuestion]
                                                              |
                                                              |
                                                              ricecooker.classes.questions


In the remainder of this document we'll describe in full detail the metadata that
is needed to specify different content nodes.

For more info about file objects see page [files](./files.md) and to learn about
the different exercise questions see the page [exercises](./exercises.md).



Content node metadata
---------------------
Each node has the following attributes:
  - __source_id__ (str): content's original id
  - __title__ (str): content's title
  - __license__ (str or License): content's license id or object
  - __language__ (str or lang_obj): language for the content node
  - __description__ (str): description of content (optional)
  - __author__ (str): who created the content (optional)
  - __aggregator__ (str): website or org hosting the content collection but not necessarily the creator or copyright holder (optional)
  - __provider__ (str): organization that commissioned or is distributing the content (optional)
  - __role__ (str): set to `roles.COACH` for teacher-facing materials (default `roles.LEARNER`)
  - __thumbnail__ (str or ThumbnailFile): path to thumbnail or file object (optional)
  - __derive_thumbnail__ (bool): set to True to generate thumbnail from contents (optional)
  - __files__ ([FileObject]): list of file objects for node (optional)
  - __extra_fields__ (dict): any additional data needed for node (optional)
  - __domain_ns__ (uuid): who is providing the content (e.g. learningequality.org) (optional)

**IMPORTANT**: nodes representing distinct pieces of content MUST have distinct `source_id`s.
Each node has a `content_id` (computed as a function of the `source_domain` and
the node's `source_id`) that uniquely identifies a piece of content within Kolibri
for progress tracking purposes. For example, if the same video occurs in multiple
places in the tree, you would use the same `source_id` for those nodes -- but
content nodes that aren't for that video need to have different `source_id`s.

### Usability guidelines

- Thumbnails: 16:9 aspect ratio ideally (e.g. 400x225 pixels)
- Titles: Aim for titles that make content items reusable independently of their containing folder,
  since curators could copy content items to other topics or channels.
  e.g. title for pdf doc "{lesson_name} - instructions.pdf" is better than just "Instructions.pdf" since that PDF could show up somewhere else.
- Descriptions: aim for about 400 characters (about 3-4 sentences)
- Licenses: Any non-public domain license must have a copyright holder, and any special permissions licenses must have a license description.


### Licenses
All content nodes within Kolibri and Kolibri Studio must have a license. The file
[le_utils/constants/licenses.py](https://github.com/learningequality/le-utils/blob/master/le_utils/constants/licenses.py)
contains the constants used to identify the license types. These constants are meant
to be used in conjunction with the helper method `ricecooker.classes.licenses.get_license`
to create `Licence` objects.

To initialize a license object, you must specify the license type and the
`copyright_holder` (str) which identifies a person or an organization. For example:
```
from ricecooker.classes.licenses import get_license
from le_utils.constants import licenses

license_obj = get_license(licenses.CC_BY, copyright_holder="Khan Academy")
```

Note: The `copyright_holder` field is required for all License types except for
the public domain license for which `copyright_holder` can be None. Everyone owns
the stuff in the public domain.


### Languages
The Python package `le-utils` defines the internal language codes used throughout
the Kolibri platform (e.g. `en`, `es-MX`, and `zul`). To find the internal language
code for a given language, you can locate it in the [lookup table](https://github.com/learningequality/le-utils/blob/master/le_utils/resources/languagelookup.json),
or use one of the language lookup helper functions defined in `le_utils.constants.languages`:
  - `getlang(<code>) --> lang_obj`: basic lookup used to ensure `<code>` is a valid
    internal language code (otherwise returns `None`).
  - `getlang_by_name(<Language name in English>) --> lang_obj`: lookup by name, e.g. `French`
  - `getlang_by_native_name(<Language autonym>) --> lang_obj`: lookup by native name, e.g., `français`
  - `getlang_by_alpha2(<two-letter ISO 639-1 code>) --> lang_obj`: lookup by standard two-letter code, e.g `fr`


You can either pass `lang_obj` as the `language` attribute when creating nodes,
or pass the internal language code (str) obtained from the property `lang_obj.code`:
```
from le_utils.constants.languages import getlang_by_native_name

lang_obj = getlang_by_native_name('français')
print(lang_obj        # Language(native_name='Français', primary_code='fr', subcode=None, name='French')
print(lang_obj.code)  # fr
```
See [languages][./languages.md] to read more about language codes.



### Thumbnails
Thumbnails can be passed in as a local filesystem path to an image file (str),
a URL (str), or a `ThumbnailFile` object.
The recommended size for thumbnail images is 400px by 225px (aspect ratio 16:9).
Use the command line argument `--thumbnails` to automatically generate thumbnails
for all content node that don't have a thumbnail specified.



Topic nodes
-----------
Topic nodes are folder-like containers that are used to organize the channel's content.


    from ricecooker.classes import TopicNode
    from le_utils.constants.languages import getlang

    topic_node = TopicNode(
        title='The folder name',
        description='A longer description of what the folder contains',
        source_id='<some unique identifier for this folder>',
        language='en',
        thumbnail=None,
        author='',
    )

It is highly recommended to find suitable thumbnail images for topic nodes. The
presence of thumbnails will make the content more appealing and easier to browse.
Set `derive_thumbnails=True` on a topic node or use the `--thumbnails` command
line argument and Ricecooker will generate thumbnails for topic nodes based on
the thumbnails of the content nodes they contain.



Content nodes
-------------
The table summarizes summarizes the content node classes, their associated files,
and the file formats supported by each file class:

      ricecooker.classes.nodes  ricecooker.classes.files
      |                         |
      AudioNode     --files-->  AudioFile                                   # .mp3
      DocumentNode  --files-->  DocumentFile                                # .pdf
                                EPubFile                                    # .epub
      SlideshowNode --files-->  SlideImageFile                              # .png/.jpg
      HTML5AppNode  --files-->  HTMLZipFile                                 # .zip
      VideoNode     --files-->  VideoFile, WebVideoFile, YouTubeVideoFile,  # .mp4
                                SubtitleFile, YouTubeSubtitleFile           # .vtt


For your copy-paste convenience, here is the sample code for creating a content
node (`DocumentNode`) and an associated (`DocumentFile`)

    content_node = DocumentNode(
          source_id='<some unique identifier within source domain>',
          title='Some Document',
          author='First Last (author\'s name)',
          description='Put node description here',
          language=getlang('en').code,
          license=get_license(licenses.CC_BY, copyright_holder='Copyright holder name'),
          thumbnail='some/local/path/name_thumb.jpg',
          files=[DocumentFile(
                    path='some/local/path/name.pdf',
                    language=getlang('en').code
                 )]
    )

Files can be passed in upon initialization as in the above sample, or can be
added after initialization using the content_node's `add_files` method.

Note you also use URLs for `path` and `thumbnail` instead of local filesystem paths,
and the files will be downloaded for you automatically.

You can replace `DocumentNode` and `DocumentFile` with any of the other combinations
of content node and file types.

Specify `derive_thumbnail=True` and leave thumbnail blank (`thumbnail=None`) to
let Ricecooker automatically generate a thumbnail for the node based on its content.
Thumbnail generation is supported for audio, video, PDF, and ePub, and HTML5 files.



### Role-based visibility
It is possible to include content nodes in any channel that are only visible to
Kolibri coaches. Setting the visibility to "coach-only" is useful for pedagogical
guides, answer keys, lesson plan suggestions, and other supporting material
intended only for teachers to see but not students.
To control content visibility set the `role` attributes to one of the constants
defined in `le_utils.constants.roles` to define the "minimum role" needed to see the content.
  - if `role=roles.LEARNER`: visible to learners, coaches, and administrators
  - if `role=roles.COACH`: visible only to Kolibri coaches and administrators


Exercise nodes
--------------
The `ExerciseNode` class (also subclasses of `ContentNode`), act as containers for
various assessment questions types defined in `ricecooker.classes.questions`.
The question types currently supported are:
  - __SingleSelectQuestion__: questions that only have one right answer (e.g. radio button questions)
  - __MultipleSelectQuestion__: questions that have multiple correct answers (e.g. check all that apply)
  - __InputQuestion__: questions that have as answers simple text or numeric expressions (e.g. fill in the blank)
  - __PerseusQuestion__: perseus json question (used in Khan Academy chef)


The following code snippet creates an exercise node that contains the three simple
question types:

    exercise_node = ExerciseNode(
            source_id='<some unique id>',
            title='Basic questions',
            author='LE content team',
            description='Showcase of the simple question type supported by Ricecooker and Studio',
            language=getlang('en').code,
            license=get_license(licenses.PUBLIC_DOMAIN),
            thumbnail=None,
            exercise_data={
                'mastery_model': exercises.M_OF_N,  # \
                'm': 2,                             #   learners must get 2/3 questions correct to complete exercise
                'n': 3,                             # /
                'randomize': True,                  # show questions in random order
            },
            questions=[
                MultipleSelectQuestion(
                    id='sampleEX_Q1',
                    question = "Which numbers the following numbers are even?",
                    correct_answers = ["2", "4",],
                    all_answers = ["1", "2", "3", "4", "5"],
                    hints=['Even numbers are divisible by 2.'],
                ),
                SingleSelectQuestion(
                    id='sampleEX_Q2',
                    question = "What is 2 times 3?",
                    correct_answer = "6",
                    all_answers = ["2", "3", "5", "6"],
                    hints=['Multiplication of $a$ by $b$ is like computing the area of a rectangle with length $a$ and width $b$.'],
                ),
                InputQuestion(
                    id='sampleEX_Q3',
                    question = "Name one of the *factors* of 10.",
                    answers = ["1", "2", "5", "10"],
                    hints=['The factors of a number are the divisors of the number that leave a whole remainder.'],
                )
            ]
    )


Creating a `PerseusQuestion` requires first obtaining the perseus-format `.json`
file for the question. You can questions using the [web interface](http://khan.github.io/perseus/).
[Click here](https://github.com/learningequality/ricecooker/tree/master/examples/data)
to see a samples of questions in the perseus json format.

To following code creates an exercise node with a single perseus question in it:

    # LOAD JSON DATA (as string) FOR PERSEUS QUESTIONS
    RAW_PERSEUS_JSON_STR = open('ricecooker/examples/data/perseus_graph_question.json', 'r').read()
    # or
    # import requests
    # RAW_PERSEUS_JSON_STR = requests.get('https://github.com/learningequality/sample-channels/blob/master/contentnodes/exercise/perseus_graph_question.json').text
    exercise_node2 = ExerciseNode(
            source_id='<another unique id>',
            title='An exercise containing a perseus question',
            author='LE content team',
            description='An example exercise with a Persus question',
            language=getlang('en').code,
            license=get_license(licenses.CC_BY, copyright_holder='Copyright holder name'),
            thumbnail=None,
            exercise_data={
                'mastery_model': exercises.M_OF_N,
                'm': 1,
                'n': 1,
            },
            questions=[
                PerseusQuestion(
                    id='ex2bQ4',
                    raw_data=RAW_PERSEUS_JSON_STR,
                    source_url='https://github.com/learningequality/sample-channels/blob/master/contentnodes/exercise/perseus_graph_question.json'
                ),
            ]
    )

The example above uses the JSON from [this question](http://khan.github.io/perseus/#content=%7B%22question%22%3A%7B%22content%22%3A%22Move%20the%20points%20in%20the%20figure%20below%20to%20obtain%20the%20graph%20of%20the%20line%20with%20equation%20%24y%3D%5C%5Cfrac%7B3%7D%7B2%7Dx-3%24.%5Cn%5Cn%5B%5B%E2%98%83%20interactive-graph%202%5D%5D%5Cn%22%2C%22images%22%3A%7B%7D%2C%22widgets%22%3A%7B%22interactive-graph%202%22%3A%7B%22type%22%3A%22interactive-graph%22%2C%22alignment%22%3A%22default%22%2C%22static%22%3Afalse%2C%22graded%22%3Atrue%2C%22options%22%3A%7B%22step%22%3A%5B1%2C1%5D%2C%22backgroundImage%22%3A%7B%22url%22%3Anull%7D%2C%22markings%22%3A%22graph%22%2C%22labels%22%3A%5B%22x%22%2C%22y%22%5D%2C%22showProtractor%22%3Afalse%2C%22showRuler%22%3Afalse%2C%22showTooltips%22%3Afalse%2C%22rulerLabel%22%3A%22%22%2C%22rulerTicks%22%3A10%2C%22range%22%3A%5B%5B-5%2C5%5D%2C%5B-5%2C5%5D%5D%2C%22gridStep%22%3A%5B0.5%2C0.5%5D%2C%22snapStep%22%3A%5B0.25%2C0.25%5D%2C%22graph%22%3A%7B%22type%22%3A%22linear%22%7D%2C%22correct%22%3A%7B%22type%22%3A%22linear%22%2C%22coords%22%3A%5B%5B0%2C-3%5D%2C%5B2%2C0%5D%5D%7D%7D%2C%22version%22%3A%7B%22major%22%3A0%2C%22minor%22%3A0%7D%7D%2C%22interactive-graph%201%22%3A%7B%22options%22%3A%7B%22labels%22%3A%5B%22x%22%2C%22y%22%5D%2C%22range%22%3A%5B%5B-10%2C10%5D%2C%5B-10%2C10%5D%5D%2C%22step%22%3A%5B1%2C1%5D%2C%22valid%22%3Atrue%2C%22backgroundImage%22%3A%7B%22url%22%3Anull%7D%2C%22markings%22%3A%22graph%22%2C%22showProtractor%22%3Afalse%2C%22showRuler%22%3Afalse%2C%22showTooltips%22%3Afalse%2C%22rulerLabel%22%3A%22%22%2C%22rulerTicks%22%3A10%2C%22correct%22%3A%7B%22type%22%3A%22linear%22%2C%22coords%22%3Anull%7D%7D%2C%22type%22%3A%22interactive-graph%22%2C%22version%22%3A%7B%22major%22%3A0%2C%22minor%22%3A0%7D%7D%2C%22expression%201%22%3A%7B%22options%22%3A%7B%22answerForms%22%3A%5B%7B%22value%22%3A%22y%3D%5C%5Cfrac%7B3%7D%7B2%7Dx-3%22%2C%22form%22%3Afalse%2C%22simplify%22%3Afalse%2C%22considered%22%3A%22correct%22%2C%22key%22%3A0%2C%22times%22%3Afalse%2C%22functions%22%3A%5B%22f%22%2C%22g%22%2C%22h%22%5D%2C%22buttonSets%22%3A%5B%22basic%22%2C%22basic%20relations%22%5D%2C%22buttonsVisible%22%3A%22focused%22%2C%22linterContext%22%3A%7B%22contentType%22%3A%22%22%2C%22highlightLint%22%3Afalse%2C%22paths%22%3A%5B%5D%2C%22stack%22%3A%5B%5D%7D%7D%2C%7B%22considered%22%3A%22correct%22%2C%22form%22%3Afalse%2C%22key%22%3A1%2C%22simplify%22%3Afalse%2C%22value%22%3A%22%5C%5Cfrac%7B3%7D%7B2%7Dx-3%22%2C%22times%22%3Afalse%2C%22functions%22%3A%5B%22f%22%2C%22g%22%2C%22h%22%5D%2C%22buttonSets%22%3A%5B%22basic%22%2C%22basic%20relations%22%5D%2C%22buttonsVisible%22%3A%22focused%22%2C%22linterContext%22%3A%7B%22contentType%22%3A%22%22%2C%22highlightLint%22%3Afalse%2C%22paths%22%3A%5B%5D%2C%22stack%22%3A%5B%5D%7D%7D%5D%2C%22buttonSets%22%3A%5B%22basic%22%2C%22basic%20relations%22%5D%2C%22functions%22%3A%5B%22f%22%2C%22g%22%2C%22h%22%5D%2C%22times%22%3Afalse%2C%22static%22%3Afalse%7D%2C%22type%22%3A%22expression%22%2C%22version%22%3A%7B%22major%22%3A1%2C%22minor%22%3A0%7D%2C%22graded%22%3Atrue%2C%22alignment%22%3A%22default%22%2C%22static%22%3Afalse%7D%7D%7D%2C%22answerArea%22%3A%7B%22calculator%22%3Afalse%2C%22chi2Table%22%3Afalse%2C%22periodicTable%22%3Afalse%2C%22tTable%22%3Afalse%2C%22zTable%22%3Afalse%7D%2C%22itemDataVersion%22%3A%7B%22major%22%3A0%2C%22minor%22%3A1%7D%2C%22hints%22%3A%5B%5D%7D),
for which you can also a [rendered preview here](http://khan.github.io/perseus/?renderer#content=%7B%22question%22%3A%7B%22content%22%3A%22Move%20the%20points%20in%20the%20figure%20below%20to%20obtain%20the%20graph%20of%20the%20line%20with%20equation%20%24y%3D%5C%5Cfrac%7B3%7D%7B2%7Dx-3%24.%5Cn%5Cn%5B%5B%E2%98%83%20interactive-graph%202%5D%5D%5Cn%22%2C%22images%22%3A%7B%7D%2C%22widgets%22%3A%7B%22interactive-graph%202%22%3A%7B%22type%22%3A%22interactive-graph%22%2C%22alignment%22%3A%22default%22%2C%22static%22%3Afalse%2C%22graded%22%3Atrue%2C%22options%22%3A%7B%22step%22%3A%5B1%2C1%5D%2C%22backgroundImage%22%3A%7B%22url%22%3Anull%7D%2C%22markings%22%3A%22graph%22%2C%22labels%22%3A%5B%22x%22%2C%22y%22%5D%2C%22showProtractor%22%3Afalse%2C%22showRuler%22%3Afalse%2C%22showTooltips%22%3Afalse%2C%22rulerLabel%22%3A%22%22%2C%22rulerTicks%22%3A10%2C%22range%22%3A%5B%5B-5%2C5%5D%2C%5B-5%2C5%5D%5D%2C%22gridStep%22%3A%5B0.5%2C0.5%5D%2C%22snapStep%22%3A%5B0.25%2C0.25%5D%2C%22graph%22%3A%7B%22type%22%3A%22linear%22%7D%2C%22correct%22%3A%7B%22type%22%3A%22linear%22%2C%22coords%22%3A%5B%5B0%2C-3%5D%2C%5B2%2C0%5D%5D%7D%7D%2C%22version%22%3A%7B%22major%22%3A0%2C%22minor%22%3A0%7D%7D%7D%7D%2C%22answerArea%22%3A%7B%22calculator%22%3Afalse%2C%22chi2Table%22%3Afalse%2C%22periodicTable%22%3Afalse%2C%22tTable%22%3Afalse%2C%22zTable%22%3Afalse%7D%2C%22itemDataVersion%22%3A%7B%22major%22%3A0%2C%22minor%22%3A1%7D%2C%22hints%22%3A%5B%5D%7D).





SlideshowNode nodes
-------------------
The `SlideshowNode` class and the associated `SlideImageFile` class are used to
create powerpoint-like presentations. The following code sample shows how to
create a `SlideshowNode` that contains two slide images:

    slideshow_node = SlideshowNode(
          source_id='<some unique identifier within source domain>',
          title='My presentations',
          author='First Last (author\'s name)',
          description='Put slideshow description here',
          language=getlang('en').code,
          license=get_license(licenses.CC_BY, copyright_holder='Copyright holder name'),
          thumbnail='some/local/path/slideshow_thumbnail.jpg',
          files=[
              SlideImageFile(
                  path='some/local/path/firstslide.png',
                  caption="The caption text to be displayed below the slide image.",
                  descriptive_text="Description of the slide for users that cannot see the image",
                  language=getlang('en').code,
              ),
              SlideImageFile(
                  path='some/local/path/secondslide.jpg',
                  caption="The caption for the second slide image.",
                  descriptive_text="Alternative text for the second slide image",
                  language=getlang('en').code,
              )
          ]
    )

Note this is a new feature in Kolibri 0.13 and prior version of Kolibri will not
be able to import and view this content kind.
