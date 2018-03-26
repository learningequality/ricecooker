Notes for ricecooker library developers
=======================================




Computed identifiers
--------------------

### Channel ID

The `channel_id` (uuid hex str) property is an important identifier that:
  - Is used in the wire formats used to communicate between `ricecooker` and Kolibri Studio
  - Appears as part of URLs for on both Kolibri Studio and Kolibri
  - Determines the filename for the channel sqlite3 database file that Kolibri imports
    from Kolibri Studio.

To compute the `channel_id`, you need to know the channel's `source_domain` (a.k.a. `channel_info['CHANNEL_SOURCE_DOMAIN']`)
and the channel's `source_id` (a.k.a `channel_info['CHANNEL_SOURCE_ID']`):

    import uuid
    channel_id = uuid.uuid5(
        uuid.uuid5(uuid.NAMESPACE_DNS, source_domain),
        source_id
    ).hex

This above code snippet is useful if you know the `source_domain` and `source_id`
and you want to determine the `channel_id` without crating a `ChannelNode` object.

The `ChannelNode` class implements the following methods:

    class ChannelNode(Node):
        def get_domain_namespace(self):
            return uuid.uuid5(uuid.NAMESPACE_DNS, self.source_domain)
        def get_node_id(self):
            return uuid.uuid5(self.get_domain_namespace(), self.source_id)

Given a channel object `ch`, you can find its id using `channel_id = ch.get_node_id().hex`.




### Node IDs

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

Content nodes inherit from the `TreeNode` class, which implements the following methods:

    class TreeNode(Node):
        def get_domain_namespace(self):
            return self.domain_ns if self.domain_ns else self.parent.get_domain_namespace()
        def get_content_id(self):
            return uuid.uuid5(self.get_domain_namespace(), self.source_id)
        def get_node_id(self):
            return uuid.uuid5(self.parent.get_node_id(), self.get_content_id().hex)

The `content_id` identifier is computed based on the channel source domain,
and the `source_id` attribute of the content node. To find the `content_id` hex
value for a content node `node`, use `content_id = node.get_content_id().hex`.

The `node_id` of a content nodes within a tree is computed based on the parent
node's `node_id` and current node's `content_id`.
