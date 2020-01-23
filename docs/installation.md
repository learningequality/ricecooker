Installation
============
The `ricecooker` library is published as a Python3-only [package on PyPI](https://pypi.python.org/pypi/ricecooker).


Software prerequisites
----------------------
The `ricecooker` library requires Python 3.5+ and the additional conversion tools
`ImageMagic` for thumbnail generation and `ffmpeg` for video compression.
Additionally we'll assume you have also installed the `git` version control system.


### Linux
On a Debian or Ubuntu GNU/Linux, you can install the necessary packages using:

    apt-get install build-essential gettext pkg-config linux-tools-generic python3-tk \
        python3 python3-dev python3-pip virtualenv \
        libxft-dev libwebp-dev libmagickwand-dev \
        ffmpeg

For other Linux distributions (ContOS/Fedora/OpenSuSE) look for the the package
`ImageMagick-devel` and install the latest python 3.x version available.


### Mac
Mac OS X users can install the necessary software using [Homebrew](https://brew.sh/):

    brew install git python3 imagemagick@6 ffmpeg
    brew link --force imagemagick@6

Note you need `imagemagick@6` and not the new version 7, which has a different API.


### Windows
On Windows the process is a little more complicated since it requires manual
downloading of each of the tools and making sure they appear the `Path` variable:

1. Download and install Git Bash from [https://git-scm.com/downloads](https://git-scm.com/downloads).
   During the installation, choose the "add shortcut to Desktop" checkbox option.
   You must use the "Git Bash" command prompt to have access to `git` and other
   command line tools.
     - **Checklist**: open "Git Bash" and try typing in `git -h` and `ssh -h` to verify the
       commands `git` and `ssh` are available.
2. Download Python from [https://www.python.org/downloads/windows/](https://www.python.org/downloads/windows/).
   Look under the Python 3.7.x heading and choose the "Windows x86-64 executable installer"
   option to download the latest installer and follow usual installation steps.
   During the installation, make sure to check the box "Add Python 3.7 to path".
     - **Checklist**: after installation, open a new Git Bash terminal and type in
       `python --version` and `pip --version` to make sure the commands are available.
3. Download `ffmpeg` from [https://ffmpeg.zeranoe.com/builds/](https://ffmpeg.zeranoe.com/builds/).
   Choose the static option then click `Download Build` to download the zip archive.
   Extract the zip file to a permanent location where you store your code,
   like `C:\Users\User\Projects` for example. Next, you must add the `bin` folder
   that contains `ffmpeg` (e.g. `C:\Users\User\Projects\ffmpeg-4.1.4-win64-static\bin`)
   to your user Path variable following [these instructions](https://www.computerhope.com/issues/ch000549.htm).
     - **Checklist**: Open a new Git Bash terminal and type in `ffmpeg -h` and `ffprobe -h`
       to verify the commands `ffmpeg` and `ffprobe` are available on your Path.
4. Download the ImageMagic **version 6** from [https://imagemagick.org/download/binaries/](https://imagemagick.org/download/binaries/)
   Choose the latest 6.x version that contains `-Q16-x86-static` in its name,
   like [https://imagemagick.org/download/binaries/ImageMagick-6.9.10-58-Q16-x86-static.exe](https://imagemagick.org/download/binaries/ImageMagick-6.9.10-58-Q16-x86-static.exe).
     - **Checklist**: after installation completes, open a Git Bash terminal and
       type in `convert -h` to make sure the command `convert` is available.

At this point you will have a working Python installation on your system, and
all the software tools necessary to write and run `ricecooker` scripts.



Installing the `ricecooker` package
-----------------------------------
To install `ricecooker` globally for your system Python installation, run this command in your terminal:

    pip install ricecooker

If you prefer to maintain an installation for each chef repo, then read on.

This is the preferred method to install `ricecooker`, as it will always install
the most recent stable release. 

Note: The recommended best practice is to keep the code associated with each
sushichef script in a separate Python `virtualenv` specific for that project,
rather that globally for your system Python installation. To learn how to create
Python virtual environment see [these docs](https://virtualenv.pypa.io/en/stable/userguide/).

Usually a chef repo will define a `requirements.txt` file that lists what packages
must be installed for the chef to run and `ricecooker` can be specified there
and installation of all required packages performed using:

    cd Projects/sushi-chef-{source_name}      # cd into the chef repo
    virtualenv -p python3 venv                # initialize Python virtual environment
    source venv/bin/activate                  # go into the virtualenv `venv`
    pip install -r requirements.txt           # install a list of python packages



### Reporting issues
If you run into problems or errores while following the above instructions,
please let us know by [opening an issue on github](https://github.com/learningequality/ricecooker/issues)
and specifying which operating system and Python version you're using.
Also if you can report the outputs you see from all the "Checklist" items in 
the section **Software prerequisites** would be helpful to include when filing the issue.










For `ricecooker` developers
---------------------------
The code for the `ricecooker` library [lives on github](https://github.com/learningequality/ricecooker).
You can clone this repo using this command:

    git clone git://github.com/learningequality/ricecooker

which will download all the source code for the `ricecooker` library and allow
you to modify its functionality.



### Other installation options

You can install `ricecooker` directly from github using the following command:

    pip install git+https://github.com/learningequality/ricecooker

Occasionally, you'll want to install a `ricecooker` version from a specific branch,
instead of the default branch version. This is the way to do this:

    pip install -U git+https://github.com/learningequality/ricecooker@somebranchname

The `-U` flag forces the update instead of reusing any previously cached version.


### Install editable source code
Another option for installing `ricecooker` is to clone the repo and install using

    git clone git://github.com/learningequality/ricecooker
    cd ricecooker
    pip install -e .

The flag `-e` installs `ricecooker` in "editable mode," which means you can now
make changes to the source code and you'll see the changes reflected immediately.
This installation method very useful if you're working around a bug in `ricecooker`
or extending the crawling/scraping/http/html utilities in `ricecooker/utils/`.


### Code contributions
The `ricecooker` project is open for code, testing, and documentation contributions.
The `ricecooker.utils` package is constantly growing with new helper methods that
simplify various aspects of the content extraction, transformations, and upload to Studio.
If you figured out how to fix a `ricecooker` bug or added some new functionality
that you would like to share with the community, please open a
[pull request](https://github.com/learningequality/ricecooker/pulls).


