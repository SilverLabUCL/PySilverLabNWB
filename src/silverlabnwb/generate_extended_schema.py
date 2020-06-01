from pynwb.spec import NWBAttributeSpec, NWBDatasetSpec, NWBGroupSpec, NWBNamespaceBuilder


def generate_extended_schema():
    # set up silverlab namespace
    ns_builder = NWBNamespaceBuilder('Extensions for acousto-optic lens data',
                                     'silverlab_extended_schema',
                                     'Silver lab data extension to NWB format for acousto-optic lens experiments',
                                     version='0.2')
    ns_builder.include_type('LabMetaData', namespace='core')
    # define attributes Silver lab extension
    cycle_time_attr = NWBAttributeSpec(name='cycle_time',
                                       doc='time in seconds for the microscope to acquire all ROIs once '
                                       'and return to its starting position',
                                       dtype='float')
    cycles_per_trial_attr = NWBAttributeSpec(name='cycles_per_trial',
                                             doc='how many microscope cycles occur in each experimental trial',
                                             dtype="int")
    imaging_mode_attr = NWBAttributeSpec(name='imaging_mode',
                                         doc='the acquisition mode for the experiment; '
                                         'pointing = single-voxel ROIs, '
                                         'miniscan = 2d rectangular ROIs, '
                                         'volume = 3d cuboid ROIs',
                                         dtype='text')
    frame_size_attr = NWBAttributeSpec(name='frame_size',
                                       doc='the 2d imaging frame size in voxels',
                                       shape=(2,),
                                       dtype='int')
    silverlab_api_version_attr = NWBAttributeSpec(name='silverlab_api_version',
                                                  doc='For potential future backwards compatibility, '
                                                  'store the \'version\' of this API that created the file.',
                                                  dtype='text')
    pockels_column_names_attr = NWBAttributeSpec(name='columns',
                                                 doc='column names for the zplane pockels dataset',
                                                 shape=(4,),
                                                 dtype='text')
    # define datasets for Silver lab extensions
    zplane_pockels_ds = NWBDatasetSpec(doc='pockels data set, recording calibration data '
                                           'for focusing at different z-planes in four columns: '
                                           'Z offset from focal plane (micrometres), '
                                           'normalised Z, '
                                           '\'Pockels\' i.e. laser power in %, '
                                           'and z offset for drive motors',
                                       name='pockels',
                                       shape=(None, 4),
                                       attributes=[pockels_column_names_attr],
                                       neurodata_type_def='ZplanePockelsDataset')
    # define groups for Silver lab extensions
    silverlab_optophys_specs = NWBGroupSpec(doc='A place to store Silver lab specific optophysiology data',
                                            attributes=[cycle_time_attr,
                                                        cycles_per_trial_attr,
                                                        frame_size_attr,
                                                        imaging_mode_attr],
                                            datasets=[zplane_pockels_ds],
                                            neurodata_type_def='SilverLabOptophysiology',
                                            neurodata_type_inc='LabMetaData')
    silverlab_metadata_specs = NWBGroupSpec(doc='A place to store Silver lab specific metadata',
                                            attributes=[silverlab_api_version_attr],
                                            neurodata_type_def='SilverLabMetaData',
                                            neurodata_type_inc='LabMetaData',
                                            )
    # export as schema extension
    ext_source = 'silverlab.ophys.yaml'
    ns_builder.add_spec(ext_source, silverlab_optophys_specs)
    ext_source = 'silverlab.metadata.yaml'
    ns_builder.add_spec(ext_source, silverlab_metadata_specs)
    ns_builder.export('silverlab.namespace.yaml')


if __name__ == '__main__':
    generate_extended_schema()
