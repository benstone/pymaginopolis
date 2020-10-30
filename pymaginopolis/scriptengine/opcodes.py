import pathlib
import xml.etree.ElementTree

import pymaginopolis.scriptengine.model as model


def load_opcode_list(opcode_xml_path=None):
    if opcode_xml_path is None:
        opcode_xml_path = pathlib.Path(__file__).parent / "data" / "opcodes.xml"
    else:
        opcode_xml_path = pathlib.Path(opcode_xml_path)

    if not opcode_xml_path.is_file():
        raise FileNotFoundError("Cannot find opcode list: %s" % opcode_xml_path.absolute())

    root = xml.etree.ElementTree.parse(opcode_xml_path.absolute())
    opcode_list = dict()

    for opcode_xml in root.findall("Opcode"):
        # Load opcode info
        opcode_number = int(opcode_xml.attrib["Opcode"])
        opcode_stack_params = int(opcode_xml.attrib["StackParams"])
        opcode_varargs = opcode_xml.attrib["Varargs"] == "true"
        opcode_returns = opcode_xml.attrib["Returns"]
        opcode_description = opcode_xml.attrib["Description"]
        this_opcode = model.Opcode(opcode_number, opcode_xml.attrib["Mnemonic"],
                                   opcode_stack_params,
                                   opcode_varargs,
                                   opcode_returns,
                                   opcode_description)

        # Load parameter info if available
        for parameter in opcode_xml.findall("Parameter"):
            param_index = int(parameter.attrib["Id"])
            param_name = parameter.attrib["Name"]
            param_type = parameter.attrib["Type"]
            param_description = parameter.attrib["Description"]

            this_param = model.Parameter(param_name, param_type, param_description)
            this_opcode.parameters[param_index] = this_param

        opcode_list[opcode_number] = this_opcode

    return opcode_list
