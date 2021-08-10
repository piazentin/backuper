#!/usr/bin/env python3
import hashlib
import os
import sys
import shutil
import csv


def process_dirs(f, source, root, dirs):
    base_path = root[len(source):]
    for dir in dirs:
        dir_name = os.path.join(base_path, dir)
        f.write(f'"d","{dir_name}",""\n')


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


def process_files(f, source, destination, root, files):
    base_path = root[len(source):]
    for file in files:
        file_name = os.path.join(base_path, file)
        original_path = os.path.join(source, file_name)
        hash = sha1_hash(original_path)
        destination_path = os.path.join(destination, 'data', hash)
        if not os.path.isfile(destination_path):
            shutil.copyfile(original_path, destination_path)
        f.write(f'"f","{file_name}","{hash}"\n')


def new_backup(source, destination):
    if not os.path.exists(source):
        raise ValueError(f'source path {source} does not exists')
    if os.path.exists(destination):
        raise ValueError(f'destination path {destination} already exists')

    print(f'Creating new backup from {source} into {destination}')

    os.mkdir(destination)
    os.mkdir(os.path.join(destination, 'data'))
    backup_control_file = os.path.join(destination, '0000-00-00T000000.csv')

    with open(backup_control_file, 'x') as f:
        for root, dirs, files in os.walk(source, topdown=True):
            print(f'root={root}, dirs={dirs}\n')
            process_dirs(f, source, root, dirs)
            process_files(f, source, destination, root, files)


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


def parse_args(args):
    if len(args) != 4:
        raise ValueError('Invalid backup arguments\nExpected format:\n'
                         '  new <source-path> <destination-path>')

    _, command, source, destination = args
    return {
        'command': command,
        'source': source,
        'destination': destination
    }


def main(args):
    args = parse_args(args)

    if args['command'] == 'new':
        new_backup(args['source'], args['destination'])
    elif args['command'] == 'check':
        check_backup(args['destination'])
    else:
        raise ValueError(f'command {args["command"]} is invalid')


if __name__ == "__main__":
    main(sys.argv)
