# Rice Cooker

A framework for creating channels on [Kolibri Studio](https://contentworkshop.learningequality.org/).


## Installation

* [Install ffmpeg](https://ffmpeg.org/) if you don't have it already.

* [Install pip](https://pypi.python.org/pypi/pip) if you don't have it already.

* Run `pip install ricecooker`

* You can now reference ricecooker using `import ricecooker` in your .py files


## Using the Rice Cooker

The rice cooker is a framework you can use to translate content into Kolibri-compatible objects.
The following steps will guide you through the creation of a program, or sushi chef,
that uses the `ricecooker` framework.
A sample sushi chef has been created [here](https://github.com/learningequality/ricecooker/blob/master/examples/sample_program.py).


### Step 1: Obtaining an Authorization Token ###
You will need an authorization token to create a channel on Kolibri Studio. In order to obtain one:

1. Create an account on [Kolibri Studio](https://contentworkshop.learningequality.org/).
2. Navigate to the Tokens tab under your Settings page.
3. Copy the given authorization token.
4. Set `token="auth-token"` in your call to uploadchannel (alternatively, you can create a file with your
    authorization token and set `token="path/to/file.txt"`).



### Step 2: Creating a Sushi Chef class ###

To use the Ricecooker, your chef script must define a sushi chef class that is a
subclass of the class `ricecooker.chefs.SushiChef`. Since it inheriting from the
`SushiChef` class, your chef class will have the method `run` which performs all
the work of uploading your channel to the content curation server.
Your sushi chef class will also inherit the method `main`, which your sushi chef
script should call when it runs on the command line.

The sushi chef class for your channel must have the following attributes:

  - `channel_info` (dict) that looks like this:
        
        channel_info = {
            'CHANNEL_SOURCE_DOMAIN': '<yourdomain.org>',       # who is providing the content (e.g. learningequality.org)
            'CHANNEL_SOURCE_ID': '<some unique identifier>',   # channel's unique id
            'CHANNEL_TITLE': 'Channel name shown in UI',
            'CHANNEL_LANGUAGE': 'en',                          # Use language codes from le_utils
            'CHANNEL_THUMBNAIL': 'http://yourdomain.org/img/logo.jpg', # (optional) local path or url to image file
            'CHANNEL_DESCRIPTION': 'What is this channel about?',      # (optional) description of the channel (optional)
        }

  - `construct_channel(**kwargs) -> ChannelNode`: This method is responsible for
    building the structure of your channel (to be discussed below).

To write the `construct_channel` method of your chef class, start by importing
`ChannelNode` from `ricecooker.classes.nodes` and create a `ChannelNode` using
the data in `self.channel_info`. Once you have the `ChannelNode` instance, the
rest of your chef's `construct_channel` method is responsible for constructing
the channel by adding various `Node`s using the method `add_child`.
`TopicNode`s correspond to folders, while `ContentNode`s correspond to different
type of content nodes.

`ContentNode` objects (and subclasses like `VideoNode`, `AudioNode`, ...) store
the metadata associate with the content, and are associated with one or more
`File` objects (`VideoFile`, `AudioFile`, ...).

For example, here is a simple sushi chef class whose `construct_channel` builds
a tree with a single topic.

```
from ricecooker.chefs import SushiChef
from ricecooker.classes.nodes import ChannelNode, TopicNode

class MySushiChef(SushiChef):
    """
    This is my sushi chef...
    """
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': '<yourdomain.org>',       # make sure to change this when testing
        'CHANNEL_SOURCE_ID': '<some unique identifier>',   # channel's unique id
        'CHANNEL_TITLE': 'Channel name shown in UI',
        'CHANNEL_THUMBNAIL': 'http://yourdomain.org/img/logo.jpg', # (optional) local path or url to image file
        'CHANNEL_DESCRIPTION': 'What is this channel about?',      # (optional) description of the channel (optional)
    }

    def construct_channel(self, **kwargs):
        # create channel
        channel = self.get_channel(**kwargs)
        # create a topic and add it to channel
        potato_topic = TopicNode(source_id="<potatos_id>", title="Potatoes!")
        channel.add_child(potato_topic)
        return channel

```

You can now run of you chef by creating an instance of the chef class and calling
it's `run` method:


```
mychef = MySushiChef()
args = {'token': 'YOURTOKENHERE9139139f3a23232', 'reset': True, 'verbose': True}
options = {}
mychef.run(args, options)
```

Note: Normally you'll pass `args` and `options` on the command line, but you can
pass dict objects with the necessary parameters for testing.

If you get an error, make sure you've replaced `YOURTOKENHERE9139139f3a23232` by
the token you obtained from the content curation server and you've changed
`channel_info['CHANNEL_SOURCE_DOMAIN']` and/or `channel_info['CHANNEL_SOURCE_ID']`
instead of using the default values.

If the channel run was successful, you should be able to see your single-topic
channel on the content curation server. The topic node "Potatoes!" is nice to
look at, but it feels kind of empty. Let's add more nodes to it!


### Step 3: Creating Nodes ###

Once your channel is created, you can start adding nodes. To do this, you need to
convert your data to the rice cooker's objects. Here are the classes that are
available to you (import from `ricecooker.classes.nodes`):

  - __TopicNode__: folders to organize to the channel's content
  - __VideoNode__: content containing mp4 file
  - __AudioNode__: content containing mp3 file
  - __DocumentNode__: content containing pdf file
  - __HTML5AppNode__: content containing zip of html files (html, js, css, etc.)
  - __ExerciseNode__: assessment-based content with questions


Each node has the following attributes:

  - __source_id__ (str): content's original id
  - __title__ (str): content's title
  - __license__ (str or License): content's license id or object
  - __description__ (str): description of content (optional)
  - __author__ (str): who created the content (optional)
  - __thumbnail__ (str or ThumbnailFile): path to thumbnail or file object (optional)
  - __files__ ([FileObject]): list of file objects for node (optional)
  - __extra_fields__ (dict): any additional data needed for node (optional)
  - __domain_ns__ (uuid): who is providing the content (e.g. learningequality.org) (optional)

**IMPORTANT**: nodes representing distinct pieces of content MUST have distinct `source_id`s.
Each node has a `content_id` (computed as a function of the `source_domain` and the node's `source_id`) that uniquely identifies a piece of content within Kolibri for progress tracking purposes. For example, if the same video occurs in multiple places in the tree, you would use the same `source_id` for those nodes -- but content nodes that aren't for that video need to have different `source_id`s.

All non-topic nodes must be assigned a license upon initialization. You can use the license's id (found under `le_utils.constants.licenses`) or create a license object from `ricecooker.classes.licenses` (recommended). When initializing a license object, you  can specify a __copyright_holder__ (str), or the person or organization who owns the license. If you are unsure which license class to use, a `get_license` method has been provided that takes in a license id and returns a corresponding license object.

For example:
```
from ricecooker.classes.licenses import get_license
from le_utils.constants import licenses

node = VideoNode(
    license = get_license(licenses.CC_BY, copyright_holder="Khan Academy"),
    ...
)
```

Thumbnails can also be passed in as a path to an image (str) or a ThumbnailFile object. Files can be passed in upon initialization, but can also be added at a later time. More details about how to create a file object can be found in the next section. VideoNodes also have a __derive_thumbnail__ (boolean) argument, which will automatically extract a thumbnail from the video if no thumbnails are provided.

Once you have created the node, add it to a parent node with `parent_node.add_child(child_node)`



### Step 4a: Adding Files ###

To add a file to your node, you must start by creating a file object from `ricecooker.classes.files`. Your sushi chef is responsible for determining which file object to create. Here are the available file models:

  - __ThumbnailFile__: png or jpg files to add to any kind of node
  - __AudioFile__: mp3 file
  - __DocumentFile__: pdf file
  - __HTMLZipFile__: zip of html files (must have `index.html` file at topmost level)
  - __VideoFile__: mp4 file (can be high resolution or low resolution)
  - __SubtitleFile__: vtt files to be used with VideoFiles
  - __WebVideoFile__: video downloaded from site such as YouTube or Vimeo
  - __YouTubeVideoFile__: video downloaded from YouTube using a youtube video id


Each file class can be passed a __preset__ and __language__ at initialization (SubtitleFiles must have a language set at initialization). A preset determines what kind of file the object is (e.g. high resolution video vs. low resolution video). A list of available presets can be found at `le_utils.constants.format_presets`. A list of available languages can be found at `le_utils.constants.languages`.

ThumbnailFiles, AudioFiles, DocumentFiles, HTMLZipFiles, VideoFiles, and SubtitleFiles must be initialized with a __path__ (str). This path can be a url or a local path to a file.
```
from le_utils.constants import languages

file_object = SubtitleFile(
    path = "file:///path/to/file.vtt",
    language = languages.getlang('en').code,
    ...
)
```

VideoFiles can also be initialized with __ffmpeg_settings__ (dict), which will be used to determine compression settings for the video file.
```
file_object = VideoFile(
    path = "file:///path/to/file.mp3",
    ffmpeg_settings = {"max_width": 480, "crf": 20},
    ...
)
```

WebVideoFiles must be given a __web_url__ (str) to a video on YouTube or Vimeo, and YouTubeVideoFiles must be given a __youtube_id__ (str). WebVideoFiles and YouTubeVideoFiles can also take in __download_settings__ (dict) to determine how the video will be downloaded and __high_resolution__ (boolean) to determine what resolution to download.
```
file_object = WebVideoFile(
    web_url = "https://vimeo.com/video-id",
    ...
)

file_object = YouTubeVideoFile(
    youtube_id = "abcdef",
    ...
)
```



### Step 4b: Adding Exercises ###

ExerciseNodes are special objects that have questions used for assessment. To add a question to your exercise, you must first create a question model from `ricecooker.classes.questions`. Your sushi chef is responsible for determining which question type to create. Here are the available question types:

  - __PerseusQuestion__: special question type for pre-formatted perseus questions
  - __MultipleSelectQuestion__: questions that have multiple correct answers (e.g. check all that apply)
  - __SingleSelectQuestion__: questions that only have one right answer (e.g. radio button questions)
  - __InputQuestion__: questions that have text-based answers (e.g. fill in the blank)


Each question class has the following attributes that can be set at initialization:

  - __id__ (str): question's unique id
  - __question__ (str): question body, in plaintext or Markdown format; math expressions must be in Latex format, surrounded by `$`, e.g. `$ f(x) = 2 ^ 3 $`.
  - __answers__ ([{'answer':str, 'correct':bool}]): answers to question, also in plaintext or Markdown
  - __hints__ (str or [str]): optional hints on how to answer question, also in plaintext or Markdown


To set the correct answer(s) for MultipleSelectQuestions, you must provide a list of all of the possible choices as well as an array of the correct answers (`all_answers [str]`) and `correct_answers [str]` respectively).
```
question = MultipleSelectQuestion(
    question = "Select all prime numbers.",
    correct_answers = ["2", "3", "5"],
    all_answers = ["1", "2", "3", "4", "5"],
    ...
)
```

To set the correct answer(s) for SingleSelectQuestions, you must provide a list of all possible choices as well as the correct answer (`all_answers [str]` and `correct_answer str` respectively).
```
question = SingleSelectQuestion(
    question = "What is 2 x 3?",
    correct_answer = "6",
    all_answers = ["2", "3", "5", "6"],
    ...
)
```

To set the correct answer(s) for InputQuestions, you must provide an array of all of the accepted answers (`answers [str]`).
```
question = InputQuestion(
    question = "Name a factor of 10.",
    answers = ["1", "2", "5", "10"],
)
```

To add images to a question's question, answers, or hints, format the image path with `'![](path/to/some/file.png)'` and the rice cooker will parse them automatically.


In order to set the criteria for completing exercises, you must set __exercise_data__ to equal a dict containing a mastery_model field based on the mastery models provided under `le_utils.constants.exercises`. If no data is provided, the rice cooker will default to mastery at 3 of 5 correct. For example:
```
node = ExerciseNode(
    exercise_data={
        'mastery_model': exercises.M_OF_N,
        'randomize': True,
        'm': 3,
        'n': 5,
    },
    ...
)
```

Once you have created the appropriate question object, add it to an exercise object with `exercise_node.add_question(question)`



### Step 5: Running your chef script ###

Your sushi chef scripts will run as standalone command line application
`mychef.py` which you can call from the command line.

To make the script file `mychef.py` a command line program, you need to do three things:

  - Add the line `#!/usr/bin/env python` as the first line of `mychef.py`
  - Add this code block at the bottom of `mychef.py`:

        if __name__ == '__main__':
            chef = MySushiChef()
            chef.main()

  - Make the file `mychef.py` executable by running `chmod +x mychef.py` on the
    command line.

The final chef script file `mychef.py` should look like this:

    #!/usr/bin/env python
    ...
    ...
    class MySushiChef(SushiChef):
        channel_info = { ... }
        def construct_channel(**kwargs):
            ...
            ...
    ...
    ...
    if __name__ == '__main__':
        chef = MySushiChef()
        chef.main()

You can now call the script by passing the appropriate command line arguments:

    ./mychef.py -v --token=YOURTOKENHERE9139139f3a23232 --reset

To see the help menu, type

    ./mychef.py -h

Here the full list of the supported command line args:

   - `-h` (help) will print how to use the rice cooker
   - `-v` (verbose) will print what the rice cooker is doing
   - `-u` (update) will force the ricecooker to redownload all files (skip checking the cache)
   - `--download-attempts=3` will set the maximum number of times to retry downloading files
   - `--debug` will print out debugging statements during rice cooking session
   - `--warn` will print out warnings during rice cooking session
   - `--quiet` will print out errors during rice cooking session
   - `--compress` will compress your high resolution videos to save space
   - `--token` will authorize you to create your channel (obtained in Step 1)
   - `--resume` will resume your previous rice cooking session
   - `--step=LAST` will specify at which step to resume your session
   - `--reset` will automatically start the rice cooker from the beginning
   - `--prompt` will prompt you to open your channel once it's been uploaded
   - `--publish` will automatically publish your channel once it's been uploaded
   - `--daemon` will start the chef in daemon mode (i.e. the chef will not execute
      immediately; instead, it will wait to receive commands via the Sushi Bar)
   - `[OPTIONS]` any additional key=value options you would like to pass to your construct_channel method



### Optional: Resuming the Rice Cooker ###

If your rice cooking session gets interrupted, you can resume from any step that
has already completed using `--resume --step=<step>` option. If step is not specified,
the rice cooker will resume from the last step you ran. If the specified step has
not been reached, the rice cooker will resume from. Other choices for `--step`:

  - __LAST__:                 Resume where the session left off (default)
  - __INIT__:                 Resume at beginning of session
  - __CONSTRUCT_CHANNEL__:    Resume with call to construct channel
  - __CREATE_TREE__:          Resume at set tree relationships
  - __DOWNLOAD_FILES__:       Resume at beginning of download process
  - __GET_FILE_DIFF__:        Resume at call to get file diff from Kolibri Studio
  - __START_UPLOAD__:         Resume at beginning of uploading files to Kolibri Studio
  - __UPLOADING_FILES__:      Resume at last upload request
  - __UPLOAD_CHANNEL__:       Resume at beginning of uploading tree to Kolibri Studio
  - __PUBLISH_CHANNEL__:      Resume at option to publish channel
  - __DONE__:                 Resume at prompt to open channel

