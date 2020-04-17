Computed identifiers
====================

Channel ID
----------
The `channel_id` (uuid hex str) property is an important identifier that:
  - Is used in the "wire format" between `ricecooker` and Kolibri Studio
  - Appears as part of URLs on both Kolibri Studio and Kolibri
  - Determines the filename for the channel sqlite3 database file that
    Kolibri imports from Kolibri Studio, from local storage, or from other
    Kolibri devices via peer-to-peer content import.

To compute the `channel_id`, you need to know the channel's `source_domain`
(a.k.a. `channel_info['CHANNEL_SOURCE_DOMAIN']`)
and the channel's `source_id` (a.k.a `channel_info['CHANNEL_SOURCE_ID']`):

```python
import uuid
domain_namespace = uuid.uuid5(uuid.NAMESPACE_DNS, source_domain)
channel_id = uuid.uuid5(domain_namespace, source_id).hex
```

This above code snippet is useful if you know the `source_domain` and `source_id`
and you want to determine the `channel_id` without crating a `ChannelNode` object.

The `ChannelNode` class implements the following methods:

```python
class ChannelNode(Node):
    def get_domain_namespace(self):
        return uuid.uuid5(uuid.NAMESPACE_DNS, self.source_domain)
    def get_node_id(self):
        return uuid.uuid5(self.get_domain_namespace(), self.source_id)
```
Given a channel object `ch`, you can find its id using `channel_id = ch.get_node_id().hex`.



Node IDs
--------
Content nodes within the Kolibri ecosystem have the following identifiers:
  - `source_id` (str): arbitrary string used to identify content item within the
    source website, e.g., the a database id or URL.
  - `node_id` (uuid): an identifier for the content node within the channel tree
  - `content_id` (uuid): an identifier derived from the channel source_domain
    and the content node's `source_id` used for tracking a user interactions with
    the content node (e.g. video watched, or exercise completed).

When a particular piece of content appears in multiple channels, or in different 
places within a tree, the `node_id` of each occurrence will be different, but the
`content_id` of each item will be the same for all copies. In other words, the
`content_id` keeps track of the "is identical to" information about content nodes.
See next section for more info about Content IDs.

Content nodes inherit from the `TreeNode` class, which implements the following methods:

```python
class TreeNode(Node):
    def get_domain_namespace(self):
        return self.domain_ns if self.domain_ns else self.parent.get_domain_namespace()
    def get_content_id(self):
        return uuid.uuid5(self.get_domain_namespace(), self.source_id)
    def get_node_id(self):
        return uuid.uuid5(self.parent.get_node_id(), self.get_content_id().hex)
```
The `content_id` identifier is computed based on the channel source domain,
and the `source_id` attribute of the content node. To find the `content_id` hex
value for a content node `node`, use `content_id = node.get_content_id().hex`.

The `node_id` of a content nodes within a tree is computed based on the parent
node's `node_id` and current node's `content_id`.



Content IDs
-----------
Every content node within the Kolibri platform is associated with a `content_id` field
that is attached to it throughout its journey: from the content source, to
content integration, transformations, transport, remixing, distribution, use,
and analytics. All these "downstream" content actions preserve the original `content_id`
which was computed based on the source domain (usually the domain name of the
content producer), and a unique source identifier that identifies this content item
within the source domain.


### Implementation
```python
domain_namespace = uuid.uuid5(uuid.NAMESPACE_DNS, source_domain)
content_id = uuid.uuid5(domain_namespace, source_id)
```
The values of `source_domain` and `source_id` can be arbitrary strings. By
convention `source_domain` is set to the domain name of the content source,
e.g. `source_domain="khanacademy.org"`. The `source_id` is set to "primary key"
of the source database or a canonical URI.


### Applications

  - `content_id`s allows us to correctly assign "activity completed" credit for
    content items that appears in multiple places within a channel, or in remixed versions.
  - Serves as a common identifier for different formats of the same content item,
    like "high res" and "low res" versions of a Khan Academy video,
    or ePub and HTML versions of an African Storybook story.
  - Enables content analytics and tracking usage of a piece of content regardless
    of which channel it was obtained from.
  - Allows us to match identical content items between different catalogues
    and content management systems since `content_id`s is based on canonical source ids.

Note it is a non-trivial task to set `source_domain` and `source_id` to the correct
values and often requires some "reverse engineering" of the source website.
Chef authors must actively coordinate the dev work across different projects
to ensure the values of `content_id` for the same content items in different channels
are computed consistently. For example, if the current chef you are working on
has content overlap with items in another channel, you must look into how it computes its
source_domain and source_id and use the same approach to get matching `content_id`s.
This cheffing-time deduplication effort is worth investing in, because it makes
possible all the applications described above.

