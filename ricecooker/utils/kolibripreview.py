#!/usr/bin/env python
import argparse
import os
import shutil
import sys


def validate(srcdir):
    """
    Check if `srcdir` has an index.html in it.
    """
    indexpath = os.path.join(srcdir, 'index.html')
    if not os.path.exists(indexpath):
        print('Missing index.html file in', srcdir)
        return False
    return True


def main(args):
    """
    Command line utility for previewing HTML5App content in Kolbri.
    """
    if not os.path.exists(args.srcdir) or not os.path.isdir(args.srcdir):
        print('Error:', args.srcdir, 'is not a directory.')
        sys.exit(1)
    if not validate(args.srcdir):
        print('Validation failed; exiting.')
        sys.exit(2)
    # Write the contents of `srcdir` to `destzip`
    destzipbase, _ = os.path.splitext(args.destzip)
    shutil.make_archive(destzipbase, 'zip', args.srcdir)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument('--srcdir',  help='HTML5 webroot (source directory)', default='.')
    parser.add_argument('--destzip', help='Path to a HTML5 zip file in local Kolibri installation', required=True)
    args = parser.parse_args()
    main(args)

