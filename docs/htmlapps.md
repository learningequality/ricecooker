HTML5App nodes and HTML5Zip files
=================================

Kolibri supports rendering of generic HTML content through the use of `HTML5Apps`
nodes, which correspond to `HTML5Zip` files. The Kolibri application serves the
contents of `index.html` in the root of the zip file inside an iframe.
All `href`s and img `src` attributes must be relative links to resources within
the zip file.



Example of HTML5App nodes
-------------------------

* [simple example](http://mitblossoms-demo.learningequality.org/learn/#/recommended/caddd1df7a7b5849a444074408e31655)
  * Note links are disabled (removed blue link) because A) external links are disable in iframe and B) because wouldn't have access offline
  * If link is to a PDF, IMG, or other useful resource than can be included in zip file then keep link but change to relative path
* [medium complexity example](http://tessa-demo.learningequality.org/learn/#/45605d184d985e74960015190a6f4e4f/recommended/ecb158bff182511db6327be6f8a91891)
  * Download all parts of a multi-part lesson into a single HTML5Zip file
  * Original source didn't have a "table of contents" so added manually (really bad CSS I need to fix in final version)
* [complex example](http://kolibridemo.learningequality.org/learn/#/topics/c/d165c4fbc3bd5bbeaf3e51360965af29)
  * Full javascript application packaged as a zip file
  * Source: [sushi-chef-phet](https://github.com/learningequality/sushi-chef-phet/blob/master/chef.py#L104)



Links and navigation
--------------------
It's currently not possible to have navigation links between different HTML5App nodes,
but relative links within the same zip file work (since they are rendered in same iframe).
It's important to "cut" the source websites content into appropriately sized chunks:

  - As small as possible so that resources are individually trackable, assignable, and reusable in multiple places
  -  But not too small, e.g. if a lesson contains three parts intended to be followed one after the other, then all three parts should be included in a single HTML5App with internal links
  - Use nested folder structure to represent complex sources.
    Whenever an HTML page that acts as a "container" with links to other pages
    and PDFs we try to turn it into a Folder and put content items inside it.
    Nested folders is main way of representing structured content.




HTML Writer utility class
-------------------------
The class `HTMLWriter` in `ricecooker.utils.html_writer` provides a basic helper
methods for creating files within a zip file.

See the source code:
[ricecooker/utils/html_writer.py](https://github.com/learningequality/ricecooker/blob/master/ricecooker/utils/html_writer.py#L5)

