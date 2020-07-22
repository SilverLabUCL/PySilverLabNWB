import abc

import numpy as np
import pandas as pd


class LabViewTimings(metaclass=abc.ABCMeta):

    def __init__(self, relative_times_path, roi_path, dwell_time):
        self.dwell_time = dwell_time
        self._read_relative_times_file(relative_times_path)
        self._read_roi_data(roi_path)

    @abc.abstractmethod
    def _read_relative_times_file(self, file_path):
        pass

    def _read_roi_data(self, roi_path):
        self.roi_data = pd.read_csv(roi_path, sep='\t', dtype=np.float64)
        self.n_rois = len(self.roi_data['ROI index'])
        # in the future, we can access more shape parameters here too, for variable size ROIs in those cases,
        # we will need to access each individual row here separately. for now, take first row and all ROIs are same
        # size and orientation. Also, we may need to store the angle somewhere in the future (to reconstruct the ROI
        # in 3D, in which case the ==0 assertion may become imprecise and we would need a tolerance to compare with a
        # double value.
        n_y_pixels = int(self.roi_data['Y stop'][0] - self.roi_data['Y start'][0])
        n_x_pixels = int(self.roi_data['X stop'][0] - self.roi_data['X start'][0])
        if self.roi_data['Angle (deg)'][0] == 0:
            self.n_lines_per_roi = n_y_pixels
            self.n_pixels_per_line = n_x_pixels
        else:
            self.n_lines_per_roi = n_x_pixels
            self.n_pixels_per_line = n_y_pixels
        if self.n_pixels_per_line == 0 and self.n_lines_per_roi == 0:
            # assume we are in pointing mode in this case, probably better if this were passed as an argument?
            # this class would need to know about the Modes class then though.
            self.n_pixels_per_line = 1
            self.n_lines_per_roi = 1


class LabViewTimingsPre2018(LabViewTimings):

    def __init__(self, relative_times_path, roi_path, dwell_time):
        super().__init__(relative_times_path, roi_path, dwell_time)
        self._format_pixel_time_offsets()

    def _read_relative_times_file(self, file_path):
        raw_data = pd.read_csv(file_path, names=('RelativeTime', 'CycleTime'),
                               sep='\t', dtype=np.float64) / 1e6  # convert to seconds
        self.pixel_time_offsets = raw_data['RelativeTime']
        self.cycle_time = raw_data['CycleTime'][0]

    def _format_pixel_time_offsets(self):
        row_increments = np.arange(self.n_pixels_per_line)*self.dwell_time
        pixel_time_offsets_by_roi = {}
        for roi_index in np.arange(self.n_rois):
            start_index = self.n_lines_per_roi * roi_index
            end_index = start_index + self.n_lines_per_roi
            row_offsets = self.pixel_time_offsets[start_index:end_index]
            pixel_time_offsets_by_roi[roi_index] = row_offsets[:, np.newaxis]+row_increments
        self.pixel_time_offsets = pixel_time_offsets_by_roi


class LabViewTimings231(LabViewTimings):

    def __init__(self, relative_times_path, roi_path, dwell_time, n_cycles_per_trial, n_trials):
        super().__init__(relative_times_path, roi_path, dwell_time)
        self._format_pixel_time_offsets(n_cycles_per_trial, n_trials)

    def _read_relative_times_file(self, file_path):
        raw_data = pd.read_csv(file_path, sep='\t', dtype=np.float64) / 1e6
        self.pixel_time_offsets = raw_data['Image Time [us]']
        self.pixel_time_offsets = self.pixel_time_offsets[self.pixel_time_offsets != 0]

    def _format_pixel_time_offsets(self, n_cycles_per_trial, n_trials):
        pixel_time_offsets_by_roi = {}
        n_lines_per_cycle = self.n_rois * self.n_lines_per_roi
        row_increments = np.arange(self.n_pixels_per_line) * self.dwell_time
        for roi_index in np.arange(0, self.n_rois):
            pixel_time_offsets_by_roi[roi_index] = []
            for cycle_index in np.arange(0, n_cycles_per_trial * n_trials):
                start_index = self.n_lines_per_roi * roi_index + n_lines_per_cycle * cycle_index
                end_index = start_index + self.n_lines_per_roi
                pixel_time_offsets_by_roi[roi_index].append(self.pixel_time_offsets.values[start_index:end_index])
            pixel_time_offsets_by_roi[roi_index] = np.reshape(pixel_time_offsets_by_roi[roi_index],
                                                              (n_trials * n_cycles_per_trial, self.n_lines_per_roi))
            pixel_time_offsets_by_roi[roi_index] = pixel_time_offsets_by_roi[roi_index][:, :, np.newaxis] + row_increments

        # estimate time for one cycle by averaging the time it takes for the first cycle of each trial.
        # The n_pixels_per_line * pixel_dwell_time contribution of the last line is negligible.
        first_cycle_times_for_each_trial_by_roi = []
        for trial_index in list(range(n_trials)):
            first_cycle_times_for_each_trial_by_roi.append(pixel_time_offsets_by_roi[self.n_rois-1]
                                                           [trial_index * n_cycles_per_trial]
                                                           [self.n_lines_per_roi-1][0])

        self.cycle_time = np.mean(first_cycle_times_for_each_trial_by_roi)  # does this introduce more error than it
        # avoids?? possibly better to keep everything in us for a while?
        # similarly, we might be better off dividing by 1e6 way later than at read time to avoid numerical error?

        self.pixel_time_offsets = pixel_time_offsets_by_roi
