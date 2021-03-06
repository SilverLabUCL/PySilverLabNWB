#!/usr/bin/env python

"""A simple script to generate test datasets by subsampling.

Given a Labview export folder and previously imported NWB file,
it will generate a new 'export' folder with a subset of the ROIs
and trials from the original, and compressed videos/images.
"""


import argparse
import glob
import os
import subprocess

import av
import h5py
import nptdms
import numpy as np
from PIL import Image


def subsample_nwb(nwb, input_path, output_path, ntrials=2, nrois=10):
    """Create a subset of an NWB Labview structure for testing purposes.

    :param nwb: h5py.File for the input NWB
    :param output_path: folder to write output to
    :param ntrials: how many trials to include
    :param nrois: how many ROIs to include
    """
    print('Processing', nwb.filename)
    os.makedirs(output_path, exist_ok=True)
    # Copy truncated ROI.dat
    orig_nrois = copy_roi_dat(input_path, output_path, nrois)
    # Copy modified header
    copy_header(
        input_path, output_path,
        ntrials, nrois, orig_nrois)
    # Figure out time duration for given ntrials
    last_trial = nwb['/epochs/trial_{:04d}'.format(ntrials)]
    end_time = last_trial['stop_time'].value
    print('Trial {} ends at {}'.format(ntrials, end_time))
    # Copy truncated speed data
    copy_speed_data(input_path, output_path, last_trial)
    # Figure out which Zstack planes have ROIs
    zstack_planes = find_used_planes(nwb, nrois)
    # Copy pockels file
    copy_pockels_file(input_path, output_path, zstack_planes)
    # Copy & compress Zstack images
    copy_zstack(input_path, output_path, zstack_planes)
    # Copy subset of TDMS files
    tdms_path = 'Functional imaging TDMS data files'
    os.makedirs(os.path.join(output_path, tdms_path), exist_ok=True)
    for tr in range(1, ntrials + 1):
        tdms_name = '{:03d}.tdms'.format(tr)
        tdms_in = os.path.join(input_path, tdms_path, tdms_name)
        tdms_out = os.path.join(output_path, tdms_path, tdms_name)
        copy_tdms(nwb, tdms_in, tdms_out, nrois)
    # Find videos defined
    video_names = [name for name in nwb['/acquisition/timeseries'].keys()
                   if name.endswith('Cam')]
    print('Videos:', video_names)
    # Compress videos
    if video_names:
        video_output_path = output_path + ' VidRec'
        os.makedirs(video_output_path, exist_ok=True)
    for name in video_names:
        ts = nwb['/acquisition/timeseries/' + name]
        old_path = ts['external_file'][0].decode()
        new_path = os.path.join(video_output_path, os.path.basename(old_path))
        times = ts['timestamps'].value
        frames_to_keep = np.count_nonzero(times <= end_time)
        compress_video(old_path, new_path, frames_to_keep)


def find_used_planes(nwb, nrois):
    used_planes = set()
    seg_iface = nwb['/processing/Acquired_ROIs/ImageSegmentation']
    for plane_name in seg_iface.keys():
        plane_num = int(plane_name[-4:])
        for roi_name in seg_iface[plane_name].keys():
            if roi_name.startswith('ROI_'):
                roi_num = int(roi_name[4:])
                if roi_num <= nrois:
                    used_planes.add(plane_num)
    used_planes = list(used_planes)
    used_planes.sort()
    print('Relevant Zstack planes are:', used_planes)
    return used_planes


def copy_zstack(input_path, output_path, zstack_planes):
    dirname = 'Zstack Images'
    sources = glob.glob(os.path.join(input_path, dirname, '*Channel*.tif'))
    os.makedirs(os.path.join(output_path, dirname), exist_ok=True)
    for source in sources:
        dest = os.path.join(output_path, os.path.relpath(source, input_path))
        fname = os.path.basename(source)
        stack_index = int(fname.split('_')[1][:-4])
        if stack_index in zstack_planes:
            print('Copying frame {}'.format(fname))
            with Image.open(source) as im:
                im.save(dest, format='TIFF', compression='tiff_lzw')


def copy_speed_data(input_path, output_path, last_trial):
    fname = 'Speed_Data/Speed data 001.txt'
    os.makedirs(os.path.join(output_path, 'Speed_Data'), exist_ok=True)
    src = os.path.join(input_path, fname)
    dest = os.path.join(output_path, fname)
    speed_data_ts = last_trial['speed_data']
    end_index = speed_data_ts['idx_start'].value + speed_data_ts['count'].value
    copy_and_truncate(src, dest, end_index + 1)


def copy_pockels_file(input_path, output_path, zstack_planes):
    fname = 'Zplane_Pockels_Values.dat'
    with open(os.path.join(output_path, fname), 'wt') as outf:
        with open(os.path.join(input_path, fname), 'rt') as inf:
            plane_index = -5
            for line in inf:
                if plane_index < 1 or plane_index in zstack_planes:
                    outf.write(line)
                # plane_index += 1


def copy_header(input_path, output_path, ntrials, nrois, orig_nrois):
    def get_value(line):
        return float(line.split('=')[1].strip())
    roi_marker = 'number of poi'
    miniscan_marker = 'number of miniscans'
    trial_marker = 'number of trials'
    fname = 'Experiment Header.ini'
    src = os.path.join(input_path, fname)
    dest = os.path.join(output_path, fname)
    with open(dest, 'wt') as outf:
        with open(src, 'rt') as inf:
            for line in inf:
                if line.startswith(roi_marker):
                    if get_value(line) > 0:
                        # Pointing mode experiment
                        line = '{} = {}\n'.format(roi_marker, nrois)
                        new_nscans = nrois
                elif line.startswith(miniscan_marker):
                    n_scans = get_value(line)
                    if n_scans > 0:
                        # Patch mode experiment
                        new_nscans = n_scans / orig_nrois * nrois
                        line = '{} = {}\n'.format(miniscan_marker, new_nscans)
                elif line.startswith(trial_marker):
                    line = '{} = {}\n'.format(trial_marker, ntrials)
                outf.write(line)
    # Only `new_nscans` lines of cycle times are now needed
    cycle_fname = 'Single cycle relative times.txt'
    copy_and_truncate(os.path.join(input_path, cycle_fname),
                      os.path.join(output_path, cycle_fname),
                      int(new_nscans))


def copy_roi_dat(input_path, output_path, nrois):
    filename = 'ROI.dat'
    src = os.path.join(input_path, filename)
    dest = os.path.join(output_path, filename)
    copy_and_truncate(src, dest, nrois + 1)
    with open(dest, 'wt') as outf:
        with open(src, 'rt') as inf:
            for i in range(nrois + 1):
                outf.write(inf.readline())
            orig_nrois = nrois
            for line in inf:
                if line.strip():
                    orig_nrois += 1
    print('Retaining {} ROIs of {}'.format(nrois, orig_nrois))
    return orig_nrois


def copy_and_truncate(src, dest, nlines):
    print('Copying {} lines of {} to {}'.format(nlines, src, dest))
    with open(dest, 'wt') as outf:
        with open(src, 'rt') as inf:
            for i in range(nlines):
                outf.write(inf.readline())


def cycles_per_trial(nwb):
    """Get the number of microscope cycles/trial.

    That is, the number of times each point is imaged in each
    trial. Currently looks at the first imaging timeseries in
    the first trial, and assumes they're all the same.
    """
    trial1 = nwb['/epochs/trial_0001']
    for ts_name in trial1:
        ts = trial1[ts_name]
        is_image_series = ts['timeseries/pixel_time_offsets'] is not None
        if is_image_series:
            return ts['count'].value
    else:
        raise ValueError('No imaging timeseries found')


def copy_tdms(nwb, in_path, out_path, nrois):
    num_all_rois = nwb['/processing/Acquired_ROIs/roi_spec'].shape[0]
    print('Copying {} of {} ROIs from {} to {}'.format(
        nrois, num_all_rois, in_path, out_path))
    in_tdms = nptdms.TdmsFile(in_path)
    group_name = 'Functional Imaging Data'
    with nptdms.TdmsWriter(out_path) as out_tdms:
        root, group = in_tdms.object(), in_tdms.object(group_name)
        out_tdms.write_segment([root, group])
        for ch, channel in {'0': 'Red', '1': 'Green'}.items():
            ch_name = 'Channel {} Data'.format(ch)
            ch_obj = in_tdms.object(group_name, ch_name)
            shape = (cycles_per_trial(nwb), num_all_rois, -1)
            ch_data = ch_obj.data.reshape(shape)
            subset = ch_data[:, :nrois, :].reshape(-1)
            new_obj = nptdms.ChannelObject(group_name, ch_name, subset, properties={})
            out_tdms.write_segment([new_obj])


def compress_video(input_path, output_path, nframes, width=300):
    print('Compressing {} frames of "{}" to "{}"'.format(
        nframes, input_path, output_path))
    input_file = av.open(input_path)
    input_vid = input_file.streams.video[0]
    assert input_vid.frames >= nframes, 'Only {} frames present in video'.format(
        input_vid.frames)
    scale = input_vid.width / width
    height = int(round(input_vid.height / scale))
    if height % 2 == 1:
        height += 1
    print('Input {}x{} @ {}, {}'.format(
        input_vid.width, input_vid.height, input_vid.rate, input_vid.bit_rate))

    # Create a ffmpeg command line for the compression & resizing
    args = [
        'ffmpeg',
        '-i', input_path,
        '-y',
        '-frames:v', str(nframes),
        '-s', '{}x{}'.format(width, height),
        '-pix_fmt', 'yuvj420p',
        '-codec:v', 'mjpeg',
        output_path
    ]
    subprocess.check_call(args)

    # Copy truncated 'relative times' file
    base = os.path.basename(input_path).split('-')[0]
    times_name = base + '-relative times.txt'
    src = os.path.join(os.path.dirname(input_path), times_name)
    dest = os.path.join(os.path.dirname(output_path), times_name)
    copy_and_truncate(src, dest, nframes)


def create_parser():
    parser = argparse.ArgumentParser(
        description='Prepare subsampled test datasets for NWB import')
    parser.add_argument('input_id',
                        help='experiment ID to subsample')
    parser.add_argument('output_path',
                        help='output folder path to write')
    parser.add_argument('--nrois', '-r',
                        type=int, default=10,
                        help='number of ROIs to retain')
    parser.add_argument('--ntrials', '-t',
                        type=int, default=2,
                        help='number of trials to retain')
    return parser


def run():
    args = create_parser().parse_args()
    input_path = args.input_id + ' FunctAcq'
    nwb_path = args.input_id + '.nwb'
    with h5py.File(nwb_path, mode='r') as nwb:
        subsample_nwb(nwb, input_path, args.output_path,
                      nrois=args.nrois, ntrials=args.ntrials)


if __name__ == '__main__':
    run()
