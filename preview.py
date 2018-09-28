import sys

import ricecooker.utils.browser

if __name__ == '__main__':

    iframe = False

    if "--iframe" in sys.argv:
        sys.argv.pop(sys.argv.index("--iframe"))
        iframe = True

    get_help = "-h" in sys.argv or "--help" in sys.argv
    if get_help or len(sys.argv) < 2:
        print("usage: preview.py [--iframe] /path/to/page/or/directory")
        print("Preview web content in a browser using a local server.")
        print("Options:")
        print("--iframe:    load the content into an iframe sandbox for security testing.")
        print("-h, --help:  display this help message.")
        sys.exit(int(not get_help))
    ricecooker.utils.browser.load_server(sys.argv[1], iframe)
