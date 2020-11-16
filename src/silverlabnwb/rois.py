"""Functionality for handling Regions of Interest in different versions."""

import abc
import os

import numpy as np
import pandas as pd

from .header import LabViewVersions
from .imaging import Modes


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
        'Z start': np.float64, 'Z stop': np.float64, 'Pixels in ROI': np.float32
    }
    base_type_conversion_post_read = {
        'x_start': np.uint16, 'x_stop': np.uint16,
        'y_start': np.uint16, 'y_stop': np.uint16,
        'num_pixels': int, 'num_lines': int
    }

    @classmethod
    def get_reader(cls, header):
        """Get an appropriate ROI reader based on the header."""
        if header.version in [LabViewVersions.pre2018, LabViewVersions.v231]:
            reader = ClassicRoiReader()
        elif header.version is LabViewVersions.v300:
            if header.allows_variable_rois:
                reader = RoiReaderv300Variable()
            else:
                reader = RoiReaderv300()
        else:
            raise ValueError('Unsupported LabView version {}.'.format(header.version))
        reader.imaging_mode = header.imaging_mode
        return reader

    @abc.abstractmethod
    def __init__(self):
        self.imaging_mode = None

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
        self.roi_data = pd.read_csv(
            roi_path, sep='\t', header=0, index_col=False,
            converters=self.type_mapping, memory_map=True)
        # Rename the columns so that we can use them as identifiers later on
        self.roi_data.rename(columns=self.column_mapping, inplace=True)
        # Convert some columns as required
        self.roi_data = self.roi_data.astype(self.type_conversion_post_read)
        return self.roi_data

    def get_lines_pixels(self, roi_number):
        """
        Get the number of lines and of pixels per line for a particular ROI.
        :param roi_number:
        :return: a tuple containing (number of lines, number of pixels per line)
        """
        # If we are in pointing mode, we always know the size of the ROI
        if self.imaging_mode is Modes.pointing:
            return (1, 1)
        # Otherwise we have to do something more elaborate, which may differ
        # between versions.
        return self._get_lines_pixels(roi_number)

    @abc.abstractmethod
    def _get_lines_pixels(self, roi_number):
        """Look into the data held to find the size of the given ROI."""
        raise NotImplementedError

    def get_row_attributes(self, roi_row):
        return {
            field: getattr(roi_row, field)
            for field in self.column_mapping.values()
        }

    def get_n_rois(self):
        return len(self.roi_data['roi_index'])

    @abc.abstractmethod
    def get_x_y_range(self, roi_number):
        raise NotImplementedError


class ClassicRoiReader(RoiReader):
    """A reader for older versions of LabView setup (up to 2.1.3)."""
    def __init__(self):
        super().__init__()
        self.column_mapping = self.base_column_mapping.copy()
        self.type_mapping = self.base_type_mapping.copy()
        self.type_conversion_post_read = self.base_type_conversion_post_read.copy()

    def _get_lines_pixels(self, roi_number):
        """
        This method determines the number of lines and the number of pixels per line by using information
        contained in x/y_start, x/y_stop, and angle_deg.
        :param roi_number:
        :return: a tuple containing (number of lines, number of pixels per line)
        """
        n_y_pixels = int(self.roi_data['y_stop'][roi_number] - self.roi_data['y_start'][roi_number])
        n_x_pixels = int(self.roi_data['x_stop'][roi_number] - self.roi_data['x_start'][roi_number])
        if self.roi_data['angle_deg'][roi_number] == 0:
            n_lines_in_roi = n_y_pixels
            n_pixels_per_line = n_x_pixels
        else:
            n_lines_in_roi = n_x_pixels
            n_pixels_per_line = n_y_pixels
        return n_lines_in_roi, n_pixels_per_line

    def get_x_y_range(self, roi_number):
        x_range = int(self.roi_data['x_stop'][roi_number] - self.roi_data['x_start'][roi_number])
        y_range = int(self.roi_data['y_stop'][roi_number] - self.roi_data['y_start'][roi_number])
        return x_range, y_range


class RoiReaderv300(RoiReader):
    """A reader for LabView version 3.0.0."""
    def __init__(self):
        super().__init__()
        self.column_mapping = self.base_column_mapping.copy()
        self.column_mapping.update({
            'Resolution': 'resolution',
            'Dwell Time per pixel': 'pixel_dwell_time',
            'Pixels per miniscan': 'pixels_per_miniscan',
            'Original FOV (um)': 'original_fov_um',
            'Apparent Frame Size': 'apparent_frame_size'
        })
        self.type_mapping = self.base_type_mapping.copy()
        # We don't need any more conversions while reading? But if we do,
        # they can be added here.
        self.type_conversion_post_read = self.base_type_conversion_post_read.copy()
        self.type_conversion_post_read.update({
            'pixels_per_miniscan': int
        })

    def _get_lines_pixels(self, roi_number):
        """
        This method overrides the base method, because the number of lines and the numbers of pixels/line
        may not match up with x_stop-x_start (depending on resolution) anymore, and is given explicitly
        in a column instead.
        :param roi_number:
        :return: a tuple containing (number of lines, number of pixels per line)
        """
        return (self.roi_data['num_lines'][roi_number],
                self.roi_data['pixels_per_miniscan'][roi_number])

    def get_x_y_range(self, roi_number):
        if self.roi_data['angle_deg'][roi_number] == 0:
            return self.get_lines_pixels(roi_number)[::-1]
        else:
            return self.get_lines_pixels(roi_number)[::-1]


class RoiReaderv300Variable(RoiReaderv300):
    """A reader for LabView version 3.0.0, supporting variable shape ROIs."""

    def get_roi_imaging_plane(self, roi_number, plane_name, nwb_file):
        """
        Gets the imaging plane for a variable size ROI.

        Overrides base method for variable size ROIs to create (if necessary, it may have been created previously
        for a different optical channel) and return an appropriately spatially calibrated imaging plane. This is
        needed because variable size ROIs need to have their own imaging plane, unlike fixed sized ROIs,
        which can share an imaging plane with other ROIs. """
        # FIXME This is the only method which uses the ROI number starting from 1. We should make
        # this consistent across all methods. This mostly matters for this class, since the other
        # subclasses handle ROIs of the same size.
        row = self.roi_data[self.roi_data['roi_index'] == roi_number]
        assert len(row) == 1
        resolution = row['resolution'].iloc[0]
        z_plane = nwb_file.nwb_file.processing['Acquired_ROIs'].get("ImageSegmentation")[plane_name].imaging_plane
        new_plane_name = z_plane.name + '_ROI_' + str(roi_number)
        if new_plane_name not in nwb_file.nwb_file.imaging_planes.keys():
            # Use the start coordinates as recorded in the ROI table
            origin = [row[f'{dim}_start'].iloc[0] for dim in ['x', 'y', 'z']]
            nwb_file.add_imaging_plane(
                name=new_plane_name,
                description='Imaging plane for variable size ROI nr. ' + str(roi_number),
                origin_coords=origin,
                grid_spacing=z_plane.grid_spacing*resolution
            )
        return nwb_file.nwb_file.imaging_planes[new_plane_name]
