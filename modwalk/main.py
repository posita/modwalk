# -*- encoding: utf-8; test-case-name: tests.test_main -*-

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

import builtins
import argparse
import importlib
import inspect
import logging
import os
import sys

from .modwalk import (
    logimporterror,
    modwalk,
)

from .version import __release__

# ---- Constants ---------------------------------------------------------

__all__ = ()

_LOGGER = logging.getLogger(__name__)

_LOG_LVL_ENV = 'LOG_LVL'
_LOG_FMT_DFLT = '%(message)s'
_LOG_FMT_ENV = 'LOG_FMT'
_LOG_LVL_DFLT = logging.getLevelName(logging.WARNING)

# ---- Classes -----------------------------------------------------------

# ========================================================================
class CallbackAppender(argparse.Action):

    # ---- Overrides -----------------------------------------------------

    def __call__(self, parser, namespace, values, option_string=None):
        callbacks = getattr(namespace, self.dest)

        if not values \
                or callbacks is None:
            callbacks = []
            setattr(namespace, self.dest, callbacks)

        for value in values:
            try:
                mod_name, callback_name = value.rsplit('.')
            except ValueError:
                mod_name = '.'
                callback_name = value

            ns = dict(inspect.getmembers(builtins))
            ns.update(globals())

            try:
                if mod_name == '.':
                    callback = ns[callback_name]
                else:
                    mod = __import__(mod_name, ns, ns, (callback_name,))
                    callback = getattr(mod, callback_name)

                if not callable(callback):
                    raise ValueError(u'"{}" is not callable'.format(value))
            except Exception:  # pylint: disable=broad-except
                if namespace.ignore_import_errors:
                    logimporterror(_LOGGER, value)
                else:
                    raise
            else:
                callbacks.append(callback)

# ========================================================================
class ModuleAppender(argparse.Action):

    # ---- Class methods -------------------------------------------------

    @classmethod
    def factory(cls, should_recurse):
        return lambda *_args, **_kw: cls(should_recurse, *_args, **_kw)

    # ---- Constructor ---------------------------------------------------

    def __init__(self, should_recurse, *args, **kw):
        super(ModuleAppender, self).__init__(*args, **kw)
        self._should_recurse = should_recurse

    # ---- Overrides -----------------------------------------------------

    def __call__(self, parser, namespace, values, option_string=None):
        mod_specs = getattr(namespace, self.dest)

        if mod_specs is None:
            mod_specs = []
            setattr(namespace, self.dest, mod_specs)

        for value in values:
            try:
                mod = importlib.import_module(value)
            except Exception:  # pylint: disable=broad-except
                if namespace.ignore_import_errors:
                    logimporterror(_LOGGER, value)
                else:
                    raise
            else:
                mod_specs.append((mod, self._should_recurse))

# ---- Functions ---------------------------------------------------------

# ========================================================================
def configlogging():  # type: (...) -> None
    log_lvl_name = os.environ.get(_LOG_LVL_ENV) or _LOG_LVL_DFLT

    try:
        log_lvl = int(log_lvl_name, 0)
    except (TypeError, ValueError):
        log_lvl = 0
        log_lvl = logging.getLevelName(log_lvl_name)  # type: ignore

    log_fmt = os.environ.get(_LOG_FMT_ENV, _LOG_FMT_DFLT)
    logging.basicConfig(format=log_fmt)
    logging.getLogger().setLevel(log_lvl)
    from . import LOGGER
    LOGGER.setLevel(log_lvl)

# ========================================================================
def main():  # type: (...) -> None
    configlogging()
    sys.exit(_main())

# ========================================================================
def _main(
    argv=None,  # type: typing.Optional[typing.Sequence[typing.Text]]
):  # type: (...) -> int
    parser = _parser()
    ns = parser.parse_args(argv)

    if not ns.mod_specs:
        parser.print_help()

        return 0

    if ns.callbacks is None:
        callbacks = (print,)
    else:
        callbacks = ns.callbacks

    modwalk(ns.mod_specs, callbacks)

    return 0

# ========================================================================
def _parser(
    prog=None,  # type: typing.Optional[typing.Text]
):  # type: (...) -> argparse.ArgumentParser
    description = u"""
Load each given module and invoke each given callback for each loaded module.
""".strip()

    log_lvls = u', '.join(u'"{}"'.format(logging.getLevelName(l)) for l in (logging.CRITICAL, logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG))
    epilog = u"""
The environment variables {log_lvl} and {log_fmt} can be used to configure logging output.
If set, {log_lvl} must be an integer, or one of (from least to most verbose): {log_lvls}.
It defaults to "{log_lvl_dflt}".
If set, {log_fmt} must be a logging format compatible with Python's ``logging`` module.
It defaults to "{log_fmt_dflt}".
""".strip().format(log_fmt=_LOG_FMT_ENV, log_fmt_dflt=_LOG_FMT_DFLT, log_lvl=_LOG_LVL_ENV, log_lvl_dflt=_LOG_LVL_DFLT, log_lvls=log_lvls)

    parser = argparse.ArgumentParser(prog=prog, description=description, epilog=epilog)

    parser.add_argument(u'-V', u'--version', action='version', version=u'%(prog)s {}'.format(__release__))

    callback_metavar = u'CALLBACK'
    mod_spec_metavar = u'MODULE'

    module_callback_group = parser.add_argument_group(
        u'modules and callbacks',
        description=u"""
{callback_metavar} is a fully qualified name of an importable callable.
{mod_spec_metavar} is a fully qualified module name suitable for use in an import statement.
Import errors are always ignored when attempting to discover sub-modules and sub-packages.
Each {callback_metavar} should take the loaded {mod_spec_metavar} as its only argument.
If a {callback_metavar} raises a ``modwalk.FilterModule`` exception, then no other {callback_metavar} will be called for that {mod_spec_metavar}.
""".strip().format(callback_metavar=callback_metavar, mod_spec_metavar=mod_spec_metavar),
    )

    callbacks_dest = 'callbacks'

    module_callback_group.add_argument(
        u'-C',
        action=CallbackAppender,
        dest=callbacks_dest,
        help=u'clear all {callback_metavar}s previously given on the command line'.format(callback_metavar=callback_metavar),
        metavar=callback_metavar,
        nargs=0,
    )

    module_callback_group.add_argument(
        u'-c',
        action=CallbackAppender,
        dest=callbacks_dest,
        help=u'load each {callback_metavar} to be called for each loaded {mod_spec_metavar}'.format(callback_metavar=callback_metavar, mod_spec_metavar=mod_spec_metavar),
        metavar=callback_metavar,
        nargs='+',
    )

    module_callback_group.add_argument(
        u'-I',
        action='store_false',
        default=False,
        dest='ignore_import_errors',
        help=u'DO NOT ignore import errors for {callback_metavar}s and explicitly named {mod_spec_metavar}s (default)'.format(callback_metavar=callback_metavar, mod_spec_metavar=mod_spec_metavar),
    )

    module_callback_group.add_argument(
        u'-i',
        action='store_true',
        dest='ignore_import_errors',
        help=u'ignore import errors for {callback_metavar}s and explicitly named {mod_spec_metavar}s'.format(callback_metavar=callback_metavar, mod_spec_metavar=mod_spec_metavar),
    )

    mod_specs_dest = 'mod_specs'

    module_callback_group.add_argument(
        u'-M',
        action=ModuleAppender.factory(True),
        dest=mod_specs_dest,
        help=u'load each {mod_spec_metavar} and discover and load any sub-modules or sub-packages'.format(mod_spec_metavar=mod_spec_metavar),
        metavar=mod_spec_metavar,
        nargs='+',
    )

    module_callback_group.add_argument(
        u'-m',
        action=ModuleAppender.factory(False),
        dest=mod_specs_dest,
        help=u'load each {mod_spec_metavar}'.format(mod_spec_metavar=mod_spec_metavar),
        metavar=mod_spec_metavar,
        nargs='+',
    )

    return parser
