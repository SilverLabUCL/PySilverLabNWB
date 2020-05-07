"""Testing that epochs are calculated and added correctly."""

import os

import h5py
import numpy as np
import pandas as pd

from ruamel.yaml import YAML
from silverlabnwb import NwbFile

ignored = ['labview_header']


def compare_hdf5(nwb_path, expected_yaml_path):
    """Test utility method comparing a generated NWB file against expected contents.

    As a side-effect, checks that we can open files for reading with our API.
    """
    global current_file
    with open(expected_yaml_path, 'r') as f:
        yaml_instance = YAML(typ='safe')
        expected = yaml_instance.load(f)
    with NwbFile(nwb_path, mode='r') as nwb:
        current_file = nwb.hdf_file
        compare_group(nwb.hdf_file, expected, '')
        current_file = None


def compare_group(nwb_group, expected_group, path):
    """Check that an HDF5 group has the expected contents."""
    for key in expected_group:
        if key in ignored:
            continue
        expected_value = expected_group[key]
        if key == '_attrs':
            # Check attributes of the node
            compare_attributes(nwb_group, expected_value, path)
        elif key == '_value':
            # nwb_group should actually be a dataset
            assert isinstance(nwb_group, h5py.Dataset)
            compare_dataset(nwb_group, expected_value, path)
        elif key == '_link':
            # This group should be a soft link to another
            link = nwb_group.get(nwb_group.name, getlink=True)
            assert isinstance(link, h5py.SoftLink)
            assert link.path == expected_value
        else:
            assert key in nwb_group
            if isinstance(expected_value, dict):
                if '_columns' in expected_value:
                    compare_table(nwb_group[key], expected_value['_columns'], path + '/' + key)
                else:
                    compare_group(nwb_group[key], expected_value, path + '/' + key)
            else:
                compare_dataset(nwb_group[key], expected_value, path + '/' + key)


def compare_attributes(nwb_node, expected_attrs, path):
    """Check that an HDF5 node has the expected attributes."""
    for attr_name, attr_value in expected_attrs.items():
        assert attr_name in nwb_node.attrs
        compare_dataset(nwb_node.attrs[attr_name], attr_value, path + '/@' + attr_name)


def compare_generic_dataset(nwb_dataset, expected_value, path):
    """Check that an HDF5 dataset has the expected contents.

    Note that this gets used for both 'normal' datasets and attribute values.
    In the former case we must access the numpy value with [()]; in the latter
    nwb_dataset is already the numpy value.
    """
    if isinstance(nwb_dataset, h5py.Dataset):
        # Extract the actual data from the dataset
        nwb_dataset = nwb_dataset[()]
    if isinstance(expected_value, str):
        if isinstance(nwb_dataset, np.bytes_):
            # Convert to string so we can compare naturally
            nwb_dataset = nwb_dataset.decode('UTF-8')
        assert nwb_dataset == expected_value, 'Mismatch at {}'.format(path)
    elif isinstance(expected_value, (int, float)):
        assert abs(nwb_dataset - expected_value) < 1e-6, 'Mismatch at {}'.format(path)
    elif isinstance(expected_value, list):
        expected_value = np.array(expected_value)
        assert nwb_dataset.shape == expected_value.shape, 'Mismatch at {}'.format(path)
        if expected_value.dtype.kind == 'U':
            expected_value = expected_value.astype('S')
        if nwb_dataset.dtype.kind in ['O', 'U']:
            nwb_dataset = nwb_dataset.astype('S')
        if expected_value.dtype.kind == 'S':
            np.testing.assert_array_equal(nwb_dataset, expected_value)
        else:
            np.testing.assert_allclose(nwb_dataset, expected_value, atol=1e-6)
    elif isinstance(expected_value, dict):
        if '_columns' in expected_value:
            compare_table(nwb_dataset, expected_value['_columns'], path)
        else:
            compare_references(nwb_dataset, expected_value, path)
    else:
        assert 0, 'Unexpected expected_value {!r}'.format(expected_value)


def compare_references(nwb_dataset, expected_value, path):
    """Compare an array of object/region references.

    It's hard to check region references, as we can't pull out the offset directly.
    But we do what we can!
    """
    print('checking ref', path)
    assert len(nwb_dataset) == len(expected_value['_targets']), 'Wrong array length at ' + path
    assert len(nwb_dataset) > 0
    first_ref = nwb_dataset[0]
    assert type(first_ref).__name__ == expected_value['_type'], 'Wrong reference type at ' + path
    # Check all references point to the correct dataset/group
    for i, ref in enumerate(nwb_dataset):
        assert current_file[ref].name == expected_value['_targets'][i], \
            'Reference at {} points to {} not {}'.format(
                path, current_file[ref].name, expected_value['_targets'][i])
    # For region references, do some content checking
    if expected_value['_type'] == 'RegionReference':
        for i, ref in enumerate(nwb_dataset):
            target = current_file[ref][ref]
            print('checking rref', current_file[ref].name, i)
            assert target.shape == tuple(expected_value['_shapes'][i]), \
                'Wrong shape at {} ref {}'.format(path, i)
            compare_generic_dataset(target, expected_value['_values'][i], path + '@{}'.format(i))


def compare_table(nwb_dataset, expected_columns, path):
    """Compare a structured dataset against expected column values."""
    assert nwb_dataset.dtype.kind == 'V', 'Not a table at {}'.format(path)
    for colname in expected_columns:
        assert colname in nwb_dataset.dtype.names, 'Missing column {} at {}'.format(
            colname, path)
        if isinstance(nwb_dataset, h5py.Dataset):
            nwb_dataset = nwb_dataset[()]
        col = nwb_dataset[colname]
        compare_generic_dataset(col, expected_columns[colname], path + '#' + colname)


def compare_device(nwb_dataset, expected_value, path):
    """Check that a dataset representing a Device has the expected contents."""
    # Temporarily disabled due to not knowing where to put the description...
    # assert nwb_dataset.attrs['source'] == expected_value, 'Mismatch at {}'.format(path)
    pass


def compare_datetime(nwb_dataset, expected_value, path):
    """Check that a dataset containing a timestamp has the expected contents.

    This may be overkill, but it insulates us against different systems writing
    the date in different format."""
    assert pd.Timestamp(nwb_dataset[()].decode()) == pd.Timestamp(expected_value),\
        'Mismatch at {}'.format(path)


def compare_dataset(nwb_dataset, expected_value, path):
    """Check an HDF5 dataset, accounting for the type of its contents."""
    if '/devices/' in path:
        compare_device(nwb_dataset, expected_value, path)
    elif path.endswith('session_start_time'):
        compare_datetime(nwb_dataset, expected_value, path)
    else:
        compare_generic_dataset(nwb_dataset, expected_value, path)


def test_metadata_only(tmpdir, capfd, ref_data_dir):
    fname = "test_metadata.nwb"
    with NwbFile(os.path.join(str(tmpdir), fname), mode='w') as nwb:
        speed_data, start_time = nwb.create_nwb_file(ref_data_dir, 'test_metadata')
        nwb.add_core_metadata()
    compare_hdf5(str(tmpdir.join(fname)), os.path.join(ref_data_dir, 'expected_meta_only.yaml'))


def test_epochs(tmpdir, capfd, ref_data_dir):
    fname = "test_epochs.nwb"
    nwb_path = os.path.join(str(tmpdir), fname)
    with NwbFile(nwb_path, mode='w') as nwb:
        speed_data, start_time = nwb.create_nwb_file(ref_data_dir, 'test_epochs')
        nwb.add_core_metadata()
        nwb.add_speed_data(speed_data, start_time)
        nwb.determine_trial_times()
    compare_hdf5(nwb_path, os.path.join(ref_data_dir, 'expected_epochs.yaml'))
