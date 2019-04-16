
Languages
=========

This tutorial will explain how to set the ``language`` property for
various nodes and file objects when using the ``ricecooker`` framework.



Explore language objects and language codes
-------------------------------------------

First we must import the ``le-utils`` pacakge. The languages supported
by Kolibri and the Content Curation Server are provided in
``le_utils.constants.languages``.

.. code:: python

    from le_utils.constants import languages as languages
    
    
    # can lookup language using language code
    language_obj = languages.getlang('en')
    language_obj




.. parsed-literal::

    Language(native_name='English', primary_code='en', subcode=None, name='English', ka_name=None)



.. code:: python

    # can lookup language using language name (the new le_utils version has not shipped yet)
    language_obj = languages.getlang_by_name('English')
    language_obj




.. parsed-literal::

    Language(native_name='English', primary_code='en', subcode=None, name='English', ka_name=None)



.. code:: python

    # all `language` attributed (channel, nodes, and files) need to use language code
    language_obj.code




.. parsed-literal::

    'en'



.. code:: python

    from le_utils.constants.languages import getlang_by_native_name
    
    lang_obj = getlang_by_native_name('français')
    print(lang_obj)
    print(lang_obj.code)



.. parsed-literal::

    Language(native_name='Français, langue française', primary_code='fr', subcode=None, name='French', ka_name='francais')
    fr


The above language code is an internal representaiton that uses
two-letter codes, and sometimes has a locale information, e.g.,
``pt-BR`` for Brazilian Portuiguese. Sometimes the internal code
representaiton for a language is the three-letter vesion, e.g., ``zul``
for Zulu.


Create chef class
-----------------

We now create subclass of ``ricecooker.chefs.SushiChef`` and defined its
``get_channel`` and ``construct_channel`` methods.

For the purpose of this example, we'll create three topic nodes in
different languages that contain one document in each.

.. code:: python

    from ricecooker.chefs import SushiChef
    from ricecooker.classes.nodes import ChannelNode, TopicNode, DocumentNode
    from ricecooker.classes.files import DocumentFile
    from le_utils.constants import languages
    from le_utils.constants import licenses
    
    
    class MySushiChef(SushiChef):
        """
        A sushi chef that creates a channel with content in EN, FR, and SP.
        """
        def get_channel(self, **kwargs):
            channel = ChannelNode(
                source_domain='testing.org',
                source_id='lang_test_chanl',
                title='Languages test channel',
                thumbnail='http://themes.mysitemyway.com/_shared/images/flags.png',
                language = languages.getlang('en').code   # set global language for channel (will apply as default option to all content items in this channel)
            )
            return channel
    
        def construct_channel(self, **kwargs):
            # create channel
            channel = self.get_channel(**kwargs)
    
            # create the English topic, add a DocumentNode to it
            topic = TopicNode(
                source_id="<en_topic_id>",
                title="New Topic in English",
                language=languages.getlang('en').code,
            )
            doc_node = DocumentNode(
                source_id="<en_doc_id>",
                title='Some doc in English',
                description='This is a sample document node in English',
                files=[DocumentFile(path='samplefiles/documents/doc_EN.pdf')],
                license=licenses.PUBLIC_DOMAIN,
                language=languages.getlang('en').code,
            )
            topic.add_child(doc_node)
            channel.add_child(topic)
    
            # create the Spanish topic, add a DocumentNode to it
            topic = TopicNode(
                source_id="<es_topic_id>",
                title="Topic in Spanish",
                language=languages.getlang('es-MX').code,
            )
            doc_node = DocumentNode(
                source_id="<es_doc_id>",
                title='Some doc in Spanish',
                description='This is a sample document node in Spanish',
                files=[DocumentFile(path='samplefiles/documents/doc_ES.pdf')],
                license=licenses.PUBLIC_DOMAIN,
                language=languages.getlang('es-MX').code,
            )
            topic.add_child(doc_node)
            channel.add_child(topic)
    
            # create the French topic, add a DocumentNode to it
            topic = TopicNode(
                source_id="<fr_topic_id>",
                title="Topic in French",
                language=languages.getlang('fr').code,
            )
            doc_node = DocumentNode(
                source_id="<fr_doc_id>",
                title='Some doc in French',
                description='This is a sample document node in French',
                files=[DocumentFile(path='samplefiles/documents/doc_FR.pdf')],
                license=licenses.PUBLIC_DOMAIN,
                language=languages.getlang('fr').code,
            )
            topic.add_child(doc_node)
            channel.add_child(topic)
    
            return channel


Run of you chef by creating an instance of the chef class and calling
it's ``run`` method:

.. code:: python

    mychef = MySushiChef()
    args = {'token': 'YOURTOKENHERE9139139f3a23232',
            'reset': True,
            'verbose': True,
            'publish': True}
    options = {}
    mychef.run(args, options)


.. parsed-literal::

    Logged in with username you@yourdomain.org
    Ricecooker v0.6.19 is up-to-date.
    Running get_channel... 
    run_id: 27a7726c4b2b418fb0f7b1842f6abe84
    
    
    ***** Starting channel build process *****
    
    
    Calling construct_channel... 
       Setting up initial channel structure... 
       Validating channel structure...
          Languages test channel (ChannelNode): 6 descendants
             New Topic in English (TopicNode): 1 descendant
                Some doc in English (DocumentNode): 1 file
             Topic in Spanish (TopicNode): 1 descendant
                Some doc in Spanish (DocumentNode): 1 file
             Topic in French (TopicNode): 1 descendant
                Some doc in French (DocumentNode): 1 file
       Tree is valid
    
    Downloading files...
    Processing content...
    	--- Downloaded e8b1fe37ce3da500241b4af4e018a2d7.pdf
    	--- Downloaded cef22cce0e1d3ba08861fc97476b8ccf.pdf
    	--- Downloaded 6c8730e3e2554e6eac0ad79304bbcc68.pdf
    	--- Downloaded de498249b8d4395a4ef9db17ec02dc91.png
       All files were successfully downloaded
    Getting file diff...
    
    Checking if files exist on Kolibri Studio...
    	Got file diff for 4 out of 4 files
    Uploading files...
    
    Uploading 0 new file(s) to Kolibri Studio...
    Creating channel...
    
    Creating tree on Kolibri Studio...
       Creating channel Languages test channel
    	Preparing fields...
    (0 of 6 uploaded)    Processing Languages test channel (ChannelNode)
    (3 of 6 uploaded)       Processing New Topic in English (TopicNode)
    (4 of 6 uploaded)       Processing Topic in Spanish (TopicNode)
    (5 of 6 uploaded)       Processing Topic in French (TopicNode)
       All nodes were created successfully.
    Upload time: 6.641212s
    Publishing channel...
    
    Publishing tree to Kolibri... 
    
    
    DONE: Channel created at https://contentworkshop.learningequality.org/channels/cba91822d3ab5a748cd19532661d690f/edit
    


Congratulations, you put three languages on the internet!



Example 2: YouTube video with subtitles in multiple languages
-------------------------------------------------------------

You can use the library ``youtube_dl`` to get lots of useful metadata
about videos and playlists, including the which language subtitle are
vailable for a video.

.. code:: python

    import youtube_dl
    
    ydl = youtube_dl.YoutubeDL({
        'quiet': True,
        'no_warnings': True,
        'writesubtitles': True,
        'allsubtitles': True,
    })
    
    
    youtube_id =  'FN12ty5ztAs'
    
    info = ydl.extract_info(youtube_id, download=False)
    subtitle_languages = info["subtitles"].keys()
    
    print(subtitle_languages)


.. parsed-literal::

    dict_keys(['en', 'fr', 'zu'])



Full sushi chef example
~~~~~~~~~~~~~~~~~~~~~~~

The ``YoutubeVideoWithSubtitlesSushiChef`` class below shows how to
create a channel with youtube video and upload subtitles files with all
available languages.

.. code:: python

    from ricecooker.chefs import SushiChef
    from ricecooker.classes import licenses
    from ricecooker.classes.nodes import ChannelNode, TopicNode, VideoNode
    from ricecooker.classes.files import YouTubeVideoFile, YouTubeSubtitleFile
    from ricecooker.classes.files import is_youtube_subtitle_file_supported_language
    
    
    import youtube_dl
    ydl = youtube_dl.YoutubeDL({
        'quiet': True,
        'no_warnings': True,
        'writesubtitles': True,
        'allsubtitles': True,
    })
    
    
    # Define the license object with necessary info
    TE_LICENSE = licenses.SpecialPermissionsLicense(
        description='Permission granted by Touchable Earth to distribute through Kolibri.',
        copyright_holder='Touchable Earth Foundation (New Zealand)'
    )
    
    
    class YoutubeVideoWithSubtitlesSushiChef(SushiChef):
        """
        A sushi chef that creates a channel with content in EN, FR, and SP.
        """
        channel_info = {
            'CHANNEL_SOURCE_DOMAIN': 'learningequality.org',        # change me!
            'CHANNEL_SOURCE_ID': 'sample_youtube_video_with_subs',  # change me!
            'CHANNEL_TITLE': 'Youtube subtitles downloading chef',
            'CHANNEL_LANGUAGE': 'en',
            'CHANNEL_THUMBNAIL': 'http://themes.mysitemyway.com/_shared/images/flags.png',
            'CHANNEL_DESCRIPTION': 'This is a test channel to make sure youtube subtitle languages lookup works'
        }
    
        def construct_channel(self, **kwargs):
            # create channel
            channel = self.get_channel(**kwargs)
    
            # get all subtitles available for a sample video
            youtube_id =  'FN12ty5ztAs'
            info = ydl.extract_info(youtube_id, download=False)
            subtitle_languages = info["subtitles"].keys()
            print('Found subtitle_languages = ', subtitle_languages)
            
            # create video node
            video_node = VideoNode(
                source_id=youtube_id,
                title='Youtube video',
                license=TE_LICENSE,
                derive_thumbnail=True,
                files=[YouTubeVideoFile(youtube_id=youtube_id)],
            )
    
            # add subtitles in whichever languages are available.
            for lang_code in subtitle_languages:
                if is_youtube_subtitle_file_supported_language(lang_code):
                    video_node.add_file(
                        YouTubeSubtitleFile(
                            youtube_id=youtube_id,
                            language=lang_code
                        )
                    )
                else:
                    print('Unsupported subtitle language code:', lang_code)
    
            channel.add_child(video_node)
    
            return channel
    
        

.. code:: python

    chef = YoutubeVideoWithSubtitlesSushiChef()
    args = {'token': 'YOURTOKENHERE9139139f3a23232',
            'reset': True,
            'verbose': True,
            'publish': True}
    options = {}
    chef.run(args, options)


.. parsed-literal::

    Logged in with username you@yourdomain.org
    Ricecooker v0.6.19 is up-to-date.
    Running get_channel... 
    run_id: 682e56ae42c246eb8c307bae35122e9e
    
    
    ***** Starting channel build process *****
    
    
    Calling construct_channel... 


.. parsed-literal::

    Found subtitle_languages =  dict_keys(['en', 'fr', 'zu'])


.. parsed-literal::

       Setting up initial channel structure... 
       Validating channel structure...
          Youtube subtitles downloading chef (ChannelNode): 1 descendant
             Youtube video (VideoNode): 4 files
       Tree is valid
    
    Downloading files...
    Processing content...
    	--- Downloaded (YouTube) 987257c13adb6d2f2c86849be6031a4c.mp4
    	--- Downloaded subtitle f589321457f81efd035bb72cb57a1b3b.vtt
    	--- Downloaded subtitle 99d24a5240d64e505a6343f50f851d2e.vtt
    	--- Downloaded subtitle a1477da82f45e776b7f889b67358e761.vtt
    	--- Extracted thumbnail 2646f5028c7925c0d304c709d39cf5b0.png
    	--- Downloaded de498249b8d4395a4ef9db17ec02dc91.png
       All files were successfully downloaded
    Getting file diff...
    
    Checking if files exist on Kolibri Studio...
    	Got file diff for 6 out of 6 files
    Uploading files...
    
    Uploading 0 new file(s) to Kolibri Studio...


