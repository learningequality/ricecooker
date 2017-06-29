Example sushi chef scripts
==========================

This directory contains examples of sushi chef scripts that use the `ricecooker`.

  - `tutorial_chef.py` the code that goes along with the suchi chef tutorial doc
    https://docs.google.com/document/d/1iiwce8B_AyJ2d6K8dYBl66n9zjz0zQ3G4gTrubdk9ws/edit
  - `sample_program.py` an example that creates audio, video, and exercise nodes.
  - `wikipedia_chef.py` an example that creates a channel from all the pages in
    two Wikipedia categories
  - `large_wikipedia_chef.py` a chef that builds a large chef and takes a long
    time to run (used for performance optimizations).

To run each of these, you'll need to edit the `SOURCE_DOMAIN` and `SOURCE_ID`
in each chef script and then call them on the command line:

    ./chef_name.py -v --token=YOURTOKENHERE9139139f3a23232


See also the jupyter notebooks in [docs/tutorial/][../docs/turorial].
