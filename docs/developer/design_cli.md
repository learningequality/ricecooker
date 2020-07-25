Command line interface
======================

This document describes control flow used by the `ricecooker` framework, and the
particular logic used to parse command line arguments. Under normal use cases you
shouldn't need modify the default command line parsing, but you need to understand
how things work in case want to customize the command line args for your chef script.


Summary
-------
A sushi chef script like this:


    #!/usr/bin/env python
    ...
    ...
    class MySushiChef(SushiChef):
        def get_channel(**kwargs)` -> ChannelNode (bare channel, used just for metadata)
            ...
        def construct_channel(**kwargs) -> ChannelNode (with populated topic tree)
            ...
    ...
    ...
    if __name__ == '__main__':
        chef = MySushiChef()
        chef.main()


Flow diagram
------------
The call to `chef.main()` results in the following sequence of six calls:

    MySushiChef -----extends----> SushiChef                  commands.uploadchannel
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



  - The chef script must define a subclass of `ricecooker.chefs.SushiChef` that
    implement the methods `get_channel` and `construct_channel`:

        class MySushiChef(ricecooker.chefs.SushiChef):
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

  - The `__init__` method of the sushi chef class configures an `argparse` parser.
    The base class `SushiChef` creates `self.arg_parser` and a chef subclass can
    adds to this shared parser its own command line arguments. This is used only
    in vary special cases; for most cases, using the CLI `options` is sufficient.

  - The `main` method of the `SushiChef` class parses the command line arguments
    and calls the `run` method:

        class SushiChef():
            ...
            def main(self):
                args, options = self.parse_args_and_options()
                self.run(args, options)

  -  The chef's `run` method calls `uploadchannel`

         class SushiChef():
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



Args, options, and kwargs
-------------------------
There are three types of arguments involved in a chef run:

  - `args` (dict): command line args as parsed by the sushi chef class and its parents
    - SushiChef: the `SushiChef.__init__` method configures argparse for the following:
        - `compress`, `download_attempts`, `prompt`, `publish`, `resume`,
          `stage`, `step`, `thumbnails`, `token`, `update`, `verbose`, `warn`
    - MySushiChef: the chef's `__init__` method can define additional cli args

  - `options` (dict): additional [OPTIONS...] passed at the end of the command line
    - often used to pass the language option (`./sushichef.py ... lang=fr`)

  - `kwargs` (dict): chef-specific keyword arguments not handled by ricecooker's `uploadchannel` method
      - the chef's `run` method makes the call `uploadchannel(self, **args.__dict__, **options)`
        while the definition of `uploadchannel` looks like `uploadchannel(chef, verbose=False, update=False, ... stage=False, **kwargs)`
        so `kwargs` contains a mix of both `args` and `options` that are not
        explicitly expected by the `uploadchannel` function
      - The function `uploadchannel` will pass `**kwargs` on to the `chef`'s
        `get_channel` and `construct_channel` methods as part of the chef run.
