import os

import pytest

from silverlabnwb import rois
from silverlabnwb.header import LabViewHeader


class TestRoiReaders(object):
    pre2018_file_names = ("synthetic pre2018 ROI.dat", "Experiment Header.ini")
    v231_file_names = ("synthetic v231 ROI.dat", "synthetic experiment Header v231.ini")
    v300_file_names = ("real life v300 ROI.dat", "real life Experiment Header v300.ini")

    @pytest.fixture(scope="function")
    def get_roi_table(self, ref_data_dir, file_names):
        header_file_name = file_names[1]
        header_file_path = os.path.join(ref_data_dir, header_file_name)
        header = LabViewHeader.from_file(header_file_path)
        reader = rois.RoiReader.get_reader(header)
        roi_file_name = file_names[0]
        roi_file_path = os.path.join(ref_data_dir, roi_file_name)
        roi_table = reader.read_roi_table(roi_file_path)
        return roi_table

    @pytest.mark.parametrize("file_names, expected",
                             [(v231_file_names, 19),
                              (pre2018_file_names, 17),
                              (v300_file_names, 24)])
    def test_number_of_columns(self, get_roi_table, file_names, expected):
        assert len(get_roi_table.keys()) == expected

    # TODO: test_column_names, parametrised.

    def test_columns_are_independent(self):
        """Ensure that columns and type mappings are not shared among versions."""
        old_reader = rois.ClassicRoiReader()
        new_reader = rois.RoiReaderv300()
        assert old_reader.column_mapping is not new_reader.column_mapping
        assert old_reader.type_mapping is not new_reader.type_mapping
        assert old_reader.type_conversion_post_read is not new_reader.type_conversion_post_read
