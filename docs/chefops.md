Running chef scripts
====================
The base class `SushiChef` provides a lot of command line arguments that control
the chef script's operation. Chef scripts often have a README.md file that explains
what are the recommended command line arguments and options for the chef script.


Ricecooker CLI
--------------
This listing shows the `ricecooker` command line interface (CLI) arguments:

    usage: sushichef.py  [-h] [--token TOKEN] [-u] [-v] [--quiet] [--warn]
                            [--debug] [--compress] [--thumbnails]
                            [--resume]  [--step {CONSTRUCT_CHANNEL, CREATE_TREE,
                                                 DOWNLOAD_FILES, GET_FILE_DIFF,
                                                 START_UPLOAD, UPLOAD_CHANNEL}]
                            [--deploy] [--publish]

    required arguments:
      --token TOKEN         Studio API Access Token (specify wither the token
                            value or the path of a file that contains the token).

    optional arguments:
      -h, --help            show this help message and exit
      --debug               Print extra debugging infomation.
      -v, --verbose         Verbose mode (default).
      --compress            Compress videos using ffmpeg -crf=32 -b:a 32k mono.
      --thumbnails          Automatically generate thumbnails for content nodes.
      --resume              Resume chef session from a specified step.
      --step  {INIT, ...    Step to resume progress from (must be used with --resume flag)
      --update              Force re-download of files (skip .ricecookerfilecache/ check)
      --sample SIZE         Upload a sample of SIZE nodes from the channel.
      --deploy              Immediately deploy changes to channel's main tree.
                            This operation will overwrite the previous channel
                            content. Use only during development.
      --publish             Publish newly uploaded version of the channel.

As you can tell, there are lot of arguments to choose from, and this is not even
the complete list: you'll have to run `./sushichef.py -h` to see the latest version.
Below is a short guide to some of the most important and useful ones arguments.


### Compression and thumbnail globals
You can specify video compression settings (see this page) and thumbnails for
specific nodes and files in the channel, or use `--compress` and `--thumbnails`
to apply compression to ALL videos, and automatically generate thumbnails for
all the supported content kinds. **We recommend you always use the `--thumbnails`**
in order to create more colorful, lively channels that learners will want to browse.


### Caching
Use `--update` argument to skip checks for the `.ricecookerfilecache` directory.
This is required if you suspect the files on the source website have been updated.

Note that some chef scripts implement their own caching mechanism, so you need
to disable those caches as well if you want to make sure you're getting new content.
Use the commands `rm -rf .webcache` to clear the webcache if it is present,
and `rm -rf .ricecookerfilecache/* storage/* restore/*` to clean all ricecooker
directories and start from scratch.



### Extra options
In addition to the command line arguments described above, the `ricecooker` CLI
supports passing additional keyword options using the format `key=value key2=value2`.

It is common for a chef script to accept a "language option" like `lang=fr` which
runs the French version of the chef script. This way a single chef codebase can
create multiple Kolibri Studio channels, one for each language.

These extra options will be parsed along with the `riceooker` arguments and
passed as along to all the chef's methods: `pre_run`, `run`, `get_channel`,
`construct_channel`, etc.

For example, a script started using `./sushichef.py ... lang=fr` could.
Subclass the method `get_channel(self, **kwargs)` to choose the channel's
name and description based on the value `fr` you'll receive in `kwargs['lang']`.
The language code `fr` will can passed in to the `construct_channel` method,
and the `pre_run` and `run` methods as well.




Using Python virtual env
------------------------
The recommended best practice is to keep the Python packages required to run each
sushichef script in a self-contained Python environment, separate from the system
Python packages. This per-project software libraries isolation is easy to accomplish
using the Python `virtualenv` tool and simple `requirements.txt` files.

By convention all the sushichef code examples and scripts we use in production
contain a `requirements.txt` file that lists what packages must be installed for
the chef to run, including `ricecooker`.

To create a virtual environment called `venv` (the standard naming convention for
virtual environments) and install all the required packages, run the following:

    cd Projects/sushi-chef-{source_name}      # cd into the chef repo
    virtualenv -p python3 venv                # create a Python3 virtual environment
    source venv/bin/activate                  # go into the virtualenv `venv`
    pip install -r requirements.txt           # install a list of python packages

Windows users will need to replace the third line with `venv\Scripts\activate` as
the commands are slightly different on Windows.

When the virtual environment is "activated," you'll see `(venv)` at the beginning
of your command prompt, which tells you that you're in project-specific environment
where you can experiment, install, uninstall, upgrade, test Python things out,
without your changes interfering with the Python installation of your operating system.
You can learn more about virtualenvs from the [Python docs](https://docs.python-guide.org/dev/virtualenvs/#lower-level-virtualenv)




Executable scripts
------------------
On UNIX systems, you can make your sushi chef script (e.g. `sushichef.py`) run as a
standalone command line application. To make a script into a program, you need to do three things:

  - Add the line `#!/usr/bin/env python` as the first line of `sushichef.py`
  - Add this code block at the bottom of `sushichef.py` if it is not already there:
    ```python
    if __name__ == '__main__':
        chef = MySushiChef()  # replace with you chef class name
        chef.main()
    ```
  - Make the file `sushichef.py` executable by running `chmod +x sushichef.py`

You can now call your sushi chef script using `./sushichef.py ...`
or `sushichef.py ...` on Windows.


Long running tasks
------------------
Certain chefs that require lots of downloads and video transcoding take a long
time to complete so it is best to run them on a dedicated server for this purpose.
  - Connect to the remove server via `ssh`
  - Clone the sushi chef git repository in the `/data` folder on the server
  - Run the chef script as follows `nohup <chef cmd> &`, where `<chef cmd>`
    is contains the entire script name and command line options,
    e.g. `./sushichef.py --token=... --thumbnails lang=fr`.
  - By default `nohup` logs stderr and stdout output to a file called `nohup.out`
    in the current working directory. Use `tail -f nohup.out` to follow this log file.

