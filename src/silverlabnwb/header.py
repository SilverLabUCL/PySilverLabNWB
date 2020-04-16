import abc
from enum import Enum
from math import ceil

from .imaging import ImagingInformation, Modes


class LabViewVersions(Enum):
    pre2018 = "pre-2018 (original)"
    v231 = "2.3.1"


class LabViewHeader(metaclass=abc.ABCMeta):
    """A class to represent all information stored in a LabView header file.

    This abstract class only offers some basic functionality and structure.

    Different subclasses should be defined to provide special behaviour for
    particular versions of the LabView setup used in the lab.
    """
    property_names = {}

    @classmethod
    def from_file(cls, filename):
        """Create an object to hold the information in a LabView header file."""
        # Parse the file
        ini = open(filename, 'r')
        fields = []
        section = ''
        parsed_fields = {}
        for line in ini:
            line = line.strip()
            if len(line) > 0:
                if line.startswith('['):
                    section = line[1:-1]
                    parsed_fields[section] = {}
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
                    parsed_fields[section][key] = value
                elif '\t' in line:
                    words = line.split('\t')
                    key, value = int(float(words[0])), float(words[1])  # TODO cast later in code
                    fields.append([section, key, value])
                    parsed_fields[section][key] = value
        # Decide which version to instantiate
        try:
            version = parsed_fields['LOGIN']['Software Version']
        except KeyError:
            # older versions do not store the LabView version
            return LabViewHeaderPre2018(fields, parsed_fields)
        else:
            if version == '2.3.1':
                return LabViewHeader231(fields, parsed_fields)
            else:
                raise ValueError('Unsupported LabView version {}.'.format(version))

    def __init__(self, fields, processed_fields):
        """Create a header object from the given raw and processed fields.

        Subclasses can add specialised behaviour by overriding this.
        """
        # Keep track of the raw fields in case we need to return them later
        # (such as to add them to an NWB file).
        self._raw_fields = fields
        # Accessing the header's information should normally be through the
        # processed fields, stored in self.sections.
        self._sections = processed_fields
        self._imaging_mode = self._determine_imaging_mode()

    def __getitem__(self, item):
        """Retrieve an entry from the header's fields."""
        return self._sections[item]

    @property
    @abc.abstractmethod
    def version(self):
        """The version of LabView as found in the header file.

        Can be used to "branch" behaviour based on the version, rather than
        inspecting the class.
        """
        pass

    @property
    def imaging_mode(self):
        return self._imaging_mode

    @abc.abstractmethod
    def _determine_imaging_mode(self):
        pass

    @abc.abstractmethod
    def _imaging_section(self):
        """Get the section of the header that holds the imaging parameters."""
        pass

    def get_imaging_information(self):
        # Imaging parameters can be stored in different sections of the header
        # depending on the LabView version.
        section = self._imaging_section()
        # Parameter names also vary between versions, so use the appropriate ones.
        property_names = self.property_names
        # Also cast the integer parameters since they are read as floats.
        cycles_per_trial = int(section[property_names["number_of_cycles"]])
        gains = {"Red": section[property_names["gain_red"]],
                 "Green": section[property_names["gain_green"]]}
        frame_size = int(section[property_names["frame_size"]])
        field_of_view = section[property_names["field_of_view"]]
        number_of_miniscans = int(section[property_names["number_of_miniscans"]])
        dwell_time = section[property_names["dwell_time"]]
        return ImagingInformation(cycles_per_trial, gains, frame_size, field_of_view,
                                  number_of_miniscans, dwell_time)

    def determine_trial_times(self):
        """Try to extract the start and stop time of each trial.

        Raise an error if this is impossible because the information is not
        included in the header.
        """
        raise NotImplementedError

    def get_raw_fields(self):
        """Get the fields of the header as directly read from the file.

        Returns a list of (section, key, value) triples containing strings,
        without any processing applied. Useful for storing the original header
        in NWB files for clearer provenance.
        """
        return self._raw_fields


class LabViewHeaderPre2018(LabViewHeader):

    property_names = {
        "frame_size": "frame size",
        "field_of_view": "field of view",
        "dwell_time": "dwelltime (us)",
        "number_of_cycles": "number of cycles",
        "number_of_miniscans": "number of miniscans",
        "gain_red": "pmt 1",
        "gain_green": "pmt 2",
    }

    @property
    def version(self):
        return LabViewVersions.pre2018

    def _determine_imaging_mode(self):
        if self['GLOBAL PARAMETERS']['number of poi'] > 0:
            return Modes.pointing
        elif self['GLOBAL PARAMETERS']['number of miniscans'] > 0:
            return Modes.miniscan
        else:
            raise ValueError('Unsupported imaging type: numbers of poi and miniscans are zero.')

    def _imaging_section(self):
        # In the older version, parameters were stored in the global section.
        return self["GLOBAL PARAMETERS"]


class LabViewHeader231(LabViewHeader):

    property_names = {
        "frame_size": "Frame Size",
        "field_of_view": "field of view",
        "dwell_time": "pixel dwell time (us)",
        "number_of_cycles": "Number of cycles",
        "number_of_miniscans": "Number of miniscans",
        "gain_red": "pmt 1",
        "gain_green": "pmt 2",
    }

    @property
    def version(self):
        return LabViewVersions.v231

    def _determine_imaging_mode(self):
        if self['IMAGING MODES']['Volume Imaging'] == 'TRUE':
            return Modes.pointing
        elif self['IMAGING MODES']['Functional Imaging'] == 'TRUE':
            return Modes.miniscan
        else:
            raise ValueError('Unsupported imaging type: could not determine imaging mode.')

    def _imaging_section(self):
        # In LabView version 2.3.1, imaging parameters are stored under the
        # relevant imaging mode section.
        imaging_section_name = ("FUNCTIONAL IMAGING"
                                if self.imaging_mode is Modes.miniscan
                                else "VOLUME IMAGING")
        return self[imaging_section_name]

    def determine_trial_times(self):
        # In this version of LabView, the trial times are stored in their own
        # (misleadingly titled) section of the header.
        trial_times = []
        number_of_trials = ceil(len(self['Intertrial FIFO Times']) / 2)
        for i in range(number_of_trials):
            trial_times.append(
                (self['Intertrial FIFO Times'][2 * i], self['Intertrial FIFO Times'][2 * i + 1]))
        # TODO handle last trial separately in case stop_time is missing
        return trial_times
