# Backuper

Very simple backup utility

## Usage

Create a new backup:

```
python3 -m backuper new ~/backup/source/dir ~/backup/destination/dir
```

Update existing backup:

```
python3 -m backuper update ~/backup/source/dir ~/backup/destination/dir
```

Check backup integrity:

```
python3 -m backuper check ~/backup/destination/dir
```


## Run tests

```
python3 -m unittest
```
