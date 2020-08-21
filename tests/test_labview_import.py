
import os

import h5py
import pytest

from silverlabnwb import NwbFile
from silverlabnwb.signature import SignatureGenerator

# Where to look for large raw data files
DATA_PATH = os.environ.get('SILVERLAB_DATA_DIR', '')


@pytest.fixture
def sig_gen():
    """A customised signature generator for large import tests."""
    sig_gen = SignatureGenerator()
    # The relative path changes on different systems
    sig_gen.ignore_path('/acquisition/.*/external_file')
    # This can be int32 or int64 depending on the Python version or operating system
    # but the schema defines its value as always 1.
    sig_gen.ignore_attribute('/(acquisition|stimulus)/.*/timestamps', 'interval')
    return sig_gen


@pytest.mark.skipif(
    os.environ.get('SILVERLAB_GEN_REF', '0') == '0',
    reason="SILVERLAB_GEN_REF not set or set to 0")
@pytest.mark.parametrize("nwb_name", [
    # Cut-down samples
    ('sample_pointing_videos_161215_15_34_21'),
    ('sample_pointing_fred_170317_10_11_01'),
    ('sample_miniscan_fred_170322_14_06_43'),
    ('sample_rois_200206_16_30_32'),
    # Full datasets
    ('161215_15_58_52'),
    ('161215_15_34_21'),
    ('170317_10_11_01'),
    ('170322_14_06_43'),
    ('161222_16_18_47'),
    ('170714_22_26_27')
])
def test_generate_signatures(ref_data_dir, sig_gen, nwb_name):
    """A 'test' to generate reference data for the tests below."""
    sig_path = os.path.join(ref_data_dir, nwb_name + '.sig2')
    if os.environ.get('SILVERLAB_REGEN_NWB', '0') != '0':
        nwb_path = os.path.join(DATA_PATH, 'nwb2', nwb_name + '.nwb')
        labview_path = os.path.join(DATA_PATH,
                                    nwb_name + ' FunctAcq' if nwb_name[0] == '1' else nwb_name)
        with NwbFile(nwb_path, mode='w') as nwb:
            nwb.import_labview_folder(labview_path)
    else:
        nwb_path = os.path.join(DATA_PATH, nwb_name + '.nwb')
    sig_gen.save_sig(nwb_path, sig_path)


@pytest.fixture
def do_import_test(tmpdir, ref_data_dir, sig_gen):
    def do_import_test(expt, add_suffix=False):
        """Helper method for tests below."""
        nwb_path = os.path.join(str(tmpdir), expt + '.nwb')
        labview_path = os.path.join(DATA_PATH, expt + ' FunctAcq' if add_suffix else expt)
        sig_path = os.path.join(ref_data_dir, expt + '.sig2')

        with NwbFile(nwb_path, mode='w') as nwb:
            nwb.import_labview_folder(labview_path)
        assert sig_gen.compare_to_sig(nwb_path, sig_path)
    return do_import_test


@pytest.mark.skipif(
    not os.path.isdir(DATA_PATH),
    reason="raw data folder '{}' not present".format(DATA_PATH))
class TestSampleImports(object):

    def test_hana_video(self, do_import_test):
        do_import_test('sample_pointing_videos_161215_15_34_21')

    def test_fred_pointing(self, do_import_test):
        do_import_test('sample_pointing_fred_170317_10_11_01')

    def test_fred_miniscan(self, do_import_test):
        do_import_test('sample_miniscan_fred_170322_14_06_43')

    def test_harsha_rois(self, do_import_test, monkeypatch):
        # For now we don't include any imaging data for this, so disable
        # that part of the code
        def do_nothing(*args):
            pass
        monkeypatch.setattr(NwbFile, "_write_roi_data", do_nothing)
        do_import_test('sample_rois_200206_16_30_32')


@pytest.mark.skipif(
    not os.path.isdir(DATA_PATH),
    reason="raw data folder '{}' not present".format(DATA_PATH))
@pytest.mark.skipif(
    os.environ.get('SILVERLAB_TEST_LONG_IMPORTS', '0') == '0',
    reason="SILVERLAB_TEST_LONG_IMPORTS not set or set to 0")
class TestFullImporting(object):

    def test_hana(self, do_import_test):
        """A sample dataset from Hana with no videos."""
        do_import_test('161215_15_58_52', True)

    def test_hana_video(self, do_import_test):
        """A sample dataset from Hana with videos."""
        do_import_test('161215_15_34_21', True)

    def test_fred_pointing(self, do_import_test):
        """A sample dataset from Fred with pointing mode data."""
        do_import_test('170317_10_11_01', True)

    def test_fred_patch(self, do_import_test):
        """A sample dataset from Fred with miniscans."""
        do_import_test('170322_14_06_43', True)


@pytest.mark.skipif(
    not os.path.isdir(DATA_PATH),
    reason="raw data folder '{}' not present".format(DATA_PATH))
def test_roundtrip(tmpdir, ref_data_dir):
    """A simple check that file written can be read back in.

    Currently this does not do anything besides ensure there are no failures.
    Reading could fail, for example, if the extension spec is not included
    in the NWB file by accident.
    """
    # Write one of the subsampled experiments to NWB
    expt = 'sample_pointing_fred_170317_10_11_01'
    nwb_path = os.path.join(str(tmpdir), expt + '.nwb')
    labview_path = os.path.join(DATA_PATH, expt)
    with NwbFile(nwb_path, mode='w') as nwb:
        nwb.import_labview_folder(labview_path)

    # You would think the below would be a good check, but actually not.
    # The extensions are already loaded (from writing the file) and I can't
    # find a way to remove them.
    # with pynwb.NWBHDF5IO(nwb_path, 'r', load_namespaces=True) as io:
    #     new_file = io.read()
    # Right now, just check that the file has been read without errors
    # assert isinstance(new_file, pynwb.NWBFile)

    # Since the above isn't a meaningful test, roughly check that we have
    # included the extension spec and custom medata in the file.
    with h5py.File(nwb_path, 'r') as new_file:
        assert 'silverlab_extended_schema' in new_file['specifications']
        assert 'silverlab_metadata' in new_file['general']
        assert 'silverlab_optophysiology' in new_file['general']
