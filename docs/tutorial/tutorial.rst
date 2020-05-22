Hands-on tutorial
=================

In this tutorial, you'll start with a basic content integration script (sushi chef)
and extend the code to construct a bigger channel based on your own content.
In the process you'll learn about all the features of the ``ricecooker`` framework.


Prerequisite steps
------------------
The steps in this tutorial assume you have:

1. Completed the `Installation <../installation.html>`__ steps
2. Created an account on `Kolibri Studio <https://studio.learningequality.org/>`__
   and obtained your access token, which you'll need to to use instead of the text
   ``<your-access-token>`` in the examples below
3. Successfully managed to run the basic chef example in the `Getting started <gettingstarted.html>`__ tutorial


Step 1: Setup your environment
------------------------------
Create a directory called ``tutorial`` where you will run this code.
In general it is recommended to have separate directories for each content
integration script you will be working on.
In order to prepare for the upcoming **Step 6**, find a ``.pdf`` document,
a small ``.mp4`` video file, and an ``.mp3`` audio file.
Save these files somewhere inside the ``tutorial`` directory.


Step 2: Copy the sample code
----------------------------
To begin, download the sample code from `here <https://github.com/learningequality/ricecooker/blob/master/examples/tutorial/sushichef.py>`__
and save it as the file `sushichef.py` in the tutorial directory.

Note all the ``TODO`` items in the code. These are the places left for you to edit.


Step 3: Edit the channel metadata
---------------------------------
1. Open your terminal and ``cd`` into the folder where ``sushichef.py`` is located.
2. Open ``sushichef.py`` in a text editor.
3. Change ``<yourdomain.org>`` to any domain. The source domain specifies who is supplying the content.
4. Change ``<yourid>`` to any id. The source_id will distinguish your channel from other channels.
5. Change ``The Tutorial Channel`` to any channel name.

Try running the sushi chef by entering the following command in your terminal::

    python sushichef.py  --token=<your-access-token>

Click the link to `Kolibri Studio <https://studio.learningequality.org/>`__ that
shows up in the final step and make sure your channel looks OK.



Step 4: Create a Topic
----------------------
1. Locate the first **TODO** in the ``sushichef.py`` file.
   Here, you will create your first topic.
2. Copy/paste the example code and change ``exampletopic`` to ``mytopic``.
3. Set the ``source_id`` to be something other than ``topic-1``
   (the ``source_id`` will distinguish your node from other nodes in the tree)
4. Set the title.
5. Go to the next **TODO** and add ``mytopic`` to channel (use example code as guide)

::

    Check Run sushi chef from your terminal. Your channel should look like this:
    Channel
    | Example Topic
    | Your Topic




Step 5: Create a Subtopic
-------------------------
1. Go to the next **TODO** in the ``sushichef.py`` file. Here, you will create a subtopic
2. Copy/paste the example code and change ``examplesubtopic`` to ``mysubtopic``
3. Set the ``source_id`` and ``title``
4. Go to the next **TODO** and add ``mysubtopic`` to ``mytopic`` (use example code as guide)

::

    Check Run the sushi chef from your terminal. Your channel should look like this:
    Channel
    | Example Topic
    |      | Example Subtopic
    | Your Topic
    |      | Your Subtopic


Step 6: Create Files
--------------------
1. Go to the next **TODO** in the sushichef.py file. Here, you will create a pdf file
2. Copy/paste the example code and change ``examplepdf`` to ``mypdf``.
   ``DocumentFile(...)`` will automatically download a pdf file from the given path.
3. Set the ``source_id``, the ``title``, and the ``path`` (any url to a pdf file)
4. Repeat steps 1-3 for video files and audio files.
5. Finally, add your files to your channel (see last \*\* statements)

::

    Check: Run the sushi chef from your terminal. Your channel should look like this:
    Channel
    | Example Topic
    |      | Example Subtopic
    |      |      | Example Audio
    |      |  Example Video
    | Your Topic
    |      | Your Subtopic
    |      |      | Your Audio
    |      | Your Video
    | Example PDF
    | Your PDF






Next steps
----------
You're now ready to start writing your own content integration scripts.
The following links will guide you to the next steps:

- `Ricecooker API reference <../index_api_reference.html>`_
- `Code examples <../examples/index.html>`_
- `Learn about the ricecooker utilities and helpers <../index_utils.html>`_
