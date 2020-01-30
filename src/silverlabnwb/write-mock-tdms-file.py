from nptdms import TdmsWriter, RootObject, GroupObject, ChannelObject
import random as rdm
import os

DATA_PATH = os.environ.get('SILVERLAB_DATA_DIR', '')
if DATA_PATH != '':
    nRois = 4
    nCycles_per_trial = 10
    nTrials = 3
    channels = [0, 1]
    channel_objects = []
    nEntries = nCycles_per_trial * nRois

    for trial in range(1, nTrials + 1):
        root_object = RootObject({})
        group_object = GroupObject("Functional Imaging Data", properties={})
        for channel in channels:
            entries = []
            for entry in range(1, nEntries + 1):
                entries.append(rdm.randint(5, 15) + (trial - 1) * 10 + 100 * channel + rdm.random())
            channel_objects.append(ChannelObject("Functional Imaging Data",
                                                 "Channel " + str(channel) + " Data",
                                                 entries,
                                                 properties={"NI_ArrayColumn": channel}))

        with TdmsWriter(DATA_PATH + "\\00" + str(trial) + ".tdms") as tdms_writer:
            tdms_writer.write_segment([
                root_object,
                group_object,
                channel_objects[0], channel_objects[1]])
