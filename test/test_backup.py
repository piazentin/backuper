from backuper.commands import NewCommand, UpdateCommand
import unittest
from datetime import datetime
import os
from tempfile import gettempdir
import csv
import backuper.backup as bkp


class BackupIntegrationTest(unittest.TestCase):
    expected_hashs = ['fef9161f9f9a492dba2b1357298f17897849fefc',
                      'cc2ff24e50730e1b7c238890fc877de269f9bd98']
    expected_control_contents = [
        ['f', 'text_file1.txt', 'fef9161f9f9a492dba2b1357298f17897849fefc'],
        ['f', 'text_file1 copy.txt', 'fef9161f9f9a492dba2b1357298f17897849fefc'],
        ['f', '/subdir/Original-Lena-image.png',
            'cc2ff24e50730e1b7c238890fc877de269f9bd98'],
        ['d', 'subdir', ''],
        ['d', '/subdir/empty dir', ''],
    ]

    def _random_backup_dir(self):
        return os.path.join(gettempdir(), 'backuper_integration_test', datetime.now().strftime("%Y-%m-%dT%H%M%S%f"))

    def test_new_backup(self):
        source = './test/resources/bkp_test_sources_new'
        bkp_destination = self._random_backup_dir()
        bkp.new(NewCommand('testing', source, bkp_destination))

        bkp_data_filenames = os.listdir(os.path.join(bkp_destination, 'data'))
        self.assertEqual(len(bkp_data_filenames), len(self.expected_hashs))
        for filename in bkp_data_filenames:
            self.assertIn(filename, self.expected_hashs)

        control_filename = os.path.join(bkp_destination, 'testing.csv')
        with open(control_filename, 'r') as control_file:
            for row in csv.reader(control_file):
                self.assertIn(row, self.expected_control_contents)

        self.assertTrue(True)

    def test_update_backup(self):
        new_source = './test/resources/bkp_test_sources_new'
        update_source = './test/resources/bkp_test_sources_update'
        expected_hashs = self.expected_hashs.copy().append(
            '7f2f5c0211b62cc0f2da98c3f253bba9dc535b17')
        expected_control_contents = [
            ['f', 'text_file1.txt', 'fef9161f9f9a492dba2b1357298f17897849fefc'],
            ['f', 'text_file1 copy.txt', '7f2f5c0211b62cc0f2da98c3f253bba9dc535b17'],
            ['d', 'subdir', ''],
            ['d', '/subdir/empty dir', ''],
        ]

        bkp_destination = self._random_backup_dir()
        bkp.new(NewCommand('test_new', new_source, bkp_destination))
        bkp.update(UpdateCommand('test_update',
                   update_source, bkp_destination))


if __name__ == '__main__':
    unittest.main()
