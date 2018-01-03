# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

from setuptools import setup

VERSION = "0.1.0"

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
    'PyYAML>=3.12'
]

setup(
    name='a01ctl',
    version=VERSION,
    description='A01 CLI',
    long_description='Command line tools for a01 system',
    license='MIT',
    author='Microsoft Corporation',
    author_email='trdai@microsoft.com',
    url='https://github.com/troydai/a01client',
    packages=[
        'a01',
    ],
    entry_points={
        'console_scripts': [
            'a01=a01.__main__:main'
        ]
    },
    install_requires=DEPENDENCIES
)
