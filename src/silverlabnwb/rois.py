"""Functionality for handling Regions of Interest in different versions."""

import abc
import os

import numpy as np
import pandas as pd

from .header import LabViewVersions


class RoiReader(metaclass=abc.ABCMeta):
    """A class for reading ROI information.

    This class provides some base functionality, but specific implementations
    are given in subclasses. Those subclasses should not be instantiated
    directly, but through this class's get_reader method.
    """
    base_column_mapping = {
            'ROI index': 'roi_index', 'Pixels in ROI': 'num_pixels',
            'X start': 'x_start', 'Y start': 'y_start', 'Z start': 'z_start',
            'X stop': 'x_stop', 'Y stop': 'y_stop', 'Z stop': 'z_stop',
            'Laser Power (%)': 'laser_power', 'ROI Time (ns)': 'roi_time_ns',
            'Angle (deg)': 'angle_deg', 'Composite ID': 'composite_id',
            'Number of lines': 'num_lines', 'Frame Size': 'frame_size',
            'Zoom': 'zoom', 'ROI group ID': 'roi_group_id'
    }
    # Some columns should be converted to int, others need more than 16 bits
    base_type_mapping = {
        'Z start': np.float64, 'Z stop': np.float64
    }
    base_type_conversion_post_read = {
        'x_start': np.uint16, 'x_stop': np.uint16,
        'y_start': np.uint16, 'y_stop': np.uint16,
        'num_pixels': int
    }

    @classmethod
    def get_reader(cls, header_version):
        """Get an appropriate ROI reader based on the header."""
        if header_version in [LabViewVersions.pre2018, LabViewVersions.v231]:
            return ClassicRoiReader()
        else:
            raise ValueError('Unsupported LabView version {}.'.format(version))

    @abc.abstractmethod
    def __init__(self):
        pass

    @property
    def columns(self):
        column_descriptions = {
            'dimensions': 'Dimensions of the ROI'
        }
        column_descriptions.update({
            new_name: old_name
            for old_name, new_name in self.column_mapping.items()
        })
        return column_descriptions

    def read_roi_table(self, roi_path):
        assert os.path.isfile(roi_path)
        # Read any columns without explicitly given types as float16
        for column in self.column_mapping:
            if column not in self.type_mapping:
                self.type_mapping[column] = np.float16
        roi_data = pd.read_csv(
            roi_path, sep='\t', header=0, index_col=False,
            converters=self.type_mapping, memory_map=True)
        # Rename the columns so that we can use them as identifiers later on
        roi_data.rename(columns=self.column_mapping, inplace=True)
        # Convert some columns as required
        roi_data = roi_data.astype(self.type_conversion_post_read)
        return roi_data

    def get_row_attributes(self, roi_row):
        return {
            field: getattr(roi_row, field)
            for field in self.column_mapping.values()
        }


class ClassicRoiReader(RoiReader):
    def __init__(self):
        self.column_mapping = self.base_column_mapping
        self.type_mapping = self.base_type_mapping
        self.type_conversion_post_read = self.base_type_conversion_post_read
