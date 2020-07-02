import pandas as pd
import numpy as np
import abc


class LabViewTimings(metaclass=abc.ABCMeta):

    @classmethod
    def from_file(cls, file_path):
        raw_data = pd.read_csv(file_path, sep='\t', dtype=np.float64)
        return cls.compute_timings(raw_data)

    @classmethod
    @abc.abstractmethod
    def compute_timings(cls, raw_data):
        pass


class LabViewTimingsPre2018(LabViewTimings):

    @classmethod
    def compute_timings(cls, raw_data):
        return 'old time offsets', 'old cycle time'


class LabViewTimings231(LabViewTimings):

    @classmethod
    def compute_timings(cls, raw_data):
        return 'new time offsets', 'new cycle time'


if __name__ == "__main__":
    new_file_path = "C:\\Users\\Alessandro\\Documents\\UCL-projects\\silverlab\\Data\\" \
                    "LabViewData2020\\HG_30_exp01\\200107_13_13_33 FunctAcq\\Single cycle relative times_HW.txt"
    print(LabViewTimingsPre2018.from_file(new_file_path))
    old_file_path = "C:\\Users\\Alessandro\\Documents\\UCL-projects\\silverlab\\Data" \
                    "\\sample_miniscan_fred_170322_14_06_43\\Single cycle relative times.txt "
    print(LabViewTimings231.from_file(old_file_path))
