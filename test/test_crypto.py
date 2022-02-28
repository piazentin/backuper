import backuper.crypto as crypto
import os
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
            {'kek_salt', 'dek'},
            set(meta.keys())
        )

    def test_write_read_meta(self):
        pass

    def test_generate_key_derivation(self):
        pass

    def test_open_dek(self):
        pass

    def test_encrypt_decrypt(self):
        pass


if __name__ == '__main__':
    unittest.main()
