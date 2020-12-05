import argparse
import logging

import pymaginopolis.chunkyfile.chunkxml as chunkyfilexml
import pymaginopolis.chunkyfile.model as chunkyfilemodel
import pymaginopolis.chunkyfile.stringtable as stringtable
import pymaginopolis.scriptengine.formatter as scriptformatter
import pymaginopolis.scriptengine.model as scriptmodel
import pymaginopolis.scriptengine.opcodes as opcodes
import pymaginopolis.tools.util as scriptutils
from pymaginopolis.scriptengine.assembler import AssembleScriptException, assemble_script

logger = logging.getLogger(__name__)


def parse_number(str):
    """ Parse a decimal or hex string as an integer """
    if str.startswith("0x"):
        value = int(str[2:], 16)
    elif str.isnumeric():
        value = int(str)
    else:
        raise ValueError("not a number: %s", str)
    return value


def parse_value(param, labels=None):
    """ Parse a string ID, label, or integer value. """
    param_split = param.lower().split(":")
    base = 0
    if param_split[0] == "string":
        # String ID
        raw_value = parse_number(param_split[1])
        base = 0x80000000
    elif param_split[0] in labels:
        # Label
        raw_value = labels[param_split[0]] - 1
        base = 0xCC000000
    else:
        # Integer
        raw_value = parse_number(param)
    return base + raw_value


def parse_and_assemble(input_file, opcode_list, verbose=False):
    """ Parse a script """

    # TODO: rewrite this using a real parser!

    # Generate reverse lookup for opcodes
    string_to_opcode = {opcode.mnemonic.lower(): opcode_id for opcode_id, opcode in opcode_list.items()}

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

        split_line = line.split(" ")
        command = split_line[0].lower()
        if command == "":
            continue
        elif command == "stringtable":
            # Create a new stringtable

            if len(split_line) < 2:
                raise AssembleScriptException("syntax: stringtable <string-table-chunk-no>")
            string_table_chunk_number = parse_number(split_line[1])

            if string_table is not None:
                raise AssembleScriptException("String table already defined")

            logger.debug("Creating string table: GSTX 0x%x", string_table_chunk_number)
            string_table = stringtable.StringTable()

        elif command == "string":
            if len(split_line) < 3:
                raise AssembleScriptException("syntax: string <id> <quoted-string>")

            string_id = parse_number(split_line[1])
            string_value = " ".join(split_line[2:]).strip("\"")

            logger.debug("Adding to string table: 0x%x -> %s", string_id, string_value)
            string_table[string_id] = string_value
        elif command == "script":
            # New script directive
            if len(split_line) < 3:
                raise AssembleScriptException("syntax: script chunk-tag chunk-number")

            script_chunk_tag = split_line[1].upper()
            if script_chunk_tag != "GLSC" and script_chunk_tag != "GLOP":
                raise AssembleScriptException("invalid script chunk tag type")

            script_chunk_number = parse_number(split_line[2])

            if script is not None:
                raise AssembleScriptException("Script already defined")

            # Use same version as in 3DMM
            compiler_version = chunkyfilemodel.Version(29, 16)
            script = scriptmodel.Script(endianness=chunkyfilemodel.Endianness.LittleEndian,
                                        characterset=chunkyfilemodel.CharacterSet.ANSI,
                                        compilerversion=compiler_version)

        elif command.endswith(":"):
            # Labels
            label_name = command[:-1]
            if label_name in labels:
                raise AssembleScriptException("Label %s already defined" % label_name)
            labels[label_name] = instruction_pointer
        elif command == "push":
            # Special handling for PUSH instructions
            if len(split_line) != 2:
                raise AssembleScriptException("syntax: push <value>")

            value = parse_value(split_line[1], labels)
            stack.append(value)
        elif command in string_to_opcode:
            # It's an opcode
            opcode = opcode_list[string_to_opcode[command]]

            # Check if we have a variable name
            variable_name = None
            if len(split_line) > 1:
                variable_name = split_line[1]

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

    # Log labels
    if len(labels.items()) > 0 and verbose:
        logger.debug("Labels:")
        for label_name, label_instruction_pointer in labels.items():
            logger.debug("%s: %d", label_name, label_instruction_pointer)

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
                                                   data=string_table_data,
                                                   flags=chunkyfilemodel.ChunkFlags.Loner)

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
                                             data=script_data
                                             )
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
