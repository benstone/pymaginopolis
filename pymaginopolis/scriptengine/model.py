import enum

import pymaginopolis.chunkyfile.model as chunkymodel

# Compiler version from 3DMM
DEFAULT_COMPILER_VERSION = chunkymodel.Version(0x1D, 0x10)


class DataType(enum.Enum):
    Long = 0
    Address = 1
    StringID = 2
    GobID = 3


class Parameter:
    def __init__(self, name, type=None, description=None):
        self.name = name
        self.type = type if type else DataType.Long
        self.description = description if description else ""


class Opcode:
    def __init__(self, opcode, mnemonic=None, stack_params=0, varargs=False, returns=None, description=None):
        self.opcode = opcode
        self.mnemonic = mnemonic if mnemonic else "opcode_0x%x" % opcode
        self.varargs = varargs
        self.returns = returns
        self.description = description
        self.parameters = list([Parameter("param%d" % n) for n in range(0, stack_params)])

    def __str__(self):
        return "0x%x: %s" % (self.opcode, self.mnemonic)


class Instruction:
    def __init__(self, opcode, variable=None, params=None, original_bytes=None, address=None):
        self.opcode = opcode
        self.params = list(params) if params else list()
        self.variable = variable
        self.original_bytes = original_bytes
        self.address = address

    @property
    def is_variable(self):
        return self.variable is not None

    @property
    def number_of_dwords(self):
        # Calculate the number of DWORDs that make up this instruction
        header_size = 2 if self.variable else 1
        return header_size + len(self.params)


class Script:
    def __init__(self, endianness=None, characterset=None, compilerversion=None):
        self.endianness = endianness if endianness else chunkymodel.Endianness.LittleEndian
        self.characterset = characterset if characterset else chunkymodel.CharacterSet.ANSI
        self.compilerversion = compilerversion if compilerversion else DEFAULT_COMPILER_VERSION
        self.instructions = list()

    def __str__(self):
        return f"Script: compiler={self.compilerversion} endianness={self.endianness} character set={self.characterset} instructions={len(self.instructions)}"
