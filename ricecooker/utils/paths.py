import ntpath
import os
from pathlib import Path


def dir_exists(filepath):
    file_ = Path(filepath)
    return file_.is_dir()


def file_exists(filepath):
    my_file = Path(filepath)
    return my_file.is_file()


def get_name_from_url(url):
    """
    get the filename from a url 
    url = http://abc.com/xyz.txt
    get_name_from_url(url) -> xyz.txt
    """

    head, tail = ntpath.split(url)
    params_index = tail.find("&")
    if params_index != -1:
        tail = tail[:params_index]
    params_index = tail.find("?")
    if params_index != -1:
        tail = tail[:params_index]

    basename = ntpath.basename(url)
    params_b_index = basename.find("&")
    if params_b_index != -1:
        basename = basename[:params_b_index]
    return tail or basename


def get_name_from_url_no_ext(url):
    """
    get the filename without the extension name from a url 
    url = http://abc.com/xyz.txt
    get_name_from_url(url) -> xyz
    """
    path = get_name_from_url(url)
    return os.path.splitext(path)[0]


def build_path(levels):
    """
    make a linear directory structure from a list of path levels names
    levels = ["chefdir", "trees", "test"]
    builds ./chefdir/trees/test/
    """
    path = os.path.join(*levels)
    if not dir_exists(path):
        os.makedirs(path)
    return path
