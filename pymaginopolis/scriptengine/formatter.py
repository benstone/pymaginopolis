import string

import pymaginopolis.scriptengine.constants as constants
import pymaginopolis.scriptengine.opcodes as opcodes


def is_dword_ascii_hex(i):
    result = True
    for x in range(0, 4):
        result = result and chr((i >> x * 8) & 0xFF) in string.printable
    return result


def dword_to_ascii(i):
    result = ""
    for x in range(0, 4):
        result = result + chr((i >> x * 8) & 0xFF)
    return result[::-1]


def format_param_value(i, known_constants=None, last_instruction=None):
    if known_constants is not None and i in known_constants:
        return known_constants[i]
    elif is_dword_ascii_hex(i):
        return "'%s'" % (dword_to_ascii(i))
    else:
        # Addresses in a script are prefixed with 0xCC
        if (i >> 24) == 0xCC:
            # The raw value is added to the instruction pointer, then it is incremented
            jump_target = ((i & 0x00FFFFFF) + 1)

            if jump_target > last_instruction:
                return "@end"
            else:
                return "$L_%04x" % jump_target
        elif (i >> 24) == 0x80:
            # String IDs are prefixed with 0x80
            return "string:0x%x" % (i & 0x00FFFFFF)
        else:
            return hex(i)


class ScriptFormatter:
    def format_script(self, script, chunk_id, chunk_name=None, file_name=None):
        raise NotImplementedError


class TextScriptFormatter(ScriptFormatter):
    """ Format a script as text.
    Uses an assembly dialect similar to the one found in CW2's disassembler.
    """

    def __init__(self, opcode_list=None, constant_list=None):
        self.opcode_list = opcode_list if opcode_list else opcodes.load_opcode_list()
        self.constants = constant_list if constant_list else constants.load_constants()

    def format_script(self, script, chunk_id, chunk_name=None, file_name=None):

        if file_name:
            file_name_prefix = str(file_name) + " "
        else:
            file_name_prefix = ""

        cid = str(chunk_id) if chunk_id else "unknown"
        if chunk_id is not None and chunk_name is not None:
            cid += " (%s)" % chunk_name

        # Add title
        result = f"{file_name_prefix}{cid} (0x{chunk_id.number:x})"
        result += "\n" + "=" * len(result) + "\n\n"

        last_instruction_address = None
        if len(script.instructions) > 0:
            last_instruction_address = script.instructions[-1].address

        for instruction in script.instructions:
            components = []

            # Address of this instruction
            address_str = f"@L_{instruction.address:04x}:"

            # Ignore Push instructions for now: they will be handled later
            if instruction.opcode != 0:
                components.append(address_str)

                # Find info about this opcode if available
                if instruction.opcode in self.opcode_list:
                    mnemonic = self.opcode_list[instruction.opcode].mnemonic
                else:
                    mnemonic = "Op0x%x" % instruction.opcode

                components.append(mnemonic)

                # Variable name
                if instruction.is_variable:
                    components.append(instruction.variable)

                result += "\t".join(components) + "\n"

                address_str = "        "

            # Print rest of the params as implicit Push instructions
            leftover_params = instruction.params
            for leftover_param in leftover_params:
                components = [address_str, "Push",
                              format_param_value(leftover_param, self.constants, last_instruction_address)]
                result += "\t".join(components) + "\n"
                address_str = "        "

        result += "@end:\n"

        return result
