Getting started tutorial
========================

This short guide will walk you through the steps required to create a new Kolibri channel
by using a content integration script (a.k.a. sushi chef script) based on the ``ricecooker`` framework.
We'll write a Python script that creates a simple channel containing one PDF file,
and run this script to upload the PDF to Kolibri Studio so it can then be imported in Kolibri.

.. Note:: The software tools developed by the Learning Equality content team
   have food-related code names. Content integration scripts are called "sushi chefs"
   since they perform the detail-oriented task of taking external educational resources (🐟),
   packaging them as individual Kolibri content nodes (🍣),
   and organizing them neatly into Kolibri channels (🍱).


Installation
------------
If you haven't done so already, go through the steps on the `installation page <../installation.html>`__
to install the ``ricecooker`` Python package and other system prerequisites.


Obtaining a Studio access token
-------------------------------
You'll need a Kolibri Studio Access Token to create channels using ricecooker scripts.
To obtain this token:

1. Create an account on `Kolibri Studio <https://studio.learningequality.org/>`__
2. Navigate to the **Settings** > `Tokens <https://studio.learningequality.org/settings/tokens>`__ page on Kolibri Studio.
3. Copy the given access token to a safe place on your computer.


You must pass the token on the command line as ``--token=<your-access-token>`` when
calling your chef script. Alternatively, you can create a file to store your token
and pass in the command line argument ``--token=path/to/studiotoken.txt``.



Video overview
--------------
Watch this `video tutorial <http://35.196.115.213/en/learn/#/topics/c/3bd5eca9a81557efbab488849058c8c7>`__
to learn how to create a new content integration script and set the required
channel metadata fields like ``CHANNEL_SOURCE_DOMAIN`` and ``CHANNEL_SOURCE_ID``.

.. raw:: html

   <a href="http://35.196.115.213/en/learn/#/topics/c/3bd5eca9a81557efbab488849058c8c7" target='_blank'>
    <iframe width="560" height="315" src="https://www.youtube.com/embed/tmCllZOzY0Q" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
   </a>
   <div style="height:70px;">&nbsp;</div>


Creating a sushichef script
---------------------------
In a new folder on your computer, create a file called ``sushichef.py`` with the
code contents shown below. Alternatively you can use the "Save as" option on
`this link <https://raw.githubusercontent.com/learningequality/ricecooker/master/examples/gettingstarted/sushichef.py>`__
to achieve the same result.
We'll use this simple example of a content integration script for this tutorial.


.. literalinclude:: ../../examples/gettingstarted/sushichef.py
   :language: python


The code above is the equivalent of a "Hello, World!" content integration script
based on the ``ricecooker`` framework that will create a Kolibri channel with a
single topic node (Folder), and put a single PDF content node inside that folder.

As you can tell from the above code sample, most of the code in a content integration
script is concerned with setting the right metadata for files, content nodes,
topics nodes (folders), and the overall channel. This will be the running theme
when you work on content integration scripts.


.. Attention::
   You need to modify the value of ``CHANNEL_SOURCE_ID`` before you continue,
   otherwise you'll get an error when you run the script in the next step.
   The combination of ``CHANNEL_SOURCE_DOMAIN`` and ``CHANNEL_SOURCE_ID`` serve
   to create the channel's unique ID. If you use the same values as an already
   existing channel, you will either get a permissions error, or if you have
   editing permissions, you could overwrite the channel contents. Therefore, you
   want to be careful to use different values from the default ones used in the
   sample code.



Running the sushichef script
----------------------------
You can run a chef script by calling it on the command line:

.. code:: bash

    python sushichef.py  --token=<your-access-token>

The most important argument when running a chef script is ``--token``, which is
used to pass in the Studio Access Token and authenticates you in Kolibri Studio.
To see all the ``ricecooker`` command line options, run ``python sushichef.py -h``.
For more details about running chef scripts see the `chefops page <../chefops.html>`__.


.. Note:: If you get an error when running this command, make sure you have
   replaced ``<your-access-token>`` with the token you obtained from Kolibri Studio.
   Also make sure you've changed the value of ``channel_info['CHANNEL_SOURCE_ID']``
   instead of using the value in the sample code.


If the command succeeds, you should see something like this printed in your terminal:

.. parsed-literal::

    In SushiChef.run method. args={'command': 'uploadchannel', 'token': '<your-access-token>', 'update': False, 'resume': False, 'stage': True, 'publish': False} options={}
    Logged in with username you@yourdomain.org
    Ricecooker v0.6.42 is up-to-date.

    ***** Starting channel build process *****

    Calling construct_channel...
       Setting up initial channel structure...
       Validating channel structure...
          Potatoes info channel (ChannelNode): 2 descendants
             Potatoes! (TopicNode): 1 descendant
                Growing potatoes (DocumentNode): 1 file
       Tree is valid

    Downloading files...
    Processing content...
    	--- Downloaded 3641693a88b37e8d0484c340a83f9364.pdf
    	--- Downloaded 290c80ed7ce4cf117772f29dda76413c.jpg
       All files were successfully downloaded


    Checking if files exist on Kolibri Studio...
    	Got file diff for 2 out of 2 files
    Uploading files...
    Uploading 0 new file(s) to Kolibri Studio...

    Creating channel...
    Creating tree on Kolibri Studio...
       Creating channel Potatoes info channel
    	(0 of 2 uploaded)    Processing Potatoes info channel (ChannelNode)
    	(1 of 2 uploaded)       Processing Potatoes! (TopicNode)
    	   All nodes were created successfully.
    Upload time: 0.896938s


    DONE: Channel created at https://api.studio.learningequality.org/channels/47147660ecb850bfb71590bf7d1ca971/staging


Congratulations, you put the potatoes on the internet!
You’re probably already a legend in Ireland!


What just happened?
~~~~~~~~~~~~~~~~~~~
As you can tell from the above messages, running a ``sushichef.py`` involves all
kinds of steps that are orchestrated by the ricecooker framework:
  - The channel structure is created based on the output of the method
    ``construct_channel`` of the ``SimpleChef`` class
  - The tree structure and metadata are validated
  - All referenced files are downloaded locally (saved in the ``storage`` directory)
  - New files are uploaded to Kolibri Studio (in the above case no new files are
    uploaded because the files already exist on Studio from a previous run)
  - The channel structure and metadata is uploaded to Kolibri Studio
  - A link is printed for you to view the channel draft you just uploaded

If you're interested, you can read `this page <../developer/uploadprocess.html>`__
to learn about the tech details behind these steps, but the details are not important for now.
Let's continue to follow your channel's journey by clicking the Kolibri Studio link.


View your channel in Kolibri Studio
-----------------------------------
At the end of the chef run the complete channel (files and metadata) will be
uploaded to a "draft version" of the channel called a "staging tree".
Use the **DEPLOY** button in the Studio web interface to take your channel out
of "draft mode." This step is normally important for reviewing changes between
the new draft version and the current version of the channel.

The next step is to `PUBLISH <https://kolibri-studio.readthedocs.io/en/latest/publish_channel.html>`__
your channel using the button on Studio. The **PUBLISH** action exports all the
channel metadata and files in the format that is used by Kolibri and so it is
needed in order to import you channel in Kolibri.

At the end of the **PUBLISH** step, you will be able to see the **channel token**
associated with your channel, which is a short two-word string that you'll use
in the next step. You'll also receive an email notification telling you when the
channel has finished publishing.

.. Tip::
   Running the chef script with the command arguments ``--deploy --publish``
   will perform both the **DEPLOY** and **PUBLISH** actions after the chef run completes.
   This combination of arguments can be used for testing and development, but
   never for "production" channels, which must be reviewed before deploying.


Import your channel in Kolibri
------------------------------
The final step is to `IMPORT <https://kolibri.readthedocs.io/en/latest/manage/resources.html#import-with-token>`__
your channel into Kolibri using the channel token you obtained after the Kolibri Studio PUBLISH step finished.

Congratulations! Thanks to your Python skills and perseverence through this multi-step
process involving three software systems, you finally have access to your content
in the offline-capable Kolibri Learning Platform.

This topic node "Potatoes!" is nice to look at no doubt, but it feels kind of empty.
Not to worry—in the `next step of this tutorial <tutorial.html>`__ we'll learn how to
add more nodes to your channel. Before that let's do a quick recap of what we've learned
thus far.



Recap and next steps
--------------------
We can summarize the entire process we the Kolibri channel followed through the
three parts of the Kolibri ecosystem using the following diagram:

::

   sushichef(ricecooker)       Kolibri Studio             Kolibri
   UPLOADCHANNEL------->-------DEPLOY+PUBLISH------>------IMPORT (using channel token)

I know it seems like a complicated process, but you'll get used to it after going
through it a couple of times. All the steps represent *necessary* complexity.
The automated extraction and packaging of source materials ricecooker into
Kolibri channels provides the "raw materials" on which educators can build by
reusing and remixing in Kolibri Studio. **Ultimately the technical effort you
invest in creating content integration scripts will benefit learners and teachers
all around the world, this week and for years to come.** So get the metadata right!

As your next step for learning about Kolibri channels, we propose an optional,
non-technical activity to get to know Kolibri Studio better. After that we'll
resume the ricecooker training with the `hands-on tutorial <tutorial.html>`__.
If you're in a hurry, and want to skip ahead to API reference docs pages, check
out `content nodes <https://ricecooker.readthedocs.io/en/latest/nodes.html>`__
and `files <https://ricecooker.readthedocs.io/en/latest/files.html>`__.


Try the manual upload (optional)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Redo the steps from this tutorial but this time using the
`Kolibri Studio <https://studio.learningequality.org/>`__ web interface.
The manual upload process (Integration Method 1) is can be described as follows:

::

   Kolibri Studio             Kolibri
   UPLOAD+PUBLISH------>------IMPORT (using channel token)

Login to `Kolibri Studio <https://studio.learningequality.org/>`__ and try these steps:

 1. `Create a new channel <https://kolibri-studio.readthedocs.io/en/latest/working_channels.html#create-a-new-channel>`__
 2. Add a topic node to your channel
 3. `Add content <https://kolibri-studio.readthedocs.io/en/latest/add_content.html>`__
    by uploading a PDF document (note which metadata fields are required and which are optional)
 4. Use the `ADD > Import from Channels <https://kolibri-studio.readthedocs.io/en/latest/add_content.html#import-content-from-other-channels>`__
    feature to import the **Growing potatoes** document node from the **Potatoes info channel**.
 5. PUBLISH your channel (a new channel token will be generated).
 6. IMPORT your channel in Kolibri using the channel token.

Most of the channel creation operations steps you can do using ``ricecooker``,
you can also do through the Kolibri Studio web interface—in both cases you're
creating Kolibri channels, that can be *PUBLISH*-ed and used offline in Kolibri.


.. Note::
   Channels created using a content integration script (ricecooker channels),
   cannot be modified manually through the Kolibri Studio web interface.
   This is because manual changes would get overwritten and lost on next chef runs.
   If you want to make manual edits/tweaks to the channel, you can create a
   "derivative channel" and import the content from the ricecooker channel
   using the **ADD** > **Import from Channels** feature as in step 4 above.




`Hands-on tutorial <tutorial.html>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Now that we have a working example of a simple chef, we're ready to extend it
by adding other kinds of nodes (nutritional groups) and ``files`` (ingredients).
The next section will take you through a `hands-on tutorial <tutorial.html>`__
where you'll learn how to use the different content kinds and file types
supported by the ricecooker framework to create Kolibri channels.
