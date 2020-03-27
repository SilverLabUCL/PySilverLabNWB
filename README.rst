========
Overview
========

.. start-badges

.. list-table::
    :stub-columns: 1

    * - docs
      - |docs|
    * - tests
      - | |travis| |appveyor|
        | |codecov|
    * - package
      - | |version| |wheel| |supported-versions| |supported-implementations|

.. |docs| image:: https://readthedocs.org/projects/pysilverlabnwb/badge/?style=flat
    :target: https://readthedocs.org/projects/pysilverlabnwb
    :alt: Documentation Status

.. |travis| image:: https://travis-ci.org/SilverLabUCL/PySilverLabNWB.svg?branch=master
    :alt: Travis-CI Build Status
    :target: https://travis-ci.org/SilverLabUCL/PySilverLabNWB

.. |appveyor| image:: https://ci.appveyor.com/api/projects/status/github/jonc125/PySilverLabNWB?branch=master&svg=true
    :alt: AppVeyor Build Status
    :target: https://ci.appveyor.com/project/jonc125/PySilverLabNWB

.. |codecov| image:: https://codecov.io/github/SilverLabUCL/PySilverLabNWB/coverage.svg?branch=master
    :alt: Coverage Status
    :target: https://codecov.io/github/SilverLabUCL/PySilverLabNWB

.. |version| image:: https://img.shields.io/pypi/v/silverlabnwb.svg
    :alt: PyPI Package latest release
    :target: https://pypi.python.org/pypi/silverlabnwb

.. |wheel| image:: https://img.shields.io/pypi/wheel/silverlabnwb.svg
    :alt: PyPI Wheel
    :target: https://pypi.python.org/pypi/silverlabnwb

.. |supported-versions| image:: https://img.shields.io/pypi/pyversions/silverlabnwb.svg
    :alt: Supported versions
    :target: https://pypi.python.org/pypi/silverlabnwb

.. |supported-implementations| image:: https://img.shields.io/pypi/implementation/silverlabnwb.svg
    :alt: Supported implementations
    :target: https://pypi.python.org/pypi/silverlabnwb


.. end-badges

Python tools for working with Silver Lab data in the NWB2 format

* Free software: MIT license

This Python package simplifies access to NWB data for typical Silver Lab experiments,
and converts data from Labview format into NWB.
It provides a few command-line utilities, as well as supporting access from other Python software.


Installation
============

Some of our dependencies are hard to install, so it's best to use ``conda``::

    conda create -n nwb2 python=3.6 pip numpy pandas hdf5 h5py
    conda install -n nwb2 av tifffile -c conda-forge
    conda activate nwb2
    pip install .[video]

Eventually the last line will be replaced with::

    pip install silverlabnwb[video]

But we haven't uploaded to PyPI yet.


Documentation
=============

https://PySilverLabNWB.readthedocs.io/


Development
===========

Testing uses ``pytest``, along with ``tox`` to test on multiple Python installations and do style checks etc.

To install the developer packages, run::

    pip install .[test]

To test just on your current Python::

    pytest

To run all the tests run::

    tox


The automatic tests make use of various environment variables to customise what is run.

No 'import' tests will run unless ``SILVERLAB_DATA_DIR`` is set and points to a folder containing suitable data.
A version of this folder is available through UCL's OneDrive at present,
but only contains smaller sample data.
The full datasets are available on Jonathan's Mac or the SilverLab shared drive.

Set ``SILVERLAB_TEST_LONG_IMPORTS`` to 1 to test importing full-size datasets.

Set ``SILVERLAB_GEN_REF`` to 1 to regenerate reference signatures.


Note, to combine the coverage data from all the tox environments run:

.. list-table::
    :widths: 10 90
    :stub-columns: 1

    - - Windows
      - ::

            set PYTEST_ADDOPTS=--cov-append
            tox

    - - Other
      - ::

            PYTEST_ADDOPTS=--cov-append tox
