
Daemon mode
===========
Running a chef scripts with the `--daemon` option will make it listen to remote
commands: either from [sushibar](https://sushibar.learningequality.org/) and/or
from localhost cron jobs.


SushiBar control channel
------------------------
To enable remote commands from sushibar, start the chef script using

    ./chef.py --daemon  <otherstuff>



Local control channel
---------------------
To also enable local UNIX domain sockets commands, start the chef script using

    ./chef.py --daemon --cmdsock=/var/run/chefname.sock  <otherstuff>

Once the chef is running, a chef run can be scheduled using the following command:

    /bin/echo '{"command":"start"}' | /bin/nc -U /var/run/chefname.sock

If you need to override chef run `args` or `options` use:

    /bin/echo '{"command":"start", "args":{"publish":true}, "options":{"lang":"en"} }' | /bin/nc -U /var/run/chefname.sock

The above command will run the chef, re-using the command line args and options,
but setting `publish` to `True` and also providing the keyword option `lang=en`.
