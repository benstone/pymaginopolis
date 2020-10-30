import logging
import struct

import pymaginopolis.chunkyfile.common
import pymaginopolis.chunkyfile.model as filemodel
import pymaginopolis.scriptengine.model as scriptmodel
from functools import lru_cache

LOGGER = logging.getLogger(__name__)

SCRIPT_HEADER_SIZE = 16


class DisassemblerException(Exception):
    pass


@lru_cache(32)
def parse_variable_name(packed_bytes):
    """ Unpack a 6-bit packed variable name """
    variable_name = ""
    this_char = 0
    read_bits = 0
    for byte in packed_bytes:

        # Read six bits at a time
        for bit in range(0, 8):
            bit_value = 1 & (byte >> (7 - bit))
            this_char = this_char | (bit_value << (5 - read_bits))
            read_bits += 1

            if read_bits == 6:
                # Convert to a char
                this_char = parse_variable_char(this_char)
                variable_name += this_char

                # Reset
                this_char = 0
                read_bits = 0
    return variable_name


def parse_variable_char(packed):
    """ Map a 6-bit packed char to ASCII """
    packed_char = packed
    if packed_char == 0:
        return ""
    if 1 <= packed_char <= 10:
        return chr(ord('0') - 1 + packed_char)
    elif 11 <= packed_char <= 36:
        return chr(ord('A') - 11 + packed_char)
    elif 37 <= packed_char <= 62:
        return chr(ord('a') - 37 + packed_char)
    else:
        return "_"


def read_instruction(stream):
    """ Read an instruction and operands from a stream """

    # Layout:
    # Variable: | V1 | V0 | CP | OP | V5 | V4 | V3 | V2 | PARAM  ONE |
    # Non-Var:  | OPCODE  | CP | 0  | PARAM ONE         | PARAM TWO  |

    # Read variable opcode / fixed flag + count
    # for some reason this is the reverse of the patent
    original_bytes = stream.read(4)

    var_or_opcode, count, flag = struct.unpack("2sBB", original_bytes)

    variable_name = None

    if flag == 0:
        # fixed opcode (no variable name)
        opcode = struct.unpack("<H", var_or_opcode)[0]
    else:
        # variable opcode
        opcode = flag
        packed_var_second_half = stream.read(4)
        original_bytes += packed_var_second_half
        packed_var_name = var_or_opcode[::-1] + packed_var_second_half[::-1]
        variable_name = parse_variable_name(packed_var_name)
        count -= 1

    # count is number of dwords
    if count > 0:
        param_data = stream.read(4 * count)
        original_bytes += param_data
        params = struct.unpack("<%dL" % count, param_data)
    else:
        params = None

    instruction = scriptmodel.Instruction(opcode, variable=variable_name, params=params)
    return instruction


def parse_header(source):
    """
    Parse the header of the script.
    :returns a dict containing script endianness, character set, version and size.
    """
    if len(source) < SCRIPT_HEADER_SIZE:
        raise DisassemblerException("Script header truncated")

    endianness, characterset = pymaginopolis.chunkyfile.common.parse_endianness_and_characterset(source[0:4])

    if endianness != filemodel.Endianness.LittleEndian:
        raise DisassemblerException("Big endian not supported yet")

    body_size, major_version, minor_version = struct.unpack("<IBB", source[8:14])

    version = filemodel.Version(major_version, minor_version)

    return {"endianness": endianness, "characterset": characterset, "body_size": body_size, "version": version}


def disassemble_script(stream):
    # Read header
    header = parse_header(stream.read(SCRIPT_HEADER_SIZE))

    # Create new script
    script = scriptmodel.Script(header["endianness"], header["characterset"], header["version"])

    # Calculate script end
    script_end_pos = SCRIPT_HEADER_SIZE + (4 * (header["body_size"] - 1))

    # Read instructions
    while stream.tell() < script_end_pos:
        instruction_address = (stream.tell() - 8) // 4
        next_instruction = read_instruction(stream)
        next_instruction.address = instruction_address
        script.instructions.append(next_instruction)

    return script
