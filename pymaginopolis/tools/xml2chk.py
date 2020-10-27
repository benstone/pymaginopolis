import argparse
import logging

import pymaginopolis.chunkyfile.loader as loader
import pymaginopolis.chunkyfile.model as model
import pymaginopolis.chunkyfile.writer as writer
from pymaginopolis.chunkyfile.chunkxml import xml_to_chunky_file
from pymaginopolis.tools.util import file_path, add_default_args, configure_logging

logger = logging.getLogger("xml2chk")

# sentinel value used to indicate empty file
EMPTY_FILE = "EmpT"


def parse_args():
    parser = argparse.ArgumentParser(description="Generate/update CHK files from XML")
    add_default_args(parser, "xml2chk")
    parser.add_argument("output", type=str, help="Chunky file to create")
    parser.add_argument("input", type=file_path, help="XML files containing chunk definitions", nargs="+")
    parser.add_argument("--template", type=file_path, help="Modify chunks in an existing chunky file")

    args = parser.parse_args()
    return args


def main():
    args = parse_args()
    configure_logging(args)

    if args.template:
        logger.info("Loading template file: %s" % args.template.absolute())
        # Load existing chunky file as a template
        with open(args.template, "rb") as template_file:
            chunky_file = loader.load_from_file(template_file)
    else:
        # Create an empty chunky file
        chunky_file = model.ChunkyFile(model.Endianness.LittleEndian, model.CharacterSet.ANSI, file_type=EMPTY_FILE)

    for input_file in args.input:
        logger.info("Processing: %s" % input_file)
        xml_to_chunky_file(chunky_file, input_file)

    logger.info("Generating: %s" % args.output)
    with open(args.output, "wb") as output_file:
        writer.write_to_file(chunky_file, output_file)

    logger.info("Complete")


if __name__ == "__main__":
    main()
