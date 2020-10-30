import base64
import io
import unittest

import pymaginopolis.chunkyfile.model
from pymaginopolis.scriptengine import disassembler


class DisassemblerTests(unittest.TestCase):
    def test_parse_variable_name(self):
        """ Test parsing a packed variable name """
        packed_bytes = bytes([0xDE, 0xDB, 0x56, 0xCF, 0x3D, 0x00])

        parsed_variable_name = disassembler.parse_variable_name(packed_bytes)
        self.assertEqual("siiLoop", parsed_variable_name)

    def test_parse_variable_char(self):
        """ Test unpacking six-bit variable name chars """
        self.assertEqual("", disassembler.parse_variable_char(0))
        self.assertEqual("0", disassembler.parse_variable_char(1))
        self.assertEqual("9", disassembler.parse_variable_char(10))
        self.assertEqual("Z", disassembler.parse_variable_char(36))
        self.assertEqual("a", disassembler.parse_variable_char(37))
        self.assertEqual("z", disassembler.parse_variable_char(62))
        self.assertEqual("_", disassembler.parse_variable_char(63))

    def test_parse_variable_instruction_no_args(self):
        source = bytearray([0xDB, 0xDE, 0x01, 0x03, 0x00, 0x3D, 0xCF, 0x56])
        result = disassembler.read_instruction(io.BytesIO(source))

        self.assertEqual(3, result.opcode)
        self.assertEqual("siiLoop", result.variable)
        self.assertEqual(True, result.is_variable)
        self.assertEqual(0, len(result.params))

    def test_parse_fixed_instruction_no_args(self):
        source = bytearray([0x01, 0x10, 0x00, 0x00])
        result = disassembler.read_instruction(io.BytesIO(source))

        self.assertEqual(0x1001, result.opcode)
        self.assertEqual(False, result.is_variable)
        self.assertEqual(0, len(result.params))

    def test_parse_header(self):
        source = base64.b64decode("AQADAwQAAACGAAAAHRAdEA==")
        header = disassembler.parse_header(source)

        self.assertEqual(header["endianness"], pymaginopolis.chunkyfile.model.Endianness.LittleEndian)
        self.assertEqual(header["characterset"], pymaginopolis.chunkyfile.model.CharacterSet.ANSI)
        self.assertEqual(header["body_size"], 134)

    def test_disassemble_simple_script(self):
        # A sample script based on one from the patent
        source = base64.b64decode("AQADAwQAAAAEAAAAHRAdEAAAAgAKAAAABwAAAAABAAA=")
        script = disassembler.disassemble_script(io.BytesIO(source))
        self.assertEqual(1, len(script.instructions))

        # PUSH instruction
        self.assertEqual(0, script.instructions[0].opcode)
        self.assertEqual(2, len(script.instructions[0].params))


if __name__ == '__main__':
    unittest.main()
