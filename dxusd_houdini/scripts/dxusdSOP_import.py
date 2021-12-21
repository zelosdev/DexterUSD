#coding:utf-8
from __future__ import print_function

import os
from pxr import Usd, Sdf

import DXUSD_HOU.Message as msg
import DXUSD_HOU.Utils as utl
import DXUSD_HOU.Vars as var
import DXRulebook.Interface as rb

if msg.DEV:
    rb.Reload()


def ReloadStage(usdpath):
    lyr = utl.AsLayer(usdpath)
    if lyr:
        with utl.OpenStage(lyr) as stg:
            stg.Reload()


def IsShot(usdpath):
    flags = rb.Flags()
    try:
        flags.D.SetDecode(utl.DirName(usdpath))
        return flags.IsShot()
    except Exception as e:
        msg.debug(e)
        return False


def GetShotChildren(usdpath, prim=None, hasVSet=False, vsel={var.ORDER:[]}):
    '''
    vsel = {
        var.ORDER:[vset1, vset2, ...],
        vset1:[sel],
        vset2:[sel], ...
    }
    '''
    lyr = utl.AsLayer(usdpath)
    if not lyr:
        return []

    with utl.OpenStage(lyr) as stg:
        target = stg.GetDefaultPrim()
        if prim:
            target = stg.GetPrimAtPath(target.GetPath().AppendChild(prim))

        for k in vsel[var.ORDER]:
            vset = target.GetVariantSet(k)
            vset.SetVariantSelection(vsel[k][0])

        res = []
        for child in target.GetChildren():
            if not hasVSet or child.HasVariantSets():
                res.append(child.GetName())
        return res


def GetVariantPrim(usdpath, primpath=None):
    lyr = utl.AsLayer(usdpath)
    if not lyr:
        return ''

    with utl.OpenStage(lyr) as stg:
        # auto find prim that has variantSet
        prims = [stg.GetPrimAtPath(primpath or '/')]
        while prims and not prims[0].HasVariantSets():
            prims.extend(prims.pop(0).GetChildren())

        return prims[0].GetPath().pathString if prims else ''


def GetAssetLayer(usdpath, primpath):
    lyr = utl.AsLayer(usdpath)
    if not lyr:
        return '', '', '', ''

    astpath  = ''
    astnslyr = ''
    asttask  = ''
    astmaster = ''
    with utl.OpenStage(lyr) as stg:
        prim = stg.GetPrimAtPath(primpath)
        if not prim:
            return '', '', '', ''

        stacks = prim.GetPrimStack()
        stacks.reverse()
        for stack in stacks:
            # ani(sim) > RIGFILE, groom > GROOMFILE, feather > FEATHERFILE
            filenames = {var.T.RIG:var.T.RIGFILE,
                         var.T.GROOM:var.T.GROOMFILE,
                         var.T.FEATHER:var.T.FEATHERFILE}
            for task, key in filenames.items():
                if stack.layer.customLayerData.has_key(key):
                    filename = stack.layer.customLayerData[key]
                    if utl.NotExist(filename):
                        continue

                    astargs = var.D.Decode(utl.DirName(filename))
                    asttask = astargs.get(var.T.TASK) or task
                    taskcode  = 'TASK'
                    if astargs.get(var.T.TASK) == var.T.MODEL:
                        astnslyr = astargs.ver
                        taskcode += 'V'
                    else:
                        taskcode += 'N'
                        if filename.endswith('.mb'):
                            astnslyr = utl.BaseName(filename).split('.')[0]
                            astargs.nslyr = astnslyr
                        elif filename.endswith('.usd'):
                            astnslyr = utl.DirName(filename).split('/')[-1]

                    try:
                        astfile = var.F.ABNAME.Encode(**astargs)
                        astpath = var.D.KINDS.Encode(**astargs)
                        astpath = utl.SJoin(astpath, astfile)

                        astfile   = var.F[asttask].MASTER.Encode(**astargs)
                        astmaster = var.D[taskcode].Encode(**astargs)
                        astmaster = utl.SJoin(astmaster, astfile)

                        if utl.NotExist(astpath) or utl.NotExist(astmaster):
                            raise ValueError()
                    except:
                        continue
                    break

    return astpath, astmaster, asttask, astnslyr


def GetVariantsFromMasterPath(usdpath):
    vsels = {var.ORDER:[]}
    try:
        args = var.D.Decode(usdpath)
        task = args.get(var.T.TASK)
        if task:
            vsels[var.ORDER].append(var.T.TASK)
            vsels[var.T.TASK] = task
        else:
            raise ValueError()

        taskvername = var.N.VAR_TASKVER.Encode(task=task)
        taskver = args.get(taskvername)
        if taskver:
            vsels[var.ORDER].append(taskvername)
            vsels[taskvername] = taskver
        else:
            raise ValueError()
    except:
        return vsels
    return vsels


def GetPrimVariants(usdpath, primpath=None, vsels={var.ORDER:[]}):
    lyr = utl.AsLayer(usdpath)
    vsets = {var.ORDER:[]}
    # vsets = {
    #     setname1  : [selected, v1, v2, v3...], ...
    #     __order__ : [setname1, setname2, ...]
    # }

    if not lyr:
        return vsets

    updated = False
    with utl.OpenStage(lyr, True) as stg:
        trglyr = stg.GetEditTarget().GetLayer()
        trglyr.SetPermissionToEdit(True)

        if not primpath:
            dprim = stg.GetDefaultPrim()
        else:
            dprim = stg.GetPrimAtPath(primpath)

        if not dprim:
            return vsets

        # set variant selections
        for name in vsels[var.ORDER]:
            if name in dprim.GetVariantSets().GetNames():
                vset = dprim.GetVariantSet(name)
                vset.SetVariantSelection(vsels[name])

        # get changed variant sets
        vsetlist = dprim.GetVariantSets()
        for name in vsetlist.GetNames():
            vset = vsetlist.GetVariantSet(name)
            vars = vset.GetVariantNames()

            if vsels.has_key(name):
                sel = vsels[name]
            else:
                sel  = vset.GetVariantSelection()
                if not sel in vars:
                    sel = vars[-1]
                    vsels[name] = sel
                    vsels[var.ORDER].append(name)
                    updated = True
            vars.insert(0, sel)
            vsets[name] = vars
            vsets[var.ORDER].append(name)

    if updated:
        return GetPrimVariants(usdpath, primpath, vsels)
    else:
        return vsets


def GetChildren(usdpath, primpath):
    res = []
    lyr = utl.AsLayer(usdpath)
    if not lyr:
        return res

    with utl.OpenStage(lyr, True) as stg:
        prim = stg.GetPrimAtPath(primpath)
        if not prim:
            return res

        for child in prim.GetChildren():
            res.append(child.GetPath().pathString)

    return res


def PrimExists(usdpath, primpath):
    lyr = utl.AsLayer(usdpath)
    if not lyr:
        return False
    with utl.OpenStage(lyr, True) as stg:
        prim = stg.GetPrimAtPath(primpath)
        if not prim:
            return False
    return True


def GetMasterUSD(node, kind):
    if kind in [var.T.ASSET, var.T.BRANCH]:
        usdpath = node.parm('assetusdpath').evalAsString()
    else:
        usdpath = node.parm('usdpath').evalAsString()

    if not os.path.exists(usdpath):
        return

    def GetVars(node, kind):
        vars = {}
        for i in range(node.parm('%svariantfolder'%kind).evalAsInt()):
            vn = node.parm('%svariantset%d'%(kind, i)).evalAsString()
            vs = node.parm('%svariants%d'%(kind, i)).evalAsString()
            vars[vn] = vs
        return vars

    arg   = var.D.Decode(usdpath)
    vars = GetVars(node, kind)

    # 만약 task가 branch 이거나, kind가 branch 일 때, variant를 다시 구해야 한다.
    if var.T.BRANCH in [vars.get(var.T.TASK), kind]:
        branch = vars.get(var.T.BRANCH)
        if not branch:
            branch = GetVars(node, var.T.ASSET).get(var.T.BRANCH, '')
        else:
            vars = GetVars(node, var.T.BRANCH)
        arg.branch = branch

    arg.task = vars.get(var.T.TASK, '')

    taskcode = 'TASK'
    if arg.task == var.T.MODEL:
        arg.ver = vars.get(var.T.VAR_MODELVER, '')
        taskcode += 'V'
    elif arg.task == var.T.RIG:
        arg.nslyr = vars.get(var.T.VAR_RIGVER, '')
        taskcode += 'N'
    elif arg.task == var.T.GROOM:
        arg.nslyr = vars.get(var.T.VAR_GROOMVER, '')
        taskcode += 'N'
    elif arg.task == var.T.CLIP:
        arg.nslyr = vars.get(var.T.VAR_CLIP, '')
        arg.nsver = vars.get(var.T.VAR_CLIPVER, '')
        taskcode += 'NV'
    else:
        arg.nslyr = node.parm('nslyrname').evalAsString()
        taskcode += 'NV'

        if vars.has_key(var.T.VAR_GROOMVER):
            arg.task = var.T.GROOM
            arg.nsver = vars.get(var.T.VAR_GROOMVER, '')
        elif vars.has_key(var.T.VAR_SIMVER):
            arg.task = var.T.SIM
            arg.nsver = vars.get(var.T.VAR_SIMVER, '')
        elif vars.has_key(var.T.VAR_ANIVER):
            arg.task = var.T.ANI
            arg.nsver = vars.get(var.T.VAR_ANIVER, '')
        else:
            return

    try:
        path = var.D[taskcode].Encode(**arg)
        file = var.F[arg.task].MASTER.Encode(**arg)
    except Exception as e:
        msg.errmsg(e)
        return

    return utl.SJoin(path, file)


def GetHighGeomDprim(usdpath):
    lyr = utl.AsLayer(usdpath)
    if not lyr or not lyr.defaultPrim:
        return

    dprim = utl.GetDefaultPrim(lyr)
    if not dprim:
        return

    primpath = dprim.path
    for vset in dprim.variantSelections.items():
        primpath = primpath.AppendVariantSelection(*vset)

    searches = ['Geom/Render', 'Geom', 'Groom/Render', 'Groom']
    searches = [primpath.AppendPath(_) for _ in searches]
    geomusdpath = None

    for search in searches:
        payloadprim = lyr.GetPrimAtPath(search)
        if not payloadprim:
            continue

        if payloadprim.payloadList.prependedItems:
            geomusdpath = payloadprim.payloadList.prependedItems[0].assetPath
        elif payloadprim.payloadList.explicitItems:
            geomusdpath = payloadprim.payloadList.explicitItems[0].assetPath

        if geomusdpath:
            break

    geomusdpath = utl.GetAbsPath(usdpath, geomusdpath)
    geomusd = utl.AsLayer(geomusdpath)
    return geomusd.defaultPrim if geomusd else None
