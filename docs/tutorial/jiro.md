The jiro command line tool
==========================

**New in 0.7**

Named after the master sushi chef, the `jiro` command line tool
provides a command line interface around sushi chef scripts and
simplifies common tasks when operating on sushi chef scripts.

It has the following commands:

#### jiro new

`jiro new [script name]`

Create a new sushi-chef script. Will create a `sushi-chef-[name]`
directory unless the command is run within a directory of that name.

#### jiro remote

Used to manage Studio server upload authentication.

`jiro remote add [remote-name] [url] <token>`

Registers a new Studio instance to upload to.

* `remote-name` is a short string used to refer to this server in `jiro` commands.
* `URL` should be the fully qualified URL to the root of a Studio server
* `token` - if specified, the token to use to authenticate to the server. If not
  specified, you will be prompted to provide the token before your first upload.

`jiro remote list`

List the Studio servers you have registered with `jiro`.

#### jiro prepare

`jiro prepare`

This command should be run in the root script directory containing `sushichef.py`.

Downloads content and creates the channel tree, but skips the upload step. Often
used while iterating on scripts.

#### jiro serve

`jiro serve <remote-name>`

This command should be run in the root script directory containing `sushichef.py`.

Runs the same steps as `jiro prepare`, but also uploads the results to Studio.
If `remote-name` is specified, it will upload to the remote server registered
with that name. Otherwise, it will upload to production Studio.

If you have never registered an API token for the Studio server you're uploading to,
it may prompt you to enter it when running this command.


