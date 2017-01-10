# Rice Cooker

A framework for creating channels on [Kolibri Studio](https://contentworkshop.learningequality.org/).


## Installation

* [Install pip](https://pypi.python.org/pypi/pip) if you don't have it already.

* Run `pip install ricecooker`

* You can now reference ricecooker using `import ricecooker` in your .py files


## Using the Rice Cooker

A sample program has been created [here](https://github.com/learningequality/ricecooker/blob/master/ricecooker/sample_program.py)

* **Initializing the Channel**

	In order for the rice cooker to run properly, you must include a `create_channel` method in your target py file
	that returns a Channel model. This function will be responsible for building a tree based on `ricecooker.classes`.

	Start by importing `Channel` from `ricecooker.classes.nodes` and create a Channel model. The Channel model has
	the following fields:

    - channel_id (str): channel's unique id
    - domain (str): who is providing the content (e.g. learningequality.org
    - title (str): name of channel
    - description (str): description of the channel (optional)
    - thumbnail (str): local path or url to image file (optional)

	For example:
	```
	from ricecooker.classes.nodes import Channel

	def construct_channel(args):

	    channel = Channel(
	        domain="learningequality.org",
	        channel_id="rice-channel",
	        title="Rice Channel",
	        thumbnail="http://path/to/some/image.png"
	    )
	    _build_tree(channel, <source tree>) 	# see sample_program.py for example build_tree function

	    return channel
    ```


* **Building the Tree**

	Once your channel is created, you can start adding content. To do this, you will need to convert your data to
	the rice cooker's models. Here are the model types that are available to you:

	- Topic: folders to add hierarchy to the channel's content
    - Video: mp4
    - Audio: mp3 or wav
    - Document: pdf
    - Exercise: assessment-based content with questions
    - HTML5App: zip containing html content (must have `index.html` file at topmost level)

    The `ricecooker.classes.nodes` module has the function `guess_content_kind`, which takes in a file or list of
    files as well as a list of questions (if available) and determines what model best suits those files
    (if no match could be found, an `UnknownContentKindError` will be raised). For example:
    ```
    	>> guess_content_kind([])
    	'topic'
    	>> guess_content_kind(["http://path/to/some/file.mp4"])
    	'video'
    	>> guess_content_kind([], ["Question?"])
    	'exercise'
    ```

    Once you have created the model, add it to a parent node with `<parent-node>.add_child(<child-node>)`


* **Adding Exercises**

	Exercises are special model kinds that have questions used for assessment. In order to set the criteria
	for completing exercises, you must set `exercise_data` to equal a dict containing a mastery_model field
	based on the mastery models provided under `le_utils.constants.exercises`. If no data is provided,
	the rice cooker will default to mastery at 3 of 5 correct. For example:
	```
	node = Exercise(
		exercise_data={'mastery_model': exercises.M_OF_N, 'randomize': True, 'm': 3, 'n': 5},
		...
	)
	```

	To add a question to your exercise, you must first create a question model from `ricecooker.classes.questions`.
	Your program is responsible for determining which question type to create. Here are the available question types:

	- PerseusQuestion: special question type for pre-formatted perseus questions
	- MultipleSelectQuestion: questions that have multiple correct answers (e.g. check all that apply)
	- SingleSelectQuestion: questions that only have one right answer (e.g. radio button questions)
	- InputQuestion: questions that have text-based answers (e.g. fill in the blank)
	- FreeResponseQuestion: questions that require subjective answers (ungraded)

	To set the correct answer(s) for input questions, you must provide an array of all of the accepted answers (`answers [str]`).
	For multiple selection questions, you must provide a list of all of the possible choices as well as an array of the correct
	answers (`all_answers [str]`) and `correct_answers [str]` respectively). For single selection questions, you must provide
	a list of all possible choices as well as the correct answer (`all_answers [str]` and `correct_answer str` respectively).

	To add images to a question's question, answers, or hints, format the image path with `'![](<path/to/some/file.png>)'`

	Once you have created the appropriate question model, add it to an exercise model with `<exercise-node>.add_question(<question>)`

* **Obtaining an Authorization Token**
    You will need an authorization token to create a channel on Kolibri Studio. In order to obtain one:
    1. Create an account on [Kolibri Studio](https://contentworkshop.learningequality.org/).
    2. Navigate to the Tokens tab under your Settings page.
    3. Copy the given authorization token.
    4. Set `token="<auth-token>"` in your call to uploadchannel (alternatively, you can create a file with your
		authorization token and set `token="<path-to-file.txt>"`).

* **Running the Rice Cooker**

	Run `python -m ricecooker uploadchannel [-huv] "<path-to-py-file>" [--debug] [--warn] [--compress] [--token=<token>] [--resume [--step=<step>] | --reset] [--prompt] [--publish]  [[OPTIONS] ...]`
	- -h (help) will print how to use the rice cooker
	- -v (verbose) will print what the rice cooker is doing
	- -u (update) will force the ricecooker to redownload all files
	- --debug will send data to localhost if you have Kolibri Studio running locally
	- --warn will print out warnings during rice cooking session
    - --compress will compress your high resolution videos to save space
	- --token will authorize you to create your channel (found under Kolibri Studio settings page)
	- --resume will resume your previous rice cooking session
	- --step will specify at which step to resume your session
	- --reset will automatically start the rice cooker from the beginning
	- --prompt will prompt you to open your channel once it's been uploaded
	- --publish will automatically publish your channel once it's been uploaded
	- [OPTIONS] any additional keyword arguments you would like to pass to your construct_channel method
