"""General test fixtures."""

import os
import pytest


@pytest.fixture
def ref_data_dir():
    return os.path.join(os.path.dirname(__file__), 'data')


@pytest.fixture(autouse=True)
def metadata_config(ref_data_dir):
    import silverlabnwb
    silverlabnwb.metadata.set_conf_dir(ref_data_dir)
