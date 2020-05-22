Examples
========

Below are some examples that demonstrate certain aspects of the content integration
process that require careful consideration and are best explained in code:


.. toctree::
   :titlesonly:

   Learn how to work with language codes <languages>
   How to create exercises and questions <exercises>
   Document conversions <document_conversion>
   Step-by-step tutorial <https://github.com/learningequality/ricecooker/blob/master/examples/tutorial/sushichef.py>
   Wikipedia scraping example <https://github.com/learningequality/ricecooker/blob/master/examples/wikipedia/sushichef.py>
   Kitchen sink example that includes all content kinds <https://github.com/learningequality/sample-channels/blob/master/channels/ricecooker_channel/sushichef.py>


Jupyter notebooks
-----------------
Jypyter notebooks are a very powerful tool for interactive programming.
You type in commands into an online shell, and you immediately see the results.

To install jupyter notebook on your machine, you run:

.. code::

    pip install jupyter

then to start the jupyter notebook server, run

.. code::

    jupyter notebook

If you then navigate to the directory `docs/examples/` in the ricecooker source
code repo, you'll find the same examples described above in the form of runnable
notebooks that will allow you to experiment and learn hands-on.


You'll need to press CTRL+C in the terminal to stop the jupyter notebook server,
or use the Shutdown button in the web interface.

Watch the beginning of this `Video tutorial <http://35.196.115.213/en/learn/#/topics/c/1ef68d0dcb52555f9b63f15f36f77b54>`__
to learn how to use the Jypyter notebook environment for interactively coding parts of the chef logic.

.. raw:: html

   <a href="http://35.196.115.213/en/learn/#/topics/c/1ef68d0dcb52555f9b63f15f36f77b54" target="_blank">
   <iframe width="560" height="315" src="https://www.youtube.com/embed/vnMCeHQYcBU" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
   </a>
   <div style="height:60px;">&nbsp;</div>


Advanced examples
-----------------
The links below will take you to the GitHub repositories of content integration
scripts we use to create some of the most popular Kolibri channels in the library:

* `Khan Academy chef <https://github.com/learningequality/sushi-chef-khan-academy>`__
* `Open Stax chef <https://github.com/learningequality/sushi-chef-openstax>`__
* `SHLS Toolkit chef <https://github.com/learningequality/sushi-chef-shls>`__

You can get a list of ALL the content integration scripts by searching for
`sushi-chef <https://github.com/learningequality?q=sushi-chef&type=public&language=python>`__
on GitHub.
