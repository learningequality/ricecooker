Parsing HTML using `BeautifulSoup`
==================================

Basic code to GET the HTML source of a webapge and parse it:

    import requests
    from bs4 import BeautifulSoup

    url = 'https://somesite.edu'
    html = requests.get(url).content
    doc = BeautifulSoup(html, "html.parser")


Basic API uses `find` and `find_all`:

    special_ul = doc.find('ul', class_='some-special-class')
    section_lis = special_ul.find_all('li', recursive=False)  # search only immediate children
    for section_li in section_lis:
        print('processing a section <li> right now...')
        print(section_li.prettify())  # useful seeing HTML in when developing...



Further reading
---------------
You can learn more about BeautifulSoup from these excellent tutorials:

  - http://akul.me/blog/2016/beautifulsoup-cheatsheet/
  - http://youkilljohnny.blogspot.ca/2014/03/beautifulsoup-cheat-sheet-parse-html-by.html
  - http://www.compjour.org/warmups/govt-text-releases/intro-to-bs4-lxml-parsing-wh-press-briefings/
