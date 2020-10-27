import struct

from pymaginopolis.chunkyfile import model as model
from pymaginopolis.chunkyfile.model import Endianness, CharacterSet

GRPB_HEADER_SIZE = 20

CHARACTER_SETS = {
    model.CharacterSet.ANSI: "latin1",
    model.CharacterSet.UTF16LE: "utf-16le"
}


def get_string_size_format(characterset):
    # FUTURE: big endian
    if characterset == model.CharacterSet.UTF16BE or characterset == model.CharacterSet.UTF16LE:
        return "H", 2, 2
    else:
        return "B", 1, 1


def parse_pascal_string_with_encoding(data):
    """
    Read a character set followed by a pascal string
    :param data:
    :return: tuple containing string, number of bytes consumed and characterset
    """
    # Read character set
    character_set = struct.unpack("<H", data[0:2])[0]
    character_set = model.CharacterSet(character_set)

    chunk_name, string_size = parse_pascal_string(character_set, data[2:])
    return chunk_name, string_size + 2, character_set


def parse_pascal_string(characterset, data):
    """
    Read a Pascal string from a byte array using the given character set.
    :param characterset: Character set to use to decode the string
    :param data: binary data
    :return: tuple containing string and number of bytes consumed
    """
    string_size_format, string_size_size, character_size = get_string_size_format(characterset)

    if len(data) < string_size_size:
        raise FileParseException("String size truncated")

    string_size = struct.unpack("<" + string_size_format, data[0:string_size_size])[0] * character_size
    string_data = data[string_size_size:string_size_size + string_size]
    result = string_data.decode(CHARACTER_SETS[characterset])

    total_size = string_size_size + string_size
    return result, total_size


def generate_pascal_string(characterset, value):
    string_size_format, string_size_size, character_size = get_string_size_format(characterset)
    encoded_string = value.encode(CHARACTER_SETS[characterset])
    return struct.pack("<" + string_size_format, len(value)) + encoded_string


class FileParseException(Exception):
    """ Raised if a problem is found with the chunky file. """
    pass


def check_size(expected, actual, desc):
    """ Raise an exception if this part of the file is truncated """
    if actual < expected:
        raise FileParseException("%s truncated: expected 0x%x, got 0x%x" % (desc, expected, actual))


def parse_u24le(data):
    """ Parse a 24-bit little endian number """
    return data[0] | (data[1] << 8) | (data[2] << 16)


def parse_endianness_and_characterset(data):
    check_size(4, len(data), "Endianness/characterset")
    endianness, characterset = struct.unpack("<2H", data)
    endianness = model.Endianness(endianness)
    characterset = model.CharacterSet(characterset)
    return endianness, characterset,


def tag_bytes_to_string(tag):
    """
    Convert the raw bytes for a tag into a string
    :param tag: bytes (eg. b'\x50\x4d\x42\x4d')
    :return: tag (eg. "MBMP")
    """
    return tag[::-1].decode("ansi").rstrip("\x00")


def parse_grpb_list(data):
    """
    Parse a GRPB chunk
    :param data: GRPB chunk
    :return: tuple containing endianness, characterset, index entry size, item index and item heap
    """

    endianness, characterset, index_entry_size, number_of_entries, heap_size, unk1 = struct.unpack("<2H4I", data[
                                                                                                            0:GRPB_HEADER_SIZE])
    endianness = Endianness(endianness)
    characterset = CharacterSet(characterset)

    # TODO: figure out what this is
    if unk1 != 0xFFFFFFFF:
        raise NotImplementedError("can't parse this GRPB because unknown1 isn't 0xFFFFFFFF")

    # Read heap
    heap = data[GRPB_HEADER_SIZE:GRPB_HEADER_SIZE + heap_size]

    # Read index
    index_size = index_entry_size * number_of_entries
    index_data = data[GRPB_HEADER_SIZE + heap_size:GRPB_HEADER_SIZE + heap_size + index_size]
    index_items = [index_data[i * index_entry_size:(i + 1) * index_entry_size] for i in range(0, number_of_entries)]

    return endianness, characterset, index_entry_size, index_items, heap
