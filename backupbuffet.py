import os
from sys import argv
from json import load, dump, JSONEncoder, JSONDecoder
from shutil import disk_usage
j = os.path.join

# Logging file name
logFile = "backupbuffet_global.json"

# Source & Destination directories
SRC = argv[1]
DEST = argv[2]

# Max free space to leave in bytes
# 1gb
MAX_FREE = 1024 ** 3

class tree(object):
    def __init__(self, files, folders, state=0, size=0):
        self.files = sorted(files)
        self.folders = folders

        # States: 0 = not backed up/incomplete.
        #         1 = to be totally backed up (when dest files & folders equal source)
        #         2 = backed up
        self.state = state

        # Files = [tuple(name, size)]
        # Folders = {name: tree(files, folders, size, state)}
        self.size = size or sum([f[1] for f in files] + [x.size for x in folders.values()])

# Encodes the trees in a JSON encodable way
class treeJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, tree):
            return obj.__dict__
        return JSONEncoder.default(self, obj)

def treeJSONDecoder(obj):
    if "files" in obj and "folders" in obj:
        return tree(obj["files"], obj["folders"], obj["state"], obj["size"])
    return obj

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

def get_files(src_tree, backup_tree, free_space):

    # If none of the folder is backed up, add the whole thing
    if not backup_tree and free_space - src_tree.size > 0:
        src_tree.state = 1
        return (src_tree, src_tree)

    backup_tree = backup_tree or tree([], {})

    # If the entire folder is backed up, add nothing
    if backup_tree.state == 1:
        return (tree([], {}), backup_tree)

    # Grab all the files that have to be backed up
    # And that there is space for
    dest_files = []
    for file in src_tree.files:
        if file not in backup_tree and free_space - file[1] > 0:
            dest_files.append(file)
            free_space -= file[1]
    backup_tree.files += dest_files

    # Check for subdirectories that can be backed up
    dest_folders = {}
    for folder, subtree in sorted(src_tree.folders.items()):
        if free_space < MAX_FREE:
            break
        backup_subtree = backup_tree.setdefault(folder, False)
        dest_folders[folder], backup_tree[folder] = get_files(subtree, backup_subtree, free_space)
        free_space -= dest_folders[folder].size

    # If the source and destination files and folders are the same, just return the source tree
    if dest_files == src_tree.files and dest_folders == src_tree.folders:
        src_tree.state = 1
        return (src_tree, src_tree)

    return (tree(dest_files, dest_folders), backup_tree)

# Reads file and folder count from a tree
def get_stats(dest_tree):
    files, folders = 0, 0
    for folder in dest_tree.folders.values():
        sub_files, sub_folders = get_stats(folder)
        files += sub_files
        folders += sub_folders

    return (len(dest_tree.files) + files, len(dest_tree.folders) + folders)

def main():

    # Build a directory tree
    print("Building source directory tree")
    src_tree = build_fs_tree(".")

    # Load the backup tree
    backup_tree = []
    if os.path.exists(j(SRC, logFile)):
        print("Reading backup log")
        with open(j(SRC, logFile), "r") as handle: backup_tree = load(handle, object_hook=treeJSONDecoder)

    # Get a list of files to back up, in a tree
    print("Picking files")
    dest_tree, backup_tree = get_files(src_tree, backup_tree, disk_usage(DEST).free)

    # Display a summary of the data we're backing up
    files, folders = get_stats(dest_tree)
    root_folders = list(dest_tree.folders.keys())

    print("About to backup %d bytes (~%d GB) in %d files and %d folders from %s.\nContinue?" % (
        dest_tree.size,
        dest_tree.size / (1024 ** 3),
        files,
        folders,
        ", ".join(root_folders)
    ))

    choice = input().lower()
    while not choice or choice[0] not in ["y", "n"]:
        print("Yes or no?")
        choice = input().lower()

    if choice == "n":
        print("Cancelling")
        return

    print("Running backup!")

    with open(j(SRC, logFile), "w") as output: dump(backup_tree, output, cls=treeJSONEncoder)
    with open(j(DEST, "backupbuffet.json"), "w") as output: dump(dest_tree, output, cls=treeJSONEncoder)

main()
