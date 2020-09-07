"""Functionality for handling Regions of Interest in different versions."""

import os

import numpy as np
import pandas as pd


class RoiReader:
    """A class for reading ROI information."""
    def __init__(self):
        self.column_mapping = {
            'ROI index': 'roi_index', 'Pixels in ROI': 'num_pixels',
            'X start': 'x_start', 'Y start': 'y_start', 'Z start': 'z_start',
            'X stop': 'x_stop', 'Y stop': 'y_stop', 'Z stop': 'z_stop',
            'Laser Power (%)': 'laser_power', 'ROI Time (ns)': 'roi_time_ns',
            'Angle (deg)': 'angle_deg', 'Composite ID': 'composite_id',
            'Number of lines': 'num_lines', 'Frame Size': 'frame_size',
            'Zoom': 'zoom', 'ROI group ID': 'roi_group_id'
        }

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
        roi_data = pd.read_csv(
            roi_path, sep='\t', header=0, index_col=False, dtype=np.float16,
            converters={'Z start': np.float64, 'Z stop': np.float64}, memory_map=True)
        # Rename the columns so that we can use them as identifiers later on
        roi_data.rename(columns=self.column_mapping, inplace=True)
        # Convert some columns to int
        roi_data = roi_data.astype(
            {'x_start': np.uint16, 'x_stop': np.uint16, 'y_start': np.uint16, 'y_stop': np.uint16,
             'num_pixels': int})
        return roi_data

    def get_row_attributes(self, roi_row):
        return {
            field: getattr(roi_row, field)
            for field in self.column_mapping.values()
        }
