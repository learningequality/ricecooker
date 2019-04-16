
``ricecooker`` exercises
========================

This mini-tutorial will walk you through the steps of running a simple
chef script ``ExercisesChef`` that creates two exercises nodes, and four
exercises questions.

We'll go over the same steps as described in the Exercises section of
the page `nodes <../nodes.md>`__, but this time showing the expected
output of each step.

Running the notebooks
~~~~~~~~~~~~~~~~~~~~~

To follow along and run the code in this notebook, you'll need to clone
the ``ricecooker`` repository, crate a virtual environement, install
``ricecooker`` using ``pip install ricecooker``, install Jypyter
notebook using ``pip install jupyter``, then start the jupyter notebook
server by running ``jupyter notebook``. You will then be able to run all
the code sections in this notebook and poke around.

Creating a Sushi Chef class
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: python

    from ricecooker.chefs import SushiChef
    from ricecooker.classes.nodes import TopicNode, ExerciseNode
    from ricecooker.classes.questions import SingleSelectQuestion, MultipleSelectQuestion, InputQuestion, PerseusQuestion
    from ricecooker.classes.licenses import get_license
    from le_utils.constants import licenses
    from le_utils.constants import exercises
    from le_utils.constants.languages import getlang
    
    
    class SimpleChef(SushiChef):
        channel_info = {
            'CHANNEL_TITLE': 'Sample Exercises',
            'CHANNEL_SOURCE_DOMAIN': '<yourdomain.org>',    # where you got the content
            'CHANNEL_SOURCE_ID': '<unique id for channel>',  # channel's unique id
            'CHANNEL_LANGUAGE': 'en',                        # le_utils language code
            'CHANNEL_DESCRIPTION': 'A test channel with different types of exercise questions',      # (optional)
            'CHANNEL_THUMBNAIL': None, # (optional)
        }
    
        def construct_channel(self, **kwargs):
            channel = self.get_channel(**kwargs)
            topic = TopicNode(title="Math Exercises", source_id="folder-id")
            channel.add_child(topic)
    
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
            topic.add_child(exercise_node)
    
            # LOAD JSON DATA (as string) FOR PERSEUS QUESTIONS    
            RAW_PERSEUS_JSON_STR = open('../../examples/data/perseus_graph_question.json', 'r').read()
            # or
            # import requests
            # RAW_PERSEUS_JSON_STR = requests.get('https://raw.githubusercontent.com/learningequality/sample-channels/master/contentnodes/exercise/perseus_graph_question.json').text
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
            topic.add_child(exercise_node2)
    
            return channel


**Note**: make sure you change the values of ``CHANNEL_SOURCE_DOMAIN``
and ``CHANNEL_SOURCE_ID`` before you try running this script. The
combination of these two values is used to compute the ``channel_id``
for the Kolibri channel you're creating. If you keep the lines above
unchanged, you'll get an error because the channel with source domain
'gov.mb.ca' and source id 'website\_docs' already exists on Kolibri
Studio.

Run of you chef by creating an instance of the chef class and calling
it's ``run`` method:

.. code:: python

    mychef = SimpleChef()
    args = {'token': '70aec3d11849e6691a8806d17f05b18bc5ca5ed4',
            'reset': True,
            'verbose': True,
            'publish': True,
            'nomonitor': True}
    options = {}
    mychef.run(args, options)


.. parsed-literal::

    Logged in with username ivan.savov@gmail.com
    Ricecooker v0.6.15 is up-to-date.
    Running get_channel... 
    
    
    ***** Starting channel build process *****
    
    
    Calling construct_channel... 
       Setting up initial channel structure... 
       Validating channel structure...
          Sample Exercises (ChannelNode): 3 descendants
             Math Exercises (TopicNode): 2 descendants
                Basic questions (ExerciseNode): 3 questions
                An exercise containing a perseus question (ExerciseNode): 1 question
       Tree is valid
    
    Downloading files...
    Processing content...
    	*** Processing images for exercise: Basic questions
    	*** Images for Basic questions have been processed
    	*** Processing images for exercise: An exercise containing a perseus question
    	*** Images for An exercise containing a perseus question have been processed
       All files were successfully downloaded
    Getting file diff...
    
    Checking if files exist on Kolibri Studio...
    Uploading files...
    
    Uploading 0 new file(s) to Kolibri Studio...
    Creating channel...
    
    Creating tree on Kolibri Studio...
       Creating channel Sample Exercises
    	Preparing fields...
    (0 of 3 uploaded)    Processing Sample Exercises (ChannelNode)
    (1 of 3 uploaded)       Processing Math Exercises (TopicNode)
       All nodes were created successfully.
    Upload time: 36.425115s
    Publishing channel...
    
    Publishing tree to Kolibri... 
    
    
    DONE: Channel created at https://contentworkshop.learningequality.org/channels/47147660ecb850bfb71590bf7d1ca971/edit
    


Congratulations, you put some math exercises on the internet!


