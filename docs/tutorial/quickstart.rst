The ``ricecooker`` quick start
==============================

This mini-tutorial will walk you through the steps of running a simple
chef script ``SimpleChef`` that uses the ``ricecooker`` framework to
upload a content channel to the Kolibri Studio server.

We’ll go over the same steps as described in the
`usage <https://ricecooker.readthedocs.io/en/latest/usage.html>`__, but
this time showing the expected output of each step.

Running the notebooks
~~~~~~~~~~~~~~~~~~~~~

To follow along and run the code in this notebook, you’ll need to clone
the ``ricecooker`` repository, crate a virtual environement, install
``ricecooker`` using ``pip install ricecooker``, install Jypyter
notebook using ``pip install jupyter``, then start the jupyter notebook
server by running ``jupyter notebook``. You will then be able to run all
the code sections in this notebook and poke around.

Step 1: Obtain a Studio Authorization Token
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You will need a\` Studio Authorization Token to create a channel on
Kolibri Studio. In order to obtain such a token: 1. Create an account on
`Kolibri Studio <https://studio.learningequality.org/>`__. 2. Navigate
to the Tokens tab under your Settings page. 3. Copy the given
authorization token to a safe place.

You must pass the token on the command line as
``--token=<your-studio-token>`` when calling your chef script.
Alternatively, you can create a file to store your token and pass in the
command line argument ``--token="path/to/file.txt"``.

Step 2: Creating a Sushi Chef class
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We’ll use following simple chef script as an the running example in this
section. You can find the full source code of it
`examples/simple_chef.py <https://github.com/learningequality/ricecooker/blob/master/examples/simple_chef.py>`__.

Mmmm, potato… potato give you power!

.. code:: ipython3

    #!/usr/bin/env python
    from ricecooker.chefs import SushiChef
    from ricecooker.classes.nodes import ChannelNode, TopicNode, DocumentNode
    from ricecooker.classes.files import DocumentFile
    from ricecooker.classes.licenses import get_license
    
    
    class SimpleChef(SushiChef):
        channel_info = {
            'CHANNEL_TITLE': 'Potatoes info channel',
            'CHANNEL_SOURCE_DOMAIN': '<yourdomain.org>',    # where you got the content
            'CHANNEL_SOURCE_ID': '<unique id for channel>',  # channel's unique id
            'CHANNEL_LANGUAGE': 'en',                        # le_utils language code
            'CHANNEL_THUMBNAIL': 'https://upload.wikimedia.org/wikipedia/commons/b/b7/A_Grande_Batata.jpg', # (optional)
            'CHANNEL_DESCRIPTION': 'What is this channel about?',      # (optional)
        }
    
        def construct_channel(self, **kwargs):
            channel = self.get_channel(**kwargs)
            potato_topic = TopicNode(title="Potatoes!", source_id="<potatos_id>")
            channel.add_child(potato_topic)
            doc_node = DocumentNode(
                title='Growing potatoes',
                description='An article about growing potatoes on your rooftop.',
                source_id='pubs/mafri-potatoe',
                license=get_license('CC BY', copyright_holder='University of Alberta'),
                language='en',
                files=[DocumentFile(path='https://www.gov.mb.ca/inr/pdf/pubs/mafri-potatoe.pdf',
                                    language='en')],
            )
            potato_topic.add_child(doc_node)
            return channel
    
    
    if __name__ == '__main__':
        """
        Run this script on the command line using:
            python simple_chef.py -v --reset --token=YOURTOKENHERE9139139f3a23232
        """
        simple_chef = SimpleChef()
        simple_chef.main()

**Note**: make sure you change the values of ``CHANNEL_SOURCE_DOMAIN``
and ``CHANNEL_SOURCE_ID`` before you try running this script. The
combination of these two values is used to compute the ``channel_id``
for the Kolibri channel you’re creating. If you keep the lines above
unchanged, you’ll get an error because the channel with source domain
‘gov.mb.ca’ and source id ‘website_docs’ already exists on Kolibri
Studio.

Run of chef script by calling it on the command line:

.. code:: ipython3

    !cd ../../examples; python simple_chef.py -v --reset --token=<your-studio-token>


.. parsed-literal::

    run_id: bb7085c289f943b89ceccb726377c59e
    In SushiChef.run method. args={'command': 'uploadchannel', 'token': '70aec3...', 'update': False, 'verbose': True, 'quiet': False, 'warn': False, 'debug': False, 'compress': False, 'thumbnails': False, 'download_attempts': 3, 'reset': True, 'resume': False, 'step': 'LAST', 'prompt': False, 'stage_deprecated': False, 'stage': True, 'publish': False, 'sample': None, 'daemon': False, 'nomonitor': False, 'cmdsock': None} options={}
    Logged in with username you@yourdomain.org
    Ricecooker v0.6.40 is up-to-date.
    
    
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
    Getting file diff...
    
    Checking if files exist on Kolibri Studio...
    	Got file diff for 2 out of 2 files
    Uploading files...
    
    Uploading 0 new file(s) to Kolibri Studio...
    Creating channel...
    
    Creating tree on Kolibri Studio...
       Creating channel Potatoes info channel
    	Preparing fields...
    (0 of 2 uploaded)    Processing Potatoes info channel (ChannelNode)
    (1 of 2 uploaded)       Processing Potatoes! (TopicNode)
       All nodes were created successfully.
    Upload time: 0.896938s
    
    
    DONE: Channel created at https://api.studio.learningequality.org/channels/47147660ecb850bfb71590bf7d1ca971/staging
    


It worked!
~~~~~~~~~~

Congratulations, you put the potatoes on the internet! You’re probably
already a legend in Ireland!


Creating more nodes
~~~~~~~~~~~~~~~~~~~

Now that you have a working example of a simple chef you can extend it
by adding more content types.

-  Complete the ricecooker hands-on tutorial:
   https://gist.github.com/jayoshih/6678546d2a2fa3e7f04fc9090d81aff6
-  `usage
   docs <https://ricecooker.readthedocs.io/en/latest/usage.html>`__ for
   more explanations about the above code.
-  See
   `nodes <https://ricecooker.readthedocs.io/en/latest/nodes.html>`__ to
   learn how to create different kinds of content nodes.
-  See
   `files <https://ricecooker.readthedocs.io/en/latest/files.html>`__ to
   learn about the file types supported, and how to create them.

