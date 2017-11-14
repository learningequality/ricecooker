
class PathBuilder:
    """
        Class for formatting paths to write to DataWriter
    """

    path = None             # List of items in path
    channel_name = None     # Name of channel

    def __init__(self, channel_name=None):
        """ Args: channel_name: (str) Name of channel """
        self.channel_name = channel_name or "Channel"
        self.path = [self.channel_name]

    def __str__(self):
        """ Converts path list to string
            e.g. [Channel, Topic, Subtopic] -> Channel/Topic/Subtopic
            Returns: str path
        """
        return "/".join(self.path)

    def reset(self):
        """ reset: Clear path
            Args: None
            Returns: None
        """
        self.path = [self.channel_name]

    def set(self, *path):
        """ set: Set path from root
            Args: *path: (str) items to add to path
            Returns: None
        """
        self.path = [self.channel_name]
        self.path.extend(list(path))

    def open_folder(self, path_item):
        """ open_folder: Add item to path
            Args: path_item: (str) item to add to path
            Returns: None
        """
        self.path.append(path_item)

    def go_to_parent_folder(self):
        """ go_to_parent_folder: Go back one level in path
            Args: None
            Returns: last item in path
        """
        if len(self.path) > 1:
            return self.path.pop()
