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
max_leftover_space = 100000

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

# Little info function to make life easier
def info(message):
    message += '\n'
    with open(logFile, 'a', 0) as log:
        log.write(message)
    print(message)

# Source directory heap
# Provides size at each sub dir
def build_fs_heap(path):

    # Listdir returns relative file names
    contents = os.listdir(path)
    dirs = [x for x in contents if os.path.isdir(x)]
    files = list(set(contents) - set(dirs))
    size = sum([os.path.getsize(j(path, f)) for f in files])
    heap = {d: build_fs_heap(j(path, d)) for d in dirs}
    size += sum([x[0] for x in heap.items()])
    return {os.path.basename(path): {"size": size, "heap": heap}}

# Checks if a path has been backed up
def is_backed_up(path):

    # Check if the path is covered in another drive
    # and that this path isn't the child of one already backed up
    for drive_dirs in backup_log:
        for path_backed in drive_dirs:
            if path_backed in path:
                return True
    return False

# Checks if a path's children have been backed up
# Returns the shallowest path containing no backed-up files
# Returns path and it's size if it is the shallowest path
def get_backup_dirs(path, data):
    used_space = 0
    dirs = []
    heap = data[1]

    # This must be done, because dirs could be the same len as heap.keys()
    # but not contain all the elements of it
    for folder, data in heap.items():
        if not is_backed_up(j(path, folder)):
            new_dirs, new_used_space = get_backup_dirs(j(path, folder), data)
            used_space += new_used_space
            dirs += new_dirs

    # Check if every child directory was used
    # If so, use the root
    if [j(path, folder) for folder in heap.keys()] == dirs:
        dirs = [path]
        used_space = data[0]
    return (dirs, used_space)

# Gets a list of directories to back up
def fill_path(path, heap, free_space, dirs_list):
    possible_dirs = [(folder, data[0], data[1]) for folder, data in heap.items() if data[0] < free_space]

    # If there are some root dirs that can be used go ahead
    while free_space > 0 and len(possible_dirs):
        for dir_data in possible_dirs:
            new_dirs, used_space = get_backup_dirs(j(path, dir_data[0]), (dir_data[1], dir_data[2]))
            dirs_list += new_dirs
            free_space -= used_space


def main():
    dirs = []
    fill_path(os.path.dirname(argv[1]), build_fs_heap(argv[1]), disk_usage(argv[2]).free, dirs)
    for path in dirs:
        copytree(j(argv[1], path), j(argv[2], path))

main()
