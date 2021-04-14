import datetime
import h5py
import os

from pynwb.ophys import ImagingPlane, TwoPhotonSeries, OpticalChannel, Device
from pynwb import NWBHDF5IO, NWBFile

with NWBHDF5IO('test_file.nwb', 'w') as io:
    params_file = h5py.File(os.path.join("data", "params.mat"))
    roi_file = h5py.File(os.path.join("data", "SkeletonScan_ROI_0002_repeat_0001_timepoints_1441.mat"))

    device = Device("Cam")  # todo where is device stored in Antoine's structure

    roi_number = 2
    origin_coords = params_file[params_file['vol/start_pixels'][roi_number][0]][()]  # vol/start_pixels hold HDF5 reference
    end_coords = params_file[params_file['vol/stop_pixels'][roi_number][0]][()]
    n_pixels_in_a_line = params_file['vol/res_list'][:,roi_number][0]
    grid_spacing = (end_coords-origin_coords)/n_pixels_in_a_line # todo this is incorrect for patches!

    plane = ImagingPlane(name="Zstack_ROI2_test",
                         optical_channel=OpticalChannel(name="red",
                                                        description="red channel",
                                                        emission_lambda=800.0), # todo where are wavelengths (excitation and emission!) stored
                         description="Imaging Plane for variable size ROI #2",
                         device=device,
                         excitation_lambda=500.0,
                         indicator="not specified",
                         location="not specified",
                         origin_coords=origin_coords,
                         origin_coords_unit="micrometres",
                         grid_spacing=grid_spacing,
                         grid_spacing_unit="micrometres",
                         reference_frame = 'TODO: In lab book (partly?)'
                         )
    roi_dimensions = roi_file['data'][0, 0, :].shape[::-1]
    pixel_size_in_m = params_file['vol/pxl_per_um'][()].flatten()/1e6
    ts = TwoPhotonSeries(name="ROI2_test_red",
                         data=roi_file['data'][0,:], # not sure whether index 0 is red or green, order is c,t,z,y,x, may want to reverse the order!
                         dimension=roi_dimensions,
                         field_of_view=roi_dimensions * pixel_size_in_m,
                         format='raw',
                         imaging_plane=plane,
                         timestamps=[0, 1, 2]  # todo where are timestamps and pixel_time_offsets found
                         )
    file = NWBFile(session_description="test session", identifier="test_id", session_start_time=datetime.datetime.now())
    file.add_device(device)
    file.add_imaging_plane(plane)
    file.add_acquisition(ts)
    io.write(file)
