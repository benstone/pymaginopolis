import argparse
import logging
import pathlib

import pkg_resources


def get_version(tool_name):
    version_number = pkg_resources.get_distribution("pymaginopolis").version
    return f"Pymaginopolis {tool_name} version {version_number}"


def file_path(value):
    path = pathlib.Path(value)
    if not path.is_file():
        raise argparse.ArgumentTypeError("invalid file path: %s" % value)
    return path


def directory_path(value):
    path = pathlib.Path(value)
    if not path.is_dir():
        raise argparse.ArgumentTypeError("invalid directory: %s" % value)
    return path


def add_default_args(parser, tool_name):
    parser.add_argument("--loglevel", choices=["debug", "info", "warning", "error", "critical"], default="info")
    parser.add_argument("-v", action="version", version=get_version(tool_name))


def configure_logging(args=None):
    # Set up logging
    log_level = "DEBUG"
    if args:
        log_level = args.loglevel.upper()
    logging.basicConfig(level=getattr(logging, log_level))
