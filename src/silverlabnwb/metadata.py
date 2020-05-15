'''
Handles loading the metadata YAML files.
'''

import collections
import os

import appdirs
import pkg_resources
import ruamel.yaml as yaml


def set_conf_dir(path=appdirs.user_config_dir('SilverLabNwb', 'SilverLab')):
    """Set where to store / read user configuration files.

    Defaults to the system-specific default user configuration folder.

    :param path: path to a configuration folder
    """
    global user_conf_dir, user_conf_path
    user_conf_dir = path
    user_conf_path = os.path.join(user_conf_dir, 'metadata.yaml')


set_conf_dir()  # Set the default paths initially


def read_user_config():
    """Read the user configuration YAML files.

    We first read the default configuration supplied with this package.
    Then we look in the user_config_dir (as defined by appdirs) for any
    machine- & user-specific configuration settings, which override the
    defaults.
    """
    with pkg_resources.resource_stream(__name__, 'metadata.yaml') as defaults:
        settings = read_config_file(defaults)
    if os.path.isfile(user_conf_path):
        with open(user_conf_path, 'r') as user_params:
            settings = read_config_file(user_params, settings)
    return settings


def read_config_file(stream, base_settings=None):
    """Read a single YAML configuration file.

    :param stream: the open file object.
    :param base_settings: if present, a settings dictionary to copy and update
    with the contents of this file.
    """
    yaml_reader = yaml.YAML()
    raw_yaml_data = yaml_reader.load(stream)
    if base_settings is None:
        settings = MetadataEntry({}, '')
    else:
        settings = base_settings.copy()
    recursive_dict_update(settings, strip_strings(raw_yaml_data))
    return settings


def save_config_file(settings):
    """Save a YAML user configuration file to the default path.

    Will try to create the user's configuration folder if it doesn't exist.

    :param settings: the settings dictionary to save
    """
    if not os.path.isdir(user_conf_dir):
        os.makedirs(user_conf_dir)
    with open(user_conf_path, 'w') as user_params:
        yaml.safe_dump(settings, user_params)


def recursive_dict_update(base_settings, new_settings):
    """Recursively update settings dictionaries.

    Since our settings are nested dictionaries, we need to merge sub-levels rather
    than overwriting when merging new settings. This method essentially does a
    recursive base_settings.update(new_settings).
    """
    for k, v in new_settings.items():
        if isinstance(v, collections.Mapping):
            base_settings[k] = recursive_dict_update(base_settings.get(k, {}), v)
        else:
            base_settings[k] = new_settings[k]
    return base_settings


def strip_strings(settings):
    """Recursively strip all strings in a settings dict.

    :param settings: the settings dictionary to process
    :returns: a new dictionary with all string settings stripped
    """
    result = MetadataEntry({}, '')
    for k, v in settings.items():
        if isinstance(v, str):
            result[k] = MetadataEntry(v.strip(), 'string_comment')
        elif isinstance(v, collections.Mapping):
            result[k] = MetadataEntry(strip_strings(v), 'mapping_comment')
        else:
            result[k] = MetadataEntry(v, 'other_comment')
    return result


class MetadataEntry:
    def __init__(self, value, comment):
        self.value = value
        self.comment = comment

    def __getattr__(self, attr):
        return getattr(self.value, attr)

    def __getitem__(self, item):
        return self.value[item]

    def __setitem__(self, key, value):
        object.__getattribute__(self, "value")[key] = value

    def __delitem__(self, key):
        del object.__getattribute__(self, "value")[key]

    def __contains__(self, item):
        return item in self.value

    def __len__(self):
        return len(self.value)
