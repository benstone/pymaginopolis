import struct

import pymaginopolis.chunkyfile.model as chunkyfilemodel


class AssembleScriptException(Exception):
    """ Raised if a problem is found with the chunky file. """
    pass


def pack_variable_char(c):
    if "0" <= c <= "9":
        return ord(c) - 48 + 1
    elif "A" <= c <= "Z":
        return ord(c) - 65 + 11
    elif "a" <= c <= "z":
        return ord(c) - 97 + 37
    elif "_" == c:
        return 63
    else:
        raise AssembleScriptException("Invalid char in variable name: %s" % c)


def assemble_script(script):
    """ Convert a script object into GLSC / GLOP chunk data """

    if script.endianness != chunkyfilemodel.Endianness.LittleEndian:
        raise AssembleScriptException("Unsupported endianness")

    total_dwords = sum([instruction.number_of_dwords for instruction in script.instructions]) + 1
    packed_version = struct.pack("<2B", script.compilerversion.major, script.compilerversion.minor)

    pieces = [script.endianness.value, script.characterset.value, 4, total_dwords]
    header = struct.pack("<2H2I", *pieces) + (packed_version * 2)

    instruction_data = bytearray()

    for instruction in script.instructions:
        # OP - opcode - byte (variable instructions) or short (all other instructions)
        # CP - number of parameters - byte
        # V - packed variable name: six bytes
        if instruction.is_variable:
            # Variable: | V1 | V0 | CP | OP | V5 | V4 | V3 | V2 | PARAM  ONE |
            packed_variable_name = pack_variable_name(instruction.variable)
            first_dword = struct.pack("<BBBB", packed_variable_name[1], packed_variable_name[0],
                                      len(instruction.params), instruction.opcode)
            second_dword = packed_variable_name[2:6][::-1]

            instruction_data.append(first_dword)
            instruction_data.append(second_dword)

        else:
            # Non-Var:  | OPCODE  | CP | 0  | PARAM ONE         | PARAM TWO  |
            instruction_data.extend(struct.pack("<HBB", instruction.opcode, len(instruction.params), 0))

        # Add params
        for param in instruction.params:
            instruction_data.extend(struct.pack("<I", param))

    return header + instruction_data


def pack_variable_name(variable_name):
    packed_var = bytearray()
    current_byte = 0
    bit_pos = 0

    # truncate variable name to eight chars
    for c in variable_name[0:8]:
        packed_char = pack_variable_char(c)

        if bit_pos < 2:
            this_char_bits = packed_char << (2 - bit_pos)
            current_byte |= this_char_bits
            bit_pos += 6
        else:
            top_bits = 8 - bit_pos
            bottom_bits = 6 - top_bits

            this_char_bits = packed_char & (((1 << top_bits) - 1) << bottom_bits)
            current_byte |= (this_char_bits >> bottom_bits)
            packed_var.append(current_byte)

            this_char_bits = packed_char & ((1 << bottom_bits) - 1)
            current_byte = this_char_bits << (8 - bottom_bits)

            bit_pos = bottom_bits

    # Add remaining byte
    if bit_pos > 0:
        packed_var.append(current_byte)

    # Ensure packed var is six bytes
    packed_var += b'\x00' * (6 - len(packed_var))

    return packed_var
