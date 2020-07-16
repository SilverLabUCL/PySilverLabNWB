import abc

import numpy as np
import pandas as pd


class LabViewTimings(metaclass=abc.ABCMeta):

    def __init__(self):
        self.pixel_time_offsets = None
        self.cycle_time = None

    @abc.abstractmethod
    def _read_relative_times_file(self, file_path):
        pass


class LabViewTimingsPre2018(LabViewTimings):

    def __init__(self, relative_times_path):
        self._read_relative_times_file(relative_times_path)

    def _read_relative_times_file(self, file_path):
        raw_data = pd.read_csv(file_path, names=('RelativeTime', 'CycleTime'),
                               sep='\t', dtype=np.float64) / 1e6
        self.pixel_time_offsets = raw_data['RelativeTime']
        self.cycle_time = raw_data['CycleTime'][0]


class LabViewTimings231(LabViewTimings):

    def __init__(self, relative_times_path, roi_path, n_cycles_per_trial, n_trials):
        self._read_relative_times_file(relative_times_path)
        self._format_pixel_time_offsets(roi_path, n_cycles_per_trial, n_trials)

    def _read_relative_times_file(self, file_path):
        raw_data = pd.read_csv(file_path, sep='\t', dtype=np.float64) / 1e6
        self.pixel_time_offsets = raw_data['Image Time [us]']
        self.pixel_time_offsets = self.pixel_time_offsets[self.pixel_time_offsets != 0]

    def _format_pixel_time_offsets(self, roi_path, n_cycles_per_trial, n_trials):
        roi_data = pd.read_csv(roi_path, sep='\t', dtype=np.float64)
        n_rois = len(roi_data['ROI index'])
        # in the future, we can access more shape parameters here too, for variable size ROIs in those cases,
        # we will need to access each individual row here separately. for now, take first row and all ROIs are same
        # size and orientation. Also, we may need to store the angle somewhere in the future (to reconstruct the ROI
        # in 3D, in which case the ==0 assertion may become imprecise and we would need a tolerance to compare with a
        # double value.
        if roi_data['Angle (deg)'][0] == 0:
            n_lines_per_roi = int(roi_data['Y stop'][0] - roi_data['Y start'][0])
        else:
            n_lines_per_roi = int(roi_data['X stop'][0] - roi_data['X start'][0])

        self.pixel_time_offsets_by_roi = {}
        n_lines_per_cycle = n_rois*n_lines_per_roi
        for i in np.arange(0, n_rois):
            self.pixel_time_offsets_by_roi[i] = []
            for j in np.arange(0, n_cycles_per_trial*n_trials):
                start_index = n_lines_per_roi * i + j * n_lines_per_cycle
                end_index = start_index+n_lines_per_roi
                self.pixel_time_offsets_by_roi[i].append(self.pixel_time_offsets.values[start_index:end_index])
            self.pixel_time_offsets_by_roi[i] = np.reshape(self.pixel_time_offsets_by_roi[i],
                                                           (n_trials*n_cycles_per_trial, n_lines_per_roi))
        self.pixel_time_offsets = np.reshape(self.pixel_time_offsets.values,
                                             (n_trials * n_cycles_per_trial,
                                              n_rois,
                                              n_lines_per_roi))

        # estimate time for one cycle by averaging the time it takes for the first cycle of each trial.
        # The n_pixels_per_line * pixel_dwell_time contribution of the last line is negligible.
        first_cycle_times_for_each_trial = []
        for i in list(range(n_trials)):
            first_cycle_times_for_each_trial.append(self.pixel_time_offsets
                                                    [i * n_cycles_per_trial]  # offset previous trials
                                                    [n_rois - 1]  # last ROI
                                                    [n_lines_per_roi - 1])  # start of last line
        self.cycle_time = np.mean(first_cycle_times_for_each_trial)  # will this introduce more error than it
        # avoids?? possibly better to keep everything in us for a while?
        # similarly, we might be better off dividing by 1e6 way later than at read time to avoid numerical error?
