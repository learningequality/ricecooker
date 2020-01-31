Running chef scripts
====================
The base class `SushiChef` provides a lot of command line arguments that control
the chef script's operation. It is expected that **every chef script will come
with a README** that explains the desired command line arguments for the chef script.


Executable scripts
------------------
On UNIX systems, you can make your sushi chef script (e.g. `sushichef.py`) run as a
standalone command line application. To make a script program, you need to do three things:

    - Add the line `#!/usr/bin/env python` as the first line of `sushichef.py`
    - Add this code block at the bottom of `sushichef.py` if it is not already there:

          if __name__ == '__main__':
              chef = MySushiChef()  # replace with you chef class name
              chef.main()

    - Make the file `sushichef.py` executable by running `chmod +x sushichef.py` on the
      command line.

You can now call your sushi chef script using `./sushichef.py ...` instead of the longer
`python sushichef.py ...`.



Ricecooker CLI
--------------
You can run `./sushichef.py -h` to see an always-up-to-date info about the `ricecooker` CLI interface:

    usage: sushichef.py  [-h] [--token TOKEN] [-u] [-v] [--quiet] [--warn]
                            [--debug] [--compress] [--thumbnails]
                            [--download-attempts DOWNLOAD_ATTEMPTS]
                            [--reset | --resume]
                            [--step {INIT, CONSTRUCT_CHANNEL, CREATE_TREE, DOWNLOAD_FILES, GET_FILE_DIFF,
                               START_UPLOAD, UPLOADING_FILES, UPLOAD_CHANNEL, PUBLISH_CHANNEL,DONE, LAST}]
                            [--prompt] [--deploy] [--publish]
                            [--daemon] [--nomonitor] [--cmdsock CMDSOCK]

    required arguments:
      --token TOKEN         Authorization token (can be token or path to file with token)

    optional arguments:
      -h, --help            show this help message and exit
      -u, --update          Force re-download of files (skip .ricecookerfilecache/ check)
      -v, --verbose         Verbose mode
      --quiet               Print only errors to stderr
      --warn                Print warnings to stderr
      --debug               Print debugging log info to stderr
      --compress            Compress high resolution videos to low resolution
                            videos
      --thumbnails          Automatically generate thumbnails for topics
      --download-attempts DOWNLOAD_ATTEMPTS
                            Maximum number of times to retry downloading files
      --reset               Restart session, overwriting previous session (cannot
                            be used with --resume flag)
      --resume              Resume from ricecooker step (cannot be used with
                            --reset flag)
      --step  {INIT, ...    Step to resume progress from (must be used with --resume flag)
      --prompt              Prompt user to open the channel after creating it
      --stage               (Deprecated.) Stage updated content for review. This
                            flag is now the default and has been kept solely to
                            maintain compatibility. Use --deploy to immediately
                            push changes.
      --deploy              Immediately deploy changes to channel's main tree.
                            This operation will delete the previous channel
                            content once upload completes. Default (recommended)
                            behavior is to post new tree for review.
      --publish             Publish newly uploaded version of the channel
      --daemon              Run chef in daemon mode
      --nomonitor           Disable SushiBar progress monitoring
      --cmdsock CMDSOCK     Local command socket (for cronjobs)

    extra options:
      You can pass arbitrary key=value options on the command line


### Extra options
In addition to the command line arguments described above, the `ricecooker` CLI
supports passing additional keyword options using the format `key=value key2=value2`.

It is common for a chef script to accept a "language option" like `lang=fr` which
runs the French version of the chef script. This way a single chef codebase can
create multiple Kolibri Studio channels, one for each language.

These extra options will be parsed along with the `riceooker` arguments and
passed as along to all the chef's methods: `pre_run`, `run`, `get_channel`,
`construct_channel`, etc.

For example, a script started using `./sushichef.py ... lang=fr` could:
  - Subclass the method `get_channel` to set the channel name to
    `"Channel Name ({})".format(getlang('fr').native_name)`
  - Use the language code `fr` in `pre_run`, `run`, and `construct_channel` to
    crawl and scrape the French version of the source website


### Resuming interrupted chef runs
If your `ricecooker` session gets interrupted, you can resume from any step that
has already completed using `--resume --step=<step>` option.
If step is not specified, `ricecooker` will resume from the last step you ran.
The "state" necessary to support these checkpoints is stored in the directory
`restore` in the folder where the chef runs.

Use the `--reset` flag to skip the auto-resume prompt.


### Caching
Use `--update` argument to skip checks for the `.ricecookerfilecache` directory.
This is required if you suspect the files on the source website have been updated.

Note that some chef scripts implement their own caching mechanism, so you need
to disable those caches as well if you want to make sure you're getting new content.
Use the commands `rm -rf .webcache` to clear the webcache if it is present,
and `rm -rf .ricecookerfilecache/* storage/* restore/*` to clean all ricecooker
directories and start from scratch.



Long running scripts
--------------------
Certain chefs that require lots of downloads and video transcoding take a long
time to complete so it is best to run them on a dedicated server for this purpose.
  - Connect to the remove server via `ssh`
  - Clone the sushi chef git repository in the `/data` folder on the server
  - Run the chef script as followd `nohup <chef cmd> &`, where `<chef cmd>`
    is contains the entire script name and command line options,
    e.g. `./sushichef.py -v --reset --token=... --thumbnails lang=fr`.
  - By default `nohup` logs stderr and stdout output to a file called `nohup.out`
    in the current working directory. Use `tail -f nohup.out` to follow this log file.


Daemon mode
-----------
Starting a chef script with the `--daemon` argument makes it listen for remote
control commands from the [sushibar](https://sushibar.learningequality.org/) host.
For more information, see [Daemonization](developer/daemonization).


