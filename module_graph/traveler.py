import os.path
import logging
import importlib
import warnings
import fnmatch
import pkgutil


LOG = logging.getLogger(__name__)


def find_all_modules(root):
    import_name = root.__name__
    if import_name == '__main__':
        return
    for root_path in set(getattr(root, "__path__", [])):
        root_path = root_path.rstrip("/")
        for root, dirs, files in os.walk(root_path):
            root = root.rstrip("/")
            if "__init__.py" in files:
                module = root[len(root_path):].replace("/", ".")
                if module:
                    yield f"{import_name}{module}"
                else:
                    yield import_name
            for filename in files:
                if filename != "__init__.py" and filename.endswith(".py"):
                    module = os.path.splitext(os.path.join(root, filename))[0]
                    module = module[len(root_path):].replace("/", ".")
                    yield f"{import_name}{module}"


BLACK_LIST = """
this
idlelib
antigravity
lib2to3
tkinter
*__main__*
"""
BLACK_LIST = BLACK_LIST.strip().split()


def get_filter_func(ignore=None):
    ignore_list = list(BLACK_LIST)
    if ignore:
        if isinstance(ignore, str):
            ignore = [x.strip() for x in ignore.strip().splitlines()]
        ignore_list.extend(ignore)

    def filter_func(module):
        for p in ignore_list:
            if fnmatch.fnmatch(module, p):
                return False
        return True

    return filter_func


class ModuleTraveler:
    def __init__(self, modules=None, ignore=None):
        self.filter_func = get_filter_func(ignore=ignore)
        if not modules:
            modules = [x[1] for x in pkgutil.iter_modules()]
        elif isinstance(modules, str):
            modules = list(modules.replace(',', ' ').strip().split())
        else:
            modules = list(modules)
        modules = [x for x in modules if self.filter_func(x)]
        self.modules = modules

    def run(self):
        warnings.simplefilter("ignore")
        roots = []
        failed_modules = set()
        for module in self.modules:
            try:
                module_object = importlib.import_module(module)
            except (ModuleNotFoundError, ImportError):
                failed_modules.add(module)
            except Exception as ex:
                failed_modules.add(module)
                msg = f'import {module} {type(ex).__name__}: {ex}'
                LOG.warning(msg, exc_info=ex)
            else:
                roots.append(module_object)
        for root in roots:
            for module in find_all_modules(root):
                if not self.filter_func(module):
                    continue
                parent = '.'.join(module.split('.')[:-1])
                if parent and parent in failed_modules:
                    continue
                try:
                    importlib.import_module(module)
                except (ModuleNotFoundError, ImportError):
                    failed_modules.add(module)
                except Exception as ex:
                    failed_modules.add(module)
                    msg = f'import {module} {type(ex).__name__}: {ex}'
                    LOG.warning(msg, exc_info=ex)
