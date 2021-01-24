import argparse
import logging

import pymaginopolis.ipc.messages as msg
from pymaginopolis.tools.util import add_default_args, configure_logging

logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Dump the graphical object tree")
    add_default_args(parser, "dumpgobs")
    parser.add_argument("--window-class", type=str, help="Window class. Defaults to 3DMOVIE.")

    args = parser.parse_args()
    return args


def main():
    args = parse_args()
    configure_logging(args)

    try:
        hwnd = msg.find_window(args.window_class)
        print(f"hWnd: 0x{hwnd:x}")

        def print_visitor(level, parent_gid, gid, type_tag):
            prefix = level * '-' + ' ' if level > 0 else ''
            print(f"{prefix}0x{gid:x}: {type_tag}")

        print("Dumping tree:")
        msg.walk_gob_tree(hwnd, print_visitor)
    except msg.WindowNotFoundException:
        logger.error("Could not find 3DMM/CW2 window")


if __name__ == "__main__":
    main()
