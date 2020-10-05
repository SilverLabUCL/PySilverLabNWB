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
    def get_reader(cls, header):
        """Get an appropriate ROI reader based on the header."""
        if header.version in [LabViewVersions.pre2018, LabViewVersions.v231]:
            return ClassicRoiReader()
        elif header.version is LabViewVersions.v300:
            if header.allows_variable_rois:
                return RoiReaderv300Variable()
            else:
                return RoiReaderv300()
        else:
            raise ValueError('Unsupported LabView version {}.'.format(header.version))

    @abc.abstractmethod
    def __init__(self):
        pass

    @classmethod
    def get_roi_imaging_plane(cls, roi_number, plane_name, nwb_file):
        """Get the imaging plane belonging to a specific ROI"""
        return nwb_file.nwb_file.processing['Acquired_ROIs'].get("ImageSegmentation")[plane_name].imaging_plane

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
    """A reader for older versions of LabView setup (up to 2.1.3)."""
    def __init__(self):
        self.column_mapping = self.base_column_mapping
        self.type_mapping = self.base_type_mapping
        self.type_conversion_post_read = self.base_type_conversion_post_read


class RoiReaderv300(RoiReader):
    """A reader for LabView version 3.0.0."""
    def __init__(self):
        self.column_mapping = self.base_column_mapping
        self.column_mapping.update({
            'Resolution': 'resolution',
            'Dwell Time per pixel': 'pixel_dwell_time',
            'Pixels per miniscan': 'pixels_per_miniscan',
            'Original FOV (um)': 'original_fov_um',
            'Apparent Frame Size': 'apparent_frame_size'
        })
        self.type_mapping = self.base_type_mapping
        # We don't need any more conversions while reading? But if we do,
        # they can be added here.
        self.type_conversion_post_read = self.base_type_conversion_post_read
        self.type_conversion_post_read.update({
            # For if we need to convert any of the new columns post-read.
        })


class RoiReaderv300Variable(RoiReaderv300):
    """A reader for LabView version 3.0.0, supporting variable shape ROIs."""

    def get_roi_imaging_plane(self, roi_number, plane_name, nwb_file):
        """
        Gets the imaging plane for a variable size ROI.

        Overrides base method for variable size ROIs to create (if necessary, it may have been created previously
        for a different optical channel) and return an appropriately spatially calibrated imaging plane. This is
        needed because variable size ROIs need to have their own imaging plane, unlike fixed sized ROIs,
        which can share an imaging plane with other ROIs. """
        roi_row_idx = [index for index, value in enumerate(nwb_file.roi_data.roi_index) if value == roi_number]
        assert len(roi_row_idx) == 1
        roi_row_idx = roi_row_idx[0]
        resolution = nwb_file.roi_data.resolution[roi_row_idx]
        z_plane = nwb_file.nwb_file.processing['Acquired_ROIs'].get("ImageSegmentation")[plane_name].imaging_plane
        new_plane_name = z_plane.name + '_ROI_' + str(roi_number)
        if new_plane_name not in nwb_file.nwb_file.imaging_planes.keys():
            nwb_file.add_imaging_plane(
                name=new_plane_name,
                description='Imaging plane for variable size ROI nr. ' + str(roi_number),
                origin_coords=z_plane.origin_coords,
                grid_spacing=z_plane.grid_spacing*resolution
            )
        return nwb_file.nwb_file.imaging_planes[new_plane_name]
