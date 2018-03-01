#!/usr/bin/env python
from ricecooker.chefs import LineCook

class CsvChef(LineCook):
    """
    Sushi chef for creating Kolibri Studio channels from local files and metdata
    provided in Channel.csv and Content.csv.
    """
    pass
    # no custom methods needed: the `LineCook` base class will do the cheffing.
    # Run `python csvchef.py -h` to see all the supported command line options

if __name__ == '__main__':
    chef = CsvChef()
    chef.main()
