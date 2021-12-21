#coding:utf-8
from __future__ import print_function

import DXUSD.moduleloader as mdl
import DXUSD.Utils as utl
DEV = mdl.importModule(__name__, utl)

import DXUSD_HOU.Vars as var
import DXUSD_HOU.Structures as srt


def DependInfoToDict(lyrdata):
    '''
    [Intput]
    {
        depend:(kind):(task):path : usd path,
        depend:(kind):(task):vars : variants (vset=var, ...)
        depend:(kind):(task):nslyr : nslyr
        ...
        depend:shot:(task):srcpath : source layer path (if ani, it's rig)
        depend:asset/branch:(task):geomdprim : geometry deault prim
    }

    [Return] - srt.Dependency
    {
        (kind) : {
            (var.USDPATH) : (path),
            (var.NSLYR) : (nslyr name)
            (var.ORDER) : [(vset), ...]
            (vset) : (variant)
            ...
            (var.LYRTASK) : task
            (var.SRCPATH) : source layer path
            (var.GEOMDPRIM) : (Geometry default prim)
        },
        ...
    }
    '''

    res = srt.Dependency()
    for key, data in lyrdata.items():
        if not key.startswith('%s:' % var.DEPEND):
            continue

        elms = key.split(':')
        dkind = elms[1]
        dtask = elms[2]
        dtype = elms[3]

        res[dkind][var.LYRTASK] = dtask

        if key.endswith(':%s'%var.PATH):
            res[dkind][var.USDPATH] = data
        elif key.endswith(':nslyr'):
            res[dkind][var.NSLYR] = data
        elif key.endswith(':%s'%var.VARS):
            orders = []
            for vsets in data.split(', '):
                vset, varient = vsets.split('=')
                orders.append(vset)
                res[dkind][vset] = varient
            res[dkind][var.ORDER] = orders
        elif key.endswith(':srcpath'):
            res[dkind][var.SRCPATH] = data
        elif key.endswith(':geomdprim'):
            res[dkind][var.GEOMDPRIM] = data

    return res


def DictToDependInfo(kind, data):
    '''
    [Inputs]
    kind (str) : kind name
    data (dict) :
    {
        (var.USDPATH) : (path),
        (var.NSLYR) : (nslyr name)
        (var.ORDER) : [(vset), ...]
        (vset) : (variant)
        ...
        (var.LYRTASK) : task
        (var.SRCPATH) : source layer path
        (var.GEOMDPRIM) : (Geometry default prim)
    }

    [Return] - dict
    {
        depend:(kind):(task):path : usd path,
        depend:(kind):(task):vars : variants (vset=var, ...)
        depend:(kind):(task):nslyr : nslyr
        ...
        depend:shot:(task):srcpath : source layer (if ani, it's rig)
        depend:asset/branch:(task):geomdprim : geometry default prim
    }
    '''
    if not data:
        return {}

    task = data.get(var.LYRTASK, '')

    varinents = []
    for vset in data[var.ORDER]:
        if vset in data:
            varinents.append('%s=%s'%(vset, data[vset]))

    res = dict()
    res[var.DEPENDPATH%(kind, task)]  = data[var.USDPATH]
    res[var.DEPENDVARS%(kind, task)]  = ', '.join(varinents)
    res[var.DEPENDNSLYR%(kind, task)] = data[var.NSLYR]

    if kind == var.T.SHOT:
        res[var.DEPENDSRCPATH%(kind, task)] = data.get(var.SRCPATH)
    else:
        res[var.DEPENDGEOMDPRIM%(kind, task)] = data.get(var.GEOMDPRIM)

    return res


def GetTxBasePath(**kwargs):
    '''
    [Arguments]
    kwargs : rulebook flags (asset, branch)
    '''
    if not kwargs.has_key('asset'):
        msg.error('Need "asset" argument')

    flags = {'asset':kwargs['asset']}
    if kwargs.has_key('branch'):
        path = 'asset/{asset}/branch/{branch}/texture'
        flags['branch'] = kwargs['branch']
    else:
        path = 'asset/{asset}/texture'

    return path.format(**flags)





#
