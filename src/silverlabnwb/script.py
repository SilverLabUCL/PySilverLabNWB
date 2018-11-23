'''
Command-line entrypoints for the Silver Lab pipeline.
'''

import argparse

from .nwb_file import NwbFile
from .metadata_gui import run_editor
from .signature import SignatureGenerator


def import_labview():
    """Command line script to import a Labview folder to NWB format."""
    parser = argparse.ArgumentParser(description='Import Labview to NWB.')
    parser.add_argument('nwb_path',
                        help='path to the NWB file to write')
    parser.add_argument('labview_path',
                        help='path to the Labview folder to import')
    parser.add_argument('--no-gui', dest='gui', action='store_false',
                        help="don't show a GUI to edit metadata; just reuse the last session")
    parser.add_argument('--check-sig', action='store_true',
                        help="check the generated NWB file against an existing signature."
                        " This expects a .sig file to be present next to the .nwb file.")
    args = parser.parse_args()

    if args.gui:
        run_editor()

    with NwbFile(args.nwb_path, mode='w') as nwb:
        nwb.import_labview_folder(args.labview_path)

    if args.check_sig:
        import os
        sig_path = os.path.splitext(args.nwb_path)[0] + '.sig'
        if os.path.exists(sig_path):
            sig_gen = SignatureGenerator()
            print('Comparing against signature file {}'.format(sig_path))
            sig_gen.compare_to_sig(args.nwb_path, sig_path)
        else:
            parser.error('No signature file {} found'.format(sig_path))
