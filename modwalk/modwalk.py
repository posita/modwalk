# -*- encoding: utf-8; test-case-name: tests.test_modwalk -*-

# ========================================================================
"""
Copyright and other protections apply. Please see the accompanying
:doc:`LICENSE <LICENSE>` and :doc:`CREDITS <CREDITS>` file(s) for rights
and restrictions governing use of this software. All rights not expressly
waived or licensed are reserved. If those files are missing or appear to
be modified from their originals, then please contact the author before
viewing or using this software in any capacity.
"""
# ========================================================================

from __future__ import absolute_import, division, print_function

TYPE_CHECKING = False  # from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import typing  # noqa: F401 # pylint: disable=import-error,unused-import,useless-suppression

from builtins import *  # noqa: F401,F403 # pylint: disable=redefined-builtin,unused-wildcard-import,useless-suppression,wildcard-import
from future.builtins.disabled import *  # noqa: F401,F403 # pylint: disable=no-name-in-module,redefined-builtin,unused-wildcard-import,useless-suppression,wildcard-import

# ---- Imports -----------------------------------------------------------

import collections
import importlib
import logging
import os.path
import re

# ---- Data --------------------------------------------------------------

__all__ = (
    'modgen',
)

_LOGGER = logging.getLogger(__name__)

_EXTS_PY = set((
    '.py',
    '.pyc',
    '.pyd',
    '.pyo',
    '.so',
))

_PKG_MOD = '__init__'

_RE_MOD_NAME = r'^[A-Za-z_][0-9A-Za-z_]*$'

# ---- Functions ---------------------------------------------------------

# ========================================================================
def logimporterror(logger, name, level=logging.INFO):
    mouthpiece = logger

    while mouthpiece.level == 0:
        if mouthpiece.parent is None:
            break
        else:
            mouthpiece = mouthpiece.parent

    logger.log(level, 'unable to load "%s" (skipping)', name, exc_info=mouthpiece.level <= logging.DEBUG)

# ========================================================================
def modgen(mod_specs):
    """
    TODO
    """
    mod_specs = collections.deque(mod_specs)
    seen = set()

    while mod_specs:
        mod, recurse = mod_specs.popleft()

        if mod.__name__ in seen:
            _LOGGER.warning('module "%s" already visited (skipping)', mod.__name__)
            continue

        mod_path = mod.__file__
        mod_path_dir = os.path.dirname(mod_path)
        mod_path_base, _ = os.path.splitext(os.path.basename(mod_path))
        seen.add(mod.__name__)
        yield mod

        if recurse:
            new_mod_specs = collections.deque()

            if mod_path_base == _PKG_MOD:
                candidates = set()

                for ent_name in os.listdir(mod_path_dir):
                    ent_path = os.path.join(mod_path_dir, ent_name)

                    if os.path.isdir(ent_path):
                        if re.search(_RE_MOD_NAME, ent_name):
                            candidates.add(ent_name)
                    elif os.path.isfile(ent_path):
                        ent_base, ent_ext = os.path.splitext(ent_name)

                        if ent_base == _PKG_MOD:
                            continue

                        if ent_ext in _EXTS_PY \
                                and re.search(_RE_MOD_NAME, ent_base):
                            candidates.add(ent_base)
                    else:
                        _LOGGER.debug('"%s" is of unknown type (skipping)', ent_path)

                mod_pfx = mod.__name__ + '.'

                for candidate in candidates:
                    fq_candidate = mod_pfx + candidate

                    try:
                        new_mod = importlib.import_module(fq_candidate)
                    except Exception:  # pylint: disable=broad-except
                        logimporterror(_LOGGER, fq_candidate)
                    else:
                        new_mod_specs.appendleft((new_mod, recurse))

            mod_specs.extendleft(new_mod_specs)
