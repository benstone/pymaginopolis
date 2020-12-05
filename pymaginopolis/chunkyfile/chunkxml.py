import base64
import logging
import pathlib
from xml.etree import ElementTree

from xml.dom import minidom

from pymaginopolis.chunkyfile import model as model, codecs as codecs

EMPTY_FILE = "EmpT"


def chunky_file_to_xml(this_file, chunk_data_dir=None):
    """
    Generate an XML representation of a chunky file
    :param this_file: chunky file object
    :param chunk_data_dir: optional, directory to write chunk data files to
    :return: string containing XML representation of a chunky file
    """
    if chunk_data_dir:
        chunk_data_dir = pathlib.Path(chunk_data_dir)
        if not chunk_data_dir.is_dir():
            chunk_data_dir.mkdir()

    # Generate XML document
    chunky_root = ElementTree.Element("ChunkyFile")
    chunky_root.set("type", this_file.file_type)
    chunky_root.set("endianness", this_file.endianness.name)
    chunky_root.set("charset", this_file.characterset.name)

    for chunk in this_file.chunks:
        chunk_element = ElementTree.SubElement(chunky_root, "Chunk")
        chunk_element.set("tag", chunk.chunk_id.tag)
        chunk_element.set("number", str(chunk.chunk_id.number))
        if chunk.name:
            chunk_element.set("name", chunk.name)
        if chunk.flags & model.ChunkFlags.Loner:
            chunk_element.set("loner", "true")

        # Add children
        for chunk_child in chunk.children:
            child_element = ElementTree.SubElement(chunk_element, "Child")
            child_element.set("chid", str(chunk_child.chid))
            child_element.set("tag", chunk_child.ref.tag)
            child_element.set("number", str(chunk_child.ref.number))

        # Add data
        if chunk.flags & model.ChunkFlags.Compressed:
            is_compressed = True
            this_chunk_data = chunk.encoded_data
            chunk_element.set("compressed", "true")
        else:
            is_compressed = False
            this_chunk_data = chunk.raw_data

        if chunk_data_dir:
            file_extension = chunk.chunk_id.tag.lower().rstrip(" ")

            # HACK
            if file_extension == "wave":
                file_extension = "wav"
            chunk_data_file_name = "%d.%s" % (chunk.chunk_id.number, file_extension)

            if is_compressed:
                compression_type = codecs.identify_compression(this_chunk_data).name
                chunk_data_file_name += ".%s" % (compression_type.lower())

            chunk_data_file_path = chunk_data_dir / chunk_data_file_name
            with open(chunk_data_file_path, "wb") as chunk_data_file:
                chunk_data_file.write(this_chunk_data)

            # Create element for data
            data_element = ElementTree.SubElement(chunk_element, "File")
            data_element.text = str(chunk_data_file_path)
            if is_compressed:
                data_element.set("compressed", "true")
        else:
            data_element = ElementTree.SubElement(chunk_element, "Data")
            data_element.text = base64.b64encode(this_chunk_data).decode("utf-8")

    this_file_xml = ElementTree.tostring(chunky_root)
    # Pretty-print the XML
    dom = minidom.parseString(this_file_xml)
    this_file_pretty_xml = dom.toprettyxml()

    return this_file_pretty_xml


def xml_to_chunky_file(chunky_file, xml_path, change_file_type=False):
    """
    Load chunks from an XML file and add them to a chunky file
    :param chunky_file: Existing chunky file instance that new chunks will be added to
    :param xml_path: XML filename
    :param change_file_type: change the file type tag in the header
    """
    logger = logging.getLogger(__name__)

    # Load XML file
    tree = ElementTree.parse(xml_path)
    chunky_file_xml = tree.getroot()

    # TODO: validate with an XSD?
    if chunky_file_xml.tag != "ChunkyFile":
        raise Exception("Not the right kind of XML file")

    # Set chunky file options if not already set
    file_type = chunky_file_xml.attrib.get("type")
    endianness = model.Endianness[chunky_file_xml.attrib.get("endianness", "LittleEndian")]
    charset = model.CharacterSet[chunky_file_xml.attrib.get("charset", "ANSI")]
    if chunky_file.file_type == EMPTY_FILE:
        chunky_file.file_type = file_type
        chunky_file.endianness = endianness
        chunky_file.characterset = charset
    else:
        if file_type is not None and chunky_file.file_type != file_type and change_file_type:
            logger.warning("Changing file type from %s to %s", chunky_file.file_type, file_type)
            chunky_file.file_type = file_type
        if chunky_file.endianness != endianness:
            logger.warning("Changing file endianness from %s to %s", chunky_file.endianness, endianness)
            chunky_file.endianness = endianness
        if chunky_file.characterset != charset:
            logger.warning("Changing file character set from %s to %s", chunky_file.characterset, charset)
            chunky_file.characterset = charset

    for chunk_xml in chunky_file_xml.findall("Chunk"):
        # Get chunk metadata
        chunk_tag = chunk_xml.attrib["tag"]
        chunk_number = int(chunk_xml.attrib["number"])
        chunk_id = model.ChunkId(chunk_tag, chunk_number)
        chunk_name = chunk_xml.attrib.get("name", None)
        logger.debug("Processing chunk: %s - %s", chunk_id, chunk_name if chunk_name else "n/a")
        chunk_flags = model.ChunkFlags.Default
        if chunk_xml.attrib.get("loner", "false").lower() == "true":
            chunk_flags |= model.ChunkFlags.Loner
        if chunk_xml.attrib.get("compressed", "false").lower() == "true":
            chunk_flags |= model.ChunkFlags.Compressed

        # Get chunk children and data
        chunk_data = None
        chunk_children = list()
        for child_xml in chunk_xml:
            if child_xml.tag == "Child":
                chid = int(child_xml.attrib["chid"])
                tag = child_xml.attrib["tag"]
                number = int(child_xml.attrib["number"])

                chunk_child = model.ChunkChild(chid=chid, ref=model.ChunkId(tag, number))
                chunk_children.append(chunk_child)

            elif child_xml.tag == "Data":
                chunk_data = base64.b64decode(child_xml.text)
            elif child_xml.tag == "File":
                with open(child_xml.text, "rb") as data_file:
                    chunk_data = data_file.read()
            else:
                raise Exception("unhandled child tag type: %s" % child_xml.tag)

        # Check if there is an existing chunk
        if chunk_id in chunky_file:
            existing_chunk = chunky_file[chunk_id]
            logger.info("%s: Modifying existing chunk", chunk_id)

            # Update chunk metadata
            if chunk_name:
                existing_chunk.name = chunk_name
            if chunk_flags != existing_chunk.flags:
                logger.warning("%s: Changing flags to: %s", chunk_id, chunk_flags)
                existing_chunk.flags = chunk_flags

            # TODO: update existing children instead of just adding
            for new_child in chunk_children:
                existing_child = [c for c in existing_chunk.children if c.chid == new_child.chid]
                if len(existing_child) > 0:
                    logger.warning("child %s: %s already exists" % (existing_chunk, existing_child))
                else:
                    existing_chunk.children.append(new_child)

            # Set chunk data
            # TODO: handle compression
            if chunk_data:
                existing_chunk.raw_data = chunk_data
        else:
            logger.info("%s: Creating new chunk", chunk_id)
            # Create a new chunk
            this_chunk = model.Chunk(chunk_tag, chunk_number, chunk_name, chunk_flags, data=chunk_data)
            this_chunk.children = chunk_children
            chunky_file.chunks.append(this_chunk)
