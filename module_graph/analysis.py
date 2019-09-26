import json
from graphviz import Digraph


def read_records(filepath):
    with open(filepath) as f:
        records = json.load(f)
    records_map = {}
    for r in records:
        module = r['module']
        if module in records_map:
            old = records_map[module]
            children = set()
            children.update(old['children'])
            children.update(r['children'])
            new = dict(
                module=module,
                parent=old['parent'],
                children=list(sorted(children)),
                usage=old['usage'] + r['usage'],
                real_usage=old['real_usage'] + r['real_usage'],
            )
            records_map[module] = new
        else:
            records_map[module] = r
    for r in records_map.values():
        module = r['module']
        if r['parent']:
            parent = records_map.get(r['parent'])
            if parent and parent['children']:
                try:
                    parent['children'].remove(r['module'])
                except ValueError:
                    pass  # ignore
        children = []
        for child in r['children']:
            if child.startswith(module) or module.startswith(child):
                continue
            children.append(child)
        r['children'] = children
    return list(records_map.values())


def main(filepath='data/graph.json'):
    records = read_records(filepath)
    dot = Digraph(comment='Module Graph', graph_attr={'rankdir': 'LR'})
    for r in records:
        module = r['module']
        usage = r['usage']
        real_usage = r['real_usage']
        parent = r['parent']
        children = r['children']
        dot.node(module, module)
        if parent:
            dot.edge(parent, module)
        for child in children:
            dot.edge(module, child, style='dashed')
    dot.render('data/graph.png')


if __name__ == "__main__":
    main()
