Complete script examples
========================

This directory contains examples of `ricecooker` content integration scripts (sushi chefs).

  - [`gettingstarted`](./gettingstarted)/[`sushichef.py`](./gettingstarted/sushichef.py)
    is a basic "Hello, World!" example used in the [Getting started](https://ricecooker.readthedocs.io/en/latest/gettingstarted.html) guide.
  - `tutorial/sushichf.py` the code that goes with the sushi chef tutorial doc
    https://docs.google.com/document/d/1iiwce8B_AyJ2d6K8dYBl66n9zjz0zQ3G4gTrubdk9ws/edit
  - `kitchensink/sushichef.py` is a comprehensive example that creates audio, video, and exercise nodes.
  - `wikipedia/sushichef.py` an example that creates a channel from two Wikipedia categories

To run each of these, you you'll need to edit the `SOURCE_DOMAIN` and `SOURCE_ID`
in each chef script and then call them on the command line:

    git clone https://github.com/learningequality/ricecooker.git
    cd ricecooker/examples/examplename
    # Follow the instructions in the README.md file...
    # ...then run the sushichef script by calling:
    python suschief.py --token=YOURSTUDIOTOKENHERE9139139f3a23232


Further reading
---------------
  - See the [examples](https://ricecooker.readthedocs.io/en/latest/examples/)
    page in the ricecooker docs site for more code samples related to specific tasks.
  - See also the [sample-channels](https://github.com/learningequality/sample-channels)
    repository which contains even more examples that cover special cases and needs.
