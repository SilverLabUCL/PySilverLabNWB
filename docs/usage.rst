=====
Usage
=====


Three main programs are provided: ``labview2nwb``, ``metadata2nwb`` and ``nwb_metadata_editor``.

``labview2nwb`` imports Labview data to the NWB format.
You need to provide it the path to the NWB file to create,
and the path to the folder containing Labview data.
At present it assumes that video data is in a folder adjacent to the Labview data;
this will be made more flexible in the future.

For more details on usage run with the ``-h`` flag, i.e.::

    labview2nwb -h

By default the import process will start by running a simple graphical editor,
allowing you to input metadata required or recommended by the NWB format,
but that is not available within the Labview data folder.

``metadata2nwb`` creates a 'bare bones' NWB file by loading metadata describing
an experiment from a YAML file. You need to provide it the path to the NWB file
to create, the path to the metadata YAML file and optionally the user. If the
metadata YAML file contains more than one user, the user must be specified. An
example for a metadata YAML file can be found on the `PySilverLabNWB Github directory`__.
Metadata YAML files are intended to be created, read and modified by users to quickly
set up a new NWB file without having to go via the metadata editor.

__ https://github.com/SilverLabUCL/PySilverLabNWB/blob/master/tests/data/meta_two_users.yaml

``nwb_metadata_editor`` runs the metadata editor in standalone mode.
It is useful for setting up details of new researchers or new experiments,
that can then be used quickly when importing experiment data.


Python library usage
====================

The main class is ``silverlabnwb.NwbFile`` defined in ``nwb_file.py``.
All its methods are documented with docstrings. There are two entry points,
``import_labview_folder`` and ``create_from_metadata``, which mirror the first
two command line tools described above.

Quick examples::

    from silverlabnwb import NwbFile

    # Write a new file from a LabView folder
    with NwbFile(nwb_path, mode='w') as nwb:
        nwb.import_labview_folder(labview_path)

    # Write a new file from metadata
    with NwbFile(nwb_path, mode='w') as nwb:
        nwb.create_from_metadata(metadata_path, user, session_id)

    # Read an existing file
    with NwbFile(nwb_path) as nwb:
        print('Opened NWB with ID {}'.format(nwb['/identifier']))

