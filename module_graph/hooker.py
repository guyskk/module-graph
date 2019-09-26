import sys
import resource


def _get_memory_maxrss():
    """Memory usage (kilobytes on Linux, bytes on OS X)"""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


def _get_memory_unit():
    # call this after process start
    base = _get_memory_maxrss()
    if base < 500 * 1024:
        unit = 1024
    else:
        unit = 1
    return unit


MEMORY_UNIT = _get_memory_unit()


def get_memory_maxrss() -> int:
    """Memory usage, bytes"""
    return _get_memory_maxrss() * MEMORY_UNIT


def mb(v):
    return round(v / 1024 / 1024)


class ModuleMemoryRecord:
    def __init__(
        self,
        module,
        parent=None,
        children=None,
        memory_begin=0,
        memory_end=0,
        memory_inner=0,
    ):
        self.module = module
        self.parent = parent
        self.children = set(children or [])
        self.memory_begin = memory_begin
        self.memory_end = memory_end
        self.memory_inner = memory_inner

    def __repr__(self):
        type_name = type(self).__name__
        real_usage = mb(self.real_usage)
        usage = mb(self.usage)
        return (f'<{type_name} {self.module} {real_usage}M/{usage}M '
                f'parent={self.parent} children={self.children}>')

    @property
    def usage(self):
        return max(0, self.memory_end - self.memory_begin)

    @property
    def real_usage(self):
        return max(0, self.usage - self.memory_inner)

    def to_dict(self):
        return dict(
            module=self.module,
            parent=self.parent,
            children=list(sorted(self.children)),
            usage=self.usage,
            real_usage=self.real_usage,
        )


class MemoryHooker:
    def __init__(self, handler=None):
        self.records = []
        self.handler = handler

    def _add_child(self, module):
        if self.records:
            parent = self.records[-1]
            if module != parent.module:
                parent.children.add(module)
                if self.handler:
                    self.handler.on_child(parent, module)

    def _begin_module(self, module):
        memory_begin = get_memory_maxrss()
        self.records.append(ModuleMemoryRecord(
            module=module,
            memory_begin=memory_begin,
        ))

    def _end_module(self, module):
        record = self.records.pop()
        if record.module != module:
            msg = f'unexpected module {record.module}, expect {module}'
            raise ValueError(msg)
        record.memory_end = get_memory_maxrss()
        if self.records:
            parent = self.records[-1]
            parent.memory_inner += record.usage
            record.parent = parent.module
        if self.handler:
            self.handler.on_import(record)


def is_magic_wrapped(obj):
    return getattr(obj, '_magic_wrapped', False)


def wrap_loader(loader, hooker):

    base_class = loader if isinstance(loader, type) else type(loader)

    class ModuleLoaderWrapper(base_class):

        _magic_wrapped = True

        def __init__(self): pass

        def __getattr__(self, *args, **kwargs):
            return getattr(loader, *args, **kwargs)

        def __repr__(self):
            return f'<{type(self).__name__} {loader}>'

        if hasattr(loader, 'create_module'):
            def create_module(self, spec):
                try:
                    return loader.create_module(spec)
                except Exception as ex:
                    msg = f'create module {spec.name} failed'
                    raise ImportError(msg) from ex

        if hasattr(loader, 'exec_module'):
            def exec_module(self, module):
                module_name = module.__name__
                hooker._begin_module(module_name)
                try:
                    return loader.exec_module(module)
                finally:
                    hooker._end_module(module_name)

        if hasattr(loader, 'load_module'):
            def load_module(self, fullname):
                hooker._begin_module(fullname)
                try:
                    return loader.load_module(fullname)
                finally:
                    hooker._end_module(fullname)

    return ModuleLoaderWrapper()


def wrap_finder(finder, hooker):

    base_class = finder if isinstance(finder, type) else type(finder)

    class ModuleFinderWrapper(base_class):

        _magic_wrapped = True

        def __init__(self): pass

        def __getattr__(self, *args, **kwargs):
            return getattr(finder, *args, **kwargs)

        def __repr__(self):
            return f'<{type(self).__name__} {finder}>'

        def __wrap_loader(self, loader):
            if is_magic_wrapped(loader):
                return loader
            return wrap_loader(loader, hooker)

        def find_module(self, fullname, path=None):
            loader = finder.find_module(fullname, path)
            if loader:
                loader = self.__wrap_loader(loader)
            return loader

        if hasattr(finder, 'find_spec'):
            def find_spec(self, fullname, path, target=None):
                spec = finder.find_spec(fullname, path=path, target=target)
                if spec and spec.loader:
                    spec.loader = self.__wrap_loader(spec.loader)
                return spec

        if hasattr(finder, 'find_loader'):
            def find_loader(self, fullname):
                loader, portion = finder.find_loader(fullname)
                if loader:
                    loader = self.__wrap_loader(loader)
                return loader, portion

    return ModuleFinderWrapper()


class MetaPathList(list):
    def __init__(self, hooker):
        self.__hooker = hooker
        super().__init__()

    def __wrap_finder(self, finder):
        if is_magic_wrapped(finder):
            return finder
        return wrap_finder(finder, self.__hooker)

    def insert(self, index, finder):
        return super().insert(index, self.__wrap_finder(finder))

    def append(self, finder):
        return super().append(self.__wrap_finder(finder))

    def __setitem__(self, key, finder):
        return super().__setitem__(self.__wrap_finder(finder))

    def extend(self, iterable):
        return super().extend(map(self.__wrap_finder, iterable))


def wrap_sys_modules(hooker):

    sys_modules = sys.modules

    def proxy_to(name):
        def proxy_method(self, *args, **kwargs):
            return getattr(sys_modules, name)(*args, **kwargs)
        return proxy_method

    methods = """
        __contains__
        __delitem__
        __eq__
        __ge__
        __gt__
        __iter__
        __le__
        __len__
        __lt__
        __ne__
        __repr__
        __setitem__
        __sizeof__
        clear
        copy
        fromkeys
        items
        keys
        pop
        popitem
        setdefault
        update
        values
    """.strip().split()

    class SysModulesDict(dict):

        __hash__ = None

        def __init__(self): pass

        def __getitem__(self, key):
            value = sys_modules.__getitem__(key)
            hooker._add_child(key)
            return value

        def get(self, key, *args, **kwargs):
            value = sys_modules.get(key, *args, **kwargs)
            if value is not None:
                hooker._add_child(key)
            return value

    for method in methods:
        setattr(SysModulesDict, method, proxy_to(method))

    return SysModulesDict()


class ModuleMomoryHandler:
    def __init__(self, save_to=None, verbose=False):
        self.save_to = save_to
        self.verbose = verbose
        self.records = []

    def on_child(self, parent_record, module):
        if self.verbose:
            parent = parent_record.module
            print(f'* {parent} --> {module}')

    def on_import(self, record: ModuleMemoryRecord):
        self.records.append(record)
        if self.verbose:
            module = record.module + " "
            memory_end_mb = " " + str(mb(record.memory_end))
            real_usage_mb = "+" + str(mb(record.real_usage))
            print(f'* {module:-<60s}-{memory_end_mb:->5s}M {real_usage_mb:>6s}M')

    def get_sorted_records(self):
        def key_func(x):
            return max(x.real_usage, x.usage)
        records = sorted(self.records, key=key_func, reverse=True)
        return list(records)

    def save(self):
        if not self.save_to:
            return
        import json
        import os.path
        records = [x.to_dict() for x in self.get_sorted_records()]
        content = json.dumps(records, indent=4, ensure_ascii=False)
        if self.save_to == '-':
            print(content)
        else:
            save_to = os.path.abspath(os.path.expanduser(self.save_to))
            print(f'* save module graph to {save_to}')
            os.makedirs(os.path.dirname(save_to), exist_ok=True)
            with open(save_to, 'w') as f:
                f.write(content)


def setup_hooker(save_to=None, verbose=False):
    handler = ModuleMomoryHandler(save_to=save_to, verbose=verbose)
    hooker = MemoryHooker(handler=handler)
    meta_path = MetaPathList(hooker)
    meta_path.extend(sys.meta_path)
    sys.meta_path = meta_path
    sys.modules = wrap_sys_modules(hooker)
    import atexit
    atexit.register(handler.save)
    return hooker


if __name__ == "__main__":
    memory_hooker = setup_hooker(verbose=True)
    import string
    import importlib
    importlib.reload(string)
    import urllib3  # noqa: F401
    from six import *  # noqa: F401,F403
    from asyncio import *  # noqa: F401,F403
