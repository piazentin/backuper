import base64
import os

from cryptography.fernet import Fernet
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from typing import Tuple, Dict


CRYPTO_META_FILENAME = 'meta.txt'
CRYPTO_VERSION = b'\x30'


def generate_key_derivation(salt: bytes, master_password: str) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    return base64.urlsafe_b64encode(kdf.derive(master_password.encode()))


def read_crypto_meta(backup_main_dir: str) -> Tuple[bytes, bytes]:
    meta_vars = {}
    filename = os.path.join(backup_main_dir, CRYPTO_META_FILENAME)
    with open(filename, mode='r') as meta_file:
        for line in meta_file:
            key, value = line.partition('=')[::2]
            meta_vars[key] = value.strip().strip('"')
    return meta_vars


def write_crypto_meta(backup_main_dir: str, vars: Dict[str, str]):
    meta_filename = os.path.join(backup_main_dir, CRYPTO_META_FILENAME)
    with open(meta_filename, mode='w', encoding="utf-8") as meta_file:
        for key, val in vars.items():
            meta_file.write(f'{key}="{val}"\n')


def open_dek(salt: bytes, master_password: str, dek: bytes) -> bytes:
    kek = generate_key_derivation(salt, master_password)
    return base64.urlsafe_b64decode(Fernet(kek).decrypt(dek))


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

    def encrypt_base64(self, plain: bytes):
        return base64.urlsafe_b64encode(self.encrypt(plain))

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

    def decrypt_base64(self, encrypted: bytes) -> bytes:
        return self.decrypt(base64.urlsafe_b64decode(encrypted))


def new_crypto(backup_main_dir: str, master_password: str) -> Crypto:
    vars = read_crypto_meta(backup_main_dir)
    salt = base64.urlsafe_b64decode(vars['kek_salt'].encode('UTF-8'))
    encrypted_dek = vars['dek'].encode('UTF-8')
    dek = open_dek(salt, master_password, encrypted_dek)
    return Crypto(dek)


def setup_backup_encryption_key(backup_main_dir: str, master_password: str):
    salt = os.urandom(16)
    key = generate_key_derivation(salt, master_password)
    data_key = Fernet.generate_key()
    fernet = Fernet(key)
    encrypted_data_key = fernet.encrypt(data_key)

    salt_str = base64.urlsafe_b64encode(salt).decode('UTF-8')
    dek_str = encrypted_data_key.decode('UTF-8')
    vars = {'kek_salt': salt_str, 'dek': dek_str}
    write_crypto_meta(backup_main_dir, vars)
