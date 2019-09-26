from .hook import patch_meta_path, MemoryRecord, mb


if __name__ == "__main__":
    memory_hooker = patch_meta_path()


import os  # noqa: E402
import sys  # noqa: E402
import importlib  # noqa: E402
import pkgutil  # noqa: E402
import argparse  # noqa: E402
import fnmatch  # noqa: E402
import warnings  # noqa: E402
import json  # noqa: E402


class MemoryReporter:

    def __init__(self, threshold=0):
        self.threshold = threshold
        self.records = []

    def on_child(self, record: MemoryRecord):
        pass

    def on_import(self, record: MemoryRecord):
        self.records.append(record)
        if record.usage >= self.threshold:
            module = record.module + " "
            memory_end_mb = " " + str(mb(record.memory_end))
            real_usage_mb = "+" + str(mb(record.real_usage))
            print(f'* {module:-<60s}-{memory_end_mb:->5s}M {real_usage_mb:>6s}M')

    def get_sorted_records(self):
        def key_func(x):
            return max(x.real_usage, x.usage)
        records = sorted(self.records, key=key_func, reverse=True)
        return list(records)

    def report(self, top=100):
        for record in self.get_sorted_records()[:top]:
            usage_mb = " " + str(mb(record.usage))
            real_usage_mb = "+" + str(mb(record.real_usage))
            print(f'* {record.module + " ":-<60s}-{usage_mb:->6s}M {real_usage_mb:>6s}M')

    def save(self, fileobj):
        records = [x.to_dict() for x in self.get_sorted_records()]
        json.dump(records, fileobj, indent=4, ensure_ascii=False)


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
*test*
encodings.cp65001
ctypes.wintypes
django.contrib.flatpages.*
django.contrib.redirects.*
django.contrib.gis.*
django.db.*oracle*
django.db.*mysql*
tornado.platform.windows
raven.contrib.django.celery.models
readability.compat.two
nltk.tokenize.nist
nltk.twitter*
nltk.app*
prompt_toolkit.*win*
gunicorn.workers.*gevent*
whitenoise.django*
"""
BLACK_LIST = BLACK_LIST.strip().split()


def get_filter_func(ignore=None):
    ignore_list = list(BLACK_LIST)
    if ignore:
        ignore_list.append(ignore)

    def filter_func(module):
        for p in ignore_list:
            if fnmatch.fnmatch(module, p):
                return False
        return True

    return filter_func


def main(modules, threshold=0, top=100, ignore=None, save_to=None):
    warnings.simplefilter("ignore")
    memory_reporter = MemoryReporter(threshold=threshold)
    memory_hooker.handler = memory_reporter
    filter_func = get_filter_func(ignore=ignore)
    modules = [x for x in modules if filter_func(x)]
    roots = []
    failed_modules = set()
    for module in modules:
        try:
            module_object = importlib.import_module(module)
        except (ModuleNotFoundError, ImportError):
            failed_modules.add(module)
        except Exception as ex:
            failed_modules.add(module)
            print(f'import {module} {type(ex).__name__}: {ex}')
        else:
            roots.append(module_object)
    for root in roots:
        for module in find_all_modules(root):
            if not filter_func(module):
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
                print(f'import {module} {type(ex).__name__}: {ex}')

    print('*' * 79)
    memory_reporter.report(top=top)
    if save_to:
        if save_to == '-':
            print('*' * 79)
            memory_reporter.save(sys.stdout)
        else:
            with open(save_to, 'w') as f:
                memory_reporter.save(f)


def cli():
    parser = argparse.ArgumentParser(description='Who eat memory?')
    parser.add_argument(
        '--modules', dest='modules', type=str, default='all',
        help='top level modules to check, default all modules')
    parser.add_argument(
        '--ignore', dest='ignore', type=str,
        help='ignore modules shell patterns')
    parser.add_argument(
        '--threshold', dest='threshold', type=int, default=1,
        help='only show modules memory usage >= threshold(MB)')
    parser.add_argument(
        '--top', dest='top', type=int, default=100,
        help='show top <TOP> modules')
    parser.add_argument(
        '--save-to', dest='save_to', type=str,
        help='save module memory usage details to file in csv format')
    args = parser.parse_args()
    threshold = args.threshold * 1024 * 1024
    if args.modules and args.modules.lower() != 'all':
        modules = list(args.modules.replace(',', ' ').strip().split())
    else:
        modules = [x[1] for x in pkgutil.iter_modules()]
    main(modules, threshold=threshold, ignore=args.ignore, top=args.top, save_to=args.save_to)


if __name__ == "__main__":
    cli()
