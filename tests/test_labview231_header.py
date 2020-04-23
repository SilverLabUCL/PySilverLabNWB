import os
import pytest

from silverlabnwb.header import LabViewHeader, LabViewVersions, Modes


@pytest.fixture
def get_header_from_file(request):
    """create header object from a Labview header file."""
    header_file = getattr(request.cls, "header_file")
    header_object = LabViewHeader.from_file(header_file)
    return header_object


@pytest.fixture
def get_expected(request):
    """create dictionary of expected values for a Labview header"""
    return getattr(request.cls, "expected")


class TestLabView231Header(object):
    header_file = os.path.join("tests", "data", "Experiment Header v231.ini")
    expected = {'version': LabViewVersions.v231, 'number of trials': 2, 'mode': Modes.miniscan}

    def test_lab_view_version(self, get_header_from_file, get_expected):
        assert get_header_from_file.version == get_expected['version']

    def test_imaging_mode(self, get_header_from_file, get_expected):
        assert get_header_from_file.imaging_mode == get_expected['mode']

    def test_trial_times(self, get_header_from_file, get_expected):
        trial_times = get_header_from_file.determine_trial_times()
        assert len(trial_times) == get_expected['number of trials']
