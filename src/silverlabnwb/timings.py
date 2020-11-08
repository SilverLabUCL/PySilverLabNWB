import abc

import numpy as np
import pandas as pd


class LabViewTimings(metaclass=abc.ABCMeta):
    """A class for storing pixel-level timing information for an ROI."""

    def __init__(self, relative_times_path, roi_reader, dwell_time):
        self.dwell_time = dwell_time
        self._read_relative_times_file(relative_times_path)
        self.roi_reader = roi_reader
        self.n_rois = roi_reader.get_n_rois()

    @abc.abstractmethod
    def _read_relative_times_file(self, file_path):
        pass


class LabViewTimingsPre2018(LabViewTimings):

    def __init__(self, relative_times_path, roi_reader, dwell_time):
        super().__init__(relative_times_path, roi_reader, dwell_time)
        self._format_pixel_time_offsets()

    def _read_relative_times_file(self, file_path):
        raw_data = pd.read_csv(file_path, names=('RelativeTime', 'CycleTime'),
                               sep='\t', dtype=np.float64) / 1e6  # convert to seconds
        self.pixel_time_offsets = raw_data['RelativeTime']
        self.cycle_time = raw_data['CycleTime'][0]

    def _format_pixel_time_offsets(self):
        pixel_time_offsets_by_roi = {}
        for roi_index in np.arange(self.n_rois):
            n_lines_in_roi, n_pixels_per_line = self.roi_reader.get_lines_pixels(roi_index)
            row_increments = np.arange(n_pixels_per_line) * self.dwell_time
            start_index = n_lines_in_roi * roi_index
            end_index = start_index + n_lines_in_roi
            row_offsets = self.pixel_time_offsets[start_index:end_index].values
            pixel_time_offsets_by_roi[roi_index] = row_offsets[:, np.newaxis] + row_increments
        self.pixel_time_offsets = pixel_time_offsets_by_roi


class LabViewTimingsPost2018(LabViewTimings):

    def __init__(self, relative_times_path, roi_reader, dwell_time, n_cycles_per_trial, n_trials):
        super().__init__(relative_times_path, roi_reader, dwell_time)
        self._format_pixel_time_offsets(n_cycles_per_trial, n_trials)

    def _read_relative_times_file(self, file_path):
        raw_data = pd.read_csv(file_path, sep='\t', dtype=np.float64) / 1e6
        self.pixel_time_offsets = raw_data['Image Time [us]']
        self.pixel_time_offsets = self.pixel_time_offsets[self.pixel_time_offsets != 0]

    def _format_pixel_time_offsets(self, n_cycles_per_trial, n_trials):
        pixel_time_offsets_by_roi = {}
        n_lines_per_cycle = sum(self.roi_reader.get_lines_pixels(roi_index)[0]
                                for roi_index in np.arange(0, self.n_rois))
        within_cycle_offset = 0
        for roi_index in np.arange(0, self.n_rois):
            pixel_time_offsets_by_roi[roi_index] = []
            n_lines_in_roi, n_pixels_per_line = self.roi_reader.get_lines_pixels(roi_index)
            row_increments = np.arange(n_pixels_per_line) * self.dwell_time
            for cycle_index in np.arange(0, n_cycles_per_trial * n_trials):
                start_index = within_cycle_offset + n_lines_per_cycle * cycle_index
                end_index = start_index + n_lines_in_roi
                pixel_time_offsets_by_roi[roi_index].append(self.pixel_time_offsets.values[start_index:end_index])
            within_cycle_offset += n_lines_in_roi
            pixel_time_offsets_by_roi[roi_index] = np.reshape(pixel_time_offsets_by_roi[roi_index],
                                                              (n_trials * n_cycles_per_trial, n_lines_in_roi))
            pixel_time_offsets_by_roi[roi_index] = pixel_time_offsets_by_roi[roi_index][:, :, np.newaxis] + row_increments

        # estimate time for one cycle by averaging the time it takes for the first cycle of each trial.
        # The n_pixels_per_line * pixel_dwell_time contribution of the last line is negligible.
        first_cycle_times_for_each_trial = []
        for trial_index in list(range(n_trials)):
            first_cycle_times_for_each_trial.append(pixel_time_offsets_by_roi[self.n_rois - 1]
                                                    [trial_index * n_cycles_per_trial]
                                                    [-1][0])

        self.cycle_time = np.mean(first_cycle_times_for_each_trial)
        self.pixel_time_offsets = pixel_time_offsets_by_roi
