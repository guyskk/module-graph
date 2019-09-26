import argparse

from .render import render_graph


def cli():
    parser = argparse.ArgumentParser(description='Module Graph Render')
    parser.add_argument(
        '--modules-filepath', dest='modules_filepath', type=str,
        help='modules to render, default all modules')
    parser.add_argument(
        '--input-filepath', dest='input_filepath', type=str,
        default='data/module_graph.json',
        help='the module graph data generated by hooker')
    parser.add_argument(
        '--output-filepath', dest='output_filepath', type=str,
        default='data/module_graph.pdf',
        help='render output PDF filepath')
    parser.add_argument(
        '--threshold', dest='threshold', type=int, default=1,
        help='donot show module which memory usage < threshold (MB)')
    args = parser.parse_args()
    render_graph(
        input_filepath=args.input_filepath,
        output_filepath=args.output_filepath,
        modules_filepath=args.modules_filepath,
        threshold=args.threshold,
    )


if __name__ == "__main__":
    cli()
