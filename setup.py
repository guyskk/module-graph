"""Show python modules dependency graph and static memory usage."""

from setuptools import setup, find_packages
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='module-graph',
    version='0.0.1',
    description=__doc__,
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/guyskk/module_graph',
    author='guyskk',
    author_email='guyskk@qq.com',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    keywords='module dependency graph memory',
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    python_requires='>=3.4, <4',
    install_requires=[],
    extras_require={
        'all': ['graphviz>=0.12'],
    },
    entry_points={
        'console_scripts': [
            'module-graph=module_graph.main:cli',
        ],
    },
)
