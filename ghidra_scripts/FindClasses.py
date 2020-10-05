# Recover the class hierarchy from Microsoft 3D Movie Maker or Creative Writer 2
# @author Ben Stone
# @category 3DMM
# @keybinding
# @menupath Tools.Pymaginopolis.Find Classes
# @toolbar

VTABLE_SYMBOL_NAME = "vtable"
PRINT_CLASS_HIERARCHY = True

# https://github.com/VDOO-Connected-Trust/ghidra-pyi-generator
try:
    from ghidra_builtins import *
except:
    pass

from ghidra.program.model.listing import VariableUtilities
from ghidra.program.model.symbol import SourceType
from ghidra.util.exception import DuplicateNameException
from ghidra.program.model.data import StructureDataType, DataTypeConflictHandler, PointerDataType
import string
from java.lang import NullPointerException


def read_u8(memory_block, address):
    """ Read a signed byte and convert it to an unsigned byte """
    v = memory_block.getByte(address)
    if v >= 0:
        return v
    else:
        return 256 + v


def u32le_to_type_tag(v):
    type_tag = ""
    for offset in range(4):
        char = chr((v >> (24 - (offset * 8))) & 0xFF)
        if char == "\x00":
            char += " "
        elif char in string.ascii_letters:
            type_tag += char
        else:
            break

    type_tag = type_tag.strip(" ")
    if len(type_tag) >= 2:
        return type_tag


def deref_vtable(current_program, vtable_address, index):
    ptr_to_function = get_vtable_entry_address(current_program, vtable_address, index)
    function_addr = vtable_address.getNewAddress(current_program.getMemory().getInt(ptr_to_function, False))
    return function_addr


def get_vtable_entry_address(current_program, vtable_address, index):
    ptr_to_function = vtable_address.add(index * current_program.getDefaultPointerSize())
    return ptr_to_function


def fixup_class_method(class_namespace, this_function, return_type):
    # Add this function to the class's namespace
    if class_namespace:
        try:
            this_function.setParentNamespace(class_namespace)
        except DuplicateNameException:
            pass
    # Fix calling convention
    this_function.setCallingConvention("__thiscall")
    # Fix return type
    this_function.setReturnType(return_type, SourceType.ANALYSIS)


def get_or_create_function(function_address, function_name):
    this_function = getFunctionAt(function_address)
    if this_function:
        if function_name is not None:
            this_function.setName(function_name, SourceType.ANALYSIS)
    else:
        # If there is data at this function address, get rid of it
        if getDataAt(function_address):
            removeDataAt(function_address)

        this_function = createFunction(function_address, function_name)
        if not this_function:
            raise Exception("Couldn't create function at %s" % function_address)

    return this_function


def find_return_constant_function_addresses(memory_block, limit=0, alignment=4):
    """
    Find addresses of possible functions that return a constant value.
    """
    block_start = memory_block.getStart()
    block_end = memory_block.getEnd()

    # These functions will look like:
    # mov eax, <constant>
    # ret
    # and will have 0xCC bytes padding them on either side
    for address in findBytes(block_start, "\\xB8....\\xC3\\xCC", limit, alignment):
        if address > block_end:
            continue

        # Check that the byte before this address is padding
        previous_byte = read_u8(memory_block, address.subtract(1))
        if previous_byte != 0xCC:
            continue

        # Get the constant return value
        return_value = currentProgram.getMemory().getInt(address.add(1))
        yield address, return_value


class FoundClass:
    name = None
    vtable = 0
    vtable_size = 0
    parent = None
    functions = None

    def __init__(self, name, vtable_address):
        self.name = name
        self.vtable_address = vtable_address
        self.parent = None
        self.functions = dict()

    def __str__(self):
        return "%s - vtable %s" % (self.name, self.vtable_address)

    @property
    def vtable_struct_name(self):
        return "%s_vtable" % (self.name)


def main():
    uint_type = getDataTypes("UINT")[0]
    bool_type = getDataTypes("BOOL")[0]
    void_type = getDataTypes("void")[0]
    pointer_type = getDataTypes("pointer")[0]

    symbol_table = currentProgram.getSymbolTable()

    found_classes = {}
    text_section = getMemoryBlock(".text")

    print("Finding classes")
    # Find classes by searching for the GetType functions
    # These may not have been identified as functions, so we search using a byte pattern
    for addr, return_value in find_return_constant_function_addresses(text_section):

        # Check if this function returns a value that looks like a type tag
        type_tag = u32le_to_type_tag(return_value)
        if not type_tag:
            continue

        # Find the vtable address by xrefs to the GetType function
        refs = getReferencesTo(addr)
        if len(refs) == 0:
            print("-> No references to %s %s" % (type_tag, addr))
        else:
            # There should only be one reference, but the BASE class has three
            for ref in refs:
                # GetType is the second entry in the vtable
                vtable_address = ref.getFromAddress().subtract(4)

                # If there are no references to this address, this isn't a vtable
                if len(getReferencesTo(vtable_address)) == 0:
                    print("Class %s rejected: no xrefs to vtable" % type_tag)
                    continue

                class_name = type_tag
                if class_name == "BASE":
                    class_name = class_name + "_%s" % (vtable_address)

                this_class = FoundClass(class_name, vtable_address)
                found_classes[class_name] = this_class

    for class_name, cls in found_classes.items():
        print("Class: %s  - vtable: %s" % (class_name, cls.vtable_address))

        # Create the class namespace
        try:
            symbol_table.createClass(None, class_name, SourceType.ANALYSIS)
        except DuplicateNameException:
            pass
        class_namespace = symbol_table.getNamespace(class_name, None)

        # Create the class struct
        class_struct = VariableUtilities.findOrCreateClassStruct(class_namespace, currentProgram.getDataTypeManager())

        # Set up default fields
        if class_struct.getComponentAt(0) is None:
            class_struct.insertAtOffset(0, pointer_type, 4, "vtable", "Pointer to virtual function table")
        else:
            class_struct.replaceAtOffset(0, pointer_type, 4, "vtable", "Pointer to virtual function table")

        if class_struct.getComponentAt(4) is None:
            class_struct.insertAtOffset(4, uint_type, 4, "RefCnt", "Reference count")
        else:
            class_struct.replaceAtOffset(4, uint_type, 4, "RefCnt", "Reference count")

        # Save the changes
        currentProgram.getDataTypeManager().addDataType(class_struct, DataTypeConflictHandler.DEFAULT_HANDLER)

        # Delete existing symbol if it exists
        existing_symbols = symbol_table.getSymbols(cls.vtable_address)
        for symbol in existing_symbols:
            if symbol.getName() != VTABLE_SYMBOL_NAME:
                symbol.delete()

        # Create a label for the vtable
        symbol_table.createLabel(cls.vtable_address, VTABLE_SYMBOL_NAME, class_namespace, SourceType.ANALYSIS)

        # Create base functions
        base_vtable_functions = [
            ("CheckType", bool_type, (("TypeTag", uint_type),)),
            ("GetType", uint_type, ()),
            ("Destructor", void_type, (("Free", bool_type),)),
        ]
        for vtable_index, (function_name, return_type, params) in enumerate(base_vtable_functions):
            function_address = deref_vtable(currentProgram, cls.vtable_address, vtable_index)

            # Create a function if it doesn't exist, and set its name
            this_function = get_or_create_function(function_address, function_name)
            fixup_class_method(class_namespace, this_function, return_type)

            # Fix parameters
            function_param_count = this_function.getParameterCount()
            for param_index, (param_name, param_type) in enumerate(params):
                if param_index + 1 < function_param_count:
                    this_function.getParameter(param_index + 1).setName(param_name, SourceType.ANALYSIS)
                    this_function.getParameter(param_index + 1).setDataType(param_type, SourceType.ANALYSIS)
                else:
                    # FUTURE: handle this?
                    pass

            # Add to the list
            cls.functions[function_name] = this_function

        # Use the CheckType function to find the CheckTypeImpl function
        check_type_function = cls.functions["CheckType"]
        called_functions = check_type_function.getCalledFunctions(getMonitor())
        if len(called_functions) == 0:
            # This is the BASE class
            pass
        elif len(called_functions) == 1:
            # Create the CheckTypeImpl function
            check_type_impl_function = called_functions.pop()
            check_type_impl_function.setName("CheckTypeImpl", SourceType.ANALYSIS)
            fixup_class_method(class_namespace, check_type_impl_function, bool_type)
            cls.functions["CheckTypeImpl"] = check_type_impl_function
        else:
            raise Exception(
                "didn't expect the CheckType function to call more than one function: %s" % check_type_function)

    # Find parent classes using xrefs to CheckTypeImpl classes
    print("Finding class hierarchy")

    multiple_refs = list()
    for name, cls in found_classes.items():
        if "CheckTypeImpl" not in cls.functions:
            assert name.startswith("BASE"), name
            cls.parent = None
            continue

        # The CheckTypeImpl function will call the parent's CheckTypeImpl function
        check_type_impl_function = cls.functions["CheckTypeImpl"]
        called_functions = check_type_impl_function.getCalledFunctions(getMonitor())
        if len(called_functions) == 0:
            # This is a BASE class
            print("%s is a base class" % name)

            if not name.startswith("BASE"):
                raise Exception(
                    "Function %s doesn't have any references, but also isn't a base class?" % check_type_impl_function)

            cls.parent = None
            pass
        elif len(called_functions) == 1:
            # Get the parent class name from the called function's namespace
            parent_check_type_impl = called_functions.pop()
            parent_namespace = parent_check_type_impl.getParentNamespace().getName()
            if parent_namespace in found_classes:
                cls.parent = parent_namespace
            else:
                # We don't know which base class is this class's parent. We'll fix this later.
                cls.parent = "BASE"
        else:
            # This handles a weird edge case in 3DMM UK where some type tags also happen to be the address of a function
            # Ghidra thinks there are two xrefs from this function.
            # We'll use the destructor to find the base class.
            cls.parent = "BASE"
            print("warning: type %s has more than one xref from the CheckTypeImpl function" % name)

    # Analyze destructors to get the rest of the class hierarchy

    # The destructor function can have:
    # - only one reference: this is the delete() function
    # - two references: the delete() function plus the destructor impl for either this class or a parent class
    # - more than two references: some inlined destructor

    # To make this easier we'll find the delete() function first
    # Find the delete() function by looking for any destructor with only one reference

    # FUTURE: could do this another way, like looking for all xrefs to GlobalFree()
    # But, there are a lot of xrefs to GlobalFree()
    print("Finding delete function")
    delete_function = None
    for name, cls in found_classes.items():
        destructor = cls.functions["Destructor"]
        called_functions = destructor.getCalledFunctions(getMonitor())
        if len(called_functions) == 1:
            delete_function = called_functions.pop()
            break

    if not delete_function:
        raise Exception("Couldn't find delete function")
    print("Delete function: %s" % delete_function.getEntryPoint())

    # Fix up delete function
    if delete_function.getName() != "delete":
        delete_function.setName("delete", SourceType.ANALYSIS)

    # Now find the destructor impl functions
    destructor_impl_functions = set()
    print("Finding destructor functions")
    for name, cls in found_classes.items():
        destructor = cls.functions["Destructor"]
        print("Finding destructor functions: %s - %s" % (name, destructor))
        called_functions = destructor.getCalledFunctions(getMonitor())
        for called_function in called_functions:
            if called_function == delete_function:
                continue
            if called_function.getExternalLocation() is not None:
                continue
            # FUTURE: Currently broken for Creative Writer 2
            if called_function.getName().startswith("Unwind"):
                print("warning: found unwind")
                continue
            destructor_impl_functions.add(called_function)

    # Disassemble the start of each DestructorImpl function to find the first vtable it references
    print("Finding vtable references from destructor functions")
    for destructor_impl_function in destructor_impl_functions:
        entry_point = destructor_impl_function.getEntryPoint()

        current_instruction = getInstructionAt(entry_point)
        class_reference = None
        limit = 10
        while class_reference is None and limit > 0:
            if current_instruction.getMnemonicString() == "MOV":
                if len(current_instruction.getOperandReferences(1)) == 1:
                    ref_address = current_instruction.getOperandReferences(1)[0].getToAddress()
                    class_reference = get_class_by_vtable_address(found_classes, ref_address)
            # Move to the next instruction
            current_instruction = getInstructionAfter(current_instruction)
            limit -= 1

        if class_reference is None:
            # This can happen in Creative Writer 2 if the vtable assignment is in a __finally() block
            printerr("could not find vtable reference in DestructorImpl function: %s" % entry_point)
            continue

        # Add this function to the class
        class_reference.functions["DestructorImpl"] = destructor_impl_function
        class_namespace = symbol_table.getNamespace(class_reference.name, None)
        destructor_impl_function.setName("DestructorImpl", SourceType.ANALYSIS)
        fixup_class_method(class_namespace, destructor_impl_function, void_type)

    # Find destructors that reference the base class vtables
    for cls in get_base_classes(found_classes):
        print("Finding references to base class vtables: %s: %s" % (cls.name, cls.vtable_address))
        vtable_refs = getReferencesTo(cls.vtable_address)
        for ref in vtable_refs:
            from_function = getFunctionContaining(ref.getFromAddress())
            if from_function is not None:
                function_name = from_function.getName()
                if function_name == "Destructor" or function_name == "DestructorImpl":
                    # Found a reference to a base vtable from a destructor
                    reference_from_class_name = from_function.getParentNamespace().getName()
                    if found_classes[reference_from_class_name].parent == "BASE":
                        found_classes[reference_from_class_name].parent = cls.name

    # HACK: for 3D Movie Maker
    # GKDS::CheckType() calls GOKD::CheckType() but there's no GOKD class
    # GOKD::CheckType() calls BACO::CheckType(), so we'll set the type to BACO
    if "GKDS" in found_classes and "BACO" in found_classes and found_classes["GKDS"].parent == "BASE":
        found_classes["GKDS"].parent = "BACO"

    # Dump the list of classes that don't have parents
    for name, cls in found_classes.items():
        if cls.parent == "BASE":
            printerr("Class %s isn't associated with a BASE class" % cls)

    # Now that we have our class hierarchy we can start fixing up those virtual functions

    # Add names to the AddRef and Release vtable functions
    def name_ref_count_functions(class_name):
        # Name the AddRef and Release functions in this class
        this_class = found_classes[class_name]

        for index, function_name in ((3, "AddRef"), (4, "Release")):
            class_namespace = symbol_table.getNamespace(class_name, None)

            function_address = deref_vtable(currentProgram, this_class.vtable_address, index)
            this_function = get_or_create_function(function_address, function_name)

            # Only set the class namespace if it doesn't have one
            # If the function already has a class namespace, it belongs to a parent class
            function_namespace = this_function.getParentNamespace().getName()
            if function_namespace in found_classes:
                class_namespace = None

            fixup_class_method(class_namespace, this_function, void_type)

    print("Naming AddRef/Release functions")
    for cls in get_base_classes(found_classes):
        walk_class_tree(found_classes, cls.name, name_ref_count_functions)

    # Find the size of all of the vtables
    print("Finding vtable sizes")

    def find_vtable_size(class_name):
        # Default BASE vtable size
        this_class = found_classes[class_name]
        min_vtable_size = 5
        parent_class = found_classes.get(this_class.parent)
        if parent_class:
            min_vtable_size = parent_class.vtable_size
        vtable_size = guess_vtable_size(this_class.vtable_address, min_size=min_vtable_size)
        this_class.vtable_size = vtable_size

    for cls in get_base_classes(found_classes):
        walk_class_tree(found_classes, cls.name, find_vtable_size)

    # Make sure the vtable sizes make sense
    print("Validating vtable sizes")
    for this_class in found_classes.values():
        if this_class.parent is None:
            continue
        parent_class = found_classes[this_class.parent]
        if this_class.vtable_size < parent_class.vtable_size:
            printerr("Detecting vtable size failed:")
            printerr("This: %s %s - %d" % (this_class.name, this_class.vtable_address, this_class.vtable_size))
            printerr("Parent: %s %s - %d" % (parent_class.name, parent_class.vtable_address, parent_class.vtable_size))
            raise Exception("%s - %s" % (this_class.name, parent_class.name))

    # Create structures for vtables
    def create_vtable_structures(class_name):
        this_class = found_classes[class_name]

        # Create a new struct
        vtable_structure_size = this_class.vtable_size * 4
        vtable_struct = StructureDataType(this_class.vtable_struct_name, vtable_structure_size)

        # Add the base functions if this is a BASE vtable
        if this_class.name.startswith("BASE"):
            for index, base_function_name in enumerate(("CheckType", "GetType", "Destructor", "AddRef", "Release")):
                vtable_struct.replaceAtOffset(index * 4, pointer_type, 4, base_function_name, "Base class function")
        else:
            # Add the parent class's vtable structure
            parent_class = found_classes[this_class.parent]
            parent_vtable_struct_path = "/" + parent_class.vtable_struct_name
            parent_vtable_struct = currentProgram.getDataTypeManager().getDataType(parent_vtable_struct_path)
            assert parent_vtable_struct is not None
            vtable_struct.replaceAtOffset(0, parent_vtable_struct, parent_class.vtable_size * 4, parent_class.name,
                                          "Base class")

            # Add pointer-sized values for any remaining values
            for index in range(parent_class.vtable_size, this_class.vtable_size):
                vtable_struct.replaceAtOffset(index * 4, pointer_type, 4, None, None)

        # If the struct already exists, a new struct will be created with ".conflict" in the name
        vtable_struct = currentProgram.getDataTypeManager().addDataType(vtable_struct,
                                                                        DataTypeConflictHandler.KEEP_HANDLER)

        # Set the class struct's vtable pointer to point to the new vtable structure
        class_namespace = symbol_table.getNamespace(this_class.name, None)
        class_struct = VariableUtilities.findOrCreateClassStruct(class_namespace, currentProgram.getDataTypeManager())

        ptr_to_vtable_type = PointerDataType(vtable_struct)
        class_struct.replaceAtOffset(0, ptr_to_vtable_type, 4, "vtable", None)

    print("Creating vtable structures")
    for cls in get_base_classes(found_classes):
        walk_class_tree(found_classes, cls.name, create_vtable_structures)

    # Sort virtual functions into class namespaces
    def add_vtable_functions_to_namespaces(class_name):
        this_class = found_classes[class_name]
        for index in range(5, this_class.vtable_size):
            class_namespace = symbol_table.getNamespace(class_name, None)

            function_address = deref_vtable(currentProgram, this_class.vtable_address, index)
            this_function = get_or_create_function(function_address, None)

            # Only set the class namespace if it doesn't have one
            # If the function already has a class namespace, it belongs to a parent class
            function_namespace = this_function.getParentNamespace().getName()
            if function_namespace in found_classes:
                class_namespace = None

            fixup_class_method(class_namespace, this_function, void_type)

    print("Sorting virtual functions into namespaces")
    for cls in get_base_classes(found_classes):
        walk_class_tree(found_classes, cls.name, add_vtable_functions_to_namespaces)

    # Finally: Print out the class hierarchy
    if PRINT_CLASS_HIERARCHY:
        def print_class(class_name):
            cls = found_classes[class_name]
            print("%s -> %s" % (cls.parent, cls.name))

        for cls in get_base_classes(found_classes):
            walk_class_tree(found_classes, cls.name, print_class)


def walk_class_tree(classes, class_name, visit, recurse_limit=10):
    # Visit this class
    visit(class_name)

    if recurse_limit > 0:
        recurse_limit -= 1
        for child_class in get_children(classes, class_name):
            walk_class_tree(classes, child_class.name, visit, recurse_limit)
    else:
        print("Reached recursion limit")


def guess_vtable_size(vtable_address, min_size=1, max_size=100):
    text_section = getMemoryBlock(".text")

    # Assume the first entry exists
    vtable_size = min_size
    for index in range(min_size, max_size):
        this_entry = get_vtable_entry_address(currentProgram, vtable_address, index)
        try:
            this_function = deref_vtable(currentProgram, vtable_address, index)
        except:
            # not a valid address
            break

        # Check that this is a valid pointer
        if not text_section.contains(this_function):
            break

        # Check xrefs to this vtable entry. If we find one, we may have found an adjacent vtable.
        if len(getReferencesTo(this_entry)) > 0:
            break

        vtable_size += 1

    return vtable_size


def get_class_by_vtable_address(classes, vtable_address):
    classes_for_vtable = [c for c in classes.values() if c.vtable_address == vtable_address]
    assert len(classes_for_vtable) < 2
    if len(classes_for_vtable) == 0:
        return None
    else:
        return classes_for_vtable[0]


def get_base_classes(classes):
    return [cls for cls in classes.values() if cls.parent is None]


def get_children(classes, class_name):
    return sorted([cls for cls in classes.values() if cls.parent == class_name], key=lambda x: x.name)


# Call entrypoint
start()
main()
end(True)
