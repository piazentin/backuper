from typing import List
import backuper.backup as bkp
import pathlib
import os
from zipfile import ZipFile, ZIP_DEFLATED


def get_all_versions(backup_main_dir: str) -> List[str]:
    return [f for f in os.listdir(backup_main_dir) if f.endswith('.csv')]


def as_hash2filename(backup_main_dir: str, version_file: str):
    reader = bkp.MetaReader(backup_main_dir, version_file)
    h2f = {}
    with reader:
        for file in reader.file_entries():
            h2f[file.hash] = file.name
    return h2f


def zip_hashed(bkp_file_name: str, hash: str):
    with ZipFile(bkp_file_name + '.zip', mode='x') as zipfile:
        zipfile.write(bkp_file_name, hash,
                      compress_type=ZIP_DEFLATED)


def migrate_1_to_zip(backup_main_dir):
    versions = get_all_versions(backup_main_dir)

    hashes2filename = {}
    for version in versions:
        hashes2filename.update(as_hash2filename(backup_main_dir, version))

    for hash, filename in hashes2filename.items():
        bkp_filename = bkp.backuped_filename(backup_main_dir, hash, False)
        extension = pathlib.Path(filename).suffix
        filter_by_extension = (
            extension is None or
            extension.lower() not in bkp.ZIP_SKIP_EXTENSIONS
        )
        if (os.path.exists(bkp_filename) and
            os.path.getsize(bkp_filename) > bkp.ZIP_MIN_FILESIZE_IN_BYTES and
                filter_by_extension):
            print(f'Gonna zip {filename}')
            zip_hashed(bkp_filename, hash)
            os.remove(bkp_filename)


def migrate_2_flatdir_to_subdirs(backup_main_dir):
    files = os.listdir(os.path.join(backup_main_dir, 'data'))
    for file in files:
        current_filename = os.path.join(backup_main_dir, 'data', file)
        if os.path.isfile(current_filename):
            dirname = bkp.backuped_dirname(backup_main_dir, file)
            new_filename = os.path.join(dirname, file)
            bkp.create_dir_if_not_exists(dirname)
            os.rename(current_filename, new_filename)
