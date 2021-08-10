import unittest
backuper = __import__('backuper')


class BackupIntegrationTest(unittest.TestCase):

    def test_new_backup(self):
        backuper.main([])
        self.assertTrue(True)


if __name__ == '__main__':
    unittest.main()
