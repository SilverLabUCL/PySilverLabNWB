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
        # in the future, we can access more shape parameters here too, for variable size ROIs
        # in those cases, we will need to access each individual row here separately.
        # for now, take first row and all ROIs are same size and orientation
        if roi_data['Angle (deg)'][0] == 0:
            n_lines_per_roi = int(roi_data['Y stop'][0]-roi_data['Y start'][0])
        else:
            n_lines_per_roi = int(roi_data['X stop'][0]-roi_data['X start'][0])
        self.pixel_time_offsets = np.reshape(self.pixel_time_offsets.values,
                                             (n_trials * n_cycles_per_trial,
                                              n_rois,
                                              n_lines_per_roi))
        self.cycle_time = 0  # TODO!!!


if __name__ == "__main__":
    old_file_path = "C:\\Users\\Alessandro\\Documents\\UCL-projects\\silverlab\\Data" \
                    "\\sample_miniscan_fred_170322_14_06_43\\Single cycle relative times.txt "
    print("old pixel time offsets: ", LabViewTimingsPre2018(old_file_path).pixel_time_offsets)
    print("new cycle time: ", LabViewTimingsPre2018(old_file_path).cycle_time)

    new_file_path = "C:\\Users\\Alessandro\\Documents\\UCL-projects\\silverlab\\Data\\" \
                    "LabViewData2020\\HG_30_exp01\\200107_13_13_33 FunctAcq\\Single cycle relative times_HW.txt"
    new_roi_path = "C:\\Users\\Alessandro\\Documents\\UCL-projects\\silverlab\\Data\\" \
                   "LabViewData2020\\HG_30_exp01\\200107_13_13_33 FunctAcq\\ROI.dat"
    print("new pixel time offsets: ",
          LabViewTimings231(new_file_path, roi_path=new_roi_path, cycles_per_trial=578, n_trials=30).pixel_time_offsets)
    print("new cycle time: ",
          LabViewTimings231(new_file_path, roi_path=new_roi_path, cycles_per_trial=578, n_trials=30).cycle_time)
    print(LabViewTimings231(new_file_path, roi_path=new_roi_path, cycles_per_trial=578, n_trials=30).pixel_time_offsets[0].shape)
