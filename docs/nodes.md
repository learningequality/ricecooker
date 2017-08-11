
Nodes
=====


Base class

    class Node(object)

Channel and it's tree's root node:

    class ChannelNode(Node)
    class TreeNode(Node)


Folder nodes

    class TopicNode(TreeNode)


Content nodes

    class ContentNode(TreeNode)
    class VideoNode(ContentNode)
    class AudioNode(ContentNode)
    class DocumentNode(ContentNode)
    class HTML5AppNode(ContentNode)
    class ExerciseNode(ContentNode)