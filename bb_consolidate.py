from json import load, dump

def walk_and_filter(tree, drive_id):
    # Shallow copy tree
    new_tree = dict(tree)
    new_tree['files'] = {}
    new_tree['folders'] = {}
    for name, data in tree['files'].items():
        if data['drive'] == drive_id:
            new_tree['files'][name] = data

    for name, data in tree['folders'].items():
        new_data = walk_and_filter(data, drive_id)
        if new_data['files'] or new_data['folders']:
            new_tree['folders'][name] = new_data

    return new_tree

def main():

    with open('backupbuffet.json') as bb_file:
        tree = load(bb_file)

    new_tree = walk_and_filter(tree, 1)

    with open('backupbuffet_1.json', 'w') as bb_file:
        dump(new_tree, bb_file)

if __name__ == '__main__':
    main()
