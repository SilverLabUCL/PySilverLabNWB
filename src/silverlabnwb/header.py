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
        # Parse the file and decide which version to instantiate.
        # Potentially call some methods on the created header object if needed.
        pass

    @abc.abstractmethod
    def __init__(self, fields):
        self.raw_fields = fields
        # Set self.sections based on fields?
        self._imaging_mode = None  # ... = self.determine_imaging_mode()?

    def __getitem__(self, item):
        """Retrieve an entry from the header's fields."""
        return self.sections[item]

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

    def _imaging_section(self):
        # In the older version, parameters were stored in the global section.
        return self["GLOBAL PARAMETERS"]


class LabViewHeader213(LabViewHeader):

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
