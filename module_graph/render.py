import re
import json
import os.path
from graphviz import Digraph

from .hooker import mb


class ModuleMemoryRecord:

    __slots__ = ('module', 'parent', 'children', 'usage', 'real_usage')

    def __init__(
        self,
        module,
        parent=None,
        children=None,
        usage=0,
        real_usage=0,
    ):
        self.module = module
        self.parent = parent
        self.children = children or []
        self.usage = usage
        self.real_usage = real_usage

    def __repr__(self):
        type_name = type(self).__name__
        real_usage = mb(self.real_usage)
        usage = mb(self.usage)
        children = [x.module for x in self.children]
        return (f'<{type_name} {self.module} {real_usage}M/{usage}M '
                f'parent={self.parent.module} children={children}>')


class RecordsProcessor:
    def __init__(self, records, threshold=None, modules=None):
        self.threshold = threshold
        if modules:
            records = self.filter_by_modules(records, modules)
        self.records_map = self.dedup_records(records)
        self.remove_duplicate_dependency()
        self.records_objects = self.build_graph()
        self.fix_real_usage()
        if threshold and threshold > 0:
            self.records = self.remove_small_record_objects()
        else:
            self.records = self.records_objects

    def filter_by_modules(self, records, modules):
        modules = set(modules)
        ret = []
        for r in records:
            if r['module'] not in modules:
                continue
            if r['parent'] and r['parent'] not in modules:
                continue
            children = []
            for child in r['children']:
                if child in modules:
                    children.append(child)
            r['children'] = children
            ret.append(r)
        return ret

    def dedup_records(self, records):
        records_map = {}
        for r in records:
            module = r['module']
            if module in records_map:
                old = records_map[module]
                children = set(old['children']) | set(r['children'])
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
        return records_map

    def remove_duplicate_dependency(self):
        for r in self.records_map.values():
            module = r['module']
            if r['parent']:
                parent = self.records_map.get(r['parent'])
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

    def build_graph(self):
        records_objects = {}
        for r in self.records_map.values():
            robj = ModuleMemoryRecord(
                module=r['module'],
                usage=r['usage'],
                real_usage=r['real_usage'],
            )
            records_objects[r['module']] = robj

        def set_default(module):
            robj = records_objects.get(module)
            if not robj:
                robj = ModuleMemoryRecord(module)
                records_objects[module] = robj
            return robj

        for r in self.records_map.values():
            robj = records_objects[r['module']]
            if r['parent']:
                robj.parent = set_default(r['parent'])
            if r['children']:
                children = []
                for child_module in r['children']:
                    children.append(set_default(child_module))
                robj.children = children
        return list(records_objects.values())

    def fix_real_usage(self):
        for r in self.records_objects:
            if r.usage < r.real_usage:
                r.usage = r.real_usage

    def remove_small_record_objects(self):
        threshold = self.threshold * 1024 * 1024
        records = []
        small_records = set()
        for r in self.records_objects:
            if r.usage < threshold:
                small_records.add(r)
            else:
                records.append(r)
        for r in records:
            r.children = [r for r in r.children if r not in small_records]
        return records

    @classmethod
    def process(cls, records, **kwargs):
        return cls(records, **kwargs).records

    @classmethod
    def read(cls, filepath, **kwargs):
        with open(filepath) as f:
            records = json.load(f)
        return cls.process(records, **kwargs)


MB = 1024 * 1024


def color_of(record):
    usage = record.usage
    if usage < 1 * MB:
        return 'grey'
    real_usage = record.real_usage
    if real_usage >= 100 * MB:
        return 'red'
    elif real_usage >= 10 * MB:
        return 'orange'
    elif real_usage >= 1 * MB:
        return 'blue'
    else:
        return 'black'


def label_of(record):
    usage = record.usage
    if usage < 1 * MB:
        return record.module
    real_usage = mb(record.real_usage)
    return f'{record.module}\n{mb(usage)}/{real_usage}M'


def render_dot(records):
    dot = Digraph(comment='ModuleGraph', graph_attr={'rankdir': 'LR'})
    for r in records:
        node_color = color_of(r)
        dot.node(r.module, label_of(r), color=node_color, fontcolor=node_color)
        if r.parent:
            dot.edge(r.parent.module, r.module, color=node_color)
        for child in r.children:
            dot.edge(r.module, child.module, style='dashed', color=color_of(child))
    return dot


def read_modules(modules_filepath):
    with open(modules_filepath) as f:
        content = f.read()
    modules = list(re.split(r"[\s\,\'\[\]]+", content))
    return [x for x in modules if x]


def normalize_filepath(p):
    return os.path.abspath(os.path.expanduser(p))


def render_graph(
    input_filepath='data/module_graph.json',
    output_filepath='data/module_graph.pdf',
    modules_filepath=None,
    threshold=1,
):
    if modules_filepath:
        modules = read_modules(normalize_filepath(modules_filepath))
    else:
        modules = None
    input_filepath = normalize_filepath(input_filepath)
    records = RecordsProcessor.read(
        input_filepath, threshold=threshold, modules=modules)
    dot = render_dot(records)
    output_filepath = normalize_filepath(output_filepath)
    print(f'* render to {output_filepath}')
    os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
    save_to, __ = os.path.splitext(output_filepath)
    dot.render(filename=save_to, format='pdf')


if __name__ == "__main__":
    render_graph()
