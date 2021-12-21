#coding:utf-8
from __future__ import print_function
import sys, os, types, importlib, inspect

import DXUSD.Message as msg

def load(file, name, other=None):
    '''
    Load all modules in pakage

    [Arguments]
    file  : package __init__.py path
    name  : package name
    other : pack class in other module

    return : DEV (bool)

    [Example]
    In Tweakers, __init__.py

    import DXUSD.moduleloader as md
    md.load(__file__, __name__, Tweaker)

    # in other packages such as DXUDS_MAYA
    from DXUSD import Tweakers
    md.load(Tweakers.__file__, Tweakers.__name__, __name__)
    '''

    # find this and the repository
    this = sys.modules[other if other else name]
    path = os.path.dirname(file)
    pkgname = name.split('.')[-1]

    # find python module
    modlist = []
    for f in os.listdir(path):
        basename, ext = os.path.splitext(f)
        if basename == '__init__':
            continue

        if not os.path.isfile(os.path.join(path, f)) or ext != '.py':
            continue

        if pkgname.startswith(basename):
            modlist.insert(0, basename)
        else:
            modlist.append(basename)

    reloaded = []
    for basename in modlist:
        # import module
        try:
            mod = importlib.import_module('%s.%s'%(name, basename))
        except Exception as err:
            msg.errmsg('Failed importing : %s.%s'%(name, basename))
            msg.error(err)

        # if DEV, reload mudule
        if msg.DEV:
            msg.message('>>> Load Module :', basename, end=' ')
            try:
                msg.message('>>> complete', end=' ')
                mod = reload(mod)
            except Exception as err:
                msg.message('>>> Reload failed')
                msg.error(err)

        # set classes
        msgattr = []
        for attr in dir(mod):
            obj = getattr(mod, attr)
            if isinstance(obj, (types.TypeType, types.ClassType)):
                submod = inspect.getmodule(obj)
                if path in os.path.dirname(submod.__file__):
                    if obj in reloaded:
                        continue
                    reloaded.append(obj)
                    setattr(this, attr, obj)
                    msgattr.append(attr)

        msg.debug(msgattr)

    if other:
        del this.__dict__[name.split('.')[-1]]

    return msg.DEV


def importModule(this, source):
    '''
    Load source module's attributes

    [Arguments]
    this (str) : destination module name
    source (module) : source module to import
    return : DEV (bool)

    [Example]
    import DXUSD.moduleloader as md
    import DXUSD.Structures as srt
    md.importMoulde(__name__, srt)
    '''
    # find this and the repository
    if msg.DEV:
        reload(source)

    this = sys.modules[this]

    # set classes
    for attr in dir(source):
        obj = getattr(source, attr)
        if attr.startswith('__'):
            continue
        setattr(this, attr, obj)

    # del source
    return msg.DEV
