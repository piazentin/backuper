import os
import shutil
from datetime import datetime
import random
import string
from tempfile import gettempdir
from typing import List


TEMP_SUBDIR = 'backuper'


def gen_temp_dir_path(prefix: str = '') -> str:
    dirname = prefix + datetime.now().strftime("%Y-%m-%dT%H%M%S%f")
    return os.path.join(gettempdir(), TEMP_SUBDIR, dirname)


def gen_temp_dir(prefix: str = '') -> str:
    dirpath = gen_temp_dir_path(prefix)
    os.makedirs(dirpath, exist_ok=True)
    return dirpath


def rm_temp_dirs():
    base_dir = os.path.join(gettempdir(), TEMP_SUBDIR)
    if os.path.isdir(base_dir):
        shutil.rmtree(base_dir)


def list_all_files_recursive(base_path: str) -> List[str]:
    def dir_filenames(dirpath, filenames):
        return [os.path.join(dirpath, filename)
                for filename in filenames]

    files = []
    dirlist = [base_path]
    while len(dirlist) > 0:
        for (dirpath, dirnames, filenames) in os.walk(dirlist.pop()):
            dirlist.extend(dirnames)
            files.extend(dir_filenames(dirpath, filenames))
    return [f[len(base_path):] for f in files]


def random_string(lenght: int = 12) -> str:
    non_whitespace = string.digits + string.ascii_letters + string.punctuation
    return ''.join(random.choices(non_whitespace, k=lenght))
