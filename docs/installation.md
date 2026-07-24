Installation
============

Ricecooker chef scripts are typically developed inside their own project, managed
with [`uv`](https://docs.astral.sh/uv/). Add `ricecooker` as a dependency in your
chef project's `pyproject.toml` and run `uv sync` to install it and its Python
dependencies. You'll need Python 3.10-3.14 (matching `ricecooker`'s supported
range), as well as some software for file conversions: `ffmpeg` and `poppler` for
media, and `pandoc` for converting documents (`.docx`, `.odt`, `.rtf`, `.md`) to KPUB.

In the next fifteen minutes or so, we'll setup your computer with all these things
so you can get started writing your first content integration scripts.


System prerequisites
--------------------
The first step will will be to make sure you have `python3` installed on your
computer and three additional file conversion tools: `ffmpeg` for video compression,
the `poppler` library for manipulating PDFs, and `pandoc` for converting article-style
documents (`.docx`, `.odt`, `.rtf`, `.md`, `.markdown`) to KPUB.

Jump to the specific instructions for your operating system, and be sure to try
the *Checklist* commands to know the installation was successful.


### Linux
On a Debian or Ubuntu GNU/Linux, you can install the necessary packages using:

    sudo apt-get install  git python3 ffmpeg poppler-utils pandoc

You may need to adjust the package names for other Linux distributions (ContOS/Fedora/OpenSuSE).

*Checklist*: verify your python version is between 3.10 and 3.14 by running `python3 --version`.
If no `python3` command exists, then try `python --version`.
Run the commands `ffmpeg -h`, `pdftoppm -h`, and `pandoc -v` to make sure they are available.


### Mac
Mac OS X users can install the necessary software using [Homebrew](https://brew.sh/):

    brew install  git python3 ffmpeg poppler pandoc

*Checklist*: verify your python version is between 3.10 and 3.14 by running `python3 --version`.
Also run the commands `ffmpeg -h`, `pdftoppm -h`, and `pandoc -v` to make sure they are available.



### Windows
On windows the process is a little longer since we'll have to download and install
several programs and make sure their `bin`-directories are added to the `Path` variable:

1. Download Python from [https://www.python.org/downloads/windows/](https://www.python.org/downloads/windows/).
   Look under a supported **Python 3.10.x** (or newer, up to 3.14) heading and choose the "Windows x86-64 executable installer"
   option to download the latest installer and follow usual installation steps.
   During the installation, make sure to check the box **"Add Python to PATH"**.
     - *Checklist*: after installation, open a new command prompt (`cmd.exe`) and
       type in `python --version` and `pip --version` to make sure the commands are available.
2. Download `ffmpeg` from [https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip](https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip).
   Extract the zip file to a permanent location where you store your code,
   like `C:\Users\User\Tools` for example. Next, you must add the `bin` folder
   that contains `ffmpeg` (e.g. `C:\Users\User\Tools\ffmpeg-4.1.4-win64-static\bin`)
   to your user Path variable following [these instructions](https://www.computerhope.com/issues/ch000549.htm).
     - *Checklist*: Open a new command prompt and type in `ffmpeg -h` and `ffprobe -h`
       to verify the commands `ffmpeg` and `ffprobe` are available on your Path.
3. Download the latest release archive from [poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases/).
   You will need to download and install [7-zip](https://www.7-zip.org/) to "unzip"
   the `.7z` archive. Extract the file to a some permanent location in your files.
   Add the `bin` folder `poppler-0.xx.y\bin` to your Path variable.
     - *Checklist*: after installation, open a command terminal and type in
       `pdftoppm -h` to make sure the command `pdftoppm` is available.
4. Install `pandoc` for converting documents to KPUB. The simplest option is the
   MSI installer from [https://github.com/jgm/pandoc/releases](https://github.com/jgm/pandoc/releases),
   which adds `pandoc` to your Path automatically; alternatively run
   `choco install pandoc` if you use [Chocolatey](https://chocolatey.org/).
     - *Checklist*: open a new command prompt and type in `pandoc -v` to make sure
       the command `pandoc` is available on your Path.

We recommend you also download and install Git from [https://git-scm.com/downloads](https://git-scm.com/downloads).
Using git is not a requirement for the getting started, but it's a great tool to
have for borrowing code from others and sharing back your own code on the web.

If you find the text descriptions to be confusing, you can watch this
[video walkthrough](http://youtube.com/watch?v=LxK8_BOSy-8) that shows the
installation steps and also explains the adding-to-Path process.


<iframe width="560" height="315" src="https://www.youtube.com/embed/LxK8_BOSy-8" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
<div style="height:50px;">&nbsp;</div>


### Optional: headless page archiving (single-file-cli)

This is **only** needed if your chef archives a JavaScript/SPA page — i.e. it
adds a node whose source URL serves an HTML page (see the render handler and
`examples/pagearchive/sushichef.py`). The DOWNLOAD stage detects such URLs and
renders them headlessly; the core `ricecooker` install and every other file type
work without it.

Page archiving shells out to the [single-file-cli](https://github.com/gildas-lormeau/single-file-cli)
Node binary, which drives a headless Chromium/Chrome to render the page. Install
both:

- **single-file-cli** (needs [Node.js](https://nodejs.org/) — any recent LTS):

      npm install -g single-file-cli

- **Chromium or Chrome**: install via your OS package manager or from
  [google.com/chrome](https://www.google.com/chrome/) — Linux:
  `sudo apt-get install chromium` (or `chromium-browser`); Mac:
  `brew install --cask google-chrome`; Windows: the Chrome installer. If the
  browser is not on your `PATH`, pass its path to the node via
  `context={"browser_executable_path": "..."}`.

*Checklist*: run `single-file --help` to confirm the binary is available.


Installing Ricecooker
---------------------
Create a `pyproject.toml` for your chef project (or use an existing one), then run:

    uv add ricecooker

`uv` resolves and installs `ricecooker` and all the Python packages required to
create content integration scripts into your project's `.venv`, and records the
dependency in `pyproject.toml`.


Contributing to ricecooker itself
----------------------------------
If you're contributing to `ricecooker` itself (not just writing a chef script),
see `AGENTS.md` for the contributor quick start.

**Reporting issues**: If you run into problems or encounter an error in any of the above steps,
please let us know by [opening an issue on github](https://github.com/learningequality/ricecooker/issues).

------

Okay so now we have all the system software and Python libraries installed.
[Let's get started!](tutorial/gettingstarted.html)
