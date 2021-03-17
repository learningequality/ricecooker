Installation
============

You can install `ricecooker` by running the command `pip install ricecooker`,
which will install the Python package and all its Python dependencies.
You'll need version 3.5 or higher of Python to use the `ricecooker` framework,
as well as some software for media file conversions (`ffmpeg` and  `poppler`).

In the next fifteen minutes or so, we'll setup your computer with all these things
so you can get started writing your first content integration scripts.


System prerequisites
--------------------
The first step will will be to make sure you have `python3` installed on your
computer and two additional file conversion tools: `ffmpeg` for video compression,
and the `poppler` library for manipulating PDFs.

Jump to the specific instructions for your operating system, and be sure to try
the *Checklist* commands to know the installation was successful.


### Linux
On a Debian or Ubuntu GNU/Linux, you can install the necessary packages using:

    sudo apt-get install  git python3 ffmpeg poppler-utils

You may need to adjust the package names for other Linux distributions (ContOS/Fedora/OpenSuSE).

*Checklist*: verify your python version is 3.5 or higher by running `python3 --version`.
If no `python3` command exists, then try `python --version`.
Run the commands `ffmpeg -h` and `pdftoppm -h` to make sure they are available.


### Mac
Mac OS X users can install the necessary software using [Homebrew](https://brew.sh/):

    brew install  git python3 ffmpeg poppler

*Checklist*: verify you python version is 3.5 or higher by running `python3 --version`.
Also run the commands `ffmpeg -h` and `pdftoppm -h` to make sure they are available.



### Windows
On windows the process is a little longer since we'll have to download and install
several programs and make sure their `bin`-directories are added to the `Path` variable:

1. Download Python from [https://www.python.org/downloads/windows/](https://www.python.org/downloads/windows/).
   Look under the **Python 3.7.x** heading and choose the "Windows x86-64 executable installer"
   option to download the latest installer and follow usual installation steps.
   During the installation, make sure to check the box **"Add Python 3.7 to path"**.
     - *Checklist*: after installation, open a new command prompt (`cmd.exe`) and
       type in `python --version` and `pip --version` to make sure the commands are available.
2. Download `ffmpeg` from [https://web.archive.org/web/20200918193047/https://ffmpeg.zeranoe.com/builds/](https://web.archive.org/web/20200918193047/https://ffmpeg.zeranoe.com/builds/).
   Choose the static option then click `Download Build` to download the zip archive.
   Extract the zip file to a permanent location where you store your code,
   like `C:\Users\User\Tools` for example. Next, you must add the `bin` folder
   that contains `ffmpeg` (e.g. `C:\Users\User\Tools\ffmpeg-4.1.4-win64-static\bin`)
   to your user Path variable following [these instructions](https://www.computerhope.com/issues/ch000549.htm).
     - *Checklist*: Open a new command prompt and type in `ffmpeg -h` and `ffprobe -h`
       to verify the commands `ffmpeg` and `ffprobe` are available on your Path.
3. Download the file linked under "Latest binary" from [poppler-windows](http://blog.alivate.com.au/poppler-windows/).
   You will need to download and install [7-zip](https://www.7-zip.org/) to "unzip"
   the `.7z` archive. Extract the file to a some permanent location in your files.
   Add the `bin` folder `poppler-0.xx.y\bin` to your Path variable.
     - *Checklist*: after installation, open a command terminal and type in
       `pdftoppm -h` to make sure the command `pdftoppm` is available.

We recommend you also download and install Git from [https://git-scm.com/downloads](https://git-scm.com/downloads).
Using git is not a requirement for the getting started, but it's a great tool to
have for borrowing code from others and sharing back your own code on the web.

If you find the text descriptions to be confusing, you can watch this
[video walkthrough](http://youtube.com/watch?v=LxK8_BOSy-8) that shows the
installation steps and also explains the adding-to-Path process.


<iframe width="560" height="315" src="https://www.youtube.com/embed/LxK8_BOSy-8" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
<div style="height:50px;">&nbsp;</div>



Installing Ricecooker
---------------------
To install the `ricecooker` package, simply run this command in a command prompt:

    pip install ricecooker

You will see lots of lines scroll on the screen as `pip`, the package installer for Python,
installs all the Python packages required to create content integration scripts.

**Reporting issues**: If you run into problems or encounter an error in any of the above steps,
please let us know by [opening an issue on github](https://github.com/learningequality/ricecooker/issues).

------

Okay so now we have all the system software and Python libraries installed.
[Let's get started!](tutorial/gettingstarted.html)
