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
from future.utils import native_str
from past.builtins import execfile  # type: ignore

# ---- Imports -----------------------------------------------------------

import argparse
import importlib
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
class EvalAppender(argparse.Action):

    # ---- Overrides -----------------------------------------------------

    def __call__(self, parser, namespace, values, option_string=None):
        callbacks = getattr(namespace, self.dest)

        if not values \
                or callbacks is None:
            callbacks = []
            setattr(namespace, self.dest, callbacks)

        ns = namespace.imported_modules

        for value in values:
            callback = eval(value, ns, ns)

            if not callable(callback):
                raise ValueError('"{}" is not a callable expression'.format(value))

            callbacks.append(callback)

# ========================================================================
class FileSymbolAppender(argparse.Action):

    # ---- Constructor ---------------------------------------------------

    # ====================================================================
    def __init__(self, *args, **kw):
        super(FileSymbolAppender, self).__init__(*args, **kw)
        self._loaded_paths = {}

    # ---- Public hooks --------------------------------------------------

    # ====================================================================
    def __call__(self, parser, namespace, values, option_string=None):
        callbacks = getattr(namespace, self.dest)

        if not values \
                or callbacks is None:
            callbacks = []
            setattr(namespace, self.dest, callbacks)

        ns = namespace.imported_modules

        for value in values:
            try:
                path, symbol = value.rsplit(':', 1)
            except ValueError:
                raise ValueError('"{}" must be in the format FILE:SYMBOL'.format(value))

            path = os.path.realpath(path)

            if path in self._loaded_paths:
                _LOGGER.debug('file "%s" already loaded', path)
            else:
                _LOGGER.debug('loading "%s"', path)
                execfile(path, ns, ns)
                self._loaded_paths[path] = ns

            callback = self._loaded_paths[path][symbol]

            if not callable(callback):
                raise ValueError('"{}" does not reference a callable expression'.format(value))

            callbacks.append(callback)

# ========================================================================
class ImportAppender(argparse.Action):

    # ---- Public hooks --------------------------------------------------

    # ====================================================================
    def __call__(self, parser, namespace, values, option_string=None):
        modules = getattr(namespace, self.dest)

        if not values \
                or modules is None:
            modules = {}
            setattr(namespace, self.dest, modules)

        for value in values:
            try:
                mod = importlib.import_module(value)
            except Exception:  # pylint: disable=broad-except
                if namespace.suppress_import_errors:
                    logimporterror(_LOGGER, value, logging.WARNING)
                else:
                    raise
            else:
                modules[value] = mod

# ========================================================================
class ModuleAppender(argparse.Action):

    # ---- Class methods -------------------------------------------------

    @classmethod
    def factory(cls, should_recurse):
        return lambda *_args, **_kw: cls(should_recurse, *_args, **_kw)

    # ---- Constructor ---------------------------------------------------

    def __init__(self, should_recurse, *args, **kw):
        super(ModuleAppender, self).__init__(*args, **kw)
        self._should_recurse = int(bool(should_recurse))

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
                if namespace.suppress_import_errors:
                    logimporterror(_LOGGER, value, logging.WARNING)
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
    namespace = parser.parse_args(argv)

    if not namespace.mod_specs:
        parser.print_help()

        return 0

    modwalk(namespace.mod_specs, namespace.callbacks)

    return 0

# ========================================================================
def _parser(
    prog=None,  # type: typing.Optional[typing.Text]
):  # type: (...) -> argparse.ArgumentParser
    description = u"""
Invoke callback chains on loaded modules.
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

    eval_callback_metavar = u'CALLBACK_EXPRESSION'
    file_callback_metavar = u'FILE:CALLBACK_NAME'
    mod_spec_metavar = u'MODULE'
    callback_dflt_str = u"functools.partial(itertools.imap, lambda x: print('{}'.format(x.__name__)) or x)"

    module_callback_group = parser.add_argument_group(
        u'modules and callbacks',
        description=u"""
{eval_callback_metavar} is an expression that evaluates to a callable that takes a single value.
The return value of each callback is passed to the next callback in the chain.
The iterable passed to the first callback in the chain will be all loaded (and discovered) {mod_spec_metavar}s.
The default callback chain consists of single callable that will print out each loaded module and return the module object: ``{callback_dflt}``.
{mod_spec_metavar} is a fully qualified module name suitable for use in an import statement.
Import errors are always ignored when attempting to discover sub-modules and sub-packages.
""".strip().format(callback_dflt=native_str(callback_dflt_str), eval_callback_metavar=eval_callback_metavar, mod_spec_metavar=mod_spec_metavar),
    )

    callbacks_dest = 'callbacks'

    import functools
    import itertools

    ns = {
        functools.__name__: functools,
        itertools.__name__: itertools,
    }

    callbacks_dflt = [eval(callback_dflt_str, ns, ns)]

    module_callback_group.add_argument(
        u'-C',
        action=EvalAppender,
        default=callbacks_dflt,
        dest=callbacks_dest,
        help=u'clear the callback chain of all prior callbacks',
        metavar=eval_callback_metavar,
        nargs=0,
    )

    module_callback_group.add_argument(
        u'-e',
        action=EvalAppender,
        dest=callbacks_dest,
        help=u'evaluate each {eval_callback_metavar} add it to the callback chain'.format(eval_callback_metavar=eval_callback_metavar),
        metavar=eval_callback_metavar,
        nargs='+',
    )

    module_callback_group.add_argument(
        u'-f',
        action=FileSymbolAppender,
        dest=callbacks_dest,
        help=u'load each {file_callback_metavar} add it to the callback chain'.format(file_callback_metavar=file_callback_metavar),
        metavar=file_callback_metavar,
        nargs='+',
    )

    imported_modules_metavar = mod_spec_metavar
    imported_modules_dest = 'imported_modules'

    module_callback_group.add_argument(
        u'-I',
        action=ImportAppender,
        default={},
        dest=imported_modules_dest,
        help=u'clear all {imported_modules_metavar}s loaded into scope for evaluating any prior {eval_callback_metavar}'.format(eval_callback_metavar=eval_callback_metavar, imported_modules_metavar=imported_modules_metavar),
        metavar=imported_modules_metavar,
        nargs=0,
    )

    module_callback_group.add_argument(
        u'-i',
        action=ImportAppender,
        dest=imported_modules_dest,
        help=u'load each {imported_modules_metavar} into scope for evaluating any subsequent {eval_callback_metavar}'.format(eval_callback_metavar=eval_callback_metavar, imported_modules_metavar=imported_modules_metavar),
        metavar=imported_modules_metavar,
        nargs='+',
    )

    mod_specs_dest = 'mod_specs'

    module_callback_group.add_argument(
        u'-M',
        action=ModuleAppender.factory(True),
        default=[],
        dest=mod_specs_dest,
        help=u'load each {mod_spec_metavar} and discover and load any sub-modules or sub-packages for passing to the first callback in the chain'.format(mod_spec_metavar=mod_spec_metavar),
        metavar=mod_spec_metavar,
        nargs='+',
    )

    module_callback_group.add_argument(
        u'-m',
        action=ModuleAppender.factory(False),
        dest=mod_specs_dest,
        help=u'load each {mod_spec_metavar} for passing to the first callback in the chain'.format(mod_spec_metavar=mod_spec_metavar),
        metavar=mod_spec_metavar,
        nargs='+',
    )

    suppress_import_errors_dest = 'suppress_import_errors'

    module_callback_group.add_argument(
        u'-S',
        action='store_false',
        default=False,
        dest=suppress_import_errors_dest,
        help=u'DO NOT suppress import errors for {eval_callback_metavar}s and explicitly named {mod_spec_metavar}s (default)'.format(eval_callback_metavar=eval_callback_metavar, mod_spec_metavar=mod_spec_metavar),
    )

    module_callback_group.add_argument(
        u'-s',
        action='store_true',
        dest=suppress_import_errors_dest,
        help=u'suppress import errors for {eval_callback_metavar}s and explicitly named {mod_spec_metavar}s'.format(eval_callback_metavar=eval_callback_metavar, mod_spec_metavar=mod_spec_metavar),
    )

    return parser
