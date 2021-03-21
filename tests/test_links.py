import os

from ricecooker.utils.html import replace_links


def test_replace_absolute_links():
    a_content = '<a href="http://replace.me/link/to/page.html">'
    noscheme_a_content = '<a href="//replace.me/link/to/page.html">'
    root_a_content = '<a href="/link/to/page.html">'

    img_content = '<img src="http://replace.me/img/hello.jpg">'

    img_srcset_content = '<img srcset="http://replace.me/img/hello.jpg 1x, http://replace.me/img/hello.jpg 2x">'

    urls_to_replace = {
        'http://replace.me/img/hello.jpg': 'img/hello.jpg',
        'http://replace.me/link/to/page.html': 'link/to/page.html'
    }

    output = replace_links(img_content, urls_to_replace)
    assert output == '<img src="img/hello.jpg">'

    output = replace_links(a_content, urls_to_replace)
    assert output == '<a href="link/to/page.html">'

    output = replace_links(noscheme_a_content, urls_to_replace)
    assert output == '<a href="link/to/page.html">'

    output = replace_links(root_a_content, urls_to_replace)
    assert output == '<a href="link/to/page.html">'

    output = replace_links(img_srcset_content, urls_to_replace)
    assert output == '<img srcset="img/hello.jpg 1x, img/hello.jpg 2x">'


def test_replace_relative_links():
    a_content = '<a href="http://replace.me/link/to/page.html">'
    noscheme_a_content = '<a href="//replace.me/link/to/page.html">'
    root_a_content = '<a href="/link/to/page.html">'

    img_content = '<img src="http://replace.me/img/hello.jpg">'

    img_srcset_content = '<img srcset="http://replace.me/img/hello.jpg 1x, http://replace.me/img/hello.jpg 2x">'

    urls_to_replace = {
        'http://replace.me/img/hello.jpg': 'replace.me/img/hello.jpg',
        'http://replace.me/link/to/page.html': 'replace.me/link/to/page.html'
    }
    content_dir = os.path.join('replace.me', 'link', 'from')
    download_root = '.'

    output = replace_links(img_content, urls_to_replace, download_root=download_root, content_dir=content_dir, relative_links=True)
    assert output == '<img src="../../img/hello.jpg">'

    output = replace_links(a_content, urls_to_replace, download_root=download_root, content_dir=content_dir, relative_links=True)
    assert output == '<a href="../to/page.html">'

    output = replace_links(noscheme_a_content, urls_to_replace, download_root=download_root, content_dir=content_dir, relative_links=True)
    assert output == '<a href="../to/page.html">'

    output = replace_links(root_a_content, urls_to_replace, download_root=download_root, content_dir=content_dir, relative_links=True)
    assert output == '<a href="../to/page.html">'

    output = replace_links(img_srcset_content, urls_to_replace, download_root=download_root, content_dir=content_dir, relative_links=True)
    assert output == '<img srcset="../../img/hello.jpg 1x, ../../img/hello.jpg 2x">'
