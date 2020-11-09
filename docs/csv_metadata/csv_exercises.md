CSV Exercises Workflow
======================
In addition to content nodes (files) and topics (folders), we can also specify exercises
using CSV metadata files (and associated images).

Exercises nodes store the usual metadata that all content nodes have (title,
description, author, license, etc.) and contain multiple types of questions.
The currently supported question types for the CSV workflow are:
  - `input_question`: Numeric input question, e.g. What is 2+2?
  - `single_selection`: Multiple choice questions where a single correct answer.
  - `multiple_selection`: Multiple choice questions with multiple correct answers/


To prepare a CSV content channel with exercises, you need the usual things
(A channel directory `channeldir`, `Channel.csv`, and `Content.csv`) and two
additional metadata files `Exercises.csv` and `ExerciseQuestions.csv`, the format
of which is defined below.

You can download template HERE
https://github.com/learningequality/sample-channels/tree/master/channels/csv_exercises



Exercises.csv
-------------
A CSV file that contains the following fields:

  - `Path *`:
  - `Title *`:
  - `Source ID *`: A unique identifier for this exercise, e.g., `exrc1`
  - `Description`:
  - `Author`:
  - `Language`:
  - `License ID *`:
  - `License Description`:
  - `Copyright Holder`:
  - `Number Correct`:  (integer, optional) This field controls how many questions
    students must get correct in order to complete the exercise.
  - `Out of Total`: (integer, optional) This field controls how many questions
    students are presented in a row, if not specified the value will be determined
    automatically based on the number of questions available (up to maximum of 5).
  - `Randomize`: (bool) True or False
  - `Thumbnail`:



ExerciseQuestions.csv
---------------------
Individual questions

  - `Source ID *`: This field is the link (foreign key) to the an exercise node, e.g. `exrc1`
  - `Question ID *`: A unique identifier for this question within the exercise, e.g. q1
  - `Question type *`: (str)  Question types are defined in
    [le-utils](https://github.com/learningequality/le-utils/blob/master/le_utils/constants/exercises.py#L34).
    The currently supported question types for the CSV workflow are:
      - `input_question`: Numeric input question, e.g. What is 2+2?
      - `single_selection`: Multiple choice questions where a single correct answer.
      - `multiple_selection`: Multiple choice questions with multiple correct answers/
  - `Question *`: (markdown) contains the question setup and the prompt, e.g. "What is 2+2?"
  - `Option A`: (markdown) The first answer option
  - `Option B`: (markdown)
  - `Option C`: (markdown)
  - `Option D`: (markdown)
  - `Option E`: (markdown) The fifth answer option
  - `Options F...`: Use this field for questions with more than five possible answers.
    This field can contain a list of multiple "🍣"-separated string values,
     e.g.,  "Answer F🍣Answer G🍣Answer H"
  - `Correct Answer *`: The correct answer
  - `Correct Answer 2`: Another correct
  - `Correct Answer 3`: A third correct answer
  - `Hint 1`: (markdown)
  - `Hint 2`:
  - `Hint 3`:
  - `Hint 4`:
  - `Hint 5`:
  - `Hint 6+`: Use this field for questions with more than five hints.
    This field stores a list of "🍣"-separated string values,
    e.g., "Hint 6 text🍣Hint 7 text🍣Hing 8 text"


The question, options, answers, and hints support Markdown and LaTeX formatting:
  - Use two newlines to start a new paragraph
  - Use the syntax `![](relative/path/to/figure.png)` to include images in text field
  - Use dollar signs as math delimiters `$\alpha\beta$`


#### Markdown image paths
Note that image paths used in Markdown will be interpreted as relative to the
location where the chef is running. For example, if the sushi chef project directory
looks like this:

    csvchef.py
    figures/
      exercise3/
        somefig.png
    content/
      Channel.csv
      Content.csv
      Exercises.csv
      ExerciseQuestions.csv
      channeldir/
         somefile.mp4
         anotherfile.pdf

Then the code for including `somefig.png` a Markdown field of an exercise question
is `![](figures/exercise3/somefig.png)`.



Ordering
--------
The order that content nodes appear in the channel is determined based on their
filenames in alphabetical order, so the choice of filenames can be used to enforce
a particular order of items within each folder.

The filename part of the `Path *` attribute of exercises specified in Exercises.csv
gives each exercise a "virtual filename" so that exercises will appear in the same
alphabetical order, intermixed with the CSV content items defined in `Content.csv`.




Implementation details
----------------------
  - To add exercises to a certain channel topic, the folder corresponding to this
    topic must exist inside the `channeldir` folder (even if it contains no files).
    A corresponding entry must be added to `Content.csv` to describe the metadata
    for the topic node containing the exercises.
