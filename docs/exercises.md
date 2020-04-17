Exercises
=========

Exercises (assessment activities) are an important part of every learning experience.
Kolibri exercises are graded automatically and provide immediate feedback learners.
Student answers to be logged and enable progress reports for teachers and coaches.
Exercises can also be used as part of lessons and quizzes.

An `ExerciseNode`s are special kind of content node contains one or more questions.
In order to set the criteria for completing exercises, you must set __exercise_data__
to a dict containing a `mastery_model` field based on the mastery models provided
in `le_utils.constants.exercises`.
If no data is provided, `ricecooker` will default to mastery at 3 of 5 correct.
For example:
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


To add a question to an exercise node, you must first create a question model from
`ricecooker.classes.questions`. Your sushi chef is responsible for determining
which question type to create. Here are the available question types:
  - __SingleSelectQuestion__: questions that only have one right answer (e.g. radio button questions)
  - __MultipleSelectQuestion__: questions that have multiple correct answers (e.g. check all that apply)
  - __InputQuestion__: questions that have text-based answers (e.g. fill in the blank)
  - __PerseusQuestion__: special question type for pre-formatted perseus questions


Each question class has the following attributes that can be set at initialization:
  - __id__ (str): question's unique id
  - __question__ (str): question body, in plaintext or Markdown format;
    math expressions must be in Latex format, surrounded by `$`, e.g. `$f(x) = 2^3$`.
  - __correct_answer__ (str) or __answers__ ([str]): the answer(s) to question as plaintext or Markdown
  - __all_answers__ ([str]): list of choices for single select and multiple select questions as plaintext or Markdown
  - __hints__ (str or [str]): optional hints on how to answer question, also in plaintext or Markdown

To set the correct answer(s) for MultipleSelectQuestions, you must provide a list
of all of the possible choices as well as an array of the correct answers
(`all_answers [str]`) and `correct_answers [str]` respectively).
```
question = MultipleSelectQuestion(
    question = "Select all prime numbers.",
    correct_answers = ["2", "3", "5"],
    all_answers = ["1", "2", "3", "4", "5"],
    ...
)
```

To set the correct answer(s) for SingleSelectQuestions, you must provide a list
of all possible choices as well as the correct answer (`all_answers [str]` and
`correct_answer str` respectively).

```
question = SingleSelectQuestion(
    question = "What is 2 x 3?",
    correct_answer = "6",
    all_answers = ["2", "3", "5", "6"],
    ...
)
```

To set the correct answer(s) for InputQuestions, you must provide an array of
all of the accepted answers (`answers [str]`).
```
question = InputQuestion(
    question = "Name a factor of 10.",
    answers = ["1", "2", "5", "10"],
)
```

To add images to a question's question, answers, or hints, format the image path
with `'![](path/to/some/file.png)'` and `ricecooker` will parse them automatically.


Once you have created the appropriate question object, add it to an exercise object
with `exercise_node.add_question(question)`.


Further reading
---------------

  - See also the section `Exercise Nodes <nodes.html#exercise-nodes>`__ on the nodes page.
