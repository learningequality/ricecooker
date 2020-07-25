SushOps
=======
SushOps engineers (also called ETL engineers) are responsible for making sure
the overall content pipeline runs smoothly. Assuming the [chefops](../chefops)
is done right, running the chef script should be as simple as running a single command.
SushOps engineers need to make sure not only that chef is running correctly,
but also monitor content in Kolibri Studio, in downstream remixed channels,
and in Kolibri installations.

SushOps is an internal role to Learning Equality but we'll document the responsibilities
here for convenience, since this role is closely related to the `ricecooker` library.



Project management and support
------------------------------
SushOps manage and support developers working on new chefs scripts, by reviewing
spec sheets, writing technical specs, crating necessary git repos, reviewing
pull requests, chefops, and participating in QA.


Cheffing servers
----------------
Chef scripts run on various cheffing servers, equipped with appropriate storage
space and processing power (if needed for video transcoding). Currently we have:
  - CPU-intensive chefs running on `vader`
  - various other chefs running on partner orgs infrastructure

### Cheffing servers conventions
  - Put all the chef repos in `/data` (usually a multi-terabyte volume), e.g.,
    use the directory `/data/sushi-chef-{{nickname}}/` for the `nickcname` chef.
  - Use the name `sushichef.py` for the chef script
  - Document all the instructions and options needed to run the chef script in
    the chef's `README.md`
  - Use the directory `/data/sushi-chef-{{nickname}}/chefdata/tmp/` to store tmp
    files to avoid cluttering the global `/tmp` directory.
  - For long running chefs, use the command `nohup  <chef cmd>  &` to run the chef
    so you can close the ssh session (hangup) without the process being terminated.



SushOps tooling and automation
------------------------------
Some of the more repetitive system administration tasks have been automated using `fab` commands:

    fab -R vader   setup_chef:nickname     # clones the nickname repo and installs requirements
    fab -R vader   update:nickname         # git fetch and git reset --hard to get latest chef code
    fab -R vader   run_chef:nickname       # runs the chef

See the [content-automation-scripts](https://github.com/learningequality/content-automation-scripts)
project for more details.
