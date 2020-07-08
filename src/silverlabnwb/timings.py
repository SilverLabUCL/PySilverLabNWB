import pandas as pd
import numpy as np
import abc


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

    def __init__(self, relative_times_path, roi_path, cycles_per_trial, n_trials):
        self._read_relative_times_file(relative_times_path)
        self._format_pixel_time_offsets(roi_path, cycles_per_trial, n_trials)

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
        print("lines per ROI", n_lines_per_roi)
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
        print(first_cycle_times_for_each_trial)
        self.cycle_time = np.mean(first_cycle_times_for_each_trial)  # will this introduce more error than it
        # avoids?? possibly better to keep everything in us for a while?
        # similarly, we might be better off dividing by 1e6 way later than at read time to avoid numerical error?


# visual integration tests until we implement pytests.
# TODO pytests
# TODO documentation
# TODO remove the __main__ function
if __name__ == "__main__":
    old_file_path = "C:\\Users\\Alessandro\\Documents\\UCL-projects\\silverlab\\Data" \
                    "\\sample_miniscan_fred_170322_14_06_43\\Single cycle relative times.txt "
    old_timings = LabViewTimingsPre2018(old_file_path)
    print("old pixel time offsets: ", old_timings.pixel_time_offsets)
    print("old cycle time: ", old_timings.cycle_time)

    new_file_path = "C:\\Users\\Alessandro\\Documents\\UCL-projects\\silverlab\\Data\\" \
                    "LabViewData2020\\HG_30_exp01\\200107_13_13_33 FunctAcq\\Single cycle relative times_HW.txt"
    new_roi_path = "C:\\Users\\Alessandro\\Documents\\UCL-projects\\silverlab\\Data\\" \
                   "LabViewData2020\\HG_30_exp01\\200107_13_13_33 FunctAcq\\ROI.dat"
    new_timings = LabViewTimings231(new_file_path, roi_path=new_roi_path, cycles_per_trial=578, n_trials=30)
    print("new pixel time offsets: ", new_timings.pixel_time_offsets)
    print("new cycle time: ", new_timings.cycle_time)

