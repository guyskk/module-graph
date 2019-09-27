from .hooker import setup_hooker


if __name__ == "__main__":
    memory_hooker = setup_hooker(save_to='data/module_graph.json', verbose=True)


import argparse  # noqa:E402
from .traveler import ModuleTraveler  # noqa:E402


IGNORE = """
*test*
encodings.cp65001
ctypes.wintypes
"""


def cli():
    parser = argparse.ArgumentParser(description='Module Graph Traveler')
    parser.add_argument(
        '--modules', dest='modules', type=str,
        help='top level modules to check, default all modules')
    parser.add_argument(
        '--ignore', dest='ignore', type=str,
        help='ignore modules (shell patterns)')
    args = parser.parse_args()
    modules = args.modules if args.modules else None
    ignore = (args.ignore or '') + IGNORE
    traveler = ModuleTraveler(modules=modules, ignore=ignore)
    traveler.run()


if __name__ == "__main__":
    cli()
