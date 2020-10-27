import enum


class CompressionType(enum.IntEnum):
    """ Type of compression for chunk data """
    Uncompressed = 0
    KCDC = 1
    KCD2 = 2


def identify_compression(data):
    if data[0:4] == b'KCDC':
        return CompressionType.KCDC
    elif data[0:4] == b'KCD2':
        return CompressionType.KCD2
    else:
        return CompressionType.Uncompressed
