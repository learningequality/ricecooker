# Rice Cooker

A framework for creating channels on [Kolibri Studio](https://contentworkshop.learningequality.org/).


## Installation

* [Install pip](https://pypi.python.org/pypi/pip) if you don't have it already.

* Run `pip install ricecooker`

* You can now reference ricecooker using `import ricecooker` in your .py files


## Using the Rice Cooker

The rice cooker is a framework you can use to translate content into Kolibri-compatible objects.
The following steps will guide you through how to create a program, or sushi chef, to utilize this framework.
A sample sushi chef has been created [here](https://github.com/learningequality/ricecooker/blob/master/ricecooker/sample_program.py)

* **Step 1: Initializing the Channel**

	To run the Ricecooker, you must include a `construct_channel` method in your sushi chef file that returns a ChannelNode object. This function will be responsible for building the structure of your channel.

	Start by importing `ChannelNode` from `ricecooker.classes.nodes` and create a ChannelNode object. The ChannelNode class has the following fields:

    - source_id (str): channel's unique id
    - source_domain (str): who is providing the content (e.g. learningequality.org)
    - title (str): name of channel
    - description (str): description of the channel (optional)
    - thumbnail (str): local path or url to image file (optional)


	For example:
	```
	from ricecooker.classes.nodes import ChannelNode

	def construct_channel(args):

	    channel = ChannelNode(
	        source_domain = "learningequality.org",
	        source_id = "rice-channel",
	        title = "Rice Channel",
	        thumbnail = "http://path/to/some/image.png"
	    )
	    build_tree() 	# see sample_program.py for example build_tree function

	    return channel
    ```


* **Step 2: Creating Nodes**

	Once your channel is created, you can start adding nodes. To do this, you will need to convert your data to the rice cooker's objects. Here are the classes that are available to you (import from `ricecooker.classes.nodes`):

	- TopicNode: folders to organize to the channel's content
    - VideoNode: content containing mp4 file
    - AudioNode: content containing mp3 file
    - DocumentNode: content containing pdf file
    - HTML5AppNode: content containing zip of html files (html, js, css, etc.)
    - ExerciseNode: assessment-based content with questions


	Each node has the following attributes:

	- source_id (str): content's original id
	- title (str): content's title
	- license (str or <License>): content's license id or object
	- description (str): description of content (optional)
	- author (str): who created the content (optional)
	- thumbnail (str or <ThumbnailFile>): path to thumbnail or file object (optional)
	- files ([<File>]): list of file objects for node (optional)
	- extra_fields (dict): any additional data needed for node (optional)
	- domain_ns (uuid): who is providing the content (e.g. learningequality.org) (optional)


	All non-topic nodes must be assigned a license upon initialization. You can use the license's id (found under `le_utils.constants.licenses`) or create a license object from `ricecooker.classes.licenses` (recommended). When initializing a license object, you  can specify a copyright_holder (str), or the person or organization who owns the license. If you are unsure which license class to use, a `get_license` method has been provided that takes in a license id and returns a corresponding license object.


	For example:
	```
	from ricecooker.classes.licenses import get_license
	from le_utils.constants import licenses

    node = VideoNode(
        license = get_license(licenses.CC_BY, copyright_holder="Khan Academy"),
        ...
    )
    ```


    Thumbnails can also be passed in as a path to an image (str) or a ThumbnailFile object. Files can be passed in upon initialization, but can also be added at a later time. More details about how to create a file object can be found in the next section. VideoNodes also have a `derive_thumbnail` (boolean) argument, which will automatically extract a thumbnail from the video if no thumbnails are provided.

    Once you have created the node, add it to a parent node with `<parent-node>.add_child(<child-node>)`


* **Step 3a: Adding Files**

	To add a file to your node, you must start by creating a file object from `ricecooker.classes.files`. Your program is responsible for determining which file object to create. Here are the available file models:

	- ThumbnailFile: png or jpg files to add to any kind of node
	- AudioFile: mp3 file
    - DocumentFile: pdf file
    - HTMLZipFile: zip of html files (must have `index.html` file at topmost level)
    - VideoFile: mp4 file (can be high resolution or low resolution)
    - SubtitleFile: vtt files to be used with VideoFiles
    - WebVideoFile: video downloaded from site such as YouTube or Vimeo
    - YouTubeVideoFile: video downloaded from YouTube using a youtube video id


    Each file class can be passed a preset and language at initialization. A preset determines what kind of file the object is (e.g. high resolution video vs. low resolution video). A list of available presets can be found at `le_utils.constants.format_presets`. A list of available languages can be found at `le_utils.constants.languages`.

    ThumbnailFiles, AudioFiles, DocumentFiles, HTMLZipFiles, VideoFiles, and SubtitleFiles must be initialized with a path (str). This path can be a url or a local path to a file.



class VideoFile(path):
    def __init__(self, path, ffmpeg_settings=None, **kwargs):
        self.ffmpeg_settings = ffmpeg_settings
    def process_file(self):
            if self.filename and (self.ffmpeg_settings or config.COMPRESS):
                self.filename = compress(self.filename, self.ffmpeg_settings)

class SubtitleFile(path):
    def __init__(self, path, language, **kwargs):

class WebVideoFile(File):
    def __init__(self, web_url, download_settings=None, high_resolution=True, **kwargs):

class YouTubeVideoFile(WebVideoFile):
    def __init__(self, youtube_id, **kwargs):










* **Step 3b: Adding Exercises**

	Exercises are special model kinds that have questions used for assessment. To add a question to your exercise, you must first create a question model from `ricecooker.classes.questions`. Your program is responsible for determining which question type to create. Here are the available question types:

	- PerseusQuestion: special question type for pre-formatted perseus questions
	- MultipleSelectQuestion: questions that have multiple correct answers (e.g. check all that apply)
	- SingleSelectQuestion: questions that only have one right answer (e.g. radio button questions)
	- InputQuestion: questions that have text-based answers (e.g. fill in the blank)
	- FreeResponseQuestion: questions that require subjective answers (ungraded)


	Each question class has the following attributes that can be set at initialization:
	- id (str): question's unique id
    - question (str): question text
    - answers ([{'answer':str, 'correct':bool}]): answers to question
    - hints (str or [str]): optional hints on how to answer question


	FreeResponseQuestions do not need any answers set.
	```
	question = FreeResponseQuestion(
		question = "Explain why any number times 1 is itself.",
        ...
    )
    ```

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


	To add images to a question's question, answers, or hints, format the image path with `'![](<path/to/some/file.png>)'` and the rice cooker will parse them automatically.


	In order to set the criteria for completing exercises, you must set `exercise_data` to equal a dict containing a mastery_model field based on the mastery models provided under `le_utils.constants.exercises`. If no data is provided, the rice cooker will default to mastery at 3 of 5 correct. For example:
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


	Once you have created the appropriate question object, add it to an exercise object with `<exercise-node>.add_question(<question>)`


* **Step 4: Obtaining an Authorization Token**
    You will need an authorization token to create a channel on Kolibri Studio. In order to obtain one:
    1. Create an account on [Kolibri Studio](https://contentworkshop.learningequality.org/).
    2. Navigate to the Tokens tab under your Settings page.
    3. Copy the given authorization token.
    4. Set `token="<auth-token>"` in your call to uploadchannel (alternatively, you can create a file with your
		authorization token and set `token="<path-to-file.txt>"`).


* **Step 5: Running the Rice Cooker**

	Run `python -m ricecooker uploadchannel [-huv] "<path-to-py-file>" [--warn] [--compress] [--token=<token>] [--resume [--step=<step>] | --reset] [--prompt] [--publish]  [[OPTIONS] ...]`
	- -h (help) will print how to use the rice cooker
	- -v (verbose) will print what the rice cooker is doing
	- -u (update) will force the ricecooker to redownload all files (skip checking the cache)
	- --warn will print out warnings during rice cooking session
    - --compress will compress your high resolution videos to save space
	- --token will authorize you to create your channel (found under Kolibri Studio settings page)
	- --resume will resume your previous rice cooking session
	- --step will specify at which step to resume your session
	- --reset will automatically start the rice cooker from the beginning
	- --prompt will prompt you to open your channel once it's been uploaded
	- --publish will automatically publish your channel once it's been uploaded
	- [OPTIONS] any additional keyword arguments you would like to pass to your construct_channel method


* **Optional: Resuming the Rice Cooker**

	If your rice cooking session gets interrupted, you can resume from any step that has already completed
	using `--resume --step=<step>` option. If step is not specified, Ricecooker will resume from the last
	step you ran. If the specified step has not been reached, the Ricecooker will resume from

	- LAST:       			Resume where the session left off (default)
  	- INIT:                 Resume at beginning of session
  	- CONSTRUCT_CHANNEL:    Resume with call to construct channel
  	- CREATE_TREE:          Resume at set tree relationships
  	- DOWNLOAD_FILES:       Resume at beginning of download process
  	- GET_FILE_DIFF:        Resume at call to get file diff from Kolibri Studio
  	- START_UPLOAD:         Resume at beginning of uploading files to Kolibri Studio
  	- UPLOADING_FILES:      Resume at last upload request
  	- UPLOAD_CHANNEL:       Resume at beginning of uploading tree to Kolibri Studio
  	- PUBLISH_CHANNEL:      Resume at option to publish channel
  	- DONE:                 Resume at prompt to open channel
