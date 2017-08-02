# -*- encoding: utf-8; grammar-ext: py; mode: python -*-

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

from __future__ import absolute_import, division, print_function, unicode_literals

TYPE_CHECKING = False  # from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import typing  # noqa: E501,F401; pylint: disable=import-error,unused-import,useless-suppression

# ---- Constants ---------------------------------------------------------

__all__ = ()

__version__ = (0, 0, 0)  # type: typing.Tuple[int, int, int]
__vers_str__ = '.'.join(str(_) for _ in __version__)
__release__ = 'v' + __vers_str__
