#!/usr/bin/env python
# -*- encoding: utf-8 -*-

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

import logging
import unittest

# ---- Constants ---------------------------------------------------------

__all__ = ()

_LOGGER = logging.getLogger(__name__)

# ---- Classes -----------------------------------------------------------

# ========================================================================
class ModwalkTestCase(unittest.TestCase):

    longMessage = True

    # ---- Public hooks --------------------------------------------------

    def test_modwalk(self):  # type: (...) -> None
        pass

# ---- Initialization ----------------------------------------------------

if __name__ == '__main__':
    import tests  # noqa: F401; pylint: disable=unused-import
    unittest.main()
