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

Installation
============

::

    pip install silverlabnwb

Documentation
=============


https://PySilverLabNWB.readthedocs.io/


Development
===========

To run all the tests run::

    tox

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
