import hashlib
import os
import shutil
import csv

import backuper.commands as commands


def _to_relative_path(root: str, path: str) -> str:
    return path[len(root):]


def _process_dirs(control_file, relative_path, dirs):
    for dir in dirs:
        dir_name = os.path.join(relative_path, dir)
        control_file.write(f'"d","{dir_name}",""\n')


def sha1_hash(file_name):
    BUF_SIZE = 65536  # 64kb
    sha1 = hashlib.sha1()
    with open(file_name, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            sha1.update(data)
    return sha1.hexdigest()


def _process_files(control_file, full_path, relative_path, destination_dirname, filenames):
    for filename in filenames:
        relative_filename = os.path.join(relative_path, filename)
        full_filename = os.path.join(full_path, filename)

        hash = sha1_hash(full_filename)
        destination_filename = os.path.join(destination_dirname, 'data', hash)
        if not os.path.isfile(destination_filename):
            shutil.copyfile(full_filename, destination_filename)
        control_file.write(f'"f","{relative_filename}","{hash}"\n')


def new(command: commands.NewCommand):
    if not os.path.exists(command.source):
        raise ValueError(f'source path {command.source} does not exists')
    if os.path.exists(command.destination):
        raise ValueError(
            f'destination path {command.destination} already exists')

    print(
        f'Creating new backup from {command.source} into {command.destination}')

    os.makedirs(command.destination)
    os.mkdir(os.path.join(command.destination, 'data'))
    backup_control_file = os.path.join(
        command.destination, command.name + '.csv')

    with open(backup_control_file, 'x') as control_file:
        for dirpath, dirnames, filenames in os.walk(command.source, topdown=True):
            relative_path = _to_relative_path(command.source, dirpath)
            print(f'Processing "{relative_path}"...')
            _process_dirs(control_file, relative_path, dirnames)
            _process_files(control_file, dirpath, relative_path,
                           command.destination, filenames)


def update(command: commands.UpdateCommand):
    pass


def check_backup(destination):
    with open(os.path.join(destination, '0000-00-00T000000.csv'), 'r') as csvfile:
        data = csv.reader(csvfile, delimiter=',', quotechar='"')
        failed = False
        for row in data:
            if row[0] == 'f':
                backuped_file = os.path.join(destination, 'data', row[2])
                if not os.path.exists(backuped_file):
                    failed = True
                    print(f'ERROR: hash {row[2]} does not exists')
        if failed:
            print('Backup check detected errors')
        else:
            print('Backup check completed without errors')
