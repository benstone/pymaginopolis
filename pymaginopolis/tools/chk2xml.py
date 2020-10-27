import argparse
import logging
import pathlib

import pymaginopolis.chunkyfile.loader as loader
import pymaginopolis.tools.util as scriptutils
from pymaginopolis.chunkyfile.chunkxml import chunky_file_to_xml


def parse_args():
    parser = argparse.ArgumentParser(description="Convert a CHK file to XML")
    scriptutils.add_default_args(parser, "chk2xml")
    parser.add_argument("input", type=scriptutils.file_path, help="Chunky file")
    parser.add_argument("output", help="XML file")
    parser.add_argument("--stdout", action="store_true", default=False, help="Print XML to stdout")
    parser.add_argument("--chunk-data-dir", type=scriptutils.directory_path, help="Directory to write chunk data to",
                        default=None)
    args = parser.parse_args()
    return args


def main():
    args = parse_args()
    scriptutils.configure_logging(args)

    logger = logging.getLogger(__name__)

    if args.chunk_data_dir:
        chunk_data_dir = args.chunk_data_dir.absolute()
        logger.info("Writing chunk data to: %s", chunk_data_dir)
    else:
        chunk_data_dir = None

    with open(args.input, "rb") as movie_file:
        this_file = loader.load_from_file(movie_file)
        output_file_path = pathlib.Path(args.output).absolute()

        this_file_xml = chunky_file_to_xml(this_file, chunk_data_dir)

        with open(output_file_path, "w") as outfile:
            outfile.write(this_file_xml)

        if args.stdout:
            print(this_file_xml)


if __name__ == "__main__":
    main()
