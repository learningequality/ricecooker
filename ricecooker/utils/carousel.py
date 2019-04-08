from bs4 import BeautifulSoup, NavigableString
from bs4.element import Tag
from urllib.parse import urlsplit
from itertools import zip_longest
import requests
import hashlib
import shutil
import os
from ricecooker.utils import nodes

html = """
<!DOCTYPE html>
<html>
  <head>

  <script>
  left_url = "{left}.html";
  right_url = "{right}.html";
  addEventListener("keypress", function(event) {{
        if (event.keyCode == 37) {{  // 37=left
          window.location.href = left_url;
          return false;
        }}
        if (event.keyCode == 39) {{  // 39=right
          window.location.href = right_url;
          return false;
        }}
  }})
  </script>
  <style>

    body {{
      margin: 0px;
      font-size: 0px;
    }}

    .big {{
      height: 80vh;
      width: 100%;
      margin: auto;
    }}

    .big img {{
      max-height: 80vh;
      max-width: 100%;
      width: auto;
      height: auto;
      margin: auto;
    }}

    .container {{
      max-height: 20vh;
    }}

    .strip {{
      overflow-x: scroll;
      overflow-y: hidden;
      white-space: nowrap;
      max-height: 20vh;
    }}

    .image img{{
      max-height: 20vh;
      width: auto;
      height: auto;
      margin: auto;
    }}
  </style>
  </head>
  <body>
    <div class='big'>
      <img src="{big}">
    </div>
    <div class='container'>
      <div class='strip'>
{strip}
      </div>
    </div>
  </body>
</html>

"""

DOWNLOAD_FOLDER = "carousel_downloads"

filenames = """
   https://artsedge.kennedy-center.org/~/media/ArtsEdge/Images/LessonArt/grade-3-4/youre-invited-to-a-ceili-exploring-irish-dance.jpg
   https://artsedge.kennedy-center.org/~/media/ArtsEdge/Images/LessonArt/grade-3-4/ceili/irish_dance.ashx
   https://artsedge.kennedy-center.org/~/media/ArtsEdge/Images/LessonArt/grade-3-4/ceili/irish_dance.ashx
   https://artsedge.kennedy-center.org/~/media/ArtsEdge/Images/LessonArt/grade-3-4/ceili/irish-dancers.ashx
   https://artsedge.kennedy-center.org/~/media/ArtsEdge/Images/LessonArt/grade-3-4/ceili/irish-shoes.ashx
   https://artsedge.kennedy-center.org/~/media/ArtsEdge/Images/LessonArt/grade-3-4/ceili/irish_costumes_2.jpg
   https://artsedge.kennedy-center.org/~/media/ArtsEdge/Images/LessonArt/grade-3-4/ceili/irish_costumes_3.jpg
   https://artsedge.kennedy-center.org/~/media/ArtsEdge/Images/LessonArt/grade-3-4/ceili/irish_costumes_4.jpg
   https://artsedge.kennedy-center.org/~/media/ArtsEdge/Images/LessonArt/grade-3-4/ceili/stolen-child.ashx
""".strip().split("\n")

filenames = [x.strip() for x in filenames]


def get_url(url, filename):
    r = requests.get(url, verify=False)
    content = r.content

    with open(filename, "wb") as f:
        try:
            f.write(content)
        except requests.exceptions.InvalidURL:
            pass

def create_carousel_zip(filenames):
    # download files and get disk filenames

    def hash_url(url):
        return hashlib.sha1((url).encode('utf-8')).hexdigest() + ".jpg"

    hashed_filenames = [hash_url(filename) for filename in filenames]
    hashed_pathnames = [DOWNLOAD_FOLDER + "/" + x for x in hashed_filenames]

    assert "downloads" in DOWNLOAD_FOLDER  # sanity check we're not deleting '/' or something wierd.
    try:
        shutil.rmtree(DOWNLOAD_FOLDER)
    except: # ignore if not present
        pass

    os.mkdir(DOWNLOAD_FOLDER)

    # create html
    create_carousel(hashed_filenames)

    for url, path in zip(filenames, hashed_pathnames):
        get_url(url, path)

    # create zip file
    ziphash = hash_url(str(filenames))
    zipfile_name = shutil.make_archive("__"+DOWNLOAD_FOLDER+"/"+ziphash, "zip", # automatically adds .zip extension!
                        DOWNLOAD_FOLDER)

    # delete contents of downloadfolder
    assert "downloads" in DOWNLOAD_FOLDER
    shutil.rmtree(DOWNLOAD_FOLDER)

    return zipfile_name

def create_carousel(filenames):
    """Take a list of filenames and create a HTML5App.
       It is not the job of this function to convert URLs to filenames!"""

    num_files = len(filenames)
    for page in range(num_files):
        left = (page - 1) % num_files
        right = (page + 1) % num_files
        strip = list(range(page, num_files)) + list(range(0, page))

        strip_segment = "        <a href='{i}.html' class='image'><img src='{image}'></a>"
        strip_list = []
        for i in strip:
            strip_list.append(strip_segment.format(i=i, image=filenames[i]))
        strip_html = '\n'.join(strip_list)

        with open(DOWNLOAD_FOLDER+"/{page}.html".format(page=page), "w") as f:
            html_full = html.format(left=left, right=right, strip=strip_html, big=filenames[page])
            f.write(html_full)

    shutil.copyfile(DOWNLOAD_FOLDER+"/0.html", DOWNLOAD_FOLDER+"/index.html")

def create_carousel_node(filenames, **metadata):
    zip_filename = create_carousel_zip(filenames)
    print(zip_filename)
    return nodes.create_node(nodes.HTMLZipFile, filename=zip_filename, **metadata)


if __name__ == "__main__":
    print(create_carousel_zip(filenames))
