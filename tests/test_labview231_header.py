import os

import pytest

from silverlabnwb.header import LabViewHeader231, LabViewVersions, Modes

# Where to look for raw data files
DATA_PATH = os.environ.get('SILVERLAB_DATA_DIR', '')


def do_header231_test(lab_view_folder, expected):
    header = LabViewHeader231.from_file(DATA_PATH+lab_view_folder+"\\Experiment Header.ini")
    trial_times = header.determine_trial_times()
    assert header.version == expected['version']
    assert len(trial_times) == expected['number of trials']
    assert header.imaging_mode == expected['mode']


@pytest.mark.skipif(
    not os.path.isdir(DATA_PATH),
    reason="raw data folder '{}' not present".format(DATA_PATH))
class TestLabView231Header(object):

    def test_hg_30_exp01(self):
        expected = {'version': LabViewVersions.v231, 'number of trials': 30, 'mode': Modes.miniscan}
        do_header231_test("\\LabViewData2020\\HG_30_exp01\\200107_13_13_33 FunctAcq", expected)

    def test_hg_29_exp02(self):
        expected = {'version': LabViewVersions.v231, 'number of trials': 30, 'mode': Modes.miniscan}
        do_header231_test("\\LabViewData2020\\HG_29_exp02\\200206_16_30_32 FunctAcq", expected)
