from pynwb.spec import NWBAttributeSpec, NWBDatasetSpec, NWBGroupSpec, NWBNamespaceBuilder


def generate_extended_schema():
    ns_builder = NWBNamespaceBuilder('Extensions for acousto-optic lens data', 'silverlab_extended_schema',
                                     'Silverlab data extension to NWB format for acousto-optic lens experiments',
                                     version='0.1')
    ns_builder.include_type('NWBDataInterface', namespace='core')

    # Silver lab optophysiology extension
    # attributes
    cycle_time_attr = NWBAttributeSpec('cycle_time', 'time in seconds for the microscope to acquire all ROIs once '
                                                     'and return to its starting position', 'float')
    cycles_per_trial_attr = NWBAttributeSpec('cycles_per_trial', 'how many microscope cycles occur'
                                                                 ' in each experimental trial', "int")
    imaging_mode_attr = NWBAttributeSpec('imaging_mode',
                                         'the acquisition mode for the experiment; '
                                         'pointing = single-voxel ROIs, '
                                         'miniscan = 2d rectangular ROIs, '
                                         'volume = 3d cuboid ROIs',
                                         'text')
    frame_size_attr = NWBAttributeSpec(name='frame_size', dtype='int', shape=(2,),
                                       doc=' the 2d imaging frame size in voxels')
    silverlab_api_version_attr = NWBAttributeSpec('silverlab_api_version',
                                                  'For potential future backwards compatibility, '
                                                  'store the \'version\' of this API that created the file.',
                                                  'text')

    # datasets
    zplane_pockels_ds = NWBDatasetSpec(doc='pockels data set, '
                                           'recording calibration data for focusing at different z-planes'
                                           'in four columns: Z offset from focal plane (micrometres), normalised Z,'
                                           '\'Pockels\' i.e. laser power in %, and z offset for drive motors',
                                       shape=(None, 4),
                                       attributes=[NWBAttributeSpec(name='columns', dtype='text', shape=(4,),
                                                                    doc='column names for the zplane pockels dataset')],
                                       # lets not require a specific name for our new type.
                                       # we can always specify a name when we include it elsewhere
                                       name='pockels',
                                       neurodata_type_def='ZplanePockelsDataset')

    silverlab_optophys_specs = NWBGroupSpec('Silverlab optophysiology specifications',
                                            attributes=[cycle_time_attr, cycles_per_trial_attr, frame_size_attr,
                                                        imaging_mode_attr, silverlab_api_version_attr],
                                            datasets=[
                                                zplane_pockels_ds
                                            ],
                                            neurodata_type_def='SilverLabExtension',
                                            neurodata_type_inc='NWBDataInterface')

    ext_source = 'silverlab.extensions.yaml'
    ns_builder.add_spec(ext_source, silverlab_optophys_specs)
    ns_builder.export('silverlab.namespace.yaml')


if __name__ == '__main__':
    generate_extended_schema()
