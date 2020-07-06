import os

import pytest

from silverlabnwb import NwbFile
from silverlabnwb.signature import SignatureGenerator


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


def test_no_start_time_fails(tmpdir, ref_data_dir):
    fname = "test_metadata_import.nwb"
    nwb_path = os.path.join(str(tmpdir), fname)
    meta_path = os.path.join(ref_data_dir, 'meta_two_users.yaml')
    with pytest.raises(ValueError) as exc_info:
        with NwbFile(nwb_path, 'w') as nwb:
            nwb.create_from_metadata(meta_path, user="A")
    assert "Start time for session not found!" == str(exc_info.value)


def test_metadata_import_correct(tmpdir, ref_data_dir):
    fname = "metadata_only_B.nwb"
    nwb_path = os.path.join(str(tmpdir), fname)
    meta_path = os.path.join(ref_data_dir, 'meta_two_users.yaml')
    sig_path = os.path.join(ref_data_dir, 'metadata_only_B.sig2')
    with NwbFile(nwb_path, 'w') as nwb:
        nwb.create_from_metadata(meta_path, user="B")
    sig_gen = SignatureGenerator()
    if os.environ.get('SILVERLAB_GEN_REF', '0') != '0':
        sig_gen.save_sig(nwb_path, sig_path)
    assert sig_gen.compare_to_sig(nwb_path, sig_path)
