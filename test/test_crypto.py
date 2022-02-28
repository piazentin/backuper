import backuper.crypto as crypto
import base64
import os
import random
import test.aux as aux
import unittest


class CryptoTest(unittest.TestCase):

    def test_setup_crypto(self):
        dirname = aux.gen_temp_dir('setup_crypto')
        master_password = aux.random_string()

        crypto.setup_backup_encryption_key(dirname, master_password)

        expected_meta_path = os.path.join(dirname, 'meta.txt')
        self.assertTrue(os.path.isfile(expected_meta_path))
        meta = crypto.read_crypto_meta(dirname)
        self.assertEqual(
            {'kek_salt', 'dek_base64'},
            set(meta.keys())
        )

    def test_write_read_meta(self):
        written_vars = {
            'a': '12kjdhgfsjkdr1234"',
            'b': 'aloha  '
        }
        dirname = aux.gen_temp_dir('write_read_meta')

        crypto.write_crypto_meta(dirname, written_vars)
        read_vars = crypto.read_crypto_meta(dirname)

        self.assertDictEqual(written_vars, read_vars)

    def test_derivate_key(self):
        salt = os.urandom(16)
        password = aux.random_string(random.randint(2, 128))

        key = crypto.derivate_key(salt, password)
        self.assertEqual(
            key,
            crypto.derivate_key(salt, password)
        )

        self.assertEqual(
            32,
            len(key)
        )

    def test_encrypt_decrypt(self):
        pass


if __name__ == '__main__':
    unittest.main()
