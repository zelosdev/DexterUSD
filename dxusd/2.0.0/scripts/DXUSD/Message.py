#coding:utf-8
from __future__ import print_function

import linecache, sys
import os, types


DEV = not __file__.startswith('/backstage') and \
      not __file__.startswith('/others/backstage')


def message(*args, **kwargs):
    '''
    Print.

    [Usage]
    message('Send', 'Message'[, end=''])
    '''
    print(*args, **kwargs)

def warning(*args, **kwargs):
    '''
    Warning print. If dev=True, only print on debug mode.

    [Arguments]
    dev (bool) : If True, only send message on debug mode

    [Usage]
    warning('Send', 'Message'[, dev=True ])
    '''
    if kwargs.has_key('dev'):
        _dev = kwargs.pop('dev')
        if not (_dev and DEV):
            return

    args = list(args)
    args.insert(0, '# Warning :')

    print(*args, **kwargs)

def errmsg(*args, **kwargs):
    '''
    Error message print. If dev=True, only print on debug mode.

    [Arguments]
    dev (bool) : If True, only send message on debug mode

    [Usage]
    errmsg('Send', 'Message'[, dev=True ])
    '''
    if kwargs.has_key('dev'):
        _dev = kwargs.pop('dev')
        if not (_dev and DEV):
            return

    args = list(args)
    args.insert(0, '# Error :')

    print(*args, **kwargs)

def error(*args, **kwargs):
    '''
    Error. The base Exception is RuntimeError. If args have other
    Exception, raise use the given Exception.

    [Usage]
    error('Send', 'Error', ...)
    error(ImportError, 'Reload Faild')

    try:
        ...
    except Exception as err:
        error(err)
    '''

    err = None
    msg = []
    for arg in args:
        if isinstance(arg, BaseException):
            err = arg
        elif type(arg) in (types.TypeType, types.ClassType) and\
             issubclass(arg, BaseException):
            err = arg()
        else:
            msg.append(str(arg))

    if err:
        if str(err):
            msg.insert(0, str(err))

        raise err.__class__(' '.join(msg))
    else:
        raise RuntimeError(' '.join(msg))


def debug(*args, **kwargs):
    '''
    Print when debug mode.

    [Arguments]
    prefix (bool, True) : If False, remove prefix message('# DEBUG')

    [Usage]
    debug('Send', 'Message'[, prefix=False, end=''])
    '''
    if DEV:
        args = list(args)
        prefix = True if not kwargs.has_key('prefix') else kwargs.pop('prefix')
        if prefix:
            args.insert(0, '# Debug :')

        print(*args, **kwargs)
