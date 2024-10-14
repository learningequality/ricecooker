class FileSlice(object):
    """
    File-like object that represents a slice of a file, starting from its
    current offset until `count`. Reads are always relative to the slice's
    start and end point.
    """

    def __init__(self, file, count=None):
        self.file = file
        self.start = file.tell()

        file.seek(0, 2)
        self.file_size = file.tell()

        if count is None:
            count = self.file_size

        count = min(self.file_size - self.start, count)
        self.end = self.start + count

        # Seek to the end of the file so the next FileSlice object will be
        # created from that point.
        file.seek(self.end)

        self.__last_offset = self.start

    @classmethod
    def from_file(cls, file, chunk_size):
        slice = cls(file, chunk_size)
        yield slice

        while slice.end < slice.file_size:
            slice = cls(file, chunk_size)
            yield slice

    @property
    def size(self):
        return self.end - self.start

    def seek(self, offset, whence=0):
        if whence == 0:
            offset = self.start + offset
        elif whence == 1:
            offset = self.tell() + offset
        elif whence == 2:
            offset = self.end + offset
        self.file.seek(offset)
        self.__store_offset()
        return self.__last_offset

    def __reset_offset(self):
        if self.file.tell() != self.__last_offset:
            self.file.seek(self.__last_offset)

    def __store_offset(self):
        self.__last_offset = self.file.tell()

    def tell(self):
        self.__reset_offset()
        return self.file.tell() - self.start

    def read(self, count=None):
        self.__reset_offset()

        if count is None:
            count = self.size

        remaining = max(0, self.size - self.tell())

        buffer = self.file.read(min(count, remaining))
        self.__store_offset()
        return buffer

    def write(self, string):
        raise NotImplementedError()
