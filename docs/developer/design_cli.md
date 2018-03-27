Command line interface
======================

This document describes logic `ricecooker` uses to parse command line arguments.
Under normal use cases you shouldn't need modify the command line parsing, but 
you need to understand how `argparse` works if you want to add new command line
arguments for your chef script.


Summary
-------
A sushi chef script using the new API looks like this:


    #!/usr/bin/env python
    ...
    ...
    class MySushiChef(BaseChef):     # or SushiChef to support remote monitoring
        def get_channel(**kwargs)` -> ChannelNode (bare channel, used just for info)
            ...
        def construct_channel(**kwargs) -> ChannelNode (with populated Tree)
            ...
    ...
    ...
    if __name__ == '__main__':
        chef = MySushiChef()
        chef.main()


Flow diagram
------------
The call to `chef.main()` results in the following sequence of six calls:

    MySushiChef -----extends----> BaseChef                   commands.uploadchannel
    ---------------------------   -----------------------    -----------------------
                                  1. main()
                                  2. parse_args_and_options()
                                  3. run(args, options)
                                                             4. uploadchannel(chef, *args, **options)
                                                             ...
    5. get_channel(**kwargs)
                                                             ...
    6. construct_channel(**kwargs)
                                                             ...
                                                             ...
                                                             DONE


Changes
-------

### Old `uploadchannel` API (a.k.a. compatibility mode)

  - pass in chef script file as `"<file_path>"` to uploadchannel
  - `uploadchannel` calls the function `contruct_channel` defined in the chef script


### New `uploadchannel` API

  - The chef script defines subclass of `riececooker.chefs.SushiChef` that implement
    the methods `get_channel` and `construct_channel`:

        class MySushiChef(riececooker.chefs.SushiChef):
            def get_channel(**kwargs)` -> ChannelNode (bare channel, used just for info)
                ...
            def construct_channel(**kwargs): --> ChannelNode (with populated Tree)
                ...

  - Each chef script is a standalone python executable.
    The `main` method of the chef instance is the entry point used by a chef script:

        #!/usr/bin/env python
        ...
        ...
        ...
        if __name__ == '__main__':
            chef = MySushiChef()
            chef.main()

  - The `__init__` method of the sushi chef class configures an `argparse` parser
    (`BaseChef` creates `self.arg_parser` and each class adds to this shared parser
     its own command line arguments.)

  - The `main` method of the class parses the command line arguments and calls
    the `run` method (or the `deamon_mode` method.)

        class BaseChef():
            ...
            def main(self):
                args, options = self.parse_args_and_options()
                self.run(args, options)

  -  The chef's `run` method calls `uploadchannel` (or `uploadchannel_wrapper`)

         class BaseChef():
             ...
             def run(self, args, options):
                 ...
                 uploadchannel(self, **args.__dict__, **options)

      note the chef instance is passed as the first argument, and not path.

  - The `uploadchannel` function expects the sushi chef class to implement the
    following two methods:
    - `get_channel(**kwargs)`: returns a ChannelNode  (previously called `create_channel`)
        - as an alternative, if `MySushiChef` has a `channel_info` attribute (a dict)
          then the default SushiChef.get_channel will create the channel from this info
    - `construct_channel(**kwargs)`: create the channel and build node tree

  - Additionally, the `MySushiChef` class can implement the following optional methods
    that will be called as part of the run
     - `__init__`: if you want to add custom chef-specific command line arguments using argparse
     - `pre_run`: if you need to do something before chef run starts (called by `run`)
     - `run`: in case you want to call `uploadchannel` yourself


Compatibility mode
------------------
Calling ricecooker as a module (`python -m ricecooker uploadchannel oldchef.py ...`)
will run the following code in `ricecooker.__main__.py`:

    from ricecooker.chefs import BaseChef
    if __name__ == '__main__':
        chef = BaseChef(compatibility_mode=True)
        chef.main()

The `BaseChef` class with `compatibility_mode=True` proxies call to its `construct_channel`
method to the function `construct_channel` in `oldchef.py`.
The call to `chef.main()` results in the following sequence of events:

    oldchef.py                    BaseChef(compat mode)      commands.uploadchannel
    ---------------------------   -----------------------    -----------------------
                                  1. main()
                                  2. parse_args_and_options()
                                  3. run(args, options)
                                                             4. uploadchannel(chef, *args, **options)
                                                             ...
                                                             ...
                                  5. construct_channel(**kwargs)
    5'. construct_channel(**kwargs)
                                                             ...
                                                             ...
                                                             DONE

Logging and progress reporting to SushiBar server is not supported in compatibility mode.



Args, options, and kwargs
-------------------------
There are three types of arguments involved in a chef run:

  - `args` (dict): command line args as parsed by the sushi chef class and its parents
    - BaseChef: the method ` BaseChef.__init__` configures argparse for the following:
        - `compress`, `download_attempts`, `prompt`, `publish`, `reset`, `resume`,
          `stage`, `step`, `thumbnails`, `token`, `update`, `verbose`, `warn`
        - in compatibility mode, also handles `uploadchannel` and `chef_script` positional arguments
    - SushiChef:
        - `daemon` = Runs in daemon mode
        - `nomonitor` = Disable SushiBar progress monitoring
    - MySushiChef: the chef's `__init__` method can define additional cli args

  - `options` (dict): additional [OPTIONS...] passed at the end of the command line
    - used for compatibility mode with old rieceooker API  (`python -m ricecooker uploadchannel ...  key=value`)

  - `kwargs` (dict): chef-specific keyword arguments not handled by ricecooker's `uploadchannel` method
      - the chef's `run` method makes the call `uploadchannel(self, **args.__dict__, **options)`
        while the definition of `uploadchannel` looks like `uploadchannel(chef, verbose=False, update=False, ... stage=False, **kwargs)`
        so `kwargs` contains a mix of both `args` and `options` that are not
        explicitly expected by the `uploadchannel` function
      - The function `uploadchannel` will pass `**kwargs` on to the `chef`'s
        `get_channel` and `construct_channel` methods as part of the chef run.



Daemon mode
-----------
In daemon mode, we open a `ControlWebSocket` connection with the SushiBar and
wait for commands.

When a command comes in on the control channel, it looks like this:

     message = {"command":"start", "args":{...}, "options":{...}}

Then the handler  `ControlWebSocket.on_message` will start a new run:

     args.update(message['args'])        # remote arguments overwrite ricecooker cli args
     options.update(message['options'])  # remote options overwrite cli options
     chef.run(args, options)

After finishing the run, a chef started with the `--daemon` option remains connected
to the SushiBar server and listens for more commands.




