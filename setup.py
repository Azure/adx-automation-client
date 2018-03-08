#!/usr/bin/env python3

import os
import sys
import datetime
from setuptools import setup

ROOT_INIT = os.path.join(os.path.dirname(__file__), 'src', 'a01', '__init__.py')
VERSION = os.environ.get('TRAVIS_TAG')

try:
    if VERSION:
        with open(ROOT_INIT, 'w') as file_handler:
            file_handler.write(f"__version__ = '{VERSION}'\n")
    else:
        with open(ROOT_INIT, 'r') as file_handler:
            line = file_handler.readline()
            VERSION = line.split('=')[1].strip()
except (ValueError, IOError):
    print('Fail to pass version string.', file=sys.stderr, flush=True)
    sys.exit(1)

with open('HISTORY.rst', 'r', encoding='utf-8') as f:
    HISTORY = f.read()

CLASSIFIERS = [
    'Development Status :: 4 - Beta',
    'Intended Audience :: Developers',
    'Intended Audience :: System Administrators',
    'Programming Language :: Python',
    'Programming Language :: Python :: 3.6',
    'License :: OSI Approved :: MIT License',
]

DEPENDENCIES = [
    'tabulate>=0.8.2',
    'requests>=2.18.4',
    'PyYAML>=3.12',
    'coloredlogs>=8.0',
    'colorama>=0.3.9',
    'adal>=0.5.0',
    'docker~=3.0.0',
    'kubernetes~=4.0.0'
]

setup(
    name='adx-automation-cli',
    version=VERSION,
    description='ADX Automation CLI',
    long_description=HISTORY,
    license='MIT',
    author='Microsoft Corporation',
    author_email='trdai@microsoft.com',
    url='https://github.com/Azure/adx-automation-client',
    packages=[
        'a01',
        'a01.models',
        'a01.output',
        'a01.docker',
    ],
    package_dir={
        '': 'src'
    },
    entry_points={
        'console_scripts': [
            'a01=a01.__main__:main'
        ]
    },
    install_requires=DEPENDENCIES
)
