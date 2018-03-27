SushOps
=======
SushOps engineers (also called ETL engineers) are responsible for making sure
the overall content pipeline runs smoothly. Assuming the [chefops](./chefops.md)
is done right, running the chef script should be as simple as running a single command.
SushOps engineers need to make sure not only that chef is running correctly,
but also monitor content on the Sushibar dashboard, in Kolibri Studio, and in 
downstream remixed channels, and in Kolibri installations.

SushOps is an internal role to Learning Equality but we'll document the responsibilities
here for convenience, since this role is closely related to the `ricecooker` library.



Project management and support
------------------------------
SushOps manage and support developers working on new chefs scripts, by reviewing
spec sheets, writing technical specs, preregistering chefs on sushibar, crating
necessary git repos, reviewing pull requests, chefops, and participating in Q/A.


Cheffing servers
----------------
Chef scripts run on various cheffing servers, equipped with appropriate storage
space and processing power (if needed for video transcoding). Currently we have:
  - CPU-intensive chefs running on `vader`
  - other chefs running on `cloud-kitchen`
  - various other chefs running on partner orgs infrastructure


Scheduled runs
--------------
Chefs scripts can be scheduled to run automatically on a periodic basis, e.g.,
once a month. In between runs, chef scripts stay dormant (daemonized).
Scheduled chefs run by default with the `--stage` argument in order not to
accidentally overwrite the currently active content tree on Studio with a broken one.
If the channel content is relatively unchanged and raises no flags for review,
the staged tree will be ACTIVATED, and the channel PUBLISHed automatically as well.


Chef inventory
--------------
In order to keep track of all the sushi chefs (30+ and growing), SushOps people
maintain this spreadsheet listing and keep it up-to-date for all chefs:
  - chef_name, short, unique identified, e.g., `khan_academy_en`
  - chef repo url
  - command necessary to run this chef, e.g., `./kachef.py ... lang=en`
  - scheduled run settings (crontab format)

This spreadsheet is used by humans as an inventory of the chef scripts currently
in operation. The automation scripts use the same data to provision chef scripts
environments, and setting up scheduling for them on the LE cheffing servers.


SushOps tooling and automation
------------------------------
Some of the more repetitive system administration tasks have been automated using
`fab` commands.

    fab -R cloud-kitchen   setup_chef:chef_name     # clones the chef_name repo and installs requirements
    fab -R cloud-kitchen   update:chef_name         # git fetch and git reset --hard to get latest chef code
    fab -R cloud-kitchen   run_chef:chef_name       # runs the chef
    fab -R cloud-kitchen   schedule_chef:chef_name  # set up chef to run as cronjob

You can import the reusable fab commands from `ricecooker.utils.fabfile`. [WIP]
