from backuper.commands import NewCommand, UpdateCommand
import unittest
from datetime import datetime
import os
import shutil
from tempfile import gettempdir
import csv
import backuper.backup as bkp


class BackupIntegrationTest(unittest.TestCase):

    new_backup = {
        'source': './test/resources/bkp_test_sources_new',
        'hashes': {'fef9161f9f9a492dba2b1357298f17897849fefc', 'cc2ff24e50730e1b7c238890fc877de269f9bd98'},
        'meta': [
            ['f', 'text_file1.txt', 'fef9161f9f9a492dba2b1357298f17897849fefc'],
            ['f', 'text_file1 copy.txt', 'fef9161f9f9a492dba2b1357298f17897849fefc'],
            ['f', '/subdir/Original-Lena-image.png',
                'cc2ff24e50730e1b7c238890fc877de269f9bd98'],
            ['d', 'subdir', ''],
            ['d', '/subdir/empty dir', '']]
    }

    update_backup = {
        'source': './test/resources/bkp_test_sources_update',
        'hashes': new_backup['hashes'].union({'7f2f5c0211b62cc0f2da98c3f253bba9dc535b17'}),
        'meta': [
            ['f', 'text_file1.txt', 'fef9161f9f9a492dba2b1357298f17897849fefc'],
            ['f', 'text_file1 copy.txt', '7f2f5c0211b62cc0f2da98c3f253bba9dc535b17'],
            ['d', 'subdir', ''],
            ['d', '/subdir/empty dir', '']
        ]
    }

    def setUp(self) -> None:
        os.makedirs(os.path.join(gettempdir(), 'backuper_integration_test'), exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(os.path.join(gettempdir(), 'backuper_integration_test'))

    def _random_dir(self):
        return os.path.join(gettempdir(), 'backuper_integration_test', datetime.now().strftime("%Y-%m-%dT%H%M%S%f"))

    def test_new_backup(self):
        destination = self._random_dir()
        bkp.new(NewCommand(
            'testing', self.new_backup['source'], destination))

        data_filenames = os.listdir(os.path.join(destination, 'data'))
        self.assertEqual(len(data_filenames),
                         len(self.new_backup['hashes']))
        for filename in data_filenames:
            self.assertIn(filename, self.new_backup['hashes'])

        meta_filename = os.path.join(destination, 'testing.csv')
        with open(meta_filename, 'r') as meta_file:
            for row in csv.reader(meta_file):
                self.assertIn(row, self.new_backup['meta'])

    def test_update_backup(self):
        destination = self._random_dir()
        bkp.new(NewCommand('test_new', self.new_backup['source'], destination))
        bkp.update(UpdateCommand('test_update',
                   self.update_backup['source'], destination))

        data_filenames = os.listdir(os.path.join(destination, 'data'))
        self.assertEqual(len(data_filenames), len(
            self.update_backup['hashes']))
        for filename in data_filenames:
            self.assertIn(filename, self.update_backup['hashes'])

        meta_filename = os.path.join(destination, 'test_update.csv')
        with open(meta_filename, 'r') as meta_file:
            for row in csv.reader(meta_file):
                self.assertIn(row, self.update_backup['meta'])

    def test_check_backup_name(self):
        # TODO
        pass

    def test_check_backup_all(self):
        # TODO
        pass


if __name__ == '__main__':
    unittest.main()
