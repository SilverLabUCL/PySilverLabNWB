from datetime import datetime
from enum import Enum
import glob
import os
import pkg_resources
import tempfile

import av
import h5py
from nptdms import TdmsFile
import numpy as np
import pandas as pd
from pytz import timezone
import tifffile

from pynwb import NWBFile
from pynwb import NWBHDF5IO
from pynwb import TimeSeries
from pynwb.file import Subject
from pynwb.image import ImageSeries
from pynwb.ophys import ImageSegmentation, OpticalChannel, TwoPhotonSeries

from . import metadata


class Modes(Enum):
    """Scanning modes supported by the AOL microscope."""
    pointing = 1
    miniscan = 2
    patch = 2
    volume = 3


class NwbFile():
    """Silver Lab wrapper for the NWB data format.data

    Designed to be used as a context manager, i.e. do something like:
    >>> with NwbFile(output_file_path) as nwb:
    ...     nwb.import_labview_folder(folder_path)

    However, there is also an explicit close() method, and this will be called
    when the object is deleted.

    Once a file has been opened, two main access mechanisms are provided:
    - nwb.nwb_file - the NWB API interface to the file
    - nwb.hdf_file - the h5py interface to the file

    You can also access nodes within the file using dictionary-style access, e.g.
    `nwb['/path/to/node']`.
    """

    SILVERLAB_NWB_VERSION = '0.2'

    def __init__(self, nwb_path, mode='r', verbose=True):
        """Create an interface to an NWB file.

        :param nwb_path: the NWB file to access
        :param mode: mode of file access. As for the NWB API, must be one of:
            'r'  - Readonly, file must exist
            'r+' - Read/write, file must exist
            'w'  - Create file, replacing if exists
            'w-' - Create file, fail if exists
            'a'  - Read/write if exists, create otherwise
        :param verbose: if True, print status information as processing happens
        """
        self.verbose = verbose
        self.nwb_file = None
        self.nwb_path = nwb_path
        assert mode in {'r', 'r+', 'w', 'w-', 'a'}
        self.nwb_open_mode = mode
        if mode in {'r', 'r+'} or (mode == 'a' and os.path.isfile(nwb_path)):
            self.open_nwb_file()

    def import_labview_folder(self, folder_path):
        """Import all data from a Labview export folder into this NWB file.

        This calls three helper methods to do most of the work, to support unit tests
        of just parts of the import code.

        This will automatically import video data only if the video folder is adjacent to
        the main labview folder, with the same name but having ' VidRec' appended. If you
        use a different layout you will need to call read_video_data() separately.

        :param folder_path: the folder to import
        """
        assert os.path.isdir(folder_path)
        folder_name = os.path.basename(folder_path)
        session_id = folder_name.split(' ')[0]  # Drop the ' FunctAcq' part
        self.log('Importing Labview session', session_id, 'from', folder_path)
        speed_data, expt_start_time = self.create_nwb_file(folder_path, session_id)
        self.add_core_metadata()
        self.import_labview_data(folder_path, folder_name, speed_data, expt_start_time)
        self.log('All data imported')

    @property
    def hdf_file(self):
        """Access the h5py interface to this NWB file."""
        assert self.nwb_file is not None
        # TODO Should we check if the file is still open? Or perhaps
        # turn this into a real field?
        return h5py.File(self.nwb_path, self.nwb_open_mode)

    def __getitem__(self, name):
        """Provide access to nodes within this file just like h5py does.

        :param name: full path (within the file) of the HDF5 node to access
        """
        return self.hdf_file[name]

    def open_nwb_file(self):
        """Open an existing NWB file for reading and optionally modification.

        TODO: If allowing modification then the copy_append setting defaults to True and
        we can't modify it via nwb_file.open - we'd need to call the underlying routines
        directly if we want to avoid copying the original file! However, this copying
        behaviour does guard against data corruption, so might well be desirable.
        """
        self.log("Opening file {}", self.nwb_path)
        with NWBHDF5IO(self.nwb_path, 'r') as io:
            self.nwb_file = io.read()

    def create_nwb_file(self, folder_path, session_id):
        """Create a new NWB file and add general lab/session metadata.

        :param folder_path: the Labview folder to import
        :param session_id: the unique session ID for this experiment
        :returns: (speed_data, expt_start_time) for passing to import_labview_data
        """
        def rel(file_name):
            """Return the path of a file name relative to the Labview folder."""
            return os.path.join(folder_path, file_name)
        # Check we're allowed to create a new file
        if not (self.nwb_open_mode == 'w' or (self.nwb_open_mode in {'a', 'w-'} and
                                              not os.path.isfile(self.nwb_path))):
            raise ValueError('Not allowed to create/overwrite {} in mode {}'.format(
                self.nwb_path, self.nwb_open_mode))
        # Figure out the metadata required when creating a new NWB file
        self.read_user_config()
        header_fields = self.parse_experiment_header_ini(rel('Experiment Header.ini'))
        speed_data, expt_start_time = self.read_speed_data(rel('Speed_Data/Speed data 001.txt'))
        localized_start_time = expt_start_time.tz_localize(timezone('Europe/London'))
        # Create the NWB file
        extensions = ["e-labview.py", "e-pixeltimes.py"]
        for i, ext in enumerate(extensions):
            extensions[i] = pkg_resources.resource_filename(__name__, ext)
        nwb_settings = {
            'session_start_time': localized_start_time.to_pydatetime(),
            'identifier': "{}; {}".format(session_id, datetime.now()),
            'session_description': self.session_description,
            'session_id': session_id,
        }
        self.nwb_file = NWBFile(**nwb_settings)
        # TODO Incorporate extensions according to new API
        self.add_labview_header(header_fields)
        # For potential future backwards compatibility, store the 'version' of this API
        # that created the file.
        # TODO Change this to use an extension instead of a custom dataset
        # self.nwb_file.set_custom_dataset('/silverlab_api_version', self.SILVERLAB_NWB_VERSION)
        # Write the new NWB file
        self._write()
        return speed_data, expt_start_time

    def add_core_metadata(self):
        """Add core metadata from the YAML config file to the NWB file.

        This fills in many of the fields in /general.
        """
        self.add_general_info('experimenter', self.user['name'])  # TODO: Add ORCID etc.
        self.add_general_info('experiment_description', self.experiment['description'])
        self.add_general_info('institution', 'University College London')
        self.add_general_info('lab', 'Silver Lab (http://silverlab.org)')
        self.add_devices_info()
        for field in ['data_collection', 'pharmacology', 'protocol', 'slices',
                      'surgery', 'virus', 'related_publications', 'notes']:
            if field in self.experiment:
                self.add_general_info(field, self.experiment[field])
        # Stimulus information is now accessed as `stimulus_notes` in the API,
        # even though it is still stored under /general/stimulus
        if 'stimulus' in self.experiment:
            self.add_general_info('stimulus_notes', self.experiment['stimulus'])
        if 'subject' in self.experiment:
            self.add_subject(self.experiment['subject'])
        # Update the file on disk:
        self._write()

    def add_subject(self, subject_data):
        """Add the subject information from YAML config to the NWB file."""
        subject = Subject(**subject_data)
        self.add_general_info('subject', subject)

    def import_labview_data(self, folder_path, folder_name, speed_data, expt_start_time):
        """Import the bulk of the Labview data to NWB.

        :param folder_path: the Labview folder to import
        :param folder_name: the name of the Labview folder
        :param speed_data: mouse speed data
        :param expt_start_time: when the experiment started
        """
        def rel(file_name):
            """Return the path of a file name relative to the Labview folder."""
            return os.path.join(folder_path, file_name)
        self.add_speed_data(speed_data, expt_start_time)
        self.determine_trial_times()
        self.add_stimulus()
        self.read_cycle_relative_times(rel('Single cycle relative times.txt'))
        self.read_zplane(rel('Zplane_Pockels_Values.dat'))
        self.read_zstack(rel('Zstack Images'))
        self.add_rois(rel('ROI.dat'))
        self.read_functional_data(rel('Functional imaging TDMS data files'))
        video_folder = os.path.join(os.path.dirname(folder_path), folder_name + ' VidRec')
        if os.path.isdir(video_folder):
            self.read_video_data(video_folder)

    def __enter__(self):
        """Return this object itself as a context manager."""
        return self

    def __exit__(self, type, value, traceback):
        """Close the NWB file when the context is exited."""
        self.close()

    def __del__(self):
        """Close the NWB file when this object is destroyed."""
        self.close()

    def close(self):
        """Close our NWB file. Note that any unwritten changes will be lost."""
        self.nwb_file = None

    def log(self, msg_template, *args, **kwargs):
        """Log status information if in verbose mode.

        :param msg_template: message to log, optionally with {} placeholders
        :param args: positional arguments to pass to msg_template.format
        :param kwargs: keyword arguments to pass to msg_template.format
        """
        if self.verbose:
            import time
            timestamp = time.strftime('%H:%M:%S ')
            print(timestamp + msg_template.format(*args, **kwargs))

    def read_user_config(self):
        """Read the user configuration YAML files.

        We first read the default configuration supplied with this package.
        Then we look in the user_config_dir (as defined by appdirs) for any
        machine- & user-specific configuration settings, which override the
        defaults.
        """
        if os.path.isfile(metadata.user_conf_path):
            self.log('Reading user metadata from {}', metadata.user_conf_path)
        self.user_metadata = metadata.read_user_config()
        return self.user_metadata

    def add_general_info(self, label, value):
        """Add a general piece of information about the experiment."""
        # In the new API version, most labels are now attributes of the NWB file
        # itself (including experiment_description, lab, and others). However,
        # it appears that the file object also supports assignment of arbitrary
        # attributes, so we do not need to check the label here. The only case
        # that causes a problem is when we set an attribute that is already set,
        # which raises an AttributeError. The error message there is clear
        # enough that I don't think we need to raise a more specific exception.
        setattr(self.nwb_file, label, value)

    def add_devices_info(self):
        """Populate /general/devices with information about the rig.

        The names and descriptions of devices are taken from the metadata config file.
        """
        for device_name, desc in self.user_metadata['devices'].items():
            if not device_name.endswith('Cam'):
                # Calling create_device immediately adds the new device to the
                # NWB file
                # HACK We're adding the description where the source should go,
                # since the "help" attribute (which seems a better fit for it)
                # will not retain any overwritten value in the written-out file.
                # Oddly, this still works even after the "source" attribute was
                # removed from the API (although the description is not written
                # out to file).
                self.nwb_file.create_device(device_name, desc)

    def parse_experiment_header_ini(self, filename):
        """Read the LabView .ini file and store fields for later processing.

        The information will be stored in self.labview_header as a nested dict
        for easy access of key fields later. Those fields that are numbers will be
        stored as floating point values; everything else will be strings. Values given
        in double quotes will have the quotes removed.

        This method also uses the header info to set self.mode, which stores the
        type of imaging being performed, and figure out which user's metadata to load.

        :param filename: path to the Labview header
        :returns: the raw Labview fields as a list of lists of strings
        """
        self.log('Parsing Labview header {}', filename)
        ini = open(filename, 'r')
        fields = []
        section = ''
        self.labview_header = header = {}
        for line in ini:
            line = line.strip()
            if len(line) > 0:
                if line.startswith('['):
                    section = line[1:-1]
                    header[section] = {}
                elif '=' in line:
                    words = line.split('=')
                    key, value = words[0].strip(), words[1].strip()
                    fields.append([section, key, value])
                    try:
                        value = float(value)
                    except ValueError:
                        pass
                    if isinstance(value, str) and value[0] == value[-1] == '"':
                        value = value[1:-1]
                    header[section][key] = value
        # Use the header to determine what kind of imaging is being performed.
        if header['GLOBAL PARAMETERS']['number of poi'] > 0:
            self.mode = Modes.pointing
        elif header['GLOBAL PARAMETERS']['number of miniscans'] > 0:
            self.mode = Modes.miniscan
        else:
            raise ValueError('Unsupported imaging type: numbers of poi and miniscans are zero.')
        # Use the user specified in the header to select default session etc. metadata
        user = header['LOGIN']['User']
        if user not in self.user_metadata['sessions']:
            if 'last_session' in self.user_metadata:
                self.log("Labview user '{}' not found in metadata;"
                         " using last session by '{}' instead.",
                         user, self.user_metadata['last_session'])
                user = self.user_metadata['last_session']
            else:
                raise ValueError("No session information found for user '{}' - please edit the"
                                 " metadata.yaml file to include their details.".format(user))
        if user not in self.user_metadata['people']:
            raise ValueError("No information found for user '{}' - please edit the metadata.yaml"
                             " file to include their details.".format(user))
        self.user = self.user_metadata['people'][user]
        expt = self.user_metadata['sessions'][user]['experiment']
        if expt not in self.user_metadata['experiments']:
            raise ValueError("Experiment '{}' not found in metadata.yaml.".format(expt))
        self.experiment = self.user_metadata['experiments'][expt]
        self.session_description = self.user_metadata['sessions'][user]['description']
        return fields

    def add_labview_header(self, fields):
        """Add the Labview header fields verbatim to the NWB file.

        We use a fixed length ASCII string array, null-padded to the length of the longest
        string, at /general/labview_header. This is defined by one of our NWB extensions.
        It is likely to be the most portable representation for this kind of data.

        :param fields: the raw Labview headers as a list of 3-element lists of strings
        """
        self.add_general_info("labview_header", fields)  # TODO use the extension

    def add_time_series_data(self, label, data, times, ts_attrs={}, data_attrs={},
                             kind=TimeSeries):
        """Create a basic acquisition timeseries and add to the NWB file.

        :param label: Name of the group within /acquisition/timeseries.
        :param data: The data array.
        :param times: The timestamps array.
        :param ts_attrs: Any attributes for the timeseries group itself.
        :param data_attrs: Any attributes for the data array.
        :param kind: The class of timeseries to create, e.g. TwoPhotonSeries.
        :returns: The new timeseries group.
        """
        all_attrs = dict(ts_attrs)
        all_attrs.update(data_attrs)
        ts = kind(name=label, data=data, timestamps=times, **all_attrs)
        return self.nwb_file.add_acquisition(ts)

    def read_speed_data(self, file_name):
        """Read acquired speed data from the raw data file.

        The columns in the file are:
         - Date as MM/DD/YYYY
         - Time at HH:MM:SS.UUUUUU
         - Microseconds since start of trial
         - Speed in rpm (1 rpm = 50 cm/s), always negative!
         - Unsure; seems to be unused

        The date & time columns give the global experiment time. The third column is used
        to identify where trials begin & end. It will reset both at the end of one trial,
        then again at the start of the next, giving a short period of 'junk' data inbetween.

        :param file_name: path to the file
        :returns: (speed_data, initial_time), where speed_data is the file contents as a
        Pandas data table, and initial_time is the experiment start time, which sets the
        session_start_time for the NWB file.
        """
        self.log('Loading speed data from {}', file_name)
        assert os.path.isfile(file_name)
        speed_data = pd.read_table(file_name, header=None, usecols=[0, 1, 2, 3], index_col=0,
                                   names=('Date', 'Time', 'Trial time', 'Speed'),
                                   dtype={'Trial time': np.int32, 'Speed': np.float32},
                                   parse_dates=[[0, 1]],  # Combine first two cols
                                   dayfirst=True, infer_datetime_format=True,
                                   memory_map=True)
        initial_offset = pd.Timedelta(microseconds=speed_data['Trial time'][0])
        initial_time = speed_data.index[0] - initial_offset
        return speed_data, initial_time

    def add_speed_data(self, speed_data, initial_time):
        """Add acquired speed data the the NWB file.

        Creates the /acquisition/speed_data and
        /acquisition/trial_times groups.

        :param speed_data: raw speed data loaded from file by read_speed_data(), as a
        Pandas data table
        :param initial_time: experiment start time, from read_speed_data()
        """
        rel_times = (speed_data.index - initial_time).total_seconds().values
        ts_attrs = {'description': 'Raw mouse speed data.',
                    'comments': 'Speed is in rpm, with conversion factor to cm/s specified.'}
        speed_attrs = {'unit': 'cm/s', 'conversion': 50.0 / 60.0, 'resolution': 0.001 * 50 / 60}
        time_attrs = {'unit': 'second', 'conversion': 1e6, 'resolution': 1e-6}
        self.add_time_series_data('speed_data', speed_data['Speed'].values, rel_times,
                                  ts_attrs=ts_attrs, data_attrs=speed_attrs)
        ts_attrs['description'] = 'Per-trial times for mouse speed data.'
        self.add_time_series_data('trial_times', speed_data['Trial time'].values, rel_times,
                                  ts_attrs=ts_attrs, data_attrs=time_attrs)
        self._write()

    def get_times(self, timeseries):
        """Get the timestamps for a timeseries as a numpy array.

        Will handle both the case where there is a 'timestamps' attribute, and the case where
        these must be determined from 'starting_time' and rate.

        :param timeseries: the timeseries
        """
        if timeseries.timestamps is not None:
            t = np.array(timeseries.timestamps)
        else:
            n = timeseries.num_samples
            t0 = timeseries.starting_time
            rate = timeseries.rate
            t = t0 + np.arange(n) / rate
        return t

    def determine_trial_times(self):
        """Use the acquired speed data to determine the start & end times for each trial.

        Each trial will be defined as an epoch within the NWB file, and the relevant portions
        of the speed data linked to these.  The epochs will be named 'trial_0001' etc.

        Trials are identified by the resets in the 'trial_times' timeseries.  This stores
        the relative times for each speed reading within a single trial.  Hence when it
        resets (i.e. one entry is less than the one before) this marks the end of a trial.
        There is a short interval between trials which still has speed data recorded, so it's
        the second reset which marks the start of the next trial.
        """
        self.log('Calculating trial times from speed data')
        trial_times_ts = self.nwb_file.get_acquisition('trial_times')
        speed_data_ts = self.nwb_file.get_acquisition('speed_data')
        trial_times = np.array(trial_times_ts.data)
        # Prepend -1 so we pick up the first trial start
        # Append -1 in case there isn't a reset recorded at the end of the last trial
        deltas = np.ediff1d(trial_times, to_begin=-1, to_end=-1)
        # Find resets and pair these up to mark start & end points
        reset_idxs = (deltas < 0).nonzero()[0].copy()
        assert reset_idxs.ndim == 1
        num_trials = reset_idxs.size // 2   # Drop the extra reset added at the end if
        reset_idxs.resize((num_trials, 2))  # it's not needed
        reset_idxs[:, 1] -= 1  # Select end of previous segment, not start of next
        # Index the timestamps to find the actual start & end times of each trial. The start
        # time is calculated using the offset value in the first reading within the trial.
        rel_times = self.get_times(trial_times_ts)
        epoch_times = rel_times[reset_idxs]
        epoch_times[:, 0] -= trial_times[reset_idxs[:, 0]] * 1e-6
        # Create the epochs in the NWB file
        # Note that we cannot pass the actual start time to nwb_file.add_epoch since it
        # would add the last previous junk speed reading to the start of the next trial,
        # since they have exactly the same timestamp. We therefore cheat and pass the next
        # floating point value after that time, instead.
        # We also massage the end time since otherwise data points at exactly that time are
        # omitted.
        expected_counts = np.diff(reset_idxs) + 1
        self.nwb_file.add_epoch_column('name', 'the name of the epoch')
        for i, (start_time, stop_time) in enumerate(epoch_times):
            assert stop_time > start_time >= 0
            trial = 'trial_{:04d}'.format(i + 1)
            self.nwb_file.add_epoch(
                name=trial,
                start_time=start_time if i == 0 else np.nextafter(start_time, stop_time),
                stop_time=np.nextafter(stop_time, stop_time * 2),
                timeseries=[speed_data_ts])
            # We also record exact start & end times in the trial table, since our epochs
            # correspond to trials.
            self.nwb_file.add_trial(start_time=start_time, stop_time=stop_time)
        self._write()

    def add_stimulus(self):
        """Add information about the stimulus presented.

        This is taken from the metadata.yaml at present, since Labview does not record this
        information.

        This adds a TimeSeries group to /stimulus/presentation containing the timings of air
        puffs. At present the stimulus is always presented at the same time within each trial,
        so the only argument is the delay from the start of the trial until the puff. The 'data'
        for this time series is simply the text 'puff' at each occasion.
        """
        for stim in self.experiment['stimulus_details']:
            attrs = {
                'name': stim['name'],
                'description': stim['description'],
                'comments': stim['comments'],
                'unit': 'n/a',
                'conversion': float('nan'),
                'resolution': float('nan')
            }
            # TODO We can maybe build puffs and times a bit more efficiently or
            # in fewer steps, although it probably won't make a huge difference
            # (eg we can now get all the times with a single indexing expression)
            num_epochs = len(self.nwb_file.epochs)
            puffs = [u'puff'] * num_epochs
            times = np.zeros((len(puffs),), dtype=np.float64)
            for i in range(num_epochs):
                times[i] = self.nwb_file.epochs[i, 'start_time'] + stim['trial_time_offset']
            attrs['timestamps'] = times
            attrs['data'] = puffs
            self.nwb_file.add_stimulus(TimeSeries(**attrs))
        self._write()

    def read_cycle_relative_times(self, file_path):
        """Read the 'Single cycle relative times.txt' file and store the values in memory.

        Note that while the file has times in microseconds, we convert to seconds for consistency
        with other timestamps in NWB.
        """
        assert os.path.isfile(file_path)
        self.cycle_relative_times = pd.read_table(file_path, names=('RelativeTime', 'CycleTime'),
                                                  dtype=np.float64) / 1e6

    def read_functional_data(self, folder_path):
        """Import functional data from Labview TDMS files.

        The folder contains files named like like "NNN.tdms", where NNN gives the trial number.
        These files are thus per-trial, but a TimeSeries needs to contain all trials. We link to
        portions corresponding to single trials from epochs.

        Each file contains data for 2 channels in the group 'Functional Imaging Data', where
        'Channel 0 Data' is Red and 'Channel 1 Data' is Green. Each channel contains data for all
        pixels in all ROIs for all time within that trial, as a single 1d array. Within this array,
        we have data first for all pixels in the first ROI at time 0, then the second ROI at time
        0, and so on through all ROIs, before moving to data from the next cycle. For 2d ROIs, it
        scans first over the X dimension then over Y.

        While it might seem that this data is well suited to become RoiResponseSeries within
        /processing/Acquired_ROIs/Fluoresence, that time series type assumes a single value per
        ROI per time, which doesn't support storing raw data from multi-pixel ROIs. Instead,
        the data will be stored within /acquisition, in TwoPhotonSeries named like ROI_NNN_Green,
        where NNN is the global (not per-imaging-plane) ROI number.

        We define the ROIs within their imaging planes first, storing zeros for the data, then
        read each TDMS file to fill in real recordings. The channel data will have its dimensions
        permuted to match the NWB (t, z, y, x) arrangement, and be stored in the appropriate
        segment of the timeseries. At present all ROIs are 2d (or less, but can be represented as
        such with length 1 dimensions), however this structure allows for extension to 3d in the
        future.

        The single cycle time (self.cycle_relative_times['CycleTime'][0]) gives you the difference
        in acquisition time between successive lines in a file. Time starts at the beginning of
        the trial (epoch in NWB speak). This is the time to record in the timestamps field. Note
        that even though these are evenly spaced we can't use starting_time and rate, since this
        would not account for time between trials.
        """
        self.log('Loading functional data from {}', folder_path)
        assert os.path.isdir(folder_path)
        # Figure out timestamps, measured in seconds
        epoch_names = self.nwb_file.epochs[:, 'name']
        trials = [int(s[6:]) for s in epoch_names]  # names start with 'trial_'
        cycles_per_trial = int(self.labview_header['GLOBAL PARAMETERS']['number of cycles'])
        num_times = cycles_per_trial * len(epoch_names)
        cycle_time = self.cycle_relative_times['CycleTime'][0]
        single_trial_times = np.arange(cycles_per_trial) * cycle_time
        times = np.zeros((num_times,), dtype=float)
        # TODO Perhaps this loop can be vectorised
        for i in range(len(epoch_names)):
            trial_start = self.nwb_file.epochs[i, 'start_time']
            times[i * cycles_per_trial:
                  (i + 1) * cycles_per_trial] = single_trial_times + trial_start
        # TODO This requires an extension
        # opto = self.nwb_file.make_group('optophysiology', abort=False)
        # opto.set_custom_dataset('cycle_time', cycle_time)

        # Prepare attributes for timeseries groups and datasets (common to all instances)
        data_attrs = {'unit': 'intensity', 'conversion': 1.0, 'resolution': float('NaN')}
        ts_desc_template = 'Fluorescence data acquired from the {channel} channel in {roi_name}.'
        ts_attrs = {'comments': 'The AOL microscope can acquire just the pixels comprising defined'
                                ' ROIs. This timeseries records those pixels over time for a'
                                ' single ROI & channel.'}
        gains = {'Red': self.labview_header['GLOBAL PARAMETERS']['pmt 1'],
                 'Green': self.labview_header['GLOBAL PARAMETERS']['pmt 2']}
        # Iterate over ROIs, which are nested inside each imaging plane section
        all_rois = {}
        seg_iface = self.nwb_file.modules['Acquired_ROIs'].get_data_interface()
        for plane_name, plane in seg_iface.plane_segmentations.items():
            self.log('  Defining ROIs for plane {}', plane_name)
            # ROIs are added using an integer id, but they are retrieved using
            # their index into the table, which does not necessarily correspond
            # to the id (in our case, ids start from 1 and indices from 0). See:
            # https://github.com/NeurodataWithoutBorders/pynwb/issues/673
            for roi_num, roi_ind in self.roi_mapping[plane_name].items():
                roi_name = 'ROI_{:03d}'.format(roi_num)
                all_rois[roi_num] = {}
                for ch, channel in {'A': 'Red', 'B': 'Green'}.items():
                    # Set zero data for now; we'll read the real data later
                    # TODO: The TDMS uses 64 bit floats; we may not really need that precision!
                    # The exported data seems to be rounded to unsigned ints. Issue #15.
                    roi_dimensions = plane[roi_ind, 'dimensions']
                    data_shape = np.concatenate((roi_dimensions, [num_times]))[::-1]
                    data = np.zeros(data_shape, dtype=np.float64)
                    # Create the timeseries object and fill in standard metadata
                    ts_name = 'ROI_{:03d}_{}'.format(roi_num, channel)
                    ts_attrs['description'] = ts_desc_template.format(channel=channel.lower(),
                                                                      roi_name=roi_name)
                    data_attrs['dimension'] = roi_dimensions
                    data_attrs['format'] = 'raw'
                    data_attrs['bits_per_pixel'] = 64
                    pixel_size_in_m = (self.labview_header['GLOBAL PARAMETERS']['field of view'] /
                                       1e6 /
                                       int(self.labview_header['GLOBAL PARAMETERS']['frame size']))
                    data_attrs['field_of_view'] = roi_dimensions * pixel_size_in_m
                    data_attrs['imaging_plane'] = plane.imaging_plane
                    data_attrs['pmt_gain'] = gains[channel]
                    data_attrs['scan_line_rate'] = 1 / cycle_time
                    # TODO The below are not supported, so will require an extension
                    # However, they can be extracted by the name of the TimeSeries
                    # or by looking into the corresponding ROI.
                    # ts.set_custom_dataset('roi_name', roi_name)
                    # ts.set_custom_dataset('channel', channel)
                    # # Save the time offset(s) for this ROI, as a link
                    # ts.set_dataset('pixel_time_offsets', 'link:' + roi['pixel_time_offsets'].name)
                    ts = self.add_time_series_data(ts_name, data=data, times=times,
                                                   kind=TwoPhotonSeries,
                                                   ts_attrs=ts_attrs, data_attrs=data_attrs)
                    # Store the path where these data should go in the file
                    all_rois[roi_num][channel] = '/acquisition/{}/data'.format(ts_name)
                    # Link to these data within the epochs
                    # TODO This will need converting to the new API, which is less flexible.
                    # Do we need to add these timeseries before we create the epochs?
                    # This is kind of a chicken-and-egg problem, as we need the
                    # epoch information for the above calculations (although it
                    # does need not to be stored in the NWBFile epochs yet)
                    # for trial, epoch_name in enumerate(epoch_names):
                    #     epoch = self.nwb_file.get_node('/epochs/' + epoch_name)
                    #     series_ref_in_epoch = epoch.make_group('<timeseries_X>', ts_name)
                    #     series_ref_in_epoch.set_dataset('idx_start', trial * cycles_per_trial)
                    #     series_ref_in_epoch.set_dataset('count', cycles_per_trial)
                    #     series_ref_in_epoch.make_group('timeseries', ts)
        # We need to write the zero-valued timeseries before editing them!
        self._write()
        # The shape to put the TDMS data in for more convenient indexing
        # TODO Are the roi_dimensions always the same across ROIs? (it seems that
        # this was the implication from the previous version of the code, as it
        # always used the last value of roi_dimensions - but that may be a bug?)
        ch_data_shape = np.concatenate((roi_dimensions,
                                       [len(all_rois), cycles_per_trial]))[::-1]
        self._write_roi_data(all_rois, len(trials), cycles_per_trial, ch_data_shape, folder_path)

    def _write_roi_data(self, all_rois, num_trials, cycles_per_trial,
                        ch_data_shape, folder_path):
        """Edit the NWB file directly to add the real ROI data."""
        with h5py.File(self.nwb_path, 'a') as out_file:
            # Iterate over trials, reading data from the TDMS file for each
            for trial_index in range(num_trials):
                self.log('  Reading TDMS {}', trial_index + 1)
                file_path = os.path.join(folder_path, '{:03d}.tdms'.format(trial_index + 1))
                tdms_file = TdmsFile(file_path,
                                     memmap_dir=tempfile.gettempdir())
                time_segment = slice(trial_index * cycles_per_trial,
                                     (trial_index + 1) * cycles_per_trial)
                for ch, channel in {'0': 'Red', '1': 'Green'}.items():
                    # Reshape the TDMS data into an nd array
                    # TODO: Consider precision: the round() here is to match the exported data...
                    ch_data = np.round(tdms_file.channel_data('Functional Imaging Data',
                                                              'Channel {} Data'.format(ch)))
                    ch_data = ch_data.reshape(ch_data_shape)
                    # Copy each ROI's data into the NWB
                    for roi_num, data_paths in all_rois.items():
                        channel_path = out_file[data_paths[channel]]
                        channel_path[time_segment, ...] = ch_data[:, roi_num - 1, ...]
        # Update our reference to the NWB file, since it's now out of sync
        # We need to keep a reference to the IO object, as the file contents are
        # not read until needed
        self.nwb_io = NWBHDF5IO(self.nwb_path, 'r')
        self.nwb_file = self.nwb_io.read()
        # Quick fix...
        self.nwb_io.close()

    def add_imaging_plane(self, name, manifold, description,
                          green=True, red=True):
        """Add a new imaging plane definition to /general/optophysiology.

        :param name: A name for the NWB group representing this imaging plane.
        :param manifold: 3d array giving the x,y,z coordinates in microns for each pixel
            in the plane. If the plane is really a line, this can be an Nx1x3 array.
        :param description: Brief text description of the plane, e.g. "Reference Z stack",
            "Pointing mode acquisition sequence".
        :param green: Whether to include the green channel.
        :param red: Whether to include the red channel.
        """
        opto_metadata = self.experiment['optophysiology']
        cycle_time = self.cycle_relative_times['CycleTime'][0]  # seconds
        cycle_rate = 1 / cycle_time  # Hz
        channels = []
        if green:
            channel = OpticalChannel('green',
                                     description='Green channel, typically used for active signal.',
                                     emission_lambda=float(opto_metadata['emission_lambda']['green']))
            channels.append(channel)
        if red:
            channel = OpticalChannel('red',
                                     description='Red channel, typically used for reference.',
                                     emission_lambda=float(opto_metadata['emission_lambda']['red']))
            channels.append(channel)
        self.nwb_file.create_imaging_plane(
            name=name,
            optical_channel=channels,
            description=description,
            device=self.nwb_file.devices['AOL_microscope'],
            excitation_lambda=float(opto_metadata['excitation_lambda']),
            imaging_rate=cycle_rate,
            indicator=opto_metadata['calcium_indicator'],
            location=opto_metadata['location'],
            manifold=manifold,
            unit='metre',
            conversion=1e6,
            reference_frame='TODO: In lab book (partly?)'
        )

    def read_zplane(self, zplane_path):
        """Determine coordinates of reference image stack from Zplane_Pockels_Values.dat.

        This also uses information from the LabView .ini file to define image planes etc
        in /general/optophysiology.

        The .dat file has 4 columns: Z offset from focal plane (micrometres), normalised Z,
        'Pockels' i.e. laser power in %, and z offset for drive motors. We save this raw
        array as the extension dataset /general/optophysiology/zplane_pockels.

        Also sets up self.zplanes as a map from Z coordinate (in microns) to imaging plane name.
        """
        self.log('Loading imaging plane information from {}', zplane_path)
        assert os.path.isfile(zplane_path)
        zplane_data = pd.read_table(
            zplane_path, skiprows=2, skip_blank_lines=True,
            names=('z', 'z_norm', 'laser_power', 'z_motor'), header=0,
            index_col=False)
        num_pixels = int(self.labview_header['GLOBAL PARAMETERS']['frame size'])
        plane_width_in_microns = self.labview_header['GLOBAL PARAMETERS']['field of view']
        template_manifold = np.zeros((num_pixels, num_pixels, 3))
        x = np.linspace(0, plane_width_in_microns, num_pixels)
        y = np.linspace(0, plane_width_in_microns, num_pixels)
        xv, yv = np.meshgrid(x, y)
        template_manifold[:, :, 0] = xv
        template_manifold[:, :, 1] = yv
        self.zplanes = {}
        for plane in zplane_data.itertuples():
            manifold = template_manifold.copy()
            manifold[:, :, 2] = plane.z
            name = 'Zstack{:04d}'.format(plane.Index + 1)
            self.zplanes[plane.z] = name
            self.add_imaging_plane(
                name=name,
                description='Reference Z stack',
                manifold=manifold)
        # TODO Define and use an extension to store these
        # self.nwb_file.set_custom_dataset(
        #     '/general/optophysiology/zplane_pockels',
        #     zplane_data.values,
        #     attrs={'columns': zplane_data.columns.tolist()})
        # self.nwb_file.set_custom_dataset(
        #     '/general/optophysiology/frame_size', [num_pixels, num_pixels])
        self._write()

    def read_zstack(self, zstack_folder):
        """Add the reference Z stack images into /acquisition.

        The folder holds one .tif file per imaging plane per channel, with the planes ordered
        as in the Zplane_Pockels_Values.dat file (see read_zplane) and hence the order matches
        the ZstackNNNN planes added there. The file names are like GreenChannel_0001.tif.

        We create a single-image TwoPhotonSeries for each plane for each channel in
        /acquisition/Zstack_<channel>_<plane>.

        Also fills in self.zstack as a mapping from [plane_name][channel_name] to the
        corresponding acquisition name (Zstack_<channel_name>_<plane_name>).
        """
        self.log('Loading reference Z stack from {}', zstack_folder)
        assert os.path.isdir(zstack_folder)
        gains = {'Red': self.labview_header['GLOBAL PARAMETERS']['pmt 1'],
                 'Green': self.labview_header['GLOBAL PARAMETERS']['pmt 2']}
        cycle_time = self.cycle_relative_times['CycleTime'][0]  # seconds
        cycle_rate = 1 / cycle_time  # Hz
        self.zstack = {}
        for plane_name, plane in self.nwb_file.imaging_planes.items():
            assert plane_name.startswith('Zstack'), 'Found unexpected plane {}'.format(plane_name)
            self.zstack[plane_name] = {}
            for channel in ('Green', 'Red'):
                plane_index = plane_name[6:]
                group_name = 'Zstack_{}_{}'.format(channel, plane_index)
                file_path = os.path.join(zstack_folder,
                                         channel + 'Channel_' + plane_index + '.tif')
                if not os.path.isfile(file_path):
                    print('Expected Zstack file "{}" missing; skipping.'.format(file_path))
                    continue
                img = tifffile.imread(file_path)
                num_pixels = int(self.labview_header['GLOBAL PARAMETERS']['frame size'])
                width_in_metres = self.labview_header['GLOBAL PARAMETERS']['field of view'] / 1e6
                # Save img to NWB
                ts_attrs = {'description': 'Initial reference Z stack plane',
                            'comments': 'Contains single slice from {} channel'.format(
                                channel.lower())}
                data_attrs = {'unit': 'intensity', 'conversion': 1.0,
                              'resolution': float('NaN'),
                              'dimension': [num_pixels, num_pixels],
                              'format': 'tiff',
                              'bits_per_pixel': 16,
                              'field_of_view': [width_in_metres, width_in_metres],
                              'imaging_plane': plane,
                              'pmt_gain': gains[channel],
                              'scan_line_rate': cycle_rate,
                              # TODO A TwoPhotonSeries doesn't store channel information.
                              # We can either an extension of it, but the channel is also
                              # stored in the imaging plane (linked to from the Series),
                              # so perhaps we don't need to?
                              # ts.set_custom_dataset('channel', channel)
                              }
                self.add_time_series_data(group_name, data=[img], times=np.array([0.0]),
                                          kind=TwoPhotonSeries,
                                          ts_attrs=ts_attrs, data_attrs=data_attrs)
                # TODO Since this is only used when adding ROIs, it might be better
                # to have a method that returns the acquisition name, rather than
                # store the mapping.
                self.zstack[plane_name][channel] = group_name
        self._write()

    def add_rois(self, roi_path):
        """Add the locations of ROIs as an ImageSegmentation module.

        We read a ROI.dat file to determine ROI locations. This has many tab-separated columns:
            ROI index; ROI ID; ROI Time (ns); Pixels in ROI;
            X start; Y start; Z start; X stop; Y stop; Z stop;
            Angle (deg); Composite ID; Number of lines; Frame Size; Zoom;
            Laser Power (%); ROI group ID.

        Each ROI must lie within one of the Z planes in the reference Z stack. We therefore can
        represent it as a rectangle (size 1x1 for pointing mode) within that plane. The relevant
        slice slice from the Z stack is used as the reference image. We group the ROIs by Z
        coordinate, since each imaging plane should only be listed once in the ImageSegmentation
        module; within a given plane, the original relative ordering of ROIs is maintained.

        TODO: Consider adding an array dataset of object references to the ROI definitions - see
        http://docs.h5py.org/en/latest/refs.html for details of how to do this. Would enable quick
        access to all ROIs (in the defined order) without having to iterate over imaging planes
        then sort. It's less of an issue with the timeseries ROI data, since that's in groups
        organised by ROI number and channel name, so we can iterate there. Issue #16.
        """
        self.log('Loading ROI locations from {}', roi_path)
        assert os.path.isfile(roi_path)
        roi_data = pd.read_table(
            roi_path, header=0, index_col=False, dtype=np.float16, memory_map=True)
        # Rename the columns so that we can use them as identifiers later on
        column_mapping = {
                 'ROI index': 'roi_index', 'Pixels in ROI': 'num_pixels',
                 'X start': 'x_start', 'Y start': 'y_start', 'Z start': 'z_start',
                 'X stop': 'x_stop', 'Y stop': 'y_stop', 'Z stop': 'z_stop',
                 'Laser Power (%)': 'laser_power', 'ROI Time (ns)': 'roi_time_ns',
                 'Angle (deg)': 'angle_deg', 'Composite ID': 'composite_id',
                 'Number of lines': 'num_lines', 'Frame Size': 'frame_size',
                 'Zoom': 'zoom', 'ROI group ID': 'roi_group_id'
        }
        roi_data.rename(columns=column_mapping, inplace=True)
        module = self.nwb_file.create_processing_module(
            'Acquired_ROIs',
            'ROI locations and acquired fluorescence readings made directly by the AOL microscope.')
        # Convert some columns to int
        roi_data = roi_data.astype(
            {'x_start': np.uint16, 'x_stop': np.uint16, 'y_start': np.uint16, 'y_stop': np.uint16,
             'num_pixels': int})
        seg_iface = ImageSegmentation()
        module.add_data_interface(seg_iface)
        self._write()
        # Define the properties of the imaging plane itself, if not a Z plane
        # TODO We will also need an extension for this (similar to previous opto attributes)
        # opto = self.nwb_file.make_group('optophysiology', abort=False)
        # opto.set_custom_dataset('imaging_mode', self.mode.name)
        if self.mode is Modes.pointing:
            # Sanity check that each ROI is a single pixel
            assert np.all(roi_data.num_pixels == 1)
        # Figure out which plane each ROI is in
        assert (roi_data['z_start'] == roi_data['z_stop']).all()  # Planes are flat in Z
        grouped = roi_data.groupby('z_start', sort=False)
        # Iterate over planes and define ROIs
        self.roi_mapping = {}  # mapping from ROI ID to row index (used to look up ROIs)
        for plane_z, roi_group in grouped:
            plane_name = self.zplanes[plane_z]
            plane_obj = self.nwb_file.imaging_planes[plane_name]
            plane = seg_iface.create_plane_segmentation(
                description=plane_obj.description,
                imaging_plane=plane_obj,
                name=plane_name,
                reference_images=self.nwb_file.acquisition[self.zstack[plane_name]['Red']]
            )
            # Specify the non-standard data we will be storing for each ROI,
            # which includes all the raw data fields from the original file
            plane.add_column('pixel_time_offsets', 'Time offsets for each pixel')
            plane.add_column('dimensions', 'Dimensions of the ROI')
            for old_name, new_name in column_mapping.items():
                plane.add_column(new_name, old_name)
            index = 0  # index of the row as it will be stored in the ROI table
            self.roi_mapping[plane_name] = {}
            for row in roi_group.itertuples():
                roi_id = int(row.roi_index)
                # The ROI mask only gives x & y coordinates - z is defined by the imaging plane.
                # The coordinates are also relative to the imaging plane, not absolute. However, our
                # plane coordinates run from 0 to frame_size, so that's easy to compute.
                # The third dimension in the pixels array indicates weight.
                pixels = np.zeros((row.num_pixels, 3), dtype=np.uint16)
                # Pixels are located contiguously from start to stop coordinates.
                num_x_pixels = row.x_stop - row.x_start
                num_y_pixels = row.y_stop - row.y_start
                if self.mode is Modes.pointing:
                    assert row.num_pixels == 1, 'Unexpectedly large ROI in pointing mode'
                    num_x_pixels = num_y_pixels = 1
                assert row.num_pixels == num_x_pixels * num_y_pixels, (
                    'ROI is not rectangular: {} != {} * {}'.format(
                        row.num_pixels, num_x_pixels, num_y_pixels))
                # Record the ROI dimensions for ease of lookup when adding functional data
                dimensions = np.array([num_x_pixels, num_y_pixels], dtype=np.int32)
                for i in range(row.num_pixels):
                    pixels[i, 0] = row.x_start + (i % num_x_pixels)
                    pixels[i, 1] = row.y_start + (i // num_x_pixels)
                    pixels[i, 2] = 1  # weight for this pixel
                # Record the time offset(s) for this ROI
                time_offsets = self.cycle_relative_times['RelativeTime']
                if self.mode is Modes.pointing:
                    pixel_time_offsets = [time_offsets[row.Index]]
                else:
                    # The relative time field records the start time for each row, not each pixel.
                    # We need to compute pixel times by adding on dwell time per pixel.
                    num_miniscans = self.labview_header['GLOBAL PARAMETERS']['number of miniscans']
                    assert len(time_offsets) == num_miniscans
                    assert num_y_pixels == num_miniscans / len(roi_data)
                    dwell_time = self.labview_header['GLOBAL PARAMETERS']['dwelltime (us)'] / 1e6
                    row_increments = np.arange(num_x_pixels) * dwell_time
                    start_index = row.Index * num_y_pixels
                    row_offsets = time_offsets[start_index:start_index + num_y_pixels].values
                    # Numpy's broadcasting lets us turn the 1d arrays into a 2d combined value
                    pixel_time_offsets = row_offsets[:, np.newaxis] + row_increments
                plane.add_roi(id=roi_id, pixel_mask=[tuple(r) for r in pixels.tolist()],
                              dimensions=dimensions,
                              pixel_time_offsets=pixel_time_offsets,
                              **{field: getattr(row, field) for field in column_mapping.values()})
                self.roi_mapping[plane_name][roi_id] = index
                index += 1
        self._write()

    def read_video_data(self, folder_path):
        """Link to video data stored in the given folder.

        :param folder_path: folder containing videos of the experiment.

        Multiple video angles are supported. This method looks for files named like
        '<Base>Cam-relative times.txt' in the folder, each of which contains timing data for a
        single video timeseries. These files contain two tab-separated columns, the first being
        frame numbers, and the second time offsets from the start of the experiment in
        milliseconds.

        The video data itself is stored in .avi files, potentially more than one per camera,
        named like '<Base>Cam-<N>.avi', where the file number <N> starts at 1.

        This method adds an ImageSeries in /acquisition for each camera, linking to
        the existing .avi files with relative paths. The timeseries are named '<Base>Cam'.
        """
        # Quick fix?
        with NWBHDF5IO(self.nwb_path, 'a') as io:
            self.nwb_file = io.read()
            self.log('Loading video data from {}', folder_path)
            assert os.path.isdir(folder_path)
            nwb_dir = os.path.dirname(os.path.realpath(self.nwb_path))
            timing_suffix = '-relative times.txt'
            timing_files = glob.glob(os.path.join(folder_path, '*' + timing_suffix))
            for timing_file_path in timing_files:
                cam_name = os.path.basename(timing_file_path)[:-len(timing_suffix)]
                self.log('Camera: {}', cam_name)
                frame_rel_times = pd.read_table(timing_file_path, names=('Frame', 'RelTime'))
                frame_rel_times['RelTime'] *= 1e-3  # Convert to seconds
                # Determine properties of each .avi file
                avi_files = glob.glob(os.path.join(folder_path, cam_name + '-*.avi'))
                num_frames = np.zeros((len(avi_files),), dtype=np.int64)
                video_file_paths = [''] * len(avi_files)
                for avi_file in avi_files:
                    file_name = os.path.basename(avi_file)
                    self.log('Video: {}', file_name)
                    index = int(file_name[len(cam_name) + 1:-4]) - 1
                    avi_file = os.path.realpath(avi_file)
                    try:
                        video_file_paths[index] = os.path.relpath(avi_file, nwb_dir)
                    except ValueError:
                        # Particularly on Windows, it's sometimes impossible to construct
                        # a relative path, so fall back to absolute
                        video_file_paths[index] = avi_file
                    container = av.open(avi_file)
                    vid = container.streams.video[0]
                    num_frames[index] = vid.frames
                    if index == 0:
                        vid_rate = vid.rate
                        vid_dimensions = [vid.width, vid.height]
                        bits_per_pixel = vid.format.components[0].bits
                    del container, vid
                starting_frames = np.roll(np.cumsum(num_frames), 1)
                starting_frames[0] = 0
                # Add camera to list of devices
                self.nwb_file.create_device(
                    cam_name, self.user_metadata['devices'][cam_name])
                # Create timeseries
                ts_attrs = {
                    'description': 'Video recording of mouse behaviour.',
                    'comments': 'Frame rate {} s'.format(vid_rate)
                }
                data_attrs = {
                    'format': 'external',
                    'external_file': video_file_paths,
                    'starting_frame': starting_frames,
                    'bits_per_pixel': bits_per_pixel,
                    'dimension': vid_dimensions,
                }
                self.add_time_series_data(
                        cam_name, data=None, times=frame_rel_times['RelTime'].values,
                        ts_attrs=ts_attrs, data_attrs=data_attrs, kind=ImageSeries)
            io.write(self.nwb_file)

    def _write(self):
        with NWBHDF5IO(self.nwb_path, 'w') as io:
            io.write(self.nwb_file)