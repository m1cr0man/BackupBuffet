import os
from sys import argv
from json import load, dump, JSONEncoder
from shutil import disk_usage, copy2, copytree, rmtree
j = os.path.join

# Logging file name
LOGFILE = "backupbuffet.json"

# Source & Destination directories
SRC = os.path.abspath(argv[1])
DEST = os.path.abspath(argv[2])

# Max free space to leave in bytes
# 1gb
MAX_FREE = 1024 ** 3

# Drive ID
DRIVE = 0

# Simulation mode stuff
if "--sim" in argv:
    voider = lambda x: True
    voider_2arg = lambda x, y: True
    os.remove = voider
    copy2 = voider_2arg
    rmtree = voider
    copytree = voider_2arg

class File(object):
    def __init__(self, size, mtime, action=0, drive=-1):
        self.size = size
        self.mtime = mtime
        self.action = action
        self.drive = drive

class Tree(object):
    def __init__(self, files, folders, size=0, action=0):
        self.files = files
        self.folders = folders

        if size:
            self.size = size
        else:
            self.calc_size()

        # Folders
        # Actions: 0 = None
        #          1 = Recusively back up (when dest files & folders equal source)
        #          2 = Delete
        # Note: Action 0 still means the folder should be iterated for sub changes
        self.action = action

        # Files
        # Actions: 0 = None
        #          1 = Back up
        #          2 = Delete
        #          3 = Modify

        # Files = {name: File(size, mtime, action, drive)}
        # Folders = {name: Tree(files, folders, size, action)}

    def calc_size(self):
        self.size = sum([f.size for f in self.files.values()] + [f.size for f in self.folders.values()])

# Encodes the trees and files in a JSON encodable way
class customJSONEncoder(JSONEncoder):
    def default(self, obj):
        return obj.__dict__ if isinstance(obj, Tree) or isinstance(obj, File) else JSONEncoder.default(self, obj)

# Decodes trees and files from JSON objects (dictionaries)
def customJSONDecoder(obj):
    if "files" in obj and "folders" in obj:
        return Tree(obj["files"], obj["folders"], obj["size"], obj["action"])
    if "mtime" in obj and "drive" in obj:
        return File(obj["size"], obj["mtime"], obj["action"], obj["drive"])
    return obj

# Source directory tree builder
# Gets the size and mtime in one run
def build_fs_tree(path):

    # Absolute(-ish) path
    abs_path = j(SRC, path)

    # Listdir returns relative file names
    contents = os.listdir(abs_path)
    dirs = [d for d in contents if os.path.isdir(j(abs_path, d))]
    files = {f: File(os.path.getsize(j(abs_path, f)), os.path.getmtime(j(abs_path, f))) for f in list(set(contents) - set(dirs))}
    folders = {d: build_fs_tree(j(path, d)) for d in dirs}
    return Tree(files, folders)

# Sets backup dir of sub files to this drive
def recurse_action(tree, set_drive=True, action=1):
    for file in tree.files.values():
        file.action = action
        file.drive = DRIVE if set_drive else file.drive
    for folder in tree.folders.values():
        recurse_action(folder, set_drive, action)

# Get a list of files to back up (Add/Modify/Delete)
def get_files(main_tree, backup_tree, free_space):

    # If none of the folder is backed up, back up the whole thing
    if (not backup_tree.size) and free_space - main_tree.size > 0:
        main_tree.action = 1

        # Assign drive letter to all sub files
        recurse_action(main_tree)
        return (main_tree.size, main_tree)

    orig_free_space = free_space

    # Deletions
    for fname in backup_tree.files.keys():
        file = backup_tree.files[fname]
        if fname not in main_tree.files and file.drive == DRIVE:
            file.action = 2
            free_space += file.size

    # There's no way to tell if the folder is on this drive or not
    # So we check on the fs before we delete in perform_fs_tasks
    for fname in backup_tree.folders.keys():
        folder = backup_tree.folders[fname]
        if fname not in main_tree.folders:
            folder.action = 2
            recurse_action(folder, False, 2)
            free_space += folder.size

    # Files
    for fname in sorted(main_tree.files.keys()):
        if fname == LOGFILE or "backupbuffet.nextid" in fname:
            continue

        file = main_tree.files[fname]

        # Addition
        # It's either not in the backup or the drive ID is -1
        if fname not in backup_tree.files or backup_tree.files[fname].drive == -1:
            if free_space - file.size > 0:
                file.action = 1
                file.drive = DRIVE
                backup_tree.files[fname] = file
                free_space -= file.size

        # Modification
        elif file.mtime != backup_tree.files[fname].mtime and backup_tree.files[fname].drive == DRIVE:
            file.action = 3
            file.drive = DRIVE
            backup_tree.files[fname] = file
            free_space -= file.size - backup_tree.files[fname].size

    # Folders
    for fname in sorted(main_tree.folders.keys()):
        folder = main_tree.folders[fname]

        # Stop if there's no more free space
        if free_space < MAX_FREE:
            break

        # Addition
        backup_subtree = backup_tree.folders.setdefault(fname, Tree({}, {}))
        size_diff, backup_subtree = get_files(folder, backup_subtree, free_space)

        # Recalculate size of backup subtree
        backup_subtree.calc_size()
        if size_diff:
            backup_tree.folders[fname] = backup_subtree
            free_space -= size_diff

    # Recalculate size of backup tree
    backup_tree.calc_size()

    return (orig_free_space - free_space, backup_tree)

def perform_fs_tasks(backup_tree, src_path=SRC, dest_path=DEST):
    empty_folder = False
    if not os.path.exists(dest_path):
        print("Create folder " + dest_path)
        os.mkdir(dest_path)
        empty_folder = True

    # Files
    for fname in sorted(backup_tree.files.keys()):
        file = backup_tree.files[fname]
        if file.action >= 2:
            print("Delete " + j(dest_path, fname))
            os.remove(j(dest_path, fname))
        if (file.action == 1 and file.drive == DRIVE) or file.action == 3:
            print("Copy %s -> %s" % (j(src_path, fname), j(dest_path, fname)))
            copy2(j(src_path, fname), j(dest_path, fname))
            empty_folder = False
        if file.action == 2:
            del backup_tree.files[fname]
        else:
            file.action = 0

    # Folders
    for fname in sorted(backup_tree.folders.keys()):
        folder = backup_tree.folders[fname]
        if folder.action == 2:
            if os.path.exists(j(dest_path, fname)):
                print("Delete " + j(dest_path, fname))
                rmtree(j(dest_path, fname))
                del backup_tree.folders[fname]
        elif folder.action == 1:
            print("Copy %s -> %s" % (j(src_path, fname), j(dest_path, fname)))
            copytree(j(src_path, fname), j(dest_path, fname))
            folder.action = 0
            recurse_action(folder, False, 0)
            empty_folder = False
        else:
            perform_fs_tasks(folder, j(src_path, fname), j(dest_path, fname))

    if empty_folder:
        print("Delete folder " + dest_path)
        os.rmdir(dest_path)

def get_summary(backup_tree):
    add, mod, rm = 0, 0, 0

    for fname in sorted(backup_tree.files.keys()):
        file = backup_tree.files[fname]
        if file.action != 0 and file.drive == DRIVE:
            add += file.action == 1
            mod += file.action == 3
            rm += file.action == 2

    for fname in sorted(backup_tree.folders.keys()):
        folder = backup_tree.folders[fname]
        add_branch, mod_branch, rm_branch = get_summary(folder)
        add += add_branch
        mod += mod_branch
        rm += rm_branch

    return (add, mod, rm)

def main():
    global DRIVE

    # Build a directory tree for the source
    print("Building source directory tree")
    src_tree = build_fs_tree(".")

    # Get free space
    # We have to figure out what the root directory is though
    # Weird list comp is to avoid empty strings/paths
    free_space = disk_usage(os.sep + [d for d in DEST.split(os.sep) if d][0]).free

    # Use the destination if it exists (Because linux root path might not be on the destination drive)
    if os.path.exists(DEST):
        free_space = disk_usage(DEST).free

    # Load the backup tree
    backup_tree = Tree({}, {})
    if os.path.exists(j(SRC, LOGFILE)):
        print("Reading backup log")
        # TODO sync the logs
        with open(j(SRC, LOGFILE), "r") as handle: backup_tree = load(handle, object_hook=customJSONDecoder)

    # Load drive IDs
    next_id = 0
    print("Loading Drive ID")
    if os.path.exists(j(SRC, "backupbuffet.nextid")):
        with open(j(SRC, "backupbuffet.nextid"), "r") as saved_id:
            next_id = int(saved_id.read())
    if os.path.exists(j(DEST, "backupbuffet.id")):
        with open(j(DEST, "backupbuffet.id"), "r") as saved_id:
            DRIVE = int(saved_id.read())
    else:
        DRIVE = next_id
        next_id += 1
    print("Drive ID is %d" % DRIVE)

    # Get a list of files to back up, in a tree
    print("Getting list of files to Add/Delete/Modify")
    size_diff, backup_tree = get_files(src_tree, backup_tree, free_space)
    add, mod, rm = get_summary(backup_tree)

    print("About to backup %d bytes (~%.1f GB)" % (
        size_diff,
        size_diff / (1024 ** 3)
    ))
    print("Added: %d\nModified: %d\nDeleted: %d" % (add, mod, rm))
    print("Continue [y/n]?")

    choice = input().lower()
    while not choice or choice[0] not in ["y", "n"]:
        print("Yes or no?")
        choice = input().lower()

    if choice != "y":
        print("Cancelling")
        return

    print("Running backup!")

    if not os.path.exists(DEST):
        os.makedirs(DEST)

    # Save before and after incase it crashes
    with open(j(SRC, LOGFILE), "w") as output: dump(backup_tree, output, cls=customJSONEncoder)
    with open(j(DEST, LOGFILE), "w") as output: dump(backup_tree, output, cls=customJSONEncoder)
    perform_fs_tasks(backup_tree)
    with open(j(DEST, "backupbuffet.id"), "w") as saved_id: saved_id.write(str(DRIVE))
    with open(j(SRC, "backupbuffet.nextid"), "w") as saved_id: saved_id.write(str(next_id))
    with open(j(SRC, LOGFILE), "w") as output: dump(backup_tree, output, cls=customJSONEncoder)
    with open(j(DEST, LOGFILE), "w") as output: dump(backup_tree, output, cls=customJSONEncoder)

main()
