import ctypes
import enum
import string
import time

USER32 = ctypes.windll.user32

# GOB ID of the root GOB
ROOT_GOB_GID = 2

DEFAULT_TIME_SCALE = 0x10000


class IpcMessages(enum.IntEnum):
    """ WM_USER messages for 3DMM """
    WM_USER_SET_TIME_SCALE = 0x4005
    WM_USER_GET_GOB_FROM_POINT = 0x4006
    WM_USER_GET_GOB_CHILD = 0x4007
    WM_USER_GET_GOB_SIBLING = 0x4008
    WM_USER_GET_GOB_PARENT = 0x4009
    WM_USER_GET_OBJECT_TYPE_TAG = 0x400a
    WM_USER_CHECK_OBJECT_TYPE_TAG = 0x400b


class WindowNotFoundException(Exception):
    """ Raised if 3DMM/CW2 is not running """
    pass


def find_window(window_class=None, window_title=None):
    """ Get the hWnd of the 3DMM/CW2 main window """
    window_class = window_class or "3DMOVIE"
    hwnd = USER32.FindWindowW(window_class, window_title)
    if hwnd == 0:
        raise WindowNotFoundException
    return hwnd


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


def walk_gob_tree(hwnd, visitor, gid=ROOT_GOB_GID, level=0):
    # Get the GOB's parent
    parent_gid = USER32.SendMessageW(hwnd, IpcMessages.WM_USER_GET_GOB_PARENT, 0, gid) & 0xFFFFFFFF

    # Get the GOB's type
    type_tag = USER32.SendMessageW(hwnd, IpcMessages.WM_USER_GET_OBJECT_TYPE_TAG, 0, gid)
    type_tag = u32le_to_type_tag(type_tag)

    visitor(level, parent_gid, gid, type_tag)

    # Get this GOB's child
    child_gid = USER32.SendMessageW(hwnd, IpcMessages.WM_USER_GET_GOB_CHILD, 0, gid) & 0xFFFFFFFF
    if child_gid != 0:
        walk_gob_tree(hwnd, visitor, child_gid, level=level + 1)

    # Get this GOB's next sibling
    next_sibling_gid = USER32.SendMessageW(hwnd, IpcMessages.WM_USER_GET_GOB_SIBLING, 0, gid) & 0xFFFFFFFF
    if next_sibling_gid != 0:
        walk_gob_tree(hwnd, visitor, next_sibling_gid, level=level)


def set_time_scale(hwnd, multiplier=1.0):
    # Bring window to the foreground - otherwise the message is ignored
    USER32.SwitchToThisWindow(hwnd, 0)
    time.sleep(1)

    scale_factor = int(multiplier * DEFAULT_TIME_SCALE)
    return USER32.SendMessageW(hwnd, IpcMessages.WM_USER_SET_TIME_SCALE, 0, scale_factor)
