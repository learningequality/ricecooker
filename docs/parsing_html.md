Parsing HTML using BeautifulSoup
================================
BeautifulSoup is an HTML parsing library that allows you to "select" various DOM
elements, and extract their attributes and text contents.



Video tutorial
--------------
To get started, you can watch this [cheffing video tutorial](http://35.196.115.213/en/learn/#/topics/c/73470ad1a3015769ace455fbfdf17d48)
that will show the basic steps of using `requests` and `BeautifulSoup` for crawling a website.
See the [sushi-chef-shls code repo](https://github.com/learningequality/sushi-chef-shls/blob/master/sushichef.py#L226-L340)
for the final version of the web crawling code that was used for this content source.

<a href="http://35.196.115.213/en/learn/#/topics/c/73470ad1a3015769ace455fbfdf17d48" target='_blank'>
<iframe width="560" height="315" src="https://www.youtube.com/embed/yo-O3A8Jj38" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</a>
<div style="height:50px;">&nbsp;</div>


Scraping 101
------------
The basic code to GET the HTML source of a webpage and parse it:

```python
import requests
from bs4 import BeautifulSoup

url = 'https://somesite.edu'
html = requests.get(url).content
doc = BeautifulSoup(html, "html5lib")
```

You can now call `doc.find` and `doc.find_all` methods to select various DOM elements:

```python
special_ul = doc.find('ul', class_='some-special-class')
section_lis = special_ul.find_all('li', recursive=False)  # search only immediate children
for section_li in section_lis:
    print('processing a section <li> right now...')
    print(section_li.prettify())  # useful seeing HTML in when developing...
```

The most commonly used parts of the BeautifulSoup API are:
  - `.find(tag_name,  <spec>)`: find the next occurrence of the tag `tag_name` that
     has attributes specified in `<spec>` (given as a dictionary), or can use the
     shortcut options `id` and `class_` (note extra underscore).
  - `.find_all(tag_name, <spec>)`: same as above but returns a list of all matching
     elements. Use the optional keyword argument `recursive=False` to select only
     immediate child nodes (instead of including children of children, etc.).
  - `.next_sibling`: find the next element (for badly formatted pages with no useful selectors)
  - `.get_text()` extracts the text contents of the node. See also helper method
    called `get_text` that performs additional cleanup of newlines and spaces.
  - `.extract()`: to extract an element from the DOM tree
  - `.decompose()`: useful to remove any unwanted DOM elements
    (same as `.extract()` but throws away the extracted element)


### Example 1
Here is some sample code for getting the text of the LE mission statement:

```python
from bs4 import BeautifulSoup
from ricecooker.utils.downloader import read

url = 'https://learningequality.org/'
html = read(url)
doc = BeautifulSoup(html, 'html5lib')

main_div = doc.find('div', {'id': 'body-content'})
mission_el = main_div.find('h3', class_='mission-state')
mission = mission_el.get_text().strip()
print(mission)
```

### Example 2
To print a list of all the links on the page, use the following code:
```python
links = doc.find_all('a')
for link in links:
    print(link.get_text().strip(), '-->', link['href'])
```



Further reading
---------------
For more info about BeautifulSoup, see [the docs](https://www.crummy.com/software/BeautifulSoup/bs4/doc/).

There are also some excellent tutorials online you can read:
  - [http://akul.me/blog/2016/beautifulsoup-cheatsheet/](http://akul.me/blog/2016/beautifulsoup-cheatsheet/)
  - [http://youkilljohnny.blogspot.com/2014/03/beautifulsoup-cheat-sheet-parse-html-by.html](http://youkilljohnny.blogspot.com/2014/03/beautifulsoup-cheat-sheet-parse-html-by.html)
  - [http://www.compjour.org/warmups/govt-text-releases/intro-to-bs4-lxml-parsing-wh-press-briefings/](http://www.compjour.org/warmups/govt-text-releases/intro-to-bs4-lxml-parsing-wh-press-briefings/)

