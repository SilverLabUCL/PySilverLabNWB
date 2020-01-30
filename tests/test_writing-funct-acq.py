import pytest
from silverlabnwb import NwbFile
import os

DATA_PATH = os.environ.get('SILVERLAB_DATA_DIR', '')


@pytest.mark.skipif(
    not os.path.isdir(DATA_PATH),
    reason="raw data folder '{}' not present".format(DATA_PATH))
def test_all_funct_acq_writing():
    for subdirs in os.walk(DATA_PATH):
        if subdirs[0].endswith('21 FunctAcq'):
            import_folder_name = subdirs[0].split("\\")[-1]
            print("writing " + import_folder_name)
            with NwbFile(DATA_PATH + "\\" + import_folder_name + "-by-pysilverlab.nwb", mode='w') as nwb:
                nwb.import_labview_folder(subdirs[0])

    print("done with all.")


if __name__ == '__main__':
    test_all_funct_acq_writing()
