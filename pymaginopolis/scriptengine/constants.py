import pathlib
import xml.etree.ElementTree


def load_constants(constants_xml_path=None):
    """
    Load known constants from an XML file. Returns a dict() mapping constant values to strings.
    """

    if constants_xml_path is None:
        constants_xml_path = pathlib.Path(__file__).parent / "data" / "constants.xml"
    else:
        constants_xml_path = pathlib.Path(constants_xml_path)

    if not constants_xml_path.is_file():
        raise FileNotFoundError("Cannot find constants list: %s" % constants_xml_path.absolute())

    root = xml.etree.ElementTree.parse(constants_xml_path)
    constants = dict()

    for constant_xml in root.findall("Constant"):
        constant_name = constant_xml.attrib["name"]

        value_str = constant_xml.attrib["value"]
        if value_str.startswith("0x"):
            constant_value = int(value_str[2:], 16)
        else:
            constant_value = int(value_str)

        if constant_value in constants:
            raise Exception("duplicate constant: %d already %s" % (constant_value, constants[constant_value]))
        constants[constant_value] = constant_name

    return constants
