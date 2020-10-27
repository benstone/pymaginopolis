import base64
import unittest

import pymaginopolis.chunkyfile.stringtable as stringtable

# String tables from 3DMOVIE.CHK
BUILDING_FILENAMES = "AQADAwgAAAACAAAAEAAAAP////8IYnVpbGRpbmcGYmxkZ2hkAAAAAAAAGAAJAAAAAAAQAA=="

# String table from a movie generated with the Japanese release of 3DMM
MOVIE_STRINGS_JPN = "AQAFBQgAAAAGAAAAugAAAP////8WADMARAAgAE0AbwB2AGkAZQAgAE0AYQBrAGUAcgAvADMARABNAE8AVgBJAEUAEwBUAGg" \
                    "AaQBzACAAbQBvAHYAaQBlACAAZABvAGMAdQBtAGUAbgB0AA8AWQBvAHUAcgAgAFUAcwBlAHIAIABSAG8AbABsAHMADQBQAG" \
                    "wAYQB5AGQAbwAvAFAAbABhAHkAZABvAAcAQwBvAHAAeQAgAG8AZgALAEEAIABOAGUAdwAgAE0AbwB2AGkAZQAAAAAAAgAAA" \
                    "C4AAAAAAAAAVgAAAAEAAAB2AAAAAwAAAJIAAAAEAAAAogAAAAUAAAA="


class StringTableTests(unittest.TestCase):
    def test_load_ansi(self):
        building_filenames = stringtable.StringTable.from_buffer(base64.b64decode(BUILDING_FILENAMES))
        assert len(building_filenames) == 2
        assert building_filenames[0x100000] == "bldghd"
        assert building_filenames[0x180000] == "building"

    def test_load_utf16(self):
        movie_strings = stringtable.StringTable.from_buffer(base64.b64decode(MOVIE_STRINGS_JPN))
        assert len(movie_strings) == 6
        assert movie_strings[0] == "This movie document"
        assert movie_strings[1] == "Your User Rolls"
        assert movie_strings[2] == "3D Movie Maker/3DMOVIE"
        assert movie_strings[3] == "Playdo/Playdo"
        assert movie_strings[4] == "Copy of"
        assert movie_strings[5] == "A New Movie"

    def test_save_ansi(self):
        # Create a new string table with the same contents as the example
        building_filenames = stringtable.StringTable()
        building_filenames[0x100000] = "bldghd"
        building_filenames[0x180000] = "building"

        # Check the serialized version == the original
        serialized_building_filenames = building_filenames.to_buffer()
        expected_building_filenames = base64.b64decode(BUILDING_FILENAMES)
        assert len(serialized_building_filenames) == len(expected_building_filenames)

        # Check if we load the serialized version that it is the same
        deserialized_building_filenames = stringtable.StringTable.from_buffer(serialized_building_filenames)
        assert building_filenames == deserialized_building_filenames

    def test_save_unicode(self):
        # Create a new string table with the same contents as the example
        movie_strings = stringtable.StringTable()
        movie_strings[0] = "This movie document"
        movie_strings[1] = "Your User Rolls"
        movie_strings[2] = "3D Movie Maker/3DMOVIE"
        movie_strings[3] = "Playdo/Playdo"
        movie_strings[4] = "Copy of"
        movie_strings[5] = "A New Movie"

        # Check the serialized version == the original
        serialized_movie_strings = movie_strings.to_buffer()

        # Check if we load the serialized version that it is the same
        deserialized_movie_strings = stringtable.StringTable.from_buffer(serialized_movie_strings)
        assert movie_strings == deserialized_movie_strings


if __name__ == '__main__':
    unittest.main()
