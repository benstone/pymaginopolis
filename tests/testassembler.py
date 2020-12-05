import io
import string
import unittest

import pymaginopolis.scriptengine.assembler as assembler
import pymaginopolis.scriptengine.disassembler as disassembler
import pymaginopolis.scriptengine.model as scriptmodel


class AssemblerTests(unittest.TestCase):
    def test_pack_variable_char(self):
        """ Test packing chars for variable names """

        test_values = string.ascii_letters + string.digits + "_"
        for c in test_values:
            self.assertEqual(c, disassembler.parse_variable_char(assembler.pack_variable_char(c)))

    def test_pack_variable_name(self):
        """ Test packing a packed variable name """
        expected_bytes = bytearray([0xDE, 0xDB, 0x56, 0xCF, 0x3D, 0x00])

        packed_variable_name = assembler.pack_variable_name("siiLoop")

        self.assertEqual(expected_bytes, packed_variable_name)

    def test_assemble_script(self):
        test_script = scriptmodel.Script()

        # Push 7 and 3 to the stack
        test_script.instructions.append(scriptmodel.Instruction(0, params=[10, 7], address=2))
        # Add them
        test_script.instructions.append(scriptmodel.Instruction(0x100, address=5))

        assembled_script = assembler.assemble_script(test_script)

        disassembled_script = disassembler.disassemble_script(io.BytesIO(assembled_script))

        self.assertEqual(2, len(disassembled_script.instructions))
        self.assertEqual(0, disassembled_script.instructions[0].opcode)
        self.assertEqual(2, len(disassembled_script.instructions[0].params))
        self.assertEqual(0x100, disassembled_script.instructions[1].opcode)
