"""Routines for creating compact signatures of NWB files, for testing.

The idea of a signature is that it's small enough to store in version control,
yet detailed enough to tell if you've changed an NWB file's content from the
reference version.
"""

from __future__ import print_function

import argparse
import collections
import difflib
import numbers
import os
import re
import sys
import zlib

import h5py
import six
from numpy import array, dtype, hstack, int32, int64, ndarray, squeeze


def cast_to_object(string):
    return squeeze(array([string], dtype='O'))


class SignatureGenerator:
    """The workhorse class for generating NWB file signatures.

    We try to generate exactly the same signature whether running under Python 2 or 3.

    Typical usage pattern:
        sig_gen = SignatureGenerator()
        sig_gen.ignore_path('.*/external_file')
        sig = sig_gen.generate(path_to_nwb)
        sig_gen.save_sig(path_to_nwb, path_to_sig)
        assert sig_gen.compare_to_sig(path_to_nwb, path_to_sig)
    """

    def __init__(self):
        """Create a signature generator."""
        self._ignore_paths = [re.compile(s) for s in [
            '/file_create_date',
            '/identifier',
            '/specifications/core/*',
            '/specifications/hdmf-common/*',
        ]]
        self._ignore_attributes = []
        for path, attr in [
            ('.*', 'help'),
            ('.*', 'namespace'),
            ('.*', 'neurodata_type'),
            ('.*', 'object_id'),
            ('/', 'nwb_version'),
        ]:
            self.ignore_attribute(path, attr)
        # some datasets need platform-specific correction of type
        self._cast_paths = {}
        for dataset_path, expected, corrected in [
            ('/acquisition/EyeCam/dimension', int32, int64),
            ('/acquisition/WhiskersCam/dimension', int32, int64),
            ('/acquisition/Zstack_.*/dimension', int32, int64),
            ('/intervals/epochs/id', int32, int64),
            ('/intervals/trials/id', int32, int64),
            ('/processing/Acquired_ROIs/.*/id', int32, int64),
            ('/processing/Acquired_ROIs/.*/num_pixels', int32, int64),
            ('/processing/Acquired_ROIs/.*/pixel_mask', int32, int64),
            ('/processing/Acquired_ROIs/.*/pixel_mask_index', int32, int64),
            ('/processing/Acquired_ROIs/.*/x_start', int32, int64),
            ('/processing/Acquired_ROIs/.*/x_stop', int32, int64),
            ('/processing/Acquired_ROIs/.*/y_start', int32, int64),
            ('/processing/Acquired_ROIs/.*/y_stop', int32, int64),
        ]:
            self.set_cast_path(dataset_path, expected, corrected)
        # some attributes need platform specific casting
        for attr_path, expected, corrected in [
            ('/general/silverlab_optophysiology/cycles_per_trial', int32, int64),
            ('/general/silverlab_optophysiology/frame_size', int32, int64),
            ('/intervals/epochs/timeseries_index', int32, int64),
            ('/intervals/epochs/colnames', dtype('|S13'), cast_to_object),
            ('/intervals/trials/colnames', dtype('|S13'), cast_to_object),
            ('/processing/Acquired_ROIs/ImageSegmentation/Zstack.*/colnames', dtype('|S21'), cast_to_object)
        ]:
            self.set_cast_path(attr_path, expected, corrected)

    def ignore_path(self, pattern):
        """Don't generate signatures for datasets/groups matching the path `pattern`.

        :param pattern: a regular expression string
        """
        self._ignore_paths.append(re.compile(pattern + '$'))

    def ignore_attribute(self, path, attr):
        """Don't generate signatures for the given attribute(s).

        :param path: regular expression path to the dataset/group on which the attribute is found
        :param attr: name of the attribute as a fixed string (not regular expression)
        """
        self._ignore_attributes.append((re.compile(path + '$'), attr))

    def set_cast_path(self, path, expected_type, corrected_type):
        """Cast dataset values to corrected_type

        Needed because some datasets and attributes are of different type on different platforms.
        Stores the necessary information for the casting in a dict called self._cast_paths

        :param path: regular expression path to the dataset that may need casting
        :param expected_type: if path is of this expected type, it will need casting to corrected_tyep
        :param corrected_type: if path is of expected_type, it will need casting to this type
        """
        self._cast_paths[re.compile(path + '$')] = {"expected": expected_type, "corrected": corrected_type}

    def generate(self, nwb_path):
        """Generate a signature for a NWB file.

        :param nwb_path: path to the NWB file
        :returns: a string with the signature
        """
        assert os.path.exists(nwb_path), 'NWB file {} does not exist'.format(nwb_path)
        header = 'Generating signature for {}\n\n'.format(os.path.basename(nwb_path))
        f = h5py.File(nwb_path, 'r')
        sig = self.group_sig(f)
        f.close()
        return header + sig

    def save_sig(self, nwb_path, sig_path):
        """Generate a signature for an NWB file and save to `sig_path`."""
        with open(sig_path, 'wt') as sig_f:
            sig_f.write(self.generate(nwb_path))

    def compare_to_sig(self, nwb_path, sig_path, verbose=True):
        """Test whether an NWB file matches the expected signature.

        Designed to be used in an ``assert`` within tests

        :param nwb_path: path to the NWB file
        :param sig_path: path to the expected signature
        :param verbose: if True, will print the diff if there's a mismatch
            (and 'Signature matches' if not)
        :returns: True iff the signature matches
        """
        assert os.path.exists(sig_path), 'Signature file {} does not exist'.format(sig_path)
        actual_sig = self.generate(nwb_path)
        with open(sig_path) as sig_f:
            expected_sig = sig_f.read()
        match = expected_sig == actual_sig
        if match and verbose:
            print('Signature matches for file {}'.format(os.path.basename(nwb_path)))
        elif verbose:
            diff = difflib.unified_diff(
                expected_sig.splitlines(), actual_sig.splitlines(),
                fromfile=sig_path, tofile=nwb_path, lineterm='')
            for line in diff:
                print(line)
        return match

    def group_sig(self, group):
        """Generate a signature for an NWB group.

        Will recursively generate signatures for subgroups, etc.

        :returns: a string with the signature
        """
        self._current_group = group
        attrs_sig = self.attrs_sig(group)
        sig = [group.name + attrs_sig + u'\n' if attrs_sig else u'']
        if self.ignored_path(group.name):
            return u''.join(sig)
        for name in sorted(group):
            item_type = group.get(name, getclass=True, getlink=True)
            if item_type is h5py.HardLink:
                item_type = group.get(name, getclass=True)
            if item_type is h5py.Group:
                sig.append(self.group_sig(group[name]))
            elif item_type is h5py.Dataset:
                sig.append(self.dataset_sig(group[name]))
            elif item_type in {h5py.SoftLink, h5py.ExternalLink}:
                path = u'{}{}{}'.format(group.name, u'' if group.name == u'/' else u'/', name)
                if self.ignored_path(path):
                    continue
                link = group.get(name, getlink=True)
                if item_type is h5py.SoftLink:
                    sig.append(u'{} -> {}\n'.format(path, link.path))
                elif item_type is h5py.ExternalLink:
                    sig.append(u'{} -> {}:{}\n'.format(path, link.filename, link.path))
        return u''.join(sig)

    def dataset_sig(self, dataset):
        """Generate a signature for an NWB dataset.

        :returns: a string with the signature
        """
        path = dataset.name
        attrs = self.attrs_sig(dataset)
        if self.ignored_path(path):
            shape = data_type = val = 'ignored'
        else:
            shape = dataset.shape
            data_type = dataset.dtype
            original_val = dataset.value
            cast_type = self.should_cast_path(path, data_type)
            if cast_type is not None:
                # note that     np.dtype(np.int32)  ==     np.int32  is True
                # but       str(np.dtype(np.int32)) == str(np.int32) is False
                data_type = dtype(cast_type)
                original_val = cast_type(original_val)
            if shape == ():
                val = self.format_value(original_val)
                if len(val) > 30:
                    val = val[:27] + u'...' + self.value_hash(val.encode('utf-8'))
            elif shape == (1,):
                val = self.format_value(original_val[0])
                if len(val) > 30:
                    val = val[:27] + u'...' + self.value_hash(val.encode('utf-8'))
                val = u'[%s]' % val
            else:
                val = self.array_hash(original_val)
        return u'{}: dtype={} shape={} val="{}"{}\n'.format(
            path, data_type, shape, val, attrs)

    def array_hash(self, array):
        """Return a short string hash of an ndarray's contents.

        For simple types we can just hash array.tobytes() but this can give different
        results on repeat runs with object dtypes, or complex dtype containing objects
        (e.g. references). For these, first casting the array to bytes seems to work.
        For structured dtypes, we need to cast the individual entries to bytes separately.
        """
        if array.dtype.kind in ['O', 'V']:
            if array.dtype.fields:
                return self.value_hash(hstack([array[name].astype(bytes) for name in array.dtype.names]).tobytes())
            else:
                return self.value_hash(array.astype(bytes).tobytes())
        else:
            return self.value_hash(array.tobytes())

    def value_hash(self, value):
        """Return a short string hash of a potentially large value.

        :param value: a byte string to hash
        :returns: a hexadecimal representation of a 32-bit hash
        """
        return hex(zlib.adler32(value) & 0xffffffff)

    def format_value(self, val):
        """Format a single value nicely as a unicode string.

        Handles unicode, bytes, integers, arrays and floats. Other types will be hashed.

        Assumes utf-8 encoding if bytes.
        """
        if isinstance(val, six.text_type):
            formatted_val = val
        elif isinstance(val, six.binary_type):
            formatted_val = val.decode('utf-8')
        elif isinstance(val, numbers.Integral):
            formatted_val = u'%d' % (val,)
        elif isinstance(val, numbers.Real):
            formatted_val = u'%.10g' % (val,)
        elif isinstance(val, h5py.h5r.Reference):
            formatted_val = u'->{}'.format(self._current_group[val].name)
        elif isinstance(val, ndarray):
            formatted_val = self.array_hash(val)
        else:
            formatted_val = self.value_hash(val.tobytes())
        return formatted_val

    def attrs_sig(self, entity):
        """Generate a signature of the attributes for a group or dataset.

        :param entity: an h5py group or dataset
        :returns: a string with the signature, one line per attribute
        """
        sig = u''
        for name, value in sorted(entity.attrs.items()):
            if not self.ignored_attr(entity.name, name):
                corrected_type = None
                if hasattr(value, 'dtype'):
                    corrected_type = self.should_cast_path(entity.name+'/'+name, value.dtype)
                if corrected_type is not None:
                    value = corrected_type(value)
                sig = sig + u'\n\t@{}: {}'.format(name, self.attr_val(value))
        return sig

    def attr_val(self, val):
        """Return a consistent representation of an attribute's value."""
        formatted_val = self.format_value(val)
        if hasattr(val, 'dtype'):
            type_info = u'dtype={} shape={}'.format(val.dtype, val.shape)
        else:
            type_info = u'type={}'.format(type(val).__name__)
        return u'{} val="{}"'.format(type_info, formatted_val)

    def ignored_attr(self, parent_path, attr_name):
        """Should we ignore this attribute?"""
        for path_re, ignored_name in self._ignore_attributes:
            if path_re.match(parent_path) and attr_name == ignored_name:
                return True
        return False

    def ignored_path(self, path):
        """Should we ignore this entity path?"""
        for path_re in self._ignore_paths:
            if path_re.match(path):
                return True
        return False

    def should_cast_path(self, path, encountered_type):
        """Should we cast this entity path, and if so, to what type?"""
        for key in self._cast_paths:
            if key.match(path) and self._cast_paths[key]["expected"] == encountered_type:
                return self._cast_paths[key]["corrected"]
        return None


class SignatureConverter:
    """Convert signatures from NWB1 to NWB2.

    This isn't fully automatic, but it will get a signature generated for an NWB1 file to
    look roughly like the signature for an NWB2 file generated from the same Labview data.
    Certainly close enough that manual inspection of the remaining diff is feasible.
    """
    # Regular expression matches and the corresponding replacements.
    # Note that these are processed in order for each line, so order matters.
    RE_CHANGES = [
        # Simple path change
        (r'/acquisition/timeseries', r'/acquisition'),
        # Removed attributes
        (r'^\t@ancestry:.*', r''),
        (r'^\t@interfaces:.*', r''),
        (r'^\t@source:.*', r''),
        # Removed datasets
        (r'^/acquisition/\S+/channel:.*', r''),
        (r'^/acquisition/\S+/roi_name:.*', r''),
        (r'^/acquisition/\S+/pixel_time_offsets ->.*', r''),
        (r'^/\S+/num_samples:.*', r''),
        (r'^/nwb_version:.*', r''),
        (r'^/silverlab_api_version:.*', r''),
        # Name becomes link
        (r'^(\S+/imaging_plane): .* val="(\S+)"$', r'\1 -> /general/optophysiology/\2'),
        (r'^(/general/\S+/device): .* val="(\S+)"$', r'\1 -> /general/devices/\2'),
        # Type change for string attrs
        # (r'^(\t@unit:) dtype=\|S\d+ shape=\S+', r'\1 type=bytes'),  # Only for timestamps???
        (r'^(\t@.*:) dtype=\|S\d+ shape=\S+', r'\1 type=str'),
        # Type change for string datasets
        (r'^(\S+:) dtype=\|S\d+ ', r'\1 dtype=object '),
        (r'^(/\S+/imaging_rate: dtype=)object(.*?)val="(\d+\.\d{7}).*', r'\1float32\2val="\3"'),
        # Epochs are completely different
        # (r'^/epochs/.*', r''),
        (r'^\t@(links|tags).*', r''),
        # Devices have data in an attribute
        (r'^(/general/devices/\S+): .* (val=".*")$', r'\1\n\t@description: type=str \2'),
        # Session start time format
        (r'^(/session_start_time.*val="\S+) (\S+)', r'\1T\2'),
        # Wavelengths are now floats not strings
        (r'^(/\S+/\w+_lambda:) dtype=object(.*?)val=.*', r'\1 dtype=float32\2val="nan"'),
    ]

    # Where datasets become attributes, they need to be 'hoisted' above other sibling datasets
    HOISTS = [
        # Some datasets in TwoPhotonSeries are now group attributes
        (r'^/acquisition/\S+/pmt_gain: (.*)', r'\t@pmt_gain: \1'),
        (r'^/acquisition/\S+/scan_line_rate: (.*)', r'\t@scan_line_rate: \1'),
    ]

    # Picking out the base item name from HDF5 paths, along with whether it's an attribute etc
    META = re.compile(r'^((?P<path>(/[^ /:]+)*/)|(?P<attr>\t))(?P<name>([^ /:])*)' +
                      r'(?P<dataset>:| ->)?')

    def __init__(self):
        """Create a signature converter."""
        self.re_changes = list(map(
            lambda match_repl: (re.compile(match_repl[0]), match_repl[1]),
            self.RE_CHANGES))
        self.hoists = list(map(
            lambda match_repl: (re.compile(match_repl[0]), match_repl[1]),
            self.HOISTS))

    def convert(self, sig_path):
        """Convert an NWB1 signature to be more like NWB2.
        """
        with open(sig_path, 'r') as sig_file:
            lines = sig_file.readlines()
        # Don't modify the header
        for line in lines[:2]:
            print(line, end='')
        # Handle hoisting
        lines = self.hoist(iter(lines[2:]))
        # Transform each non-header line
        for line in lines:
            print(self.convert_line(line), end='')

    def hoist(self, lines):
        """Hoist some datasets to become attributes of the parent group.

        Not all groups have an explicit signature line for the group itself, but we assume
        all groups that need hoisting *do*. We process signature lines in order, tracking
        the current group, and where one exists deferring output until something not in the
        group is seen. If any datasets require hoisting, they are converted to attributes
        and the group's children sorted alphabetically, attributes first, before output.

        :param lines: an iterator over the lines in the signature
        """
        # A map from dataset/@attribute name to the new signature lines for it + children
        group_members = collections.defaultdict(list)
        meta = {
            'this_group': None,     # The current group path to hoist datasets into
            'this_group_level': 0,  # The level of the current group
            'last_parent': None,    # The group/dataset to associate an attribute with
        }
        new_lines = []  # The result being generated

        def finish_group(reason):
            """This group is done; add ordered signatures of it + all children."""
            for key in sorted(group_members):
                new_lines.extend(group_members[key])
            group_members.clear()
            meta['this_group'] = None
            meta['this_group_level'] = 0
            meta['last_parent'] = None

        def start_group(line, level):
            """This line starts a new group at the current level."""
            meta['this_group'] = line.strip()
            meta['this_group_level'] = level
            meta['last_parent'] = ''
            group_members[meta['last_parent']] = [line]

        for line in lines:
            line_meta = self.META.match(line)
            name = line_meta.group('name')
            path = line_meta.group('path') or ''
            level = path.count('/')
            if not line_meta.group('dataset'):
                # This is a group
                if meta['this_group'] is not None:
                    finish_group('new group')
                start_group(line, level)
            else:
                if meta['this_group'] is None:
                    # We're not hoisting at present; just output unchanged
                    new_lines.append(line)
                elif line_meta.group('attr'):
                    # This is an attribute that just needs to be logged
                    group_members[meta['last_parent']].append(line)
                else:
                    # This is a dataset. Check if it's in the group being processed!
                    if (level == meta['this_group_level'] + 1 and
                            path.startswith(meta['this_group'])):
                        # It is, and might need hoisting within its group
                        meta['last_parent'] = name
                        for match_repl in self.hoists:
                            match, repl = match_repl
                            new_line = match.sub(repl, line)
                            if new_line != line:
                                # Hoist!
                                meta['last_parent'] = ''
                                line = new_line
                                break
                        group_members[meta['last_parent']].append(line)
                    else:
                        # It isn't; end the group and just output new lines
                        finish_group('non-child dataset ' + path)
                        new_lines.append(line)
        if meta['this_group'] is not None:
            # Finish final group
            finish_group('final group')
        return new_lines

    def convert_line(self, line):
        """Convert a single line of a signature."""
        for match_repl in self.re_changes:
            match, repl = match_repl
            line = match.sub(repl, line)
        if not line.strip():
            return ''  # Allow substitutions to remove lines entirely
        else:
            return line


def convert_sig_cli():
    """Command line entry-point to convert signatures from NWB1 to NWB2."""
    parser = argparse.ArgumentParser(description='Convert NWB file signatures')
    parser.add_argument('sig_path',
                        help='path to the signature to convert')
    args = parser.parse_args()
    converter = SignatureConverter()
    converter.convert(args.sig_path)


def cli():
    """Command line entry-point to check or generate NWB signatures."""
    parser = argparse.ArgumentParser(description='Check/generate NWB file signatures')
    parser.add_argument('nwb_path',
                        help='path to the NWB file to compute a signature for')
    parser.add_argument('sig_path', nargs='?',
                        help='if supplied, compare against the signature in this file')
    parser.add_argument('--debug', action='store_true',
                        help='launch pdb on error')
    parser.add_argument('-i', '--ignore-path', nargs='*', default=[],
                        help='ignore datasets matching the given regular expression path')
    args = parser.parse_args()
    try:
        sig_gen = SignatureGenerator()
        for ignore_path in args.ignore_path:
            sig_gen.ignore_path(ignore_path)
        if args.sig_path:
            sys.exit(not sig_gen.compare_to_sig(args.nwb_path, args.sig_path))
        else:
            print(sig_gen.generate(args.nwb_path))
    except:  # noqa
        if args.debug:
            import pdb
            pdb.post_mortem()
        else:
            raise
