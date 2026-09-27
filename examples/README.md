Complete script examples
========================

This directory contains examples of `ricecooker` content integration scripts (sushi chefs).

  - [`gettingstarted`](./gettingstarted)/[`sushichef.py`](./gettingstarted/sushichef.py)
    is a basic "Hello, World!" example used in the [Getting started](https://ricecooker.readthedocs.io/en/latest/gettingstarted.html) guide.
  - [`tutorial`](./tutorial)/[`sushichef.py`](./tutorial/sushichef.py) goes with the
    [tutorial](https://ricecooker.readthedocs.io/en/latest/tutorial/tutorial.html) and adds a document, a video and an audio file.
  - [`wikipedia`](./wikipedia)/[`sushichef.py`](./wikipedia/sushichef.py) builds a channel from two Wikipedia list pages.
  - [`pagearchive`](./pagearchive)/[`sushichef.py`](./pagearchive/sushichef.py) archives a JavaScript web page into an offline HTML5 zip.
  - [`studiocontent`](./studiocontent)/[`sushichef.py`](./studiocontent/sushichef.py) curates nodes from a channel already on Studio into a new channel.
  - [`curriculum_courses`](./curriculum_courses)/[`sushichef.py`](./curriculum_courses/sushichef.py) builds a course channel from `content.json`.

To run each of these, you'll need to edit `CHANNEL_SOURCE_DOMAIN` and `CHANNEL_SOURCE_ID`
in the chef's `channel_info` and then call it on the command line:

    git clone https://github.com/learningequality/ricecooker.git
    cd ricecooker/examples/examplename
    # Follow the instructions in the README.md file...
    # ...then run the sushichef script by calling:
    python sushichef.py --token=YOURSTUDIOTOKENHERE9139139f3a23232


Further reading
---------------
  - See the [examples](https://ricecooker.readthedocs.io/en/latest/examples/)
    page in the ricecooker docs site for more code samples related to specific tasks.
  - See also the [sample-channels](https://github.com/learningequality/sample-channels)
    repository which contains even more examples that cover special cases and needs.
