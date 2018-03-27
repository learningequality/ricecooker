Installation
============
The `ricecooker` library is published as a Python3-only [package on PyPI](https://pypi.python.org/pypi/ricecooker).


Software prerequisites
----------------------
The `ricecooker` library requires Python 3.5+ and some additional tools like
`ffmpeg` for video compression, and `phantomjs` for scraping webpages that
require JavaScript to run before the DOM is rendered.

On a Debian-like linux box, you can install all the necessary packages using:

    apt-get install build-essential gettext pkg-config \
        python3 python3-pip python3-dev python3-virtualenv virtualenv python3-tk \
        linux-tools libfreetype6-dev libxft-dev libwebp-dev libjpeg-dev libmagickwand-dev \
        ffmpeg phantomjs

Mac OS X users can install the necessary software using Homebrew:

    brew install freetype imagemagick@6 ffmpeg phantomjs
    brew link --force imagemagick@6



Stable release
--------------
To install `ricecooker`, run this command in your terminal:

    pip install ricecooker

This is the preferred method to install `ricecooker`, as it will always install
the most recent stable release.

If you don't have `pip` installed, then this
[Python installation guide](http://docs.python-guide.org/en/latest/starting/installation/)
will guide you through the process of setting up.

Note: We recommend you install `ricecooker` in a Python `virtualenv` specific for
cheffing work, rather that globally for your system python. For information about
creating and activating a virtualenv, you can follow the instructions provided
[here](http://kolibri-dev.readthedocs.io/en/develop/start/getting_started.html#virtual-environment).



Install from github
-------------------
You can install `ricecooker` directly from the [github repo](https://github.com/learningequality/ricecooker)
using the following command:

    pip install git+https://github.com/learningequality/ricecooker

Occasionally, you'll want to install a `ricecooker` version from a specific branch,
instead of the default branch version. This is the way to do this:

    pip install -U git+https://github.com/learningequality/ricecooker@somebranchname

The `-U` flag forces the update instead of reusing any previously installed/cached versions.


Install from source
-------------------
Another option for installing `ricecooker` is to clone the repo and install using:

    git clone git://github.com/learningequality/ricecooker
    cd ricecooker
    pip install -e .

The flag `-e` installs `ricecooker` in "editable mode," which means you can now
make changes to the source code and you'll see the changes reflected immediately.
This installation method very useful if you're working around a bug in `ricecooker`
or extending the crawling/scraping/http/html utilities in `ricecooker/utils/`.

Speaking of bugs, if you ever run into problems while using `ricecooker`, you should
let us know by [opening an issue](https://github.com/learningequality/ricecooker/issues).

