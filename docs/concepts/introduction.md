Kolibri content ecosystem overview
==================================

Educational content in the Kolibri platform is organized into **content channels**.
The `ricecooker` framework is used for creating content channels and uploading them
to [Kolibri Studio](https://studio.learningequality.org/), which is the central
content server that [Kolibri](https://learningequality.org/kolibri/) applications
talk to when importing their content.

Content flow within the Kolibri ecosystem is pictured below.

![The Kolibri Content Pipeline](../figures/content_pipeline_diagram.png)

This `ricecooker` framework is the main tool used to facilitate **Integration Method 2**.



Kolibri channels
----------------
A Kolibri channel is the combination of a topic tree (a nested folder structure)
and number of self-contained "content items" packaged for offline use and distribution.
Each content item within the channel is represented as a content node with one
or more files associated with it. In summary, a channel is a nested structure of
`TopicNodes` (folders) that contain `ContentNode` objects similar to how files
are organized into folders on computers.

The Kolibri channel is the fundamental structure common to all parts of the Kolibri ecosystem:
the Kolibri Learning Platform is where Kolibri channels are used by learners and teachers,
Kolibri Studio is the editor for Kolibri Channels (think five Rs),
and Ricecooker scripts are used for content integrations that pull in OER from
external sources, package them for offline use, and upload them to Kolibri Studio.


Supported content kinds
-----------------------
Kolibri channels are tree-like structures that consist of the following types of nodes:

  * **Topic nodes** (folders): the nested folders structure is the is main way of
    representing structured content in Kolibri. Depending on the particular channel,
    a topic node could be a language, a subject, a course, a unit, a module, a section,
    a lesson, or any other structural element. Rather than impose a particular fixed structure,
    we let educators decide the folder structure that is best suited for the learners needs.

  * **Content nodes**:

     - Document (either an `epub` or a `pdf` file)
     - Audio (`mp3` files of audio lessons, audiobooks, podcasts, radio shows, etc.)
     - Video (`mp4` files with `h264` video codec and `aac` audio codec)
     - HTML5App (`zip` files containing web content like HTML, JavaScript, css and images)
     - H5PApp (self-contained `h5p` files)
     - Slideshow (a sequence of `jpg` and `png` slide images)
     - Exercises containing questions like multiple choice, multiple selection, and numeric inputs


Further reading
---------------
  - [Kolibri channel](https://kolibri.readthedocs.io/en/latest/manage/resources.html#channels-and-resources)
    as explained in the Kolibri documentation.
  - [Kolibri Studio User Guide](https://kolibri-studio.readthedocs.io/en/latest/index.html)
