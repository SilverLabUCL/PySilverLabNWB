import os

from silverlabnwb.header import LabViewHeader, LabViewVersions, Modes


def do_header_test(lab_view_header, expected):
    header = LabViewHeader.from_file(lab_view_header)
    trial_times = header.determine_trial_times()
    assert header.version == expected['version']
    assert len(trial_times) == expected['number of trials']
    assert header.imaging_mode == expected['mode']


class TestLabView231Header(object):

    def test_synthetic_v231header(self):
        expected = {'version': LabViewVersions.v231, 'number of trials': 2, 'mode': Modes.miniscan}
        path_to_header = os.path.join("tests", "data", "Experiment Header v231.ini")
        do_header_test(path_to_header, expected)
