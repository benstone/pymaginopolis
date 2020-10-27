import struct

import pymaginopolis.chunkyfile.model as model

DEFAULT_VERSION = model.Version(5, 4)

# Known file types
FILE_TYPE_3DMM = "SOC "
# Other unknown file types: "CHED" (chunk editor?), "CHMP" (?)

DEFAULT_FILE_TYPE = FILE_TYPE_3DMM
DEFAULT_ENDIANNESS = model.Endianness.LittleEndian
DEFAULT_CHARACTER_SET = model.CharacterSet.ANSI

# TODO: maybe refactor this
CHARACTER_SETS = {
    model.CharacterSet.ANSI: "cp1252",
    model.CharacterSet.UTF16LE: "utf-16le"
}

FILE_HEADER_SIZE = 128
INDEX_HEADER_SIZE = 20


def string_to_tag_bytes(tag_str):
    """
    Convert a tag into raw bytes
    :param tag_str: tag (eg. "MBMP")
    :return: tag bytes (eg. b'\x50\x4d\x42\x4d')
    """
    tag_bytes = tag_str.encode("ansi")
    tag_bytes += b'\x00' * (4 - len(tag_bytes))
    return tag_bytes[::-1]


def generate_file_header(file_size, index_offset, index_size, file_type=None):
    # Set defaults
    if file_type is None:
        file_type = DEFAULT_FILE_TYPE

    file_magic = b'CHN2'
    file_type_magic = string_to_tag_bytes(file_type)
    version = DEFAULT_VERSION
    endianness = DEFAULT_ENDIANNESS
    characterset = DEFAULT_CHARACTER_SET
    post_index_offset = index_offset + index_size
    post_index_size = 0

    pieces = [file_magic, file_type_magic, version.major, version.minor, endianness.value, characterset.value,
              file_size, index_offset, index_size, post_index_offset, post_index_size
              ]

    return struct.pack("<4s4s4H5I92x", *pieces)


def generate_index_header(number_of_entries, chunk_attributes_size):
    # FUTURE: Make configurable
    endianness = DEFAULT_ENDIANNESS
    characterset = DEFAULT_CHARACTER_SET
    unknown1 = 0xFFFFFFFF
    unknown2 = 20

    pieces = [endianness.value, characterset.value, number_of_entries, chunk_attributes_size, unknown1, unknown2]
    return struct.pack("<2H4I", *pieces)


def generate_chunk_attributes(chunk, file_offset, data_size, number_of_parents):
    # Pack header

    packed_data_size = bytearray((data_size & 0xFF, (data_size >> 8) & 0xFF, (data_size >> 16) & 0xFF))
    header_pieces = (string_to_tag_bytes(chunk.chunk_id.tag), chunk.chunk_id.number,
                     file_offset, chunk.flags.value, packed_data_size,
                     len(chunk.children), number_of_parents
                     )
    ca = struct.pack("<4sIIB3sHH", *header_pieces)

    # Write the list of children
    for child in chunk.children:
        packed_tag = string_to_tag_bytes(child.ref.tag)
        ca += struct.pack("<4s2I", packed_tag, child.ref.number, child.chid)

    # Write the chunk name
    if chunk.name:
        assert len(chunk.name) <= 255

        # FUTURE: Currently only support ANSI
        character_set = DEFAULT_CHARACTER_SET
        ca += struct.pack("<HB", character_set.value, len(chunk.name))
        ca += (chunk.name + "\x00").encode(CHARACTER_SETS[character_set])

    return ca


def write_to_file(chunky_file, file):
    """
    Save a 3DMM chunky file
    :param chunky_file: ChunkyFile object
    :param file: file to write to
    """

    # File layout:
    # Header | Chunk Data | Index Header | Chunk Attributes | Index Entries | Post-Index

    # Reserve 128 bytes for the header
    file.seek(128)

    # Write out the data for each chunk
    chunk_info = {}
    for chunk in chunky_file.chunks:
        this_chunk_data = chunk.encoded_data
        this_chunk_offset = file.tell()
        file.write(this_chunk_data)

        # Keep track of chunk offsets and sizes
        if chunk.chunk_id not in chunk_info:
            chunk_info[chunk.chunk_id] = dict()
        chunk_info[chunk.chunk_id]["offset"] = this_chunk_offset
        chunk_info[chunk.chunk_id]["size"] = len(this_chunk_data)

        # While we're here, keep track of the number of parents of each chunk
        for child in chunk.children:
            if child.ref not in chunk_info:
                chunk_info[child.ref] = dict()
            if chunk_info[child.ref].get("parents") is None:
                chunk_info[child.ref]["parents"] = 1
            else:
                chunk_info[child.ref]["parents"] += 1

    # Reserve space for the index header
    index_offset = file.tell()
    # file.write(b'\x00' * 0x14)
    file.seek(INDEX_HEADER_SIZE, 1)

    # Write out attributes for each chunk.
    index_entries = list()

    ca_total_size = 0
    for chunk in chunky_file.chunks:

        file_offset = chunk_info[chunk.chunk_id]["offset"]
        data_size = chunk_info[chunk.chunk_id]["size"]
        number_of_parents = chunk_info[chunk.chunk_id].get("parents", 0)

        ca = generate_chunk_attributes(chunk, file_offset, data_size, number_of_parents)

        this_ca_pos = ca_total_size
        this_ca_size = len(ca)
        ca_total_size += this_ca_size

        index_entries.append((chunk.chunk_id, this_ca_pos, this_ca_size))
        file.write(ca)

        # Chunk attribute lists generated by 3DMM are aligned to four bytes
        padding = (4 - (ca_total_size % 4))
        if padding < 4:
            file.write(b'\x00' * padding)
            ca_total_size += padding

    # Write the index entries
    # the index should be sorted by chunk tag and chunk number
    for chunk_id, chunk_pos, chunk_size in sorted(index_entries, key=lambda i: i[0]):
        index_entry = struct.pack("<II", chunk_pos, chunk_size)
        file.write(index_entry)

    total_file_size = file.tell()

    # Write index header
    file.seek(index_offset)
    file.write(generate_index_header(len(index_entries), ca_total_size))

    # Write header at the start of the file
    index_size = total_file_size - index_offset
    header = generate_file_header(total_file_size, index_offset, index_size)
    file.seek(0)
    file.write(header)