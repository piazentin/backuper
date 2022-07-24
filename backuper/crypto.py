import backuper.utils as utils
import os

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from typing import Dict


CRYPTO_META_FILENAME = 'meta.txt'
CRYPTO_VERSION = b'\x30'


def derivate_key(salt: bytes, password: str) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    return kdf.derive(password.encode())


def read_crypto_meta(backup_main_dir: str) -> Dict[str, str]:
    meta_vars = {}
    filename = os.path.join(backup_main_dir, CRYPTO_META_FILENAME)
    with open(filename, mode='r') as meta_file:
        for line in meta_file:
            key, value = line.partition('=')[::2]
            meta_vars[key] = value.strip().removeprefix('"').removesuffix('"')
    return meta_vars


def write_crypto_meta(backup_main_dir: str, vars: Dict[str, str]):
    meta_filename = os.path.join(backup_main_dir, CRYPTO_META_FILENAME)
    with open(meta_filename, mode='w', encoding="utf-8") as meta_file:
        for key, val in vars.items():
            meta_file.write(f'{key}="{val}"\n')


class Crypto:
    def __init__(self, key: bytes):
        self._key = key

    def encrypt(self, plain: bytes) -> bytes:
        padder = padding.PKCS7(algorithms.AES.block_size).padder()
        padded_data = padder.update(plain) + padder.finalize()

        iv = os.urandom(16)
        encryptor = Cipher(
            algorithms.AES(self._key), modes.CBC(iv)
        ).encryptor()

        return (CRYPTO_VERSION +
                iv +
                encryptor.update(padded_data) +
                encryptor.finalize())

    def encrypt_base64(self, plain: bytes) -> str:
        return utils.to_base64str(self.encrypt(plain))

    def decrypt(self, encrypted: bytes) -> bytes:
        if bytes(encrypted[0:1]) != CRYPTO_VERSION:
            raise InvalidSignature("Unknown version")
        iv = encrypted[1:17]
        decryptor = Cipher(
            algorithms.AES(self._key), modes.CBC(iv)
        ).decryptor()
        unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()

        return unpadder.update(
            decryptor.update(encrypted[17:]) + decryptor.finalize()
        ) + unpadder.finalize()

    def decrypt_base64(self, encrypted: str) -> bytes:
        return self.decrypt(utils.from_base64str(encrypted))


def new_crypto(backup_main_dir: str, master_password: str) -> Crypto:
    vars = read_crypto_meta(backup_main_dir)
    salt = utils.from_base64str(vars['kek_salt'])
    kek = derivate_key(salt, master_password)

    encrypted_dek = utils.from_base64str(vars['dek_base64'])
    dek = Crypto(kek).decrypt(encrypted_dek)
    return Crypto(dek)


def setup_backup_encryption_key(backup_main_dir: str, password: str):
    salt = os.urandom(16)
    key = derivate_key(salt, password)

    plain_dek = os.urandom(32)
    encrypted_dek = Crypto(key).encrypt(plain_dek)

    salt_str = utils.to_base64str(salt)
    dek_str = utils.to_base64str(encrypted_dek)
    vars = {'kek_salt': salt_str, 'dek_base64': dek_str}
    write_crypto_meta(backup_main_dir, vars)
