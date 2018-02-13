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
import collections
import importlib
import logging
import os
import sys

from twisted import logger as t_logger
from twisted.internet import defer as t_i_defer
from twisted.internet import reactor as t_i_reactor
from twisted.internet import task as t_i_task
from twisted.python import failure as t_p_failure

from .modwalk import (
    logimporterror,
    modgen,
)

from .version import __release__

# ---- Constants ---------------------------------------------------------

__all__ = ()

_LOGGER = logging.getLogger(__name__)
_T_LOGGER = t_logger.Logger(__name__)
_T_LOG_OBSERVER = t_logger.STDLibLogObserver()

_LOG_FMT_ENV = 'LOG_FMT'
_LOG_FMT_DFLT = '%(message)s'
_LOG_LVL_ENV = 'LOG_LVL'
_LOG_LVL_DFLT = logging.getLevelName(logging.WARNING)

# ---- Classes -----------------------------------------------------------

# ========================================================================
class CallbackAppender(argparse.Action):

    # ---- Class methods -------------------------------------------------

    @classmethod
    def evalcallback(cls,
        value,
        ns,
    ):
        args = ()
        kw = {}

        if value.startswith('@'):
            try:
                path, symbol = value[1:].rsplit(':', 1)
            except ValueError:
                raise ValueError('"{}" must be in the format @FILE:SYMBOL'.format(value))

            path = os.path.realpath(path)
            execfile(path, ns, ns)
            callback = ns[symbol]
        else:
            callback = eval(value, ns, ns)

            try:
                callback, args, kw = callback
            except TypeError:
                pass
            except ValueError:
                try:
                    callback, args = callback
                except ValueError:
                    pass

        return (callback, args, kw)

    @classmethod
    def factory(cls,
        errback_options=(),
        both_options=(),
    ):
        return lambda *_args, **_kw: cls(errback_options, both_options, *_args, **_kw)

    # ---- Constructor ---------------------------------------------------

    def __init__(self,
        errback_options,  # type: typing.Tuple[typing.Text, ...]
        both_options,  # type: typing.Tuple[typing.Text, ...]
    *args, **kw):  # type: (...) -> None
        super(CallbackAppender, self).__init__(*args, **kw)
        self._both_options = set(both_options)
        self._errback_options = set(errback_options)

    # ---- Overrides -----------------------------------------------------

    def __call__(self, parser, namespace, values, option_string=None):
        d = getattr(namespace, self.dest)

        if not values \
                or d is None:
            d = t_i_defer.Deferred()
            setattr(namespace, self.dest, d)

        default_callback_vals = (t_i_defer.passthru, None, None)

        if len(values) == 0:
            return
        elif len(values) == 1:
            evaled_callback_vals = self.evalcallback(values[0], dict(namespace.imported_modules))

            if option_string in self._errback_options:
                callback, callback_args, callback_kw = default_callback_vals
                errback, errback_args, errback_kw = evaled_callback_vals
            elif option_string in self._both_options:
                callback, callback_args, callback_kw = evaled_callback_vals
                errback, errback_args, errback_kw = evaled_callback_vals
            else:
                callback, callback_args, callback_kw = evaled_callback_vals
                errback, errback_args, errback_kw = default_callback_vals
        elif len(values) == 2:
            callback, callback_args, callback_kw = self.evalcallback(values[0], dict(namespace.imported_modules))
            errback, errback_args, errback_kw = self.evalcallback(values[1], dict(namespace.imported_modules))
        else:
            option_string_msg = ' given to option {}'.format(option_string) if option_string else ''

            raise ValueError('too many arguments ({}){}'.format(len(values), option_string_msg))

        d.addCallbacks(callback, errback, callback_args, callback_kw, errback_args, errback_kw)
        callback_name = None if callback is t_i_defer.passthru else getattr(callback, '__name__', repr(callback))
        errback_name = None if errback is t_i_defer.passthru else getattr(errback, '__name__', repr(errback))

        if callback_name is not None \
                and errback_name is not None:
            _LOGGER.debug('added %s and %s to callback and errback chain, respectively', callback_name, errback_name)
        elif callback_name is not None:
            _LOGGER.debug('added %s to callback chain', callback_name)
        elif errback_name is not None:
            _LOGGER.debug('added %s to errback chain', errback_name)

# ========================================================================
class ImportAppender(argparse.Action):

    # ---- Overrides -----------------------------------------------------

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

    def __init__(self,
        should_recurse,  # type: bool
    *args, **kw):  # type: (...) -> None
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
    t_logger.globalLogBeginner.beginLoggingTo((_T_LOG_OBSERVER,), redirectStandardIO=False)

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

    d = t_i_task.deferLater(t_i_reactor, 0, modgen, namespace.mod_specs)
    d.chainDeferred(namespace.deferred)

    def _consumeall(_pipeline):
        try:
            _pipeline = iter(_pipeline)
        except TypeError:
            # _pipeline was not iterable, so assume it was already
            # consumed
            pass
        else:
            # Make sure pipeline is consumed
            collections.deque(_pipeline, maxlen=0)

    namespace.deferred.addCallback(_consumeall)

    def _stop(_arg):
        if isinstance(_arg, t_p_failure.Failure):
            _T_LOGGER.failure('Unhandled error', _arg)

        t_i_reactor.stop()

        # Suppress "Main loop terminated." message
        t_logger.globalLogPublisher.removeObserver(_T_LOG_OBSERVER)

    namespace.deferred.addBoth(_stop)
    t_i_reactor.run()

    return 0

# ========================================================================
def _parser(
    prog=None,  # type: typing.Optional[typing.Text]
):  # type: (...) -> argparse.ArgumentParser
    description = """
Invoke callback chains on loaded modules.
""".strip()

    log_lvls = ', '.join('"{}"'.format(logging.getLevelName(l)) for l in (logging.CRITICAL, logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG))
    epilog = """
The environment variables {log_lvl} and {log_fmt} can be used to configure logging output.
If set, {log_lvl} must be an integer, or one of (from least to most verbose): {log_lvls}.
It defaults to "{log_lvl_dflt}".
If set, {log_fmt} must be a logging format compatible with Python's ``logging`` module.
It defaults to "{log_fmt_dflt}".
""".strip().format(log_fmt=_LOG_FMT_ENV, log_fmt_dflt=_LOG_FMT_DFLT, log_lvl=_LOG_LVL_ENV, log_lvl_dflt=_LOG_LVL_DFLT, log_lvls=log_lvls)

    parser = argparse.ArgumentParser(prog=prog, description=description, epilog=epilog)

    parser.add_argument('-V', '--version', action='version', version='%(prog)s {}'.format(__release__))

    eval_callback_metavar = 'CALLBACK'
    mod_spec_metavar = 'MODULE'
    callback_dflt_str = "functools.partial(itertools.imap, lambda x: print('{}'.format(x.__name__)) or x)"

    module_callback_group = parser.add_argument_group(
        'modules and callbacks',
        description="""
{eval_callback_metavar} can be one of two formats: "CALLBACK_EXPR[, ARGS_EXPR[, KW_EXPR]]" or "@FILE:CALLBACK_NAME".
The first format is an expression that evaluates to a callable (with optional args and kw that will be passed back to it).
The second is a reference to a path to a file and symbol name within that file.
(Note that the second form begins with a "@" character.)
All {eval_callback_metavar}s must be suitable for appending to a Twisted Deferred's callback chain.
The iterable passed to the first callback in the chain will be all loaded (and discovered) {mod_spec_metavar}s.
The default callback chain consists of single callback that will print out each loaded module and return the module object: ``{callback_dflt}``.
{mod_spec_metavar} is a fully qualified module name suitable for use in an import statement.
Import errors are always ignored when attempting to discover sub-modules and sub-packages.
""".strip().format(callback_dflt=native_str(callback_dflt_str), eval_callback_metavar=eval_callback_metavar, mod_spec_metavar=mod_spec_metavar),
    )

    callbacks_dest = 'deferred'

    import functools
    import itertools

    ns = {
        functools.__name__: functools,
        itertools.__name__: itertools,
    }

    callback, callback_args, callback_kw = CallbackAppender.evalcallback(callback_dflt_str, ns)
    callbacks_dflt = t_i_defer.Deferred()
    callbacks_dflt.addCallback(callback, *callback_args, **callback_kw)
    callback_options = ('-c', '--add-callback')
    callbacks_options = ('-C', '--add-callbacks')
    errback_options = ('-e', '--add-errback')
    both_options = ('-b', '--add-both')
    callback_appender = CallbackAppender.factory(errback_options, both_options)

    module_callback_group.add_argument(
        '-D',
        action=callback_appender,
        default=callbacks_dflt,
        dest=callbacks_dest,
        help='clear the callback chain of all prior callbacks',
        metavar=eval_callback_metavar,
        nargs=0,
    )

    module_callback_group.add_argument(
        *callback_options,
        action=callback_appender,
        dest=callbacks_dest,
        help='add {eval_callback_metavar} as a callback'.format(eval_callback_metavar=eval_callback_metavar),
        metavar=eval_callback_metavar,
        nargs=1  # ,
    )

    module_callback_group.add_argument(
        *errback_options,
        action=callback_appender,
        dest=callbacks_dest,
        help='add {eval_callback_metavar} as an errback'.format(eval_callback_metavar=eval_callback_metavar),
        metavar=eval_callback_metavar,
        nargs=1  # ,
    )

    module_callback_group.add_argument(
        *both_options,
        action=callback_appender,
        dest=callbacks_dest,
        help='add {eval_callback_metavar} to as both a callback and an errback'.format(eval_callback_metavar=eval_callback_metavar),
        metavar=eval_callback_metavar,
        nargs=1  # ,
    )

    module_callback_group.add_argument(
        *callbacks_options,
        action=callback_appender,
        dest=callbacks_dest,
        help='add the first {eval_callback_metavar} as a callback and the second {eval_callback_metavar} as an errback'.format(eval_callback_metavar=eval_callback_metavar),
        metavar=eval_callback_metavar,
        nargs=2  # ,
    )

    imported_modules_metavar = mod_spec_metavar
    imported_modules_dest = 'imported_modules'

    module_callback_group.add_argument(
        '-I',
        action=ImportAppender,
        default={},
        dest=imported_modules_dest,
        help='clear all {imported_modules_metavar}s loaded into scope for evaluating any prior {eval_callback_metavar}'.format(eval_callback_metavar=eval_callback_metavar, imported_modules_metavar=imported_modules_metavar),
        metavar=imported_modules_metavar,
        nargs=0,
    )

    module_callback_group.add_argument(
        '-i',
        action=ImportAppender,
        dest=imported_modules_dest,
        help='load each {imported_modules_metavar} into scope for evaluating any subsequent {eval_callback_metavar}'.format(eval_callback_metavar=eval_callback_metavar, imported_modules_metavar=imported_modules_metavar),
        metavar=imported_modules_metavar,
        nargs='+',
    )

    mod_specs_dest = 'mod_specs'

    module_callback_group.add_argument(
        '-M',
        action=ModuleAppender.factory(True),
        default=[],
        dest=mod_specs_dest,
        help='load each {mod_spec_metavar} and discover and load any sub-modules or sub-packages for passing to the first callback in the chain'.format(mod_spec_metavar=mod_spec_metavar),
        metavar=mod_spec_metavar,
        nargs='+',
    )

    module_callback_group.add_argument(
        '-m',
        action=ModuleAppender.factory(False),
        dest=mod_specs_dest,
        help='load each {mod_spec_metavar} for passing to the first callback in the chain'.format(mod_spec_metavar=mod_spec_metavar),
        metavar=mod_spec_metavar,
        nargs='+',
    )

    suppress_import_errors_dest = 'suppress_import_errors'

    module_callback_group.add_argument(
        '-S',
        action='store_false',
        default=False,
        dest=suppress_import_errors_dest,
        help='DO NOT suppress import errors for {eval_callback_metavar}s and explicitly named {mod_spec_metavar}s (default)'.format(eval_callback_metavar=eval_callback_metavar, mod_spec_metavar=mod_spec_metavar),
    )

    module_callback_group.add_argument(
        '-s',
        action='store_true',
        dest=suppress_import_errors_dest,
        help='suppress import errors for {eval_callback_metavar}s and explicitly named {mod_spec_metavar}s'.format(eval_callback_metavar=eval_callback_metavar, mod_spec_metavar=mod_spec_metavar),
    )

    return parser
