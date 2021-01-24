import argparse
import logging

import pymaginopolis.ipc.messages as msg
from pymaginopolis.tools.util import add_default_args, configure_logging

logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Set the clock speed of 3DMM/CW2")
    add_default_args(parser, "setclock")
    parser.add_argument("--window-class", type=str, help="Window class. Defaults to 3DMOVIE.")
    parser.add_argument("--multiplier", type=float, help="Scale factor for clock speed. Default is 1.0.", required=True)

    args = parser.parse_args()
    return args


def main():
    args = parse_args()
    configure_logging(args)

    minimum_multiplier = 0.0001

    if args.multiplier < minimum_multiplier:
        logger.error(f"Invalid multiplier: must be >= {minimum_multiplier}")
    else:
        try:
            hwnd = msg.find_window(args.window_class)
            logger.info(f"hWnd: 0x{hwnd:x}")

            if msg.set_time_scale(hwnd, args.multiplier) != 0:
                logger.info(f"Clock set to {args.multiplier}x")
            else:
                logger.error("Failed to set clock")
                
        except msg.WindowNotFoundException:
            logger.error("Could not find 3DMM/CW2 window")


if __name__ == "__main__":
    main()
