from collections import namedtuple
from enum import IntEnum, IntFlag


class Endianness(IntEnum):
    """ Endianness of pointers inside the file. """
    LittleEndian = 0x0001
    BigEndian = 0x0100


class CharacterSet(IntEnum):
    """ Character set used for strings in a chunky file. """

    # Common character sets
    ANSI = 0x0303
    UTF16LE = 0x0505

    # Uncommon character sets
    Macintosh = 0x0202
    UTF16BE = 0x0404


class ChunkFlags(IntFlag):
    Default = 0
    Loner = 2  # Set if the chunk does not have parents
    Compressed = 4  # Set if the chunk is compressed


class ChunkId(namedtuple("ChunkId", field_names=["tag", "number"])):
    """ Tuple of chunk tag and number """

    def __repr__(self):
        return "%s:%d" % (self.tag, self.number)


class Version(namedtuple("Version", field_names=["major", "minor"])):
    """ Major and minor version """

    def __repr__(self):
        return "%d.%d" % (self.major, self.minor)


class ChunkChild(namedtuple("ChunkChild", field_names=["chid", "ref"])):
    """ Relationship between a chunk and another chunk """

    def __repr__(self):
        return "%s: %d" % (self.ref, self.chid)


class Chunk:
    def __init__(self, tag, number, name=None, flags=None, data=None, children=None):
        self.chunk_id = ChunkId(tag, number)
        self.name = name
        self.raw_data = data
        self.flags = flags if flags is not None else ChunkFlags.Default
        self.children = children if children else list()

    @property
    def decoded_data(self):
        """ Get chunk data. Decompress if compressed. """
        if self.flags & ChunkFlags.Compressed:
            raise NotImplementedError("Chunk decompression not yet supported")
        else:
            return self.raw_data

    @property
    def encoded_data(self):
        """ Get chunk data, without decompression. """
        return self.raw_data


class ChunkyFile:
    def __init__(self, endianness, characterset, file_type=None, chunks=None):
        self.file_type = file_type if file_type else "TEST"
        self.endianness = endianness
        self.characterset = characterset
        self.chunks = chunks if chunks else []

    def __str__(self):
        return "ChunkyFile: %s %s/%s - %d chunks" % (
            self.file_type, self.endianness.name, self.characterset.name, len(self.chunks))

    def get_chunks(self, key):
        if type(key) is ChunkId:
            # Key is already a ChunkId
            pass
        elif type(key) is tuple and len(key) is 2:
            # Create a new ChunkId from the type
            key = ChunkId(tag=key[0], number=key[1])
        elif type(key) is str and len(key) <= 4:
            key = key + " " * (4 - len(key))
            # Return a list of chunks with the given tag
            return [c for c in self.chunks if c.chunk_id.tag == key]
        else:
            raise NotImplementedError

        found_chunks = [c for c in self.chunks if c.chunk_id == key]
        return found_chunks

    def __getitem__(self, key):
        """ Get a chunk or a list of chunks. Supports:
            * Getting a chunk by ChunkId: chunky_file[ChunkId("MVIE", 1")]
            * Getting a chunk by chunk tag and id: chunky_file[("MVIE", 1)]
            * Getting a list of chunks by chunk tag: chunky_file["MVIE"]
        """
        found_chunks = self.get_chunks(key)

        if len(found_chunks) == 0:
            raise KeyError(key)
        elif len(found_chunks) == 1:
            return found_chunks[0]
        else:
            return found_chunks

    def __contains__(self, key):
        found_chunks = self.get_chunks(key)
        return found_chunks is not None and len(found_chunks) == 1


class Serializable:
    """ A serializable object. """

    @staticmethod
    def from_buffer(data):
        raise NotImplementedError

    @classmethod
    def to_buffer(cls):
        raise NotImplementedError
