"""Unit style tests for reading from various LabView headers (.ini files)"""
import os

import pytest

from silverlabnwb.header import LabViewHeader, LabViewVersions, Modes


@pytest.fixture(scope="module")
def header(request, ref_data_dir):
    """Create header object from a LabView header file."""
    header_file = os.path.join(ref_data_dir, request.param)
    header_object = LabViewHeader.from_file(header_file)
    return header_object


class TestLabViewHeaders(object):
    synthetic_header_path_v231 = 'synthetic experiment Header v231.ini'
    synthetic_header_path_v231_no_last_time = 'synthetic experiment Header v231 no last time.ini'
    synthetic_header_path_pre2018 = 'Experiment Header.ini'
    header_with_unrecognised_line_path = 'unrecognised line Header.ini'
    real_life_header_path_v231_pointing = 'real life Experiment Header v231 pointing.ini'

    @pytest.mark.parametrize("header, expected_version",
                             [(synthetic_header_path_v231, LabViewVersions.v231),
                              (synthetic_header_path_pre2018, LabViewVersions.pre2018),
                              (real_life_header_path_v231_pointing, LabViewVersions.v231)],
                             indirect=["header"])
    def test_lab_view_version(self, header, expected_version):
        assert header.version == expected_version

    @pytest.mark.parametrize("header, expected_mode",
                             [(synthetic_header_path_v231, Modes.miniscan),
                              (synthetic_header_path_pre2018, Modes.pointing),
                              (real_life_header_path_v231_pointing, Modes.pointing)],
                             indirect=["header"])
    def test_imaging_mode(self, header, expected_mode):
        assert header.imaging_mode == expected_mode

    @pytest.mark.parametrize("header, expected_trial_times",
                             [(synthetic_header_path_v231, [(0.0, 12.345678), (12.567890, 23.456789)]),
                              (synthetic_header_path_v231_no_last_time, [(0.0, 12.345678), (12.567890, None)])],
                             indirect=["header"])
    def test_trial_times(self, header, expected_trial_times):
        assert header.determine_trial_times() == expected_trial_times

    @pytest.mark.parametrize("header, expected_number_of_trials",
                             [(synthetic_header_path_v231, 2),
                              (synthetic_header_path_v231_no_last_time, 2),
                              (real_life_header_path_v231_pointing, 29)],
                             indirect=["header"])
    def test_number_of_trials(self, header, expected_number_of_trials):
        assert len(header.determine_trial_times()) == expected_number_of_trials

    @pytest.mark.parametrize("header",
                             [synthetic_header_path_pre2018],
                             indirect=["header"])
    def test_pre2018_trial_times_raises_error(self, header):
        with pytest.raises(NotImplementedError):
            header.determine_trial_times()

    @pytest.mark.parametrize("header, expected_subject",
                             [(synthetic_header_path_v231, "Animal Code or Name: Test1\nRegion of brain imaged: crus"),
                              (synthetic_header_path_v231_no_last_time, ""),
                              (synthetic_header_path_pre2018, ""),
                              (real_life_header_path_v231_pointing, "")],
                             indirect=["header"])
    def test_subject_info(self, header, expected_subject):
        assert header.get_subject_info() == expected_subject

    def test_unrecognised_line_causes_warning(self):
        with pytest.warns(UserWarning) as list_of_warnings:
            LabViewHeader.from_file(os.path.join("tests", "data", self.header_with_unrecognised_line_path))
        assert len(list_of_warnings) == 1
        assert str(list_of_warnings[0].message).startswith("Unrecognised non-blank line")
