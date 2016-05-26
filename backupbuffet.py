import os
from sys import argv
from json import load
from shutil import copytree, disk_usage
j = os.path.join

# Logging file
logFile = "backupbuffet.log"

# Source & Destination directories
SRC = argv[1]
DEST = argv[2]

class tree(object):
    def __init__(self, files, folders):
        self.files = sorted(files)
        self.folders = sorted(folders)

        # Files are 2-pair tuples, folders are trees
        self.size = sum([f[1] for f in files] + [x.size for x in folders.items()])

# Source directory tree
# Provides size at each sub dir
def build_fs_tree(path):

    # Absolute(-ish) path
    abs_path = j(SRC, path)

    # Listdir returns relative file names
    contents = os.listdir(abs_path)
    dirs = [x for x in contents if os.path.isdir(j(abs_path, x))]
    files = [(f, os.path.getsize(j(abs_path, f))) for f in list(set(contents) - set(dirs))]
    folders = {d: build_fs_tree(j(path, d)) for d in dirs}
    return tree(files, folders)

# TODO: Check space usage
def get_files(src_tree, backup_tree):

    # If none of the folder is backed up, add the whole thing
    if not backup_tree:
        return (src_tree, src_tree)

    # Grab all the files that have to be backed up
    dest_files = [f for f in src_tree.files if f not in backup_tree.files]
    backup_tree.files += dest_files

    # Check the subdirectories that can be backed up
    dest_folders = {}
    for folder, subtree in src_tree.folders.items():
        backup_subtree = backup_tree.setdefault(folder, False)
        dest_folders[folder], backup_tree[folder] = get_files(subtree, backup_subtree)

    # If the source and destination files and folders are the same, just return the source tree
    if dest_files == src_tree.files and dest_folders == src_tree.folders:
        return (src_tree, src_tree)

    return (tree(dest_files, dest_folders), backup_tree)

def main():

    # Build a directory tree
    src_tree = build_fs_tree(".")

    # Load the backup tree
    backup_tree = []
    with open(logFile, "r") as handle: backup_tree = load(handle)

    # Get a list of files to back up, in a tree
    dest_tree, backup_tree = get_files(src_tree, backup_tree)

main()
