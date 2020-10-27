import unittest
import pathlib
import pymaginopolis.chunkyfile.loader as loader
import pymaginopolis.chunkyfile.model as filemodel
import logging
import os

CHUNKY_FILE_EXTENSIONS = {".3mm", ".3th", ".3cn",  # 3DMM
                          ".nmm", ".nth", ".1mm",  # Nickelodeon 3DMM
                          ".ath", ".bth", ".gth", ".mth", ".tth",  # Creative Writer 2
                          ".chk",  # Generic
                          }


class ChunkyLoaderTests(unittest.TestCase):

    @staticmethod
    def get_data_dir():
        return pathlib.Path(__file__).parent / "data"

    def test_load_movie(self):
        """ Test loading a 3DMM movie """
        movie_file_path = self.get_data_dir() / "unittest.3mm"
        self.assertTrue(movie_file_path.is_file())

        with open(movie_file_path, "rb") as movie_file:
            movie_chunky_file = loader.load_from_file(movie_file)

            # Check the header was parsed correctly
            self.assertEqual(movie_chunky_file.endianness, filemodel.Endianness.LittleEndian)
            self.assertEqual(movie_chunky_file.characterset, filemodel.CharacterSet.ANSI)
            self.assertEqual(movie_chunky_file.file_type, "SOC ")

            # Check for expected chunks
            mvie_chunk = movie_chunky_file[filemodel.ChunkId("MVIE", 0)]
            gst_chunks = movie_chunky_file["GST"]
            self.assertEqual(len(gst_chunks), 2)

            # Check for chunk names
            tmpl_chunk = movie_chunky_file[filemodel.ChunkId("TMPL", 1)]
            self.assertEqual(tmpl_chunk.name, "Pymaginopolis Unit Test")

            scen_chunk = movie_chunky_file[filemodel.ChunkId("SCEN", 1)]
            self.assertEqual(scen_chunk.name, "MY-Street Background")

            # Check for children
            self.assertEqual(len(tmpl_chunk.children), 1)
            self.assertEqual(len(mvie_chunk.children), 3)

    def test_load_all_chunky_files(self):
        """ Test loading a directory of chunky files """
        logger = logging.getLogger(__name__)

        # Allow override of test data path
        unit_test_data_path = os.environ.get("PYMAGINOPOLIS_UNITTEST_DATA")
        if unit_test_data_path:
            chunky_files_path = pathlib.Path(unit_test_data_path)
        else:
            chunky_files_path = self.get_data_dir()

        self.assertTrue(chunky_files_path.is_dir())

        logger.debug("Loading chunky files from: %s", chunky_files_path)

        for file_path in chunky_files_path.glob("*"):
            if file_path.suffix.lower() not in CHUNKY_FILE_EXTENSIONS:
                continue

            logger.info("Loading %s", file_path)

            with open(file_path, "rb") as chunky_file:
                header = chunky_file.read(4)
                chunky_file.seek(0)
                if header != b'CHN2':
                    logger.debug("%s is not a chunky file", file_path)
                    continue

                # This should throw if the file cannot be loaded
                loaded_file = loader.load_from_file(chunky_file)

                self.assertTrue(len(loaded_file.chunks) > 0)
