import os

import pytest

from silverlabnwb import NwbFile


def test_ambiguous_user_fails(tmpdir, ref_data_dir):
    fname = "test_metadata_import.nwb"
    nwb_path = os.path.join(str(tmpdir), fname)
    meta_path = os.path.join(ref_data_dir, 'meta_two_users.yaml')
    with pytest.raises(ValueError, match="Multiple users found in file."):
        with NwbFile(nwb_path, 'w') as nwb:
            nwb.create_from_metadata(meta_path)


def test_user_not_found_fails(tmpdir, ref_data_dir):
    fname = "test_metadata_import.nwb"
    nwb_path = os.path.join(str(tmpdir), fname)
    meta_path = os.path.join(ref_data_dir, 'meta_two_users.yaml')
    with pytest.raises(ValueError) as exc_info:
        with NwbFile(nwb_path, 'w') as nwb:
            nwb.create_from_metadata(meta_path, user="Mr Faker")
    assert "No session information found for user" in str(exc_info.value)

