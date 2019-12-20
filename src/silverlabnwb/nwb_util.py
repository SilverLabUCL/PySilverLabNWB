"""Standalone utility methods for working with NWB files."""

import sys

try:
    from contextlib import redirect_stdout
except ImportError:
    # Python 2 support
    from contextlib import contextmanager

    @contextmanager
    def redirect_stdout(new_target):
        old_target, sys.stdout = sys.stdout, new_target
        try:
            yield new_target
        finally:
            sys.stdout = old_target


def strip_ignorables(signature, ignore_external_file=False):
    """Strip ignorable text from the given NWB signature.

    The NWB signature algorithm can place items that trivially vary (like file paths,
    modification times) within <% ... %> tags. This method modifies the supplied list
    of strings to strip these out from individual entries.

    :param signature: the signature to strip
    :param ignore_external_file: if True, also strip external file paths
    """
    import re
    ignorable = re.compile(r'<%.*?%>')
    if ignore_external_file:
        ext_re = re.compile(r"( *\d+\. '/.+/external_file): dtype=")
    for i, line in enumerate(signature):
        signature[i] = ignorable.sub('<% ... %>', line)
        if ignore_external_file:
            m = ext_re.match(signature[i])
            if m:
                signature[i] = m.group(1) + ': value ignored'
