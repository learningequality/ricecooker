PDF Utils
=========

The module `ricecooker.utils.pdf` contains helper functions for manipulating PDFs.



PDF splitter
------------
When importing source PDFs like books that are very long documents (100+ pages),
it is better for the Kolibri user experience to split them into multiple shorter PDF
content nodes.

The `PDFParser` class in `ricecooker.utils.pdf` is a wrapper around the `PyPDF2`
library that allows us to split long PDF documents into individual chapters,
based on either the information available in the PDF's table of contents, or user-defined page ranges.


### Split into chapters

Here is how to split a PDF document located at `pdf_path`, which can be either
a local path or a URL:

    from ricecooker.utils.pdf import PDFParser
    
    pdf_path = '/some/local/doc.pdf' or 'https://somesite.org/some/remote/doc.pdf'
    with PDFParser(pdf_path) as pdfparser:
        chapters = pdfparser.split_chapters()

The output `chapters` is list of dictionaries with `title` and `path` attributes:

    [ 
      {'title':'First chapter',  'path':'downloads/doc/First-chapter.pdf'},
      {'title':'Second chapter', 'path':'downloads/doc/Second-chapter.pdf'},
      ... 
    ]

Use this information to create an individual `DocumentNode` for each PDF and store
them in a `TopicNode` that corresponds to the book:

    from ricecooker.classes import nodes, files

    book_node = nodes.TopicNode(title='Book title', description='Book description')
    for chapter in chapters:
        chapter_node = nodes.DocumentNode(
            title=chapter['title'],
            files=[files.DocumentFile(chapter['path'])],
            ...
        )
        book_node.add_child(chapter_node)

By default, the split PDFs are saved in the directory `./downloads`. You can customize
where the files are saved by passing the optional argument `directory` when initializing
the `PDFParser` class, e.g., `PDFParser(pdf_path, directory='somedircustomdir')`.


The `split_chapters` method uses the internal `get_toc` method to obtain a list
of page ranges for each chapter. Use `pdfparser.get_toc()` to inspect the PDF's
table of contents. The table of contents data returned by the `get_toc` method
has the following format:

    [
      {'title': 'First chapter',  'page_start': 0,  'page_end': 10},
      {'title': 'Second chapter', 'page_start': 10, 'page_end': 20},
      ...
    ]

If the page ranges automatically detected form the PDF's table of contents are
not suitable for the document you're processing, or if the PDF document does not
contain table of contents information, you can manually create the title and 
page range data and pass it as the `jsondata` argument to the `split_chapters()`.

    page_ranges = pdfparser.get_toc()
    # possibly modify/customize page_ranges, or load from a manually created file
    chapters = pdfparser.split_chapters(jsondata=page_ranges)



### Split into chapters and subchapters

By default the `get_toc` will detect only the top-level document structure,
which might not be sufficient to split the document into useful chunks.
You can pass the `subchapters=True` optional argument to the `get_toc()` method
to obtain a two-level hierarchy of chapters and subchapter from the PDF's TOC.

For example, if the table of contents of textbook PDF has the following structure:

     Intro
     Part I
        Subchapter 1
        Subchapter 2
     Part II
        Subchapter 21
        Subchapter 22
     Conclusion

then calling `pdfparser.get_toc(subchapters=True)` will return the following
chapter-subchapter tree structure:

    [
      { 'title': 'Part I', 'page_start': 0,  'page_end': 10,
        'children': [
            {'title': 'Subchapter 1',  'page_start': 0,  'page_end': 5},
            {'title': 'Subchapter 2',  'page_start': 5,  'page_end': 10}
         ]},
      { 'title': 'Part II', 'page_start': 10,  'page_end': 20,
        'children': [
            {'title': 'Subchapter 21',  'page_start': 10, 'page_end': 15},
            {'title': 'Subchapter 22',  'page_start': 15,  'page_end': 20}
         ]},
      { 'title': 'Conclusion', 'page_start': 20,  'page_end': 25 }
    ]

Use the `split_subchapters` method to process this tree structure and obtain the
tree of title and paths:


    [
      { 'title': 'Part I',
        'children': [
            {'title': 'Subchapter 1', 'path': '/tmp/0-0-Subchapter-1.pdf'},
            {'title': 'Subchapter 2', 'path': '/tmp/0-1-Subchapter-2.pdf'},
         ]},
      { 'title': 'Part II',
        'children': [
            {'title': 'Subchapter 21', 'path': '/tmp/1-0-Subchapter-21.pdf'},
            {'title': 'Subchapter 22', 'path': '/tmp/1-1-Subchapter-22.pdf'},
         ]},
      { 'title': 'Conclusion', 'path': '/tmp/2-Conclusion.pdf'}
    ]

You'll need to create a `TopicNode` for each chapter that has `children` and
create a `DocumentNode` for each of the children of that chapter.





Accessibility notes
-------------------
Do not use `PDFParser` for tagged PDFs because splitting and processing loses
the accessibility features of the original PDF document.

