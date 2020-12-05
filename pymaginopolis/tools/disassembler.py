import argparse
import io
import logging

import pymaginopolis.chunkyfile.loader as loader
import pymaginopolis.chunkyfile.stringtable as stringtable
import pymaginopolis.scriptengine.disassembler as disassembler
import pymaginopolis.scriptengine.formatter as formatter
import pymaginopolis.tools.util as scriptutils

SCRIPT_CHUNK_TAGS = {"GLOP", "GLSC"}
STRING_TABLE_TAGS = {"GST ", "GSTX"}


def parse_args():
    parser = argparse.ArgumentParser(description="Disassemble scripts in a Chunky file")
    scriptutils.add_default_args(parser, "disassembler")
    parser.add_argument("file", type=scriptutils.file_path, help="Chunky file")
    args = parser.parse_args()
    return args


def main():
    args = parse_args()
    scriptutils.configure_logging(args)

    logger = logging.getLogger(__name__)

    filename = args.file
    logger.info(f"Loading file: {filename}")
    with open(filename, "rb") as chunky_file_handle:
        this_chunky_file = loader.load_from_file(chunky_file_handle)
        logger.info(f"Loaded: {this_chunky_file}")
        script_chunks = [c for c in this_chunky_file.chunks if c.chunk_id.tag in SCRIPT_CHUNK_TAGS]
        string_table_chunks = [c for c in this_chunky_file.chunks if c.chunk_id.tag in STRING_TABLE_TAGS]

        if len(script_chunks) > 0:
            logger.info(f"Found {len(script_chunks)} script chunks")
            fmt = formatter.TextScriptFormatter()

            for c in script_chunks:
                script = disassembler.disassemble_script(io.BytesIO(c.decoded_data))
                print(fmt.format_script(script, chunk_id=c.chunk_id, chunk_name=c.name, file_name=filename))

        if len(string_table_chunks) > 0:
            for c in string_table_chunks:
                logger.info(f"Dumping string table: {c.chunk_id} {c.name}")

                try:
                    strings = stringtable.StringTable.from_buffer(c.decoded_data)

                    for k, v in strings.items():
                        logger.info(f"    0x{k:x} - {v}")
                except:
                    logger.exception("failed to load string table")


if __name__ == "__main__":
    main()
