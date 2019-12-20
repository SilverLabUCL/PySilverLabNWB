=====
Usage
=====


Two main programs are provided: ``labview2nwb`` and ``nwb_metadata_editor``.

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

``nwb_metadata_editor`` runs the metadata editor in standalone mode.
It is useful for setting up details of new researchers or new experiments,
that can then be used quickly when importing experiment data.


Python library usage
====================

The main class is ``silverlabnwb.NwbFile`` defined in ``nwb_file.py``.
All its methods are documented with docstrings.

Quick examples::

    from silverlabnwb import NwbFile

    # Write a new file
    with NwbFile(nwb_path, mode='w') as nwb:
        nwb.import_labview_folder(labview_path)

    # Read an existing file
    with NwbFile(nwb_path) as nwb:
        print('Opened NWB with ID {}'.format(nwb['/identifier']))
