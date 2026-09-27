Wikipedia example
=================

The content integration script `sushichef.py` reads two Wikipedia list pages
and adds each linked article as a `ContentNode(uri=...)`. Ricecooker archives
every article headlessly into an HTML5 zip, which needs single-file-cli and
Chromium; see the [page archiving example](../pagearchive/README.md).


## Running the script

    ./sushichef.py   --token=YOURSTUDIOTOKENHERE9139139f3a23232
