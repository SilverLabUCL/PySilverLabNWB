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
    # first cycle ofs trial 1 and trial 2 take 1300.4 and 1200.4 nanoseconds, respectively
    return timings.LabViewTimings231(timings_file_path,
                                     roi_path=roi_file_path,
                                     n_cycles_per_trial=3,
                                     n_trials=2)


def test_pixel_time_offsets_v231_shape(synthetic_timings_v231):
    expected_shape = (6, 4, 5)
    assert synthetic_timings_v231.pixel_time_offsets.shape == expected_shape


def test_cycle_time_v231(synthetic_timings_v231):
    expected_mean_first_cycle_time_s = 1250.4 / 1e6
    assert synthetic_timings_v231.cycle_time == expected_mean_first_cycle_time_s
