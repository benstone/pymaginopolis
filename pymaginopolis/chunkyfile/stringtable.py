import logging
import struct

from pymaginopolis.chunkyfile.common import parse_pascal_string, parse_grpb_list, generate_pascal_string
from pymaginopolis.chunkyfile.model import Endianness, CharacterSet, Serializable

LOGGER = logging.getLogger(__name__)

GST_INDEX_ENTRY_SIZE = 8


class StringTable(dict, Serializable):
    """ String table loaded from a GST chunk"""

    def __init__(self, endianness=None, characterset=None):
        super().__init__()
        self.endianness = endianness if endianness else Endianness.LittleEndian
        self.characterset = characterset if characterset else CharacterSet.ANSI

    def to_buffer(self):
        # Generate string heap and index
        string_index = bytearray()
        string_data = bytearray()
        string_data_pos = 0
        for string_id, string_value in self.items():
            # Add to heap
            string_data += generate_pascal_string(self.characterset, string_value)

            # Add to index
            string_index += struct.pack("<II", string_data_pos, string_id)
            string_data_pos += len(string_value) + 1

        # Generate header
        pieces = [self.endianness.value, self.characterset.value,
                  GST_INDEX_ENTRY_SIZE, len(self), len(string_data), 0xFFFFFFFF]
        header = struct.pack("<2H4I", *pieces)

        return header + string_data + string_index

    @staticmethod
    def from_buffer(data):

        # Read the base GL list
        endianness, characterset, index_entry_size, index_items, heap = parse_grpb_list(data)

        # TODO: Support other types of string tables
        # - movies have a string table that uses a 32 byte index entry
        # - there is one GSTX chunk in STUDIO.chk that uses four byte index entries
        assert index_entry_size == 8

        new_table = StringTable(endianness, characterset)

        # Read the string index
        for item_data in index_items:
            string_pos, index = struct.unpack("<2I", item_data[0:8])
            string_value, _ = parse_pascal_string(characterset, heap[string_pos:])
            new_table[index] = string_value

        return new_table
