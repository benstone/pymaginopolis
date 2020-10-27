import logging
import struct

import pymaginopolis.chunkyfile.model as model
from pymaginopolis.chunkyfile.common import parse_pascal_string_with_encoding, FileParseException, check_size, \
    parse_u24le, \
    parse_endianness_and_characterset, tag_bytes_to_string, CHARACTER_SETS

# Structure sizes
FILE_HEADER_SIZE = 0x24
INDEX_HEADER_SIZE = 0x14
CHUNK_ATTRIBUTES_HEADER_SIZE = 0x14
CHUNK_CHILD_SIZE = 0xc

LOGGER = logging.getLogger(__name__)


def parse_file_header(data):
    """ Parse the header of a chunky file. Returns a dictionary containing header information. """
    check_size(FILE_HEADER_SIZE, len(data), "File header")

    # Read file magic and file type
    file_magic, file_type_magic = struct.unpack("<4s4s", data[0:8])
    if file_magic != b'CHN2':
        raise FileParseException("Bad file header magic: expected CHN2, got %s", file_magic)

    # Read file version
    version_major, version_minor = struct.unpack("<2H", data[8:12])
    file_version = model.Version(version_major, version_minor)

    # Read endianness and character set.
    endianness, characterset = parse_endianness_and_characterset(data[12:16])

    if endianness == model.Endianness.BigEndian:
        raise FileParseException("Big endian chunky files are not supported yet")
    if characterset not in CHARACTER_SETS.keys():
        raise FileParseException("%s character set not supported yet" % characterset)

    # Read file size and offsets
    file_size, index_offset, index_size, post_index_offset, post_index_size = struct.unpack("<5I", data[16:36])

    result = {
        "file_type": tag_bytes_to_string(file_type_magic), "version": file_version,
        "endianness": endianness, "characterset": characterset, "file_size": file_size,
        "index_offset": index_offset, "index_size": index_size,
        "post_index_offset": post_index_offset, "post_index_size": post_index_size
    }

    return result


def parse_index_header(data):
    """
    Parse the index header
    :param data: raw index header data
    :return: a dict containing the parsed index header
    """
    check_size(INDEX_HEADER_SIZE, len(data), "Index header")

    # Read endianness and string type
    endianness, characterset = parse_endianness_and_characterset(data[0:4])
    number_of_entries, entries_size, unknown1, unknown2 = struct.unpack("<4I", data[4:20])

    # The unknown fields are usually these specific values:
    if unknown1 != 0xFFFFFFFF:
        LOGGER.warning("File header unknown1 is not expected value: 0x%x" % unknown1)

    if unknown2 != 20:
        LOGGER.warning("File header unknown2 is not expected value: 0x%x" % unknown2)

    result = {
        "endianness": endianness,
        "characterset": characterset,
        "number_of_entries": number_of_entries,
        "entries_size": entries_size,
        "unknown1": unknown1,
        "unknown2": unknown2
    }
    return result


def parse_chunk_attributes(data):
    """
    Parse chunk attributes
    :param data: raw chunk attribute data
    :return: dict containing information about the current chunk
    """
    check_size(CHUNK_ATTRIBUTES_HEADER_SIZE, len(data), "Chunk attributes")

    chunk_attributes = struct.unpack("<4sIIB3sHH", data[0:CHUNK_ATTRIBUTES_HEADER_SIZE])
    tag, number, offset, flags, size_packed, number_of_children, number_of_parents = chunk_attributes

    result = {
        # Tags are four byte little-endian ASCII strings
        "tag": tag_bytes_to_string(tag),
        "number": number,
        "offset": offset,
        "flags": model.ChunkFlags(flags),
        "size": parse_u24le(size_packed),  # This is a 24-bit number
        "children": number_of_children,
        "parents": number_of_parents,
    }

    # Read children
    pos = CHUNK_ATTRIBUTES_HEADER_SIZE
    children = []
    if number_of_children > 0:
        # TODO: validate enough bytes for the chunk attributes header

        expected_size = number_of_children * CHUNK_CHILD_SIZE
        check_size(expected_size, len(data) - pos, "Chunk attributes list")

        for r in range(0, number_of_children):
            child_data = data[pos:pos + CHUNK_CHILD_SIZE]
            tag, number, child_id = struct.unpack("<4s2I", child_data)
            tag = tag_bytes_to_string(tag)

            children.append({"tag": tag, "number": number, "chid": child_id})
            pos += CHUNK_CHILD_SIZE

    result["children"] = children

    # If we have trailing data, this is the chunk name
    if pos != len(data):
        chunk_name, _, _ = parse_pascal_string_with_encoding(data[pos:])
        result["name"] = chunk_name

    return result


def read_index(file, index_offset):
    # Read the index header
    file.seek(index_offset)
    index_header_data = file.read(INDEX_HEADER_SIZE)
    index_header = parse_index_header(index_header_data)
    LOGGER.debug("Parsed index header: %s", index_header)
    number_of_chunks = index_header["number_of_entries"]

    # Read each index entry to get the address of the chunk attributes
    file.seek(index_offset + INDEX_HEADER_SIZE + index_header["entries_size"])

    index_entries = []
    for i in range(0, number_of_chunks):
        offset, size = struct.unpack("<2I", file.read(8))
        index_entries.append((offset, size))

    # Read attributes for each chunk
    chunks = []
    has_compressed_chunks = False
    for (chunk_attributes_offset, chunk_attributes_size) in index_entries:
        file.seek(index_offset + INDEX_HEADER_SIZE + chunk_attributes_offset)
        chunk_attributes_data = file.read(chunk_attributes_size)

        attrs = parse_chunk_attributes(chunk_attributes_data)
        LOGGER.debug(attrs)

        # Read chunk data
        file.seek(attrs["offset"])
        chunk_data = file.read(attrs["size"])

        if not has_compressed_chunks and attrs["flags"] & model.ChunkFlags.Compressed:
            has_compressed_chunks = True

        # Create a new chunk
        children = [model.ChunkChild(t["chid"], model.ChunkId(t["tag"], t["number"])) for t in attrs["children"]]
        name = attrs.get("name")
        this_chunk = model.Chunk(attrs["tag"], attrs["number"], flags=attrs["flags"],
                                 data=chunk_data, children=children, name=name)
        chunks.append(this_chunk)

    return chunks


def load_from_file(file):
    """
    Load a 3DMM chunky file
    :param file: File object to read from
    :return: a chunky file object
    """

    # Read the header
    file_header_data = file.read(FILE_HEADER_SIZE)
    file_header = parse_file_header(file_header_data)
    LOGGER.debug("Parsed file header: %s", file_header)

    chunks = read_index(file, file_header["index_offset"])

    this_file = model.ChunkyFile(file_header["endianness"], file_header["characterset"], chunks=chunks,
                                 file_type=file_header["file_type"])
    return this_file
