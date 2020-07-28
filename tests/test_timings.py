import os

import pytest

from silverlabnwb import timings


@pytest.fixture(scope="module")
def synthetic_timings_v231(ref_data_dir):
    timings_file_name = "synthetic v231 Single cycle relative times_HW.txt"
    timings_file_path = os.path.join(ref_data_dir, timings_file_name)
    roi_file_name = "synthetic v231 ROI.dat"
    roi_file_path = os.path.join(ref_data_dir, roi_file_name)
    # the synthetic file has
    # 2 trials, each of which has 3 cycles and 4 rois a 5 lines
    # and a few zero lines as may be expected "in the wild"
    # first cycle of trial 1 and trial 2 take 1300.4 and 1200.4 nanoseconds, respectively
    return timings.LabViewTimings231(relative_times_path=timings_file_path,
                                     roi_path=roi_file_path,
                                     n_cycles_per_trial=3,
                                     n_trials=2,
                                     dwell_time=1.e-6)


@pytest.fixture(scope="module")
def synthetic_timings_pre2018(ref_data_dir):
    timings_file_name = "synthetic pre2018 Single cycle relative times.txt"
    timings_file_path = os.path.join(ref_data_dir, timings_file_name)
    roi_file_name = "synthetic pre2018 ROI.dat"
    roi_file_path = os.path.join(ref_data_dir, roi_file_name)
    return timings.LabViewTimingsPre2018(relative_times_path=timings_file_path,
                                         roi_path=roi_file_path,
                                         dwell_time=1.e-6)


def test_cycle_time_v231(synthetic_timings_v231):
    expected_mean_first_cycle_time_s = 1250.4 / 1e6
    assert synthetic_timings_v231.cycle_time == expected_mean_first_cycle_time_s


@pytest.mark.parametrize("roi_index", list(range(4)))  # 4 ROIs
def test_pixel_time_offsets_for_rois_v231(synthetic_timings_v231, roi_index):
    roi_offsets = synthetic_timings_v231.pixel_time_offsets[roi_index]
    expected_shape = (6, 5, 6)  # 2 trials * 3 cycles , 5 lines/roi, 6 pixels/line
    expected_first_cycle_first_row_offset = (200 + 300 * roi_index) / 1e6
    expected_first_cycle_last_row_offset = (400.4 + 300 * roi_index) / 1e6
    expected_last_cycle_first_row_offset = (4100 + 300 * roi_index) / 1e6
    assert roi_offsets.shape == expected_shape
    assert roi_offsets[0][0][0] == expected_first_cycle_first_row_offset
    assert roi_offsets[0][4][0] == expected_first_cycle_last_row_offset
    assert roi_offsets[-1][0][0] == expected_last_cycle_first_row_offset


def test_cycle_time_pre2018(synthetic_timings_pre2018):
    expected_cycle_time = 12345 / 1e6
    assert synthetic_timings_pre2018.cycle_time == expected_cycle_time


@pytest.mark.parametrize("roi_index", list(range(2)))  # 2 ROIs
def test_pixel_time_offsets_for_roi_pre2018(synthetic_timings_pre2018, roi_index):
    roi_offsets = synthetic_timings_pre2018.pixel_time_offsets[roi_index]
    expected_shape = (4, 10)  # 4 lines/roi, 10 pixels/line
    expected_first_row_offset = (400 + 400 * roi_index) / 1e6
    expected_last_row_offset = (700 + 400 * roi_index) / 1e6
    assert roi_offsets.shape == expected_shape
    assert roi_offsets[0][0] == expected_first_row_offset
    assert roi_offsets[-1][0] == expected_last_row_offset
