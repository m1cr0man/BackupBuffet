import os
from sys import argv
from time import time
from json import load, dump
from shutil import copytree, disk_usage
j = os.path.join

# Logging file
logFile = "backupbuffet.log"

# First drive ID index
driveID = 0

# Max free space to leave on the drive in bytes
max_remainder = 100000

# Work out the deadline
deadline = round(time() + float(argv[2]) * 3600)

# Backed up files, format:
# ]
#  [
#   path,
#   path,
#   path
#  ],
#  [
#   path,
#   path,
#   path
#  ]
# ]
# Root list is indexed by drive ID
backup_log = []
with open("backuplist.json", "r") as backup_log_save:
    backup_log = load(backup_log_save)

# Source directory heap
# Provides size at each sub dir
def build_fs_heap(path):

    # Listdir returns relative paths
    contents = os.listdir(path)
    dirs = [x for x in contents if os.path.isdir(x)]
    files = list(set(contents) - set(dirs))
    size = sum([os.path.getsize(j(path, f)) for f in files])
    heap = {d: build_fs_heap(j(path, d)) for d in dirs}
    size += sum([x[0] for x in heap.items()])
    return {os.path.basename(path): (size, heap)}

# Little info function to make life easier
def info(message):
    message += '\n'
    with open(logFile, 'a', 0) as log:
        log.write(message)
    print(message)

# TODO Get a list of directories to back up
def fill_path(heap, free_space, list):

    pass

def main():
    dirs = []
    fill_path(build_fs_heap(argv[1]), disk_usage(argv[2]).free, dirs)
    for path in dirs:
        copytree(j(argv[1], path), j(argv[2], path))

main()
