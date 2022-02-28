import os
import unittest
import filecmp

from importlib_metadata import version
import test.aux as aux

import backuper.backup as bkp
from backuper.commands import (
    CheckCommand,
    NewCommand,
    RestoreCommand,
    UpdateCommand
)


class BackupIntegrationTest(unittest.TestCase):

    new_backup = {
        'source': './test/resources/bkp_test_sources_new',
        'hashes': {'/f/e/f/9/fef9161f9f9a492dba2b1357298f17897849fefc',
                   '/c/c/2/f/cc2ff24e50730e1b7c238890fc877de269f9bd98',
                   '/1/0/e/4/10e4b6f822c7493e1aea22d15e515b584b2db7a2'},
        'meta': [
            bkp.FileEntry('text_file1.txt',
                          'fef9161f9f9a492dba2b1357298f17897849fefc'),
            bkp.FileEntry('text_file1 copy.txt',
                          'fef9161f9f9a492dba2b1357298f17897849fefc'),
            bkp.FileEntry('subdir/Original-Lena-image.png',
                          'cc2ff24e50730e1b7c238890fc877de269f9bd98'),
            bkp.FileEntry('LICENSE',
                          '10e4b6f822c7493e1aea22d15e515b584b2db7a2'),
            bkp.DirEntry('subdir'),
            bkp.DirEntry('subdir/empty dir')
        ]
    }

    update_backup = {
        'source': './test/resources/bkp_test_sources_update',
        'hashes': new_backup['hashes'].union({
            '/7/f/2/f/7f2f5c0211b62cc0f2da98c3f253bba9dc535b17',
            '/5/b/5/1/5b5174193c004d8f27811b961fbaa545b5460f2a'
        }),
        'meta': [
            bkp.FileEntry('text_file1.txt',
                          'fef9161f9f9a492dba2b1357298f17897849fefc'),
            bkp.FileEntry('text_file1 copy.txt',
                          '7f2f5c0211b62cc0f2da98c3f253bba9dc535b17'),
            bkp.FileEntry('LICENSE',
                          '5b5174193c004d8f27811b961fbaa545b5460f2a'),
            bkp.DirEntry('subdir'),
            bkp.DirEntry('subdir/empty dir')
        ]
    }

    def tearDown(self) -> None:
        aux.rm_temp_dirs()

    def test_normalize_path(self):
        dir = 'direc tory'
        self.assertEqual(bkp.normalize_path(dir), dir)

        nix_filename = '/subdir/another dir/file.name.csv'
        self.assertEqual(bkp.normalize_path(nix_filename),
                         'subdir/another dir/file.name.csv')

        windows_filename = '\\subdir\\another dir\\file.name.csv'
        self.assertEqual(bkp.normalize_path(windows_filename),
                         'subdir/another dir/file.name.csv')

    def test_new_backup(self):
        destination = aux.gen_temp_dir_path('new_backup')
        bkp.new(NewCommand(
            'testing',
            self.new_backup['source'],
            destination,
            password=None,
            zip=False
        ))

        data_filenames = aux.list_all_files_recursive(
            os.path.join(destination, 'data')
        )
        self.assertEqual(len(data_filenames),
                         len(self.new_backup['hashes']))
        for filename in data_filenames:
            self.assertIn(filename, self.new_backup['hashes'])

        reader = bkp.MetaReader(destination, 'testing')
        with reader:
            for entry in reader.entries():
                self.assertIn(entry, self.new_backup['meta'])

    def test_new_backup_with_zip(self):
        destination = aux.gen_temp_dir_path('new_backup')
        bkp.new(NewCommand(
            version='testing',
            source=self.new_backup['source'],
            location=destination,
            password=None,
            zip=True
        ))

        data_filenames = aux.list_all_files_recursive(
            os.path.join(destination, 'data')
        )
        self.assertEqual(len(data_filenames),
                         len(self.new_backup['hashes']))
        for filename in data_filenames:
            self.assertIn(filename.strip('.zip'),
                          self.new_backup['hashes'])

        reader = bkp.MetaReader(destination, 'testing')
        with reader:
            for entry in reader.entries():
                self.assertIn(entry, self.new_backup['meta'])

    def test_update_backup(self):
        destination = aux.gen_temp_dir_path('update_backup')
        bkp.new(NewCommand(
            'test_new',
            self.new_backup['source'],
            destination,
            password=None,
            zip=False
        ))
        bkp.update(UpdateCommand(
            'test_update',
            self.update_backup['source'],
            destination,
            password=None,
            zip=False
        ))

        data_filenames = aux.list_all_files_recursive(
            os.path.join(destination, 'data')
        )
        self.assertEqual(len(data_filenames), len(
            self.update_backup['hashes']))
        for filename in data_filenames:
            self.assertIn(filename, self.update_backup['hashes'])

        reader = bkp.MetaReader(destination, 'test_update')
        with reader:
            for entry in reader.entries():
                self.assertIn(entry, self.update_backup['meta'])

    def test_update_backup_with_zip(self):
        destination = aux.gen_temp_dir_path('update_backup')
        bkp.new(NewCommand(
            'test_new',
            self.new_backup['source'],
            destination,
            password=None,
            zip=False
        ))
        bkp.update(UpdateCommand(
            'test_update',
            self.update_backup['source'],
            destination,
            password=None,
            zip=True
        ))

        data_filenames = aux.list_all_files_recursive(
            os.path.join(destination, 'data')
        )
        self.assertEqual(len(data_filenames), len(
            self.update_backup['hashes']))
        for filename in data_filenames:
            self.assertIn(filename.strip('.zip'), self.update_backup['hashes'])

        reader = bkp.MetaReader(destination, 'test_update')
        with reader:
            for entry in reader.entries():
                self.assertIn(entry, self.update_backup['meta'])

    def test_meta_reader(self):
        destination = aux.gen_temp_dir_path('meta_reader')
        bkp.new(NewCommand(
            'test_new',
            self.new_backup['source'],
            destination,
            password=None,
            zip=False
        ))

        reader = bkp.MetaReader(destination, 'test_new')
        with reader:
            entries = list(reader.entries())

        for expected in self.new_backup['meta']:
            self.assertIn(expected, entries)

    def test_check_backup_version(self):
        destination = aux.gen_temp_dir_path('check_backup_name')
        bkp.new(NewCommand(
            'test_new',
            self.new_backup['source'],
            destination,
            password=None,
            zip=False
        ))

        errors = bkp.check(CheckCommand(
            location=destination,
            version='test_new'
        ))
        self.assertEqual(errors, [])

        # corrupt meta file inserting non existing hash
        meta_writer = bkp.MetaWriter(destination, 'test_new')
        with meta_writer._open('a'):
            meta_writer.add_file('file-with-missing-meta',
                                 '44efbcfa3f99f75e396a56a119940e2c1f902d2c')

        errors = bkp.check(CheckCommand(
            location=destination,
            version='test_new'
        ))
        self.assertEqual(errors,
                         ['Missing hash '
                          '44efbcfa3f99f75e396a56a119940e2c1f902d2c'
                          ' for file-with-missing-meta in test_new'])

    def test_check_all_backup_versions(self):
        destination = aux.gen_temp_dir_path('check_backup_all')
        bkp.new(NewCommand(
            'test_new',
            self.new_backup['source'],
            destination,
            password=None,
            zip=False
        ))
        bkp.update(UpdateCommand(
            'test_update',
            self.update_backup['source'],
            destination,
            password=None,
            zip=False
        ))

        errors = bkp.check(CheckCommand(destination))
        self.assertEqual(errors, [])

        # corrupt meta file inserting non existing hash
        meta_writer = bkp.MetaWriter(destination, 'test_new')
        with meta_writer._open('a'):
            meta_writer.add_file('file-with-missing-meta (new)',
                                 '44efbcfa3f99f75e396a56a119940e2c1f902d2c')

        meta_writer = bkp.MetaWriter(destination, 'test_update')
        with meta_writer._open('a'):
            meta_writer.add_file('file-with-missing-meta (update)',
                                 'acf6cd23d9aec2664665886e068504e799a0053f')

        errors = bkp.check(CheckCommand(destination))
        self.assertEqual(set(errors), {
            'Missing hash acf6cd23d9aec2664665886e068504e799a0053f '
            'for file-with-missing-meta (update) in test_update',
            'Missing hash 44efbcfa3f99f75e396a56a119940e2c1f902d2c '
            'for file-with-missing-meta (new) in test_new'
        })

    def test_restore_source_not_found(self):
        from_source = aux.gen_temp_dir_path('non_existing')
        to_destination = aux.gen_temp_dir_path('to_destination')
        with self.assertRaises(ValueError):
            bkp.restore(RestoreCommand(
                from_source,
                to_destination,
                version_name='test',
                password=None
            ))

    def test_restore_destination_not_empty(self):
        from_source = aux.gen_temp_dir_path('from_source')
        to_destination = '.'
        bkp.new(NewCommand(
            'test',
            self.new_backup['source'],
            from_source,
            password=None,
            zip=False
        ))

        with self.assertRaises(ValueError):
            bkp.restore(RestoreCommand(
                from_source,
                to_destination,
                version_name='test',
                password=None
            ))

    def test_restore_version_not_found(self):
        from_source = aux.gen_temp_dir_path('from_source')
        to_destination = aux.gen_temp_dir_path('to_destination')
        bkp.new(NewCommand(
            'test',
            self.new_backup['source'],
            from_source,
            password=None,
            zip=False
        ))

        with self.assertRaises(ValueError):
            bkp.restore(RestoreCommand(
                from_source,
                to_destination,
                version_name='non_existing_version',
                password=None
            ))

    def test_restore_with_success(self):
        from_source = aux.gen_temp_dir_path('from_source')
        to_destination = aux.gen_temp_dir_path('to_destination')
        bkp.new(NewCommand(
            'test',
            self.new_backup['source'],
            from_source,
            password=None,
            zip=False
        ))
        bkp.restore(RestoreCommand(
            from_source,
            to_destination,
            version_name='test',
            password=None
        ))

        comp = filecmp.dircmp(self.new_backup['source'], to_destination)
        self.assertEqual(['LICENSE', 'text_file1 copy.txt', 'text_file1.txt'],
                         comp.common_files)
        self.assertEqual(['Original-Lena-image.png'],
                         comp.subdirs['subdir'].common_files)
        self.assertEqual(['empty dir'],
                         comp.subdirs['subdir'].common_dirs)


if __name__ == '__main__':
    unittest.main()
