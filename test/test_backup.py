from math import exp
import os
from typing import Set
import unittest
import filecmp
from backuper.implementation import models, utils
from backuper.implementation.config import CsvDbConfig
import backuper.implementation.config as config
from backuper.implementation.csv_db import CsvDb

import test.aux as aux
import test.aux.fixtures as fixtures

import backuper.implementation.backup as bkp
from backuper.implementation.commands import (
    CheckCommand,
    NewCommand,
    RestoreCommand,
    UpdateCommand,
)


class BackupIntegrationTest(unittest.TestCase):

    new_backup = {
        "source": "./test/resources/bkp_test_sources_new",
        "hashes": {
            "/f/e/f/9/fef9161f9f9a492dba2b1357298f17897849fefc",
            "/0/7/c/8/07c8762861e8f1927708408702b1fd747032f050",
            "/1/0/e/4/10e4b6f822c7493e1aea22d15e515b584b2db7a2",
        },
    }

    new_backup_with_zip = {
        "source": "./test/resources/bkp_test_sources_new",
        "hashes": {
            "/f/e/f/9/fef9161f9f9a492dba2b1357298f17897849fefc",
            "/0/7/c/8/07c8762861e8f1927708408702b1fd747032f050",
            "/1/0/e/4/10e4b6f822c7493e1aea22d15e515b584b2db7a2",
        },
    }

    update_backup = {
        "source": "./test/resources/bkp_test_sources_update",
        "hashes": new_backup["hashes"].union(
            {
                "/7/f/2/f/7f2f5c0211b62cc0f2da98c3f253bba9dc535b17",
                "/5/b/5/1/5b5174193c004d8f27811b961fbaa545b5460f2a",
            }
        ),
    }

    update_backup_with_zip = {
        "source": "./test/resources/bkp_test_sources_update",
        "hashes": new_backup["hashes"].union(
            {
                "/7/f/2/f/7f2f5c0211b62cc0f2da98c3f253bba9dc535b17",
                "/5/b/5/1/5b5174193c004d8f27811b961fbaa545b5460f2a",
            }
        ),
    }

    def setUp(self) -> None:
        test_dirs = os.path.join(self.new_backup["source"], "subdir", "empty dir")
        os.makedirs(test_dirs, exist_ok=True)
        return super().setUp()

    def tearDown(self) -> None:
        aux.rm_temp_dirs()

    def assertStoredFileIn(
        self, stored_file: models.StoredFile, files: Set[models.StoredFile]
    ) -> None:
        found = False
        for expected_file in files:
            if (
                expected_file.sha1hash == stored_file.sha1hash
                and expected_file.restore_path == stored_file.restore_path
                and expected_file.is_compressed == stored_file.is_compressed
                and expected_file.stored_location == stored_file.stored_location
            ):
                found = True
                break

        if not found:
            raise self.failureException(
                f"StoredFile[{stored_file.restore_path}] not found in files"
            )

    def assertDbStatus(self, db: CsvDb, version: models.Version, expected):
        dirs = db.get_dirs_for_version(version)
        self.assertSetEqual(set(dirs), expected["dirs"])

        for stored_file in db.get_files_for_version(version):
            self.assertStoredFileIn(stored_file, expected["stored_files"])

    def test_normalize_path(self):
        dir = "direc tory"
        self.assertEqual(utils.normalize_path(dir), dir)

        nix_filename = "/subdir/another dir/file.name.csv"
        self.assertEqual(
            utils.normalize_path(nix_filename), "subdir/another dir/file.name.csv"
        )

        windows_filename = "\\subdir\\another dir\\file.name.csv"
        self.assertEqual(
            utils.normalize_path(windows_filename), "subdir/another dir/file.name.csv"
        )

    def test_new_backup(self):
        config.ZIP_ENABLED = False

        destination = aux.gen_temp_dir_path("new_backup")
        bkp.new(
            NewCommand(
                "testing",
                self.new_backup["source"],
                destination,
            )
        )

        data_filenames = aux.list_all_files_recursive(os.path.join(destination, "data"))
        self.assertEqual(len(data_filenames), len(self.new_backup["hashes"]))
        for filename in data_filenames:
            self.assertIn(filename, self.new_backup["hashes"])

        self.assertDbStatus(
            CsvDb(CsvDbConfig(destination)),
            models.Version("testing"),
            fixtures.new_backup_db,
        )

    def test_new_backup_with_zip(self):
        config.ZIP_ENABLED = True

        destination = aux.gen_temp_dir_path("new_backup")
        bkp.new(
            NewCommand(
                version="testing",
                source=self.new_backup["source"],
                location=destination,
            )
        )

        data_filenames = aux.list_all_files_recursive(os.path.join(destination, "data"))
        self.assertEqual(len(data_filenames), len(self.new_backup["hashes"]))
        for filename in data_filenames:
            self.assertIn(filename.strip(".zip"), self.new_backup["hashes"])

        self.assertDbStatus(
            CsvDb(CsvDbConfig(destination)),
            models.Version("testing"),
            fixtures.new_backup_with_zip_db,
        )

    def test_update_backup(self):
        config.ZIP_ENABLED = False

        destination = aux.gen_temp_dir_path("update_backup")
        bkp.new(
            NewCommand(
                "test_new",
                self.new_backup["source"],
                destination,
            )
        )
        bkp.update(
            UpdateCommand(
                "test_update",
                self.update_backup["source"],
                destination,
            )
        )

        data_filenames = aux.list_all_files_recursive(os.path.join(destination, "data"))
        self.assertEqual(len(data_filenames), len(self.update_backup["hashes"]))
        for filename in data_filenames:
            self.assertIn(filename, self.update_backup["hashes"])

        self.assertDbStatus(
            CsvDb(CsvDbConfig(destination)),
            models.Version("test_update"),
            fixtures.update_backup,
        )

    def test_update_backup_with_zip(self):
        config.ZIP_ENABLED = True

        destination = aux.gen_temp_dir_path("update_backup")
        bkp.new(
            NewCommand(
                "test_new",
                self.new_backup["source"],
                destination,
            )
        )
        bkp.update(
            UpdateCommand(
                "test_update",
                self.update_backup["source"],
                destination,
            )
        )

        data_filenames = aux.list_all_files_recursive(os.path.join(destination, "data"))
        self.assertEqual(len(data_filenames), len(self.update_backup["hashes"]))
        for filename in data_filenames:
            self.assertIn(filename.strip(".zip"), self.update_backup["hashes"])

        self.assertDbStatus(
            CsvDb(CsvDbConfig(destination)),
            models.Version("test_update"),
            fixtures.update_backup_with_zip,
        )

    def test_check_backup_version(self):
        destination = aux.gen_temp_dir_path("check_backup_name")
        bkp.new(
            NewCommand(
                "test_new",
                self.new_backup["source"],
                destination,
            )
        )

        errors = bkp.check(CheckCommand(location=destination, version="test_new"))
        self.assertEqual(errors, [])

        # corrupt db by inserting non existing hash
        version = models.Version("test_new")
        db = CsvDb(CsvDbConfig(destination))
        db.insert_file(
            version,
            models.StoredFile(
                "file-with-missing-meta",
                "44efbcfa3f99f75e396a56a119940e2c1f902d2c",
                "/4/4/e/f/44efbcfa3f99f75e396a56a119940e2c1f902d2c",
                False,
            ),
        )

        errors = bkp.check(CheckCommand(location=destination, version="test_new"))
        self.assertEqual(
            errors,
            [
                "Missing hash "
                "44efbcfa3f99f75e396a56a119940e2c1f902d2c"
                " for file-with-missing-meta in test_new"
            ],
        )

    def test_check_all_backup_versions(self):
        destination = aux.gen_temp_dir_path("check_backup_all")
        bkp.new(
            NewCommand(
                "test_new",
                self.new_backup["source"],
                destination,
            )
        )
        bkp.update(
            UpdateCommand(
                "test_update",
                self.update_backup["source"],
                destination,
            )
        )

        errors = bkp.check(CheckCommand(destination))
        self.assertEqual(errors, [])

        # corrupt db inserting non existing hash
        db = CsvDb(CsvDbConfig(destination))
        db.insert_file(
            models.Version("test_new"),
            models.StoredFile(
                "file-with-missing-meta (new)",
                "44efbcfa3f99f75e396a56a119940e2c1f902d2c",
                "/4/4/e/f/44efbcfa3f99f75e396a56a119940e2c1f902d2c",
                False,
            ),
        )
        db.insert_file(
            models.Version("test_update"),
            models.StoredFile(
                "file-with-missing-meta (update)",
                "acf6cd23d9aec2664665886e068504e799a0053f",
                "/a/c/f/6/acf6cd23d9aec2664665886e068504e799a0053f",
                False,
            ),
        )

        errors = bkp.check(CheckCommand(destination))
        self.assertEqual(
            set(errors),
            {
                "Missing hash acf6cd23d9aec2664665886e068504e799a0053f "
                "for file-with-missing-meta (update) in test_update",
                "Missing hash 44efbcfa3f99f75e396a56a119940e2c1f902d2c "
                "for file-with-missing-meta (new) in test_new",
            },
        )

    def test_restore_source_not_found(self):
        from_source = aux.gen_temp_dir_path("non_existing")
        to_destination = aux.gen_temp_dir_path("to_destination")
        with self.assertRaises(ValueError):
            bkp.restore(
                RestoreCommand(from_source, to_destination, version_name="test")
            )

    def test_restore_destination_not_empty(self):
        from_source = aux.gen_temp_dir_path("from_source")
        to_destination = "."
        bkp.new(
            NewCommand(
                "test",
                self.new_backup["source"],
                from_source,
            )
        )

        with self.assertRaises(ValueError):
            bkp.restore(
                RestoreCommand(
                    from_source,
                    to_destination,
                    version_name="test",
                )
            )

    def test_restore_version_not_found(self):
        from_source = aux.gen_temp_dir_path("from_source")
        to_destination = aux.gen_temp_dir_path("to_destination")
        bkp.new(
            NewCommand(
                "test",
                self.new_backup["source"],
                from_source,
            )
        )

        with self.assertRaises(ValueError):
            bkp.restore(
                RestoreCommand(
                    from_source,
                    to_destination,
                    version_name="non_existing_version",
                )
            )

    def test_restore_with_success(self):
        from_source = aux.gen_temp_dir_path("from_source")
        to_destination = aux.gen_temp_dir_path("to_destination")
        bkp.new(
            NewCommand(
                "test",
                self.new_backup["source"],
                from_source,
            )
        )
        bkp.restore(
            RestoreCommand(
                from_source,
                to_destination,
                version_name="test",
            )
        )

        comp = filecmp.dircmp(self.new_backup["source"], to_destination)
        self.assertEqual(
            ["LICENSE", "text_file1 copy.txt", "text_file1.txt"], comp.common_files
        )
        self.assertEqual(["starry_night.png"], comp.subdirs["subdir"].common_files)
        self.assertEqual(["empty dir"], comp.subdirs["subdir"].common_dirs)

    def test_restore_with_zip(self):
        from_source = aux.gen_temp_dir_path("from_source")
        to_destination = aux.gen_temp_dir_path("restore_with_zip_to_destination")
        bkp.new(NewCommand("test", self.new_backup["source"], from_source))
        bkp.restore(RestoreCommand(from_source, to_destination, version_name="test"))

        comp = filecmp.dircmp(self.new_backup["source"], to_destination)
        self.assertEqual(
            ["LICENSE", "text_file1 copy.txt", "text_file1.txt"], comp.common_files
        )
        self.assertEqual(["starry_night.png"], comp.subdirs["subdir"].common_files)
        self.assertEqual(["empty dir"], comp.subdirs["subdir"].common_dirs)


if __name__ == "__main__":
    unittest.main()
