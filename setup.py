#!/usr/bin/env python3

import os
import datetime
from setuptools import setup

def get_version() -> str:
    if "TRAVIS" in os.environ:
        tag = os.environ.get('TRAVIS_TAG', None)
        if tag:
            return tag
        else:
            return f'0.0.0.{os.environ["TRAVIS_BUILD_NUMBER"]}'
    return f'0.0.0.{datetime.datetime.now().strftime("%Y%m%d%H%M%S")}'


VERSION = get_version()

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
    long_description='Command line tools for ADX automation system',
    license='MIT',
    author='Microsoft Corporation',
    author_email='trdai@microsoft.com',
    url='https://github.com/Azure/adx-automation-client',
    packages=[
        'a01',
        'a01.models',
        'a01.output',
        'a01.jobs',
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
