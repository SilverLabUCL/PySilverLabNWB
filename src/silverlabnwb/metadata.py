
'''
Handles loading the metadata YAML files.
'''

import collections.abc
import os

import appdirs
import pkg_resources
from ruamel.yaml import YAML


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
        settings, comments = read_base_config_file(defaults)
    if os.path.isfile(user_conf_path):
        with open(user_conf_path, 'r') as user_params:
            settings = update_config_file(user_params, settings)
    return settings, comments


def read_custom_config(config_file):
    """Read the metadata from a user-provided YAML file."""
    with open(config_file) as config:
        settings, _ = read_base_config_file(config)
    return settings


def read_base_config_file(stream):
    yaml_reader = YAML()
    parsed_yaml_data = yaml_reader.load(stream)
    yaml_data_comments = read_comments(parsed_yaml_data)
    settings = {}
    recursive_dict_update(settings, strip_strings(parsed_yaml_data))
    return settings, yaml_data_comments


def should_keep_comment(line):
    return len(line) > 0 and not line.startswith('>')


def beautify_comment(comment_token):
    """Format CommentToken instance to display nicely as a tooltip."""
    yaml_comment = comment_token[2].value
    return "\n".join(filter(should_keep_comment, [line.strip() for line in yaml_comment.split('#')]))


def read_comments(settings):
    comments = {}
    for k, v in settings.items():
        if isinstance(v, collections.abc.Mapping):
            comments[k] = read_comments(v)
        elif isinstance(v, list):
            comments[k] = [read_comments(entry) for entry in v]
        else:
            comment = settings.ca.items.get(k, None)
            if comment is not None:
                comments[k] = beautify_comment(comment)
    return comments


def update_config_file(stream, base_settings):
    """Read a single YAML configuration file.

    :param stream: the open file object.
    :param base_settings: a settings dictionary to copy and update
    with the contents of this file.
    """
    yaml_reader = YAML(typ='safe')
    parsed_yaml_data = yaml_reader.load(stream)
    settings = base_settings.copy()
    if parsed_yaml_data is not None:  # if the streamed file is not empty
        recursive_dict_update(settings, strip_strings(parsed_yaml_data))
    return settings


def save_config_file(settings, yaml_instance=None):
    """Save a YAML user configuration file to the default path.

    Will try to create the user's configuration folder if it doesn't exist.

    :param settings: the settings dictionary to save
    :param yaml_instance: a specific YAML instance to use (we may require it to have certain representers)
    """
    if not os.path.isdir(user_conf_dir):
        os.makedirs(user_conf_dir)
    with open(user_conf_path, 'w') as user_params:
        if yaml_instance is None:
            yaml_instance = YAML(typ='safe')
        yaml_instance.dump(settings, user_params)


def recursive_dict_update(base_settings, new_settings):
    """Recursively update settings dictionaries.

    Since our settings are nested dictionaries, we need to merge sub-levels rather
    than overwriting when merging new settings. This method essentially does a
    recursive base_settings.update(new_settings).
    """
    for k, v in new_settings.items():
        if isinstance(v, collections.abc.Mapping):
            base_settings[k] = recursive_dict_update(base_settings.get(k, {}), v)
        else:
            base_settings[k] = new_settings[k]
    return base_settings


def strip_strings(settings):
    """Recursively strip all strings in a settings dict.

    :param settings: the settings dictionary to process
    :returns: a new dictionary with all string settings stripped
    """
    result = {}
    for k, v in settings.items():
        if isinstance(v, str):
            result[k] = v.strip()
        elif isinstance(v, collections.abc.Mapping):
            result[k] = strip_strings(v)
        else:
            result[k] = v
    return result
