import unittest
from unittest.mock import patch

import backuper.argparser as parser
import backuper.commands as c


class ArgParserTest(unittest.TestCase):

    def test_new_backup(self):
        args = parser.parse(
            'new /first/source /second/destination -n BackupName'.split())
        self.assertIsInstance(args, c.NewCommand)
        self.assertEqual(args,
                         c.NewCommand(
                             name='BackupName',
                             source='/first/source',
                             destination='/second/destination',
                             zip=False))

    def test_new_backup_with_zip(self):
        args = parser.parse(
            'new /first/source /second/destination -n BackupName --zip'.split()
        )
        self.assertIsInstance(args, c.NewCommand)
        self.assertEqual(args,
                         c.NewCommand(
                             name='BackupName',
                             source='/first/source',
                             destination='/second/destination',
                             zip=True))

    @patch('backuper.argparser._default_name')
    def test_new_backup_default_name(self, _mocked_default_name):
        _mocked_default_name.return_value = '2021-01-31T120102'

        args = parser.parse(
            'new /first/source /second/destination'.split())
        self.assertIsInstance(args, c.NewCommand)
        self.assertEqual(args, c.NewCommand(
            name='2021-01-31T120102',
            source='/first/source',
            destination='/second/destination',
            zip=False))

    def test_update_backup(self):
        args = parser.parse(
            'update /first/source /second/destination '
            '--name BackupName'.split())
        self.assertIsInstance(args, c.UpdateCommand)
        self.assertEqual(args, c.UpdateCommand(
            name='BackupName',
            source='/first/source',
            destination='/second/destination',
            zip=False))

    def test_update_backup_with_zip(self):
        args = parser.parse(
            'update /first/source /second/destination '
            '--zip --name BackupName'.split())
        self.assertIsInstance(args, c.UpdateCommand)
        self.assertEqual(args, c.UpdateCommand(
            name='BackupName',
            source='/first/source',
            destination='/second/destination',
            zip=True))

    @patch('backuper.argparser._default_name')
    def test_update_backup_default_name(self, _mocked_default_name):
        _mocked_default_name.return_value = '2021-01-31T120102'

        args = parser.parse('update /first/source /second/destination'.split())
        self.assertIsInstance(args, c.UpdateCommand)
        self.assertEqual(args, c.UpdateCommand(
            name='2021-01-31T120102',
            source='/first/source',
            destination='/second/destination',
            zip=False))

    def test_check_backup(self):
        args = parser.parse('check /second/destination'.split())
        self.assertIsInstance(args, c.CheckCommand)
        self.assertEqual(args, c.CheckCommand(
            destination='/second/destination', name=None))

        args = parser.parse('check /second/destination -n testName'.split())
        self.assertIsInstance(args, c.CheckCommand)
        self.assertEqual(args, c.CheckCommand(
            destination='/second/destination', name='testName'))

    def test_restore_backup(self):
        args = parser.parse(
            'restore --from /backup/source --to /backup/destination '
            '--version backup-version'.split())
        self.assertIsInstance(args, c.RestoreCommand)
        self.assertEqual(args, c.RestoreCommand(
            from_source='/backup/source',
            to_destination='/backup/destination',
            version_name='backup-version'
        ))
