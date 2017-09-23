
Parsing HTML using `BeautifulSoup`
==================================


Basic setup to get the HTML:

    url = 'https://somesite.edu'
    html = requests.get(url).content
    doc = BeautifulSoup(html, "html.parser")


Basic API uses `find` and `find_all`:

    sections_ul = doc.find('ul', class_='some-special-class')
    section_lis = sections_ul.find_all('li', recursive=False) # search only immediate children
    for section_li in section_lis:
        print('processing a section <li> right now...')
        print(section_li.prettify())    # useful for debugging

