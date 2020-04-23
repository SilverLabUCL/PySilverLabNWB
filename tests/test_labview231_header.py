import os
import pytest

from silverlabnwb.header import LabViewHeader, LabViewVersions, Modes

expected = {'version': LabViewVersions.v231, 'number of trials': 2, 'mode': Modes.miniscan}


@pytest.fixture(params=[os.path.join("tests", "data", "Experiment Header v231.ini")])
def get_header_from_file(request):
    """create header object from a Labview header file."""
    header_file = request.param
    header_object = LabViewHeader.from_file(header_file)
    return header_object


class TestLabView231Header(object):

    def test_lab_view_version(self, get_header_from_file):
        assert get_header_from_file.version == expected['version']

    def test_imaging_mode(self, get_header_from_file):
        assert get_header_from_file.imaging_mode == expected['mode']

    def test_trial_times(self, get_header_from_file):
        trial_times = get_header_from_file.determine_trial_times()
        assert len(trial_times) == expected['number of trials']
