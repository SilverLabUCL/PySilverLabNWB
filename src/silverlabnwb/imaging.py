from enum import Enum


class Modes(Enum):
    """Scanning modes supported by the AOL microscope."""
    pointing = 1
    miniscan = 2
    patch = 2
    volume = 3


class ImagingInformation:
    """A class to hold imaging-related information found in the LabView header."""
    def __init__(self, cycles_per_trial, gains, frame_size, field_of_view,
                 number_of_miniscans, dwell_time):
        self.cycles_per_trial = cycles_per_trial
        self.gains = gains
        self.frame_size = frame_size
        self.field_of_view = field_of_view
        self.number_of_miniscans = number_of_miniscans
        self.dwell_time = dwell_time
