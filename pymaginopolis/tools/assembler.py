import argparse
import logging
import re

import pymaginopolis.chunkyfile.chunkxml as chunkyfilexml
import pymaginopolis.chunkyfile.model as chunkyfilemodel
import pymaginopolis.chunkyfile.stringtable as stringtable
import pymaginopolis.scriptengine.constants as knownconstants
import pymaginopolis.scriptengine.formatter as scriptformatter
import pymaginopolis.scriptengine.model as scriptmodel
import pymaginopolis.scriptengine.opcodes as opcodes
import pymaginopolis.tools.util as scriptutils
from pymaginopolis.scriptengine.assembler import AssembleScriptException, assemble_script

logger = logging.getLogger(__name__)

LABEL_FORMAT = re.compile("^[A-Za-z_@$][A-Za-z0-9_@$]+$")
STRING_ID_FORMAT = re.compile("^string\:((0x)?\d+)$", re.IGNORECASE)
DEFINE_FORMAT = re.compile("^([A-Za-z0-9_@$]+)\s+equ\s+((0x)?[0-9a-fA-F]+)$")


def parse_number(str):
    """ Parse a decimal or hex string as an integer """
    return int(str, 0)


def parse_value(param, constants=None):
    """ Parse a string ID, or integer value. """
    # Check if it is a constant
    if constants and param in constants:
        return constants[param]

    # Check if it's a string ID reference
    string_id_match = STRING_ID_FORMAT.match(param)
    if string_id_match:
        return 0x80000000 + parse_number(string_id_match.group(1))

    # Check if it is a label that we can resolve later
    if LABEL_FORMAT.match(param):
        return LabelReference(param)

    # Try parsing as a number
    return parse_number(param)


class LabelReference():
    def __init__(self, label_name):
        self.label_name = label_name


def parse_and_assemble(input_file, opcode_list, verbose=False):
    """ Parse a script """

    # TODO: rewrite this using a real parser!

    # Generate reverse lookup for opcodes
    string_to_opcode = {opcode.mnemonic.lower(): opcode_id for opcode_id, opcode in opcode_list.items()}

    # Load known constants
    defs = knownconstants.load_constants()
    defs = {v: k for k, v in defs.items()}

    string_table = None
    script = None
    script_chunk_tag = None
    script_chunk_number = None
    string_table_chunk_tag = "GSTX"
    string_table_chunk_number = None

    # instruction pointer starts at 2
    instruction_pointer = 2
    labels = {"start": instruction_pointer}
    stack = list()

    for line_number, line in enumerate(input_file):
        # Remove whitespace and comments. This is pretty rough.
        line = line.strip()
        while "#" in line:
            line = line[:line.find("#")]
        line = line.strip()

        if len(line) == 0:
            continue

        # Check if this is a define
        define_match = DEFINE_FORMAT.match(line)
        if define_match:
            define_name, define_value_str, _ = define_match.groups()
            define_value = parse_number(define_value_str)
            if define_name in defs:
                logger.warning("replacing const value %s with 0x%x (was 0x%x)", define_name, define_value,
                               defs[define_name])
            defs[define_name] = define_value
            continue

        # Split line into components
        split_line = re.match("^((?P<label>[A-Za-z0-9_@]+)\:\s*)?(?P<cmd>[A-Za-z]+)?\s*(?P<args>.*)$", line)
        if not split_line:
            continue

        label_name = split_line.group("label")
        command = split_line.group("cmd").lower()
        args = split_line.group("args")

        # Handle labels first
        if label_name:
            if label_name in labels:
                raise AssembleScriptException("Label %s already defined" % label_name)
            labels[label_name] = instruction_pointer

            if not command:
                continue

        if command == "stringtable":
            # Create a new stringtable

            if not args:
                raise AssembleScriptException("syntax: stringtable <string-table-chunk-no>")
            string_table_chunk_number = parse_number(args)

            if string_table is not None:
                raise AssembleScriptException("String table already defined")

            logger.debug("Creating string table: GSTX 0x%x", string_table_chunk_number)
            string_table = stringtable.StringTable()

        elif command == "string":
            string_id = None
            string_value = None

            if args:
                string_args = args.split()
                if len(string_args) >= 2:
                    string_id = parse_number(string_args[0])
                    string_value = " ".join(string_args[1:]).strip("\"")

            if not string_id or not string_value:
                raise AssembleScriptException("syntax: string <id> <quoted-string>")

            logger.debug("Adding to string table: 0x%x -> %s", string_id, string_value)
            string_table[string_id] = string_value
        elif command == "script":
            # New script directive

            script_chunk_tag = None
            script_chunk_number = None

            if args:
                script_args = args.split()
                if len(script_args) == 2:
                    script_chunk_tag = script_args[0].upper()
                    script_chunk_number = parse_number(script_args[1])

            if script_chunk_tag is None or script_chunk_number is None:
                raise AssembleScriptException("syntax: script chunk-tag chunk-number")

            if script_chunk_tag != "GLSC" and script_chunk_tag != "GLOP":
                raise AssembleScriptException("invalid script chunk tag type")

            if script is not None:
                raise AssembleScriptException("Cannot have more than one script in a source file yet")

            # Use same version as in 3DMM
            compiler_version = chunkyfilemodel.Version(29, 16)
            script = scriptmodel.Script(endianness=chunkyfilemodel.Endianness.LittleEndian,
                                        characterset=chunkyfilemodel.CharacterSet.ANSI,
                                        compilerversion=compiler_version)

        elif command == "push":
            # Special handling for PUSH instructions
            if not args:
                raise AssembleScriptException("syntax: push <value>")

            stack.append(parse_value(args, defs))

        elif command in string_to_opcode:
            # It's an opcode
            opcode = opcode_list[string_to_opcode[command]]

            # Check if we have a variable name
            variable_name = None
            if args:
                variable_name = args

            # If there's existing stuff on the stack, generate a PUSH instruction
            if len(stack) > 0:
                push_instruction = scriptmodel.Instruction(opcode=0, params=list(stack), address=instruction_pointer)
                stack.clear()
                script.instructions.append(push_instruction)
                instruction_pointer += push_instruction.number_of_dwords

            # Generate this instruction
            this_instruction = scriptmodel.Instruction(opcode=opcode.opcode, address=instruction_pointer,
                                                       variable=variable_name)
            script.instructions.append(this_instruction)
            instruction_pointer += this_instruction.number_of_dwords
        else:
            raise AssembleScriptException("invalid command: %s", command)

    # Add trailing PUSH instruction if required
    if len(stack) > 0:
        push_instruction = scriptmodel.Instruction(opcode=0, params=list(stack))
        stack.clear()
        script.instructions.append(push_instruction)
        instruction_pointer += push_instruction.number_of_dwords()

    # Log defined labels
    if len(labels.items()) > 0 and verbose:
        logger.debug("Labels:")
        for label_name, label_instruction_pointer in labels.items():
            logger.debug("%s: %d", label_name, label_instruction_pointer)

    # Resolve defined labels:
    for ins_pos in range(0, len(script.instructions)):
        if len(script.instructions[ins_pos].params) > 0:
            for param_pos, param in enumerate(script.instructions[ins_pos].params):
                if isinstance(param, LabelReference):

                    # hack to handle output from disassembler
                    if param.label_name[0] == "$":
                        param.label_name = "@" + param.label_name[1:]

                    label_ip = labels.get(param.label_name)
                    if label_ip is None:
                        raise AssembleScriptException("Label %s not found" % param.label_name)

                    # Replace parameter with resolved value
                    script.instructions[ins_pos].params[param_pos] = 0xCC000000 + label_ip

    # Create a chunky file containing the script and string table
    chunky_file = chunkyfilemodel.ChunkyFile(endianness=chunkyfilemodel.Endianness.LittleEndian,
                                             characterset=chunkyfilemodel.CharacterSet.ANSI,
                                             file_type="ASMX")

    if string_table:
        if verbose:
            logger.debug("String table:")
            for string_id, string_value in string_table.items():
                logger.debug("0x%x: %s", string_id, string_value)

        string_table_data = string_table.to_buffer()
        string_table_chunk = chunkyfilemodel.Chunk(tag=string_table_chunk_tag,
                                                   number=string_table_chunk_number,
                                                   data=string_table_data)

        chunky_file.chunks.append(string_table_chunk)

    if script:
        if verbose:
            logger.debug("Script:")
            script_formatter = scriptformatter.TextScriptFormatter()

            logger.debug(
                script_formatter.format_script(script, chunkyfilemodel.ChunkId(script_chunk_tag, script_chunk_number)))

        script_data = assemble_script(script)
        script_chunk = chunkyfilemodel.Chunk(tag=script_chunk_tag,
                                             number=script_chunk_number,
                                             data=script_data)
        if string_table:
            string_table_id = chunkyfilemodel.ChunkId(string_table_chunk_tag, string_table_chunk_number)
            string_table_child = chunkyfilemodel.ChunkChild(chid=0, ref=string_table_id)
            script_chunk.children.append(string_table_child)

        chunky_file.chunks.append(script_chunk)

    return chunky_file


def parse_args():
    parser = argparse.ArgumentParser(description="Assemble a script to an XML file + chunk data files")
    scriptutils.add_default_args(parser, "assembler")
    parser.add_argument("input", type=scriptutils.file_path, help="Script text file")
    parser.add_argument("--output", help="XML file")
    parser.add_argument("--build-dir", type=scriptutils.directory_path, help="Directory to write chunk data to",
                        default=None)
    parser.add_argument("--verbose", type=bool, help="More output", default=False)
    args = parser.parse_args()
    return args


def main():
    args = parse_args()
    scriptutils.configure_logging(args)

    logger = logging.getLogger(__name__)

    script_file_path = args.input
    output_xml_path = args.output
    build_dir = args.build_dir

    opcode_list = opcodes.load_opcode_list()

    logger.debug("Loading script file: %s", script_file_path)
    with open(script_file_path, "r") as script_file:
        result_chunky_file = parse_and_assemble(script_file, opcode_list, args.verbose)

    # Generate chunky file XML
    chunky_file_xml = chunkyfilexml.chunky_file_to_xml(result_chunky_file, build_dir)

    if output_xml_path:
        logger.debug("Writing XML file: %s", output_xml_path)
        with open(output_xml_path, "w") as output_xml_file:
            output_xml_file.write(chunky_file_xml)
    else:
        print(chunky_file_xml)


if __name__ == "__main__":
    main()
