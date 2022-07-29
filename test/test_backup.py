import os
import unittest
import filecmp
from backuper.implementation import models, utils
from backuper.implementation.config import CsvDbConfig
from backuper.implementation.csv_db import CsvDb

import test.aux as aux

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
        "meta": [
            models.StoredFile(
                "text_file1.txt",
                "fef9161f9f9a492dba2b1357298f17897849fefc",
                "f/e/f/9/fef9161f9f9a492dba2b1357298f17897849fefc",
                False,
            ),
            models.StoredFile(
                "text_file1 copy.txt",
                "fef9161f9f9a492dba2b1357298f17897849fefc",
                "f/e/f/9/fef9161f9f9a492dba2b1357298f17897849fefc",
                False,
            ),
            models.StoredFile(
                "subdir/starry_night.png",
                "07c8762861e8f1927708408702b1fd747032f050",
                "0/7/c/8/07c8762861e8f1927708408702b1fd747032f050",
                False,
            ),
            models.StoredFile(
                "LICENSE",
                "10e4b6f822c7493e1aea22d15e515b584b2db7a2",
                "1/0/e/4/10e4b6f822c7493e1aea22d15e515b584b2db7a2",
                False,
            ),
            models.DirEntry("subdir"),
            models.DirEntry("subdir/empty dir"),
        ],
    }

    new_backup_with_zip = {
        "source": "./test/resources/bkp_test_sources_new",
        "hashes": {
            "/f/e/f/9/fef9161f9f9a492dba2b1357298f17897849fefc",
            "/0/7/c/8/07c8762861e8f1927708408702b1fd747032f050",
            "/1/0/e/4/10e4b6f822c7493e1aea22d15e515b584b2db7a2",
        },
        "meta": [
            models.StoredFile(
                "text_file1.txt",
                "fef9161f9f9a492dba2b1357298f17897849fefc",
                "f/e/f/9/fef9161f9f9a492dba2b1357298f17897849fefc",
                False,
            ),
            models.StoredFile(
                "text_file1 copy.txt",
                "fef9161f9f9a492dba2b1357298f17897849fefc",
                "f/e/f/9/fef9161f9f9a492dba2b1357298f17897849fefc",
                False,
            ),
            models.StoredFile(
                "subdir/starry_night.png",
                "07c8762861e8f1927708408702b1fd747032f050",
                "0/7/c/8/07c8762861e8f1927708408702b1fd747032f050",
                False,
            ),
            models.StoredFile(
                "LICENSE",
                "10e4b6f822c7493e1aea22d15e515b584b2db7a2",
                "1/0/e/4/10e4b6f822c7493e1aea22d15e515b584b2db7a2.zip",
                True,
            ),
            models.DirEntry("subdir"),
            models.DirEntry("subdir/empty dir"),
        ],
    }

    update_backup = {
        "source": "./test/resources/bkp_test_sources_update",
        "hashes": new_backup["hashes"].union(
            {
                "/7/f/2/f/7f2f5c0211b62cc0f2da98c3f253bba9dc535b17",
                "/5/b/5/1/5b5174193c004d8f27811b961fbaa545b5460f2a",
            }
        ),
        "meta": [
            models.StoredFile(
                "text_file1.txt",
                "fef9161f9f9a492dba2b1357298f17897849fefc",
                "f/e/f/9/fef9161f9f9a492dba2b1357298f17897849fefc",
                False,
            ),
            models.StoredFile(
                "text_file1 copy.txt",
                "7f2f5c0211b62cc0f2da98c3f253bba9dc535b17",
                "7/f/2/f/7f2f5c0211b62cc0f2da98c3f253bba9dc535b17",
                False,
            ),
            models.StoredFile(
                "LICENSE",
                "5b5174193c004d8f27811b961fbaa545b5460f2a",
                "5/b/5/1/5b5174193c004d8f27811b961fbaa545b5460f2a",
                False,
            ),
            models.DirEntry("subdir"),
            models.DirEntry("subdir/empty dir"),
        ],
    }

    update_backup_with_zip = {
        "source": "./test/resources/bkp_test_sources_update",
        "hashes": new_backup["hashes"].union(
            {
                "/7/f/2/f/7f2f5c0211b62cc0f2da98c3f253bba9dc535b17",
                "/5/b/5/1/5b5174193c004d8f27811b961fbaa545b5460f2a",
            }
        ),
        "meta": [
            models.StoredFile(
                "text_file1.txt",
                "fef9161f9f9a492dba2b1357298f17897849fefc",
                "f/e/f/9/fef9161f9f9a492dba2b1357298f17897849fefc",
                False,
            ),
            models.StoredFile(
                "text_file1 copy.txt",
                "7f2f5c0211b62cc0f2da98c3f253bba9dc535b17",
                "7/f/2/f/7f2f5c0211b62cc0f2da98c3f253bba9dc535b17",
                False,
            ),
            models.StoredFile(
                "LICENSE",
                "5b5174193c004d8f27811b961fbaa545b5460f2a",
                "5/b/5/1/5b5174193c004d8f27811b961fbaa545b5460f2a.zip",
                True,
            ),
            models.DirEntry("subdir"),
            models.DirEntry("subdir/empty dir"),
        ],
    }

    def tearDown(self) -> None:
        pass  # aux.rm_temp_dirs()

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
        destination = aux.gen_temp_dir_path("new_backup")
        bkp.new(
            NewCommand(
                "testing",
                self.new_backup["source"],
                destination,
                password=None,
                zip=False,
            )
        )

        data_filenames = aux.list_all_files_recursive(os.path.join(destination, "data"))
        self.assertEqual(len(data_filenames), len(self.new_backup["hashes"]))
        for filename in data_filenames:
            self.assertIn(filename, self.new_backup["hashes"])

        db = CsvDb(CsvDbConfig(destination))
        for entry in db.get_fs_objects_for_version(models.Version("testing")):
            self.assertIn(entry, self.new_backup["meta"])

    def test_new_backup_with_zip(self):
        destination = aux.gen_temp_dir_path("new_backup")
        bkp.new(
            NewCommand(
                version="testing",
                source=self.new_backup["source"],
                location=destination,
                password=None,
                zip=True,
            )
        )

        data_filenames = aux.list_all_files_recursive(os.path.join(destination, "data"))
        self.assertEqual(len(data_filenames), len(self.new_backup["hashes"]))
        for filename in data_filenames:
            self.assertIn(filename.strip(".zip"), self.new_backup["hashes"])

        db = CsvDb(CsvDbConfig(destination))
        for entry in db.get_fs_objects_for_version(models.Version("testing")):
            self.assertIn(entry, self.new_backup_with_zip["meta"])

    def test_update_backup(self):
        destination = aux.gen_temp_dir_path("update_backup")
        bkp.new(
            NewCommand(
                "test_new",
                self.new_backup["source"],
                destination,
                password=None,
                zip=False,
            )
        )
        bkp.update(
            UpdateCommand(
                "test_update",
                self.update_backup["source"],
                destination,
                password=None,
                zip=False,
            )
        )

        data_filenames = aux.list_all_files_recursive(os.path.join(destination, "data"))
        self.assertEqual(len(data_filenames), len(self.update_backup["hashes"]))
        for filename in data_filenames:
            self.assertIn(filename, self.update_backup["hashes"])

        db = CsvDb(CsvDbConfig(destination))
        for entry in db.get_fs_objects_for_version(models.Version("test_update")):
            self.assertIn(entry, self.update_backup["meta"])

    def test_update_backup_with_zip(self):
        destination = aux.gen_temp_dir_path("update_backup")
        bkp.new(
            NewCommand(
                "test_new",
                self.new_backup["source"],
                destination,
                password=None,
                zip=False,
            )
        )
        bkp.update(
            UpdateCommand(
                "test_update",
                self.update_backup["source"],
                destination,
                password=None,
                zip=True,
            )
        )

        data_filenames = aux.list_all_files_recursive(os.path.join(destination, "data"))
        self.assertEqual(len(data_filenames), len(self.update_backup["hashes"]))
        for filename in data_filenames:
            self.assertIn(filename.strip(".zip"), self.update_backup["hashes"])

        db = CsvDb(CsvDbConfig(destination))
        for entry in db.get_fs_objects_for_version(models.Version("test_update")):
            self.assertIn(entry, self.update_backup_with_zip["meta"])

    def test_meta_reader(self):
        destination = aux.gen_temp_dir_path("meta_reader")
        bkp.new(
            NewCommand(
                "test_new",
                self.new_backup["source"],
                destination,
                password=None,
                zip=False,
            )
        )

        db = CsvDb(CsvDbConfig(destination))
        for expected in self.new_backup["meta"]:
            self.assertIn(
                expected, db.get_fs_objects_for_version(models.Version("test_new"))
            )

    def test_check_backup_version(self):
        destination = aux.gen_temp_dir_path("check_backup_name")
        bkp.new(
            NewCommand(
                "test_new",
                self.new_backup["source"],
                destination,
                password=None,
                zip=False,
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
                password=None,
                zip=False,
            )
        )
        bkp.update(
            UpdateCommand(
                "test_update",
                self.update_backup["source"],
                destination,
                password=None,
                zip=False,
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
                RestoreCommand(
                    from_source, to_destination, version_name="test", password=None
                )
            )

    def test_restore_destination_not_empty(self):
        from_source = aux.gen_temp_dir_path("from_source")
        to_destination = "."
        bkp.new(
            NewCommand(
                "test", self.new_backup["source"], from_source, password=None, zip=False
            )
        )

        with self.assertRaises(ValueError):
            bkp.restore(
                RestoreCommand(
                    from_source, to_destination, version_name="test", password=None
                )
            )

    def test_restore_version_not_found(self):
        from_source = aux.gen_temp_dir_path("from_source")
        to_destination = aux.gen_temp_dir_path("to_destination")
        bkp.new(
            NewCommand(
                "test", self.new_backup["source"], from_source, password=None, zip=False
            )
        )

        with self.assertRaises(ValueError):
            bkp.restore(
                RestoreCommand(
                    from_source,
                    to_destination,
                    version_name="non_existing_version",
                    password=None,
                )
            )

    def test_restore_with_success(self):
        from_source = aux.gen_temp_dir_path("from_source")
        to_destination = aux.gen_temp_dir_path("to_destination")
        bkp.new(
            NewCommand(
                "test", self.new_backup["source"], from_source, password=None, zip=False
            )
        )
        bkp.restore(
            RestoreCommand(
                from_source, to_destination, version_name="test", password=None
            )
        )

        comp = filecmp.dircmp(self.new_backup["source"], to_destination)
        self.assertEqual(
            ["LICENSE", "text_file1 copy.txt", "text_file1.txt"], comp.common_files
        )
        self.assertEqual(["starry_night.png"], comp.subdirs["subdir"].common_files)
        self.assertEqual(["empty dir"], comp.subdirs["subdir"].common_dirs)


if __name__ == "__main__":
    unittest.main()
