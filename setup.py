#!/usr/bin/env python
# -*- encoding: utf-8 -*-
from __future__ import absolute_import, print_function

import io
import re
from glob import glob
from os.path import basename, dirname, join, splitext

from setuptools import find_packages, setup


def read(*names, **kwargs):
    with io.open(
        join(dirname(__file__), *names),
        encoding=kwargs.get('encoding', 'utf8')
    ) as fh:
        return fh.read()


setup(
    name='silverlabnwb',
    version='0.1.0',
    license='MIT license',
    description='Python tools for working with Silver Lab data in the NWB2 format',
    long_description='%s\n%s' % (
        re.compile('^.. start-badges.*^.. end-badges', re.M | re.S).sub('', read('README.rst')),
        re.sub(':[a-z]+:`~?(.*?)`', r'``\1``', read('CHANGELOG.rst'))
    ),
    author='UCL Research Software Development Group',
    author_email='rc-softdev@ucl.ac.uk',
    url='https://github.com/SilverLabUCL/PySilverLabNWB',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    py_modules=[splitext(basename(path))[0] for path in glob('src/*.py')],
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        # complete classifier list: http://pypi.python.org/pypi?%3Aaction=list_classifiers
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Operating System :: Unix',
        'Operating System :: POSIX',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: Implementation :: CPython',
    ],
    keywords=[
        # eg: 'keyword1', 'keyword2', 'keyword3',
    ],
    install_requires=[
        'pynwb==1.2.1',
        'appdirs',
        'h5py>=2.7.1',
        'nptdms',
        'numpy',
        'pandas>=0.20',
        'pyyaml',
        'tifffile',
    ],
    extras_require={
        ':python_version=="2"': ['enum34'],
        'test': ['pytest', 'tox'],
        'video': ['av'],
    },
    entry_points={
        'console_scripts': [
            'labview2nwb = silverlabnwb.script:import_labview',
            'subsample_nwb = silverlabnwb.subsample_nwb:run',
            'nwb_sig = silverlabnwb.signature:cli',
            'nwb_sig_convert = silverlabnwb.signature:convert_sig_cli',
        ],
        'gui_scripts': [
            'nwb_metadata_editor = silverlabnwb.metadata_gui:run_editor'
        ]
    },
)
