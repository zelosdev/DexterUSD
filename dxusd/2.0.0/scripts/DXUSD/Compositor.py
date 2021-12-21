#coding:utf-8
from __future__ import print_function

import os
import glob
from pxr import Sdf, Usd, UsdGeom

from DXUSD.Structures import Arguments
import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg

_TVORDER = ['ani', 'sim', 'groom']
_LGTUSD  = '/assetlib/3D/usd/light/prman/prman.usd'
_MAXNUM  = 4


def GetLayer(out):
    outlyr = utl.AsLayer(out, create=True, format=var.USDA)
    utl.CheckPipeLineLayerVersion(outlyr)
    with utl.OpenStage(outlyr) as stage:
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    return outlyr

def SubLayerComp(out, src, update=True):
    relpath = utl.GetRelPath(out, src)
    outlyr  = GetLayer(out)
    srclyr  = utl.AsLayer(src)
    default = srclyr.defaultPrim
    outlyr.defaultPrim = default
    if update:
        utl.UpdateLayerData(outlyr, srclyr).timecode()
    utl.SubLayersAppend(outlyr, relpath)
    outlyr.Save()
    del outlyr, srclyr

def Packing(
        out, src,
        primPath=None, rkind=None, rname=None,
        vsets=list(),
        addChild=True, ckind=None, cname=None,
        update=False, timecode=False
    ):
    '''
    primPath (str, Sdf.Path) : prepend xform prim
    rkind    (str)  : root prim kind
    rname    (str)  : root prim assetInfo name

    vsets    (list) : variant setup [(name, value), ...]

    addChild (str)  : 'path' or 'vset'. path is appendChild to primPath, vset is appendChild to last vspec.primSpec
    ckind    (str)  : last prim kind
    cname    (str)  : last prim assetInfo name

    update   (bool) : update customLayerData and timecode
    timecode (bool) : update timecode
    '''
    def getVariantSpec(parent, name, value):
        vsetSpec = utl.GetVariantSetSpec(parent, name)
        vspec    = utl.GetVariantSpec(vsetSpec, value)
        # if value != 'v000':
        parent.variantSelections.update({name: value})
        return vspec.primSpec

    if primPath:
        primPath = Sdf.Path(primPath)

    outlyr  = GetLayer(out)
    relpath = None
    if src:
        srclyr  = utl.AsLayer(src)
        relpath = utl.GetRelPath(out, src)
        srcRoot = srclyr.defaultPrim
        if primPath:
            if addChild == 'path':
                primPath = primPath.AppendChild(srcRoot)
        else:
            primPath = Sdf.Path('/' + srcRoot)

    prefixes = primPath.GetPrefixes()
    # defaultPrim
    outlyr.defaultPrim = prefixes[0].name

    # make prim
    for p in prefixes:
        utl.GetPrimSpec(outlyr, p)

    # root prim kind
    if rkind:
        rcount = 0
        if len(prefixes) > 2: rcount = 1
        for i in range(len(prefixes) - rcount):
            spec = outlyr.GetPrimAtPath(prefixes[i])
            spec.SetInfo('kind', rkind)
    # root prim assetInfo
    if rname:
        spec = outlyr.GetPrimAtPath(prefixes[0])
        spec.assetInfo = {'name': rname}

    # variant setup
    parent = outlyr.GetPrimAtPath(prefixes[-1])
    for n, v in vsets:
        parent = getVariantSpec(parent, n, v)

    if src:
        if addChild == 'vset':
            parent = utl.GetPrimSpec(outlyr, parent.path.AppendChild(srcRoot))
        utl.ReferenceAppend(parent, relpath)
        if update:
            utl.UpdateLayerData(outlyr, srclyr).doIt()
        if timecode:
            utl.UpdateLayerData(outlyr, srclyr).timecode()
        del srclyr

    outlyr.Save()
    del outlyr

# def SelectVariant(out, name, value, primPath=None):
#     dstlyr = utl.AsLayer(out)
#     with utl.OpenStage(dstlyr) as stage:
#         prim = stage.GetDefaultPrim()
#         if primPath:
#             prim = stage.GetPrimAtPath(primPath)
#         vnames = prim.GetVariantSet(name).GetVariantNames()
#         if value in vnames:
#             spec = dstlyr.GetPrimAtPath(prim.GetPath())
#             spec.variantSelections.update({name: value})
#             dstlyr.Save()
#     del dstlyr
def SelectVariant(out, name, value, primPath=None):
    dstlyr = utl.AsLayer(out)
    spec   = dstlyr.GetPrimAtPath('/' + dstlyr.defaultPrim)
    if primPath:
        spec = dstlyr.GetPrimAtPath(primPath)
    vsetSpec = spec.variantSets.get(name)
    if value in vsetSpec.variants.keys():
        spec.variantSelections.update({name: value})
    dstlyr.Save()
    del dstlyr

def CleanupVariant(input, name, primPath=None):
    rootDir = utl.DirName(input)
    outlyr  = utl.AsLayer(input)
    if primPath:
        spec = outlyr.GetPrimAtPath(primPath)
    else:
        spec = outlyr.GetPrimAtPath('/' + outlyr.defaultPrim)

    vsetSpec = spec.variantSets.get(name)
    if not vsetSpec:
        del outlyr
        return

    current = spec.variantSelections.get(name)
    data = vsetSpec.variants
    src  = data.keys()
    src.remove(current)
    if len(src) <= _MAXNUM:
        del outlyr
        return

    src.sort()
    targets = src[:len(src) - _MAXNUM]  # cleanup targets
    for n in targets:
        # remove variant
        msg.debug('\tCleanup %s : %s' % (name, n))
        vsetSpec.RemoveVariant(data[n])
        # rename directory
        os.rename(utl.SJoin(rootDir, n), utl.SJoin(rootDir, '_' + n))

    outlyr.Save()
    del outlyr


#-------------------------------------------------------------------------------
class Composite:
    def __init__(self, master):
        arg = Arguments()
        arg.master = master
        arg.D.SetDecode(utl.DirName(arg.master))
        self.arg = arg
        self.src = self.arg.master
        print('#', self.arg)

    #---------------------------------------------------------------------------
    # ASSET
    def assetLightComp(self):
        output = self.src.replace('.usd', '.prv.usd')
        outlyr = GetLayer(output)
        utl.SubLayersAppend(outlyr, _LGTUSD)
        utl.SubLayersAppend(outlyr, './' + utl.BaseName(self.src))
        utl.UpdateLayerData(outlyr, self.src).timecode()
        outlyr.Save()
        del outlyr

    def assetPack(self):
        output = utl.SJoin(self.arg.D.ROOTS, 'asset', self.arg.F.ASSETS)
        msg.debug('COMP ASSET\t:', output)
        msg.debug('')
        vsets = [(var.T.VAR_ASSET, self.arg.asset)]
        if self.arg.seq:
            name = self.arg.seq
            if self.arg.shot:
                name += '_' + self.arg.shot
            vsets.append(('entity', name))
        else:
            vsets.append(('entity', 'asset'))
        Packing(output, self.src, primPath='/World', rkind='assembly',
                vsets=vsets, addChild='vset')
        # asset entity select
        SelectVariant(output, 'entity', 'asset', primPath='/World{asset=%s}' % self.arg.asset)

    def asset_taskPack(self):
        output = utl.SJoin(self.arg.D.ASSET, self.arg.F.ASSET)
        msg.debug('COMP TASK\t:', output)
        msg.debug('')
        task = self.arg.task
        if self.arg.has_key('branch'):
            task = 'branch'
        Packing(output, self.src, rkind='assembly', rname=self.arg.asset,
            vsets=[(var.T.VAR_TASK, task)])
        # model task select
        if not self.arg.customdir:
            SelectVariant(output, var.T.VAR_TASK, 'model', primPath='/' + self.arg.asset)
        self.src = output
        self.assetLightComp()

        # collect asset
        self.assetPack()
        # output = utl.SJoin(self.arg.D.ASSETS, self.arg.F.ASSETS)
        # msg.debug('COMP ASSET\t:', output)
        # msg.debug('')
        # Packing(output, self.src, primPath='/World', rkind='assembly',
        #     vsets=[(var.T.VAR_ASSET, self.arg.asset)], addChild='vset')

    def asset_branchPack(self):
        if not self.arg.has_key('branch'):
            return
        output = utl.SJoin(self.arg.D.BRANCH, self.arg.F.BRANCH)
        msg.debug('COMP TASK\t:', output)
        msg.debug('')
        Packing(output, self.src, rkind='assembly', rname=self.arg.assetName,
            vsets=[(var.T.VAR_TASK, self.arg.task)])
        # model task select
        SelectVariant(output, var.T.VAR_TASK, 'model', primPath='/' + self.arg.assetName)
        self.src = output
        self.assetLightComp()

        # collect branch
        output = utl.SJoin(self.arg.D.BRANCHES, self.arg.F.BRANCHES)
        msg.debug('COMP BRANCH\t:', output)
        msg.debug('')
        Packing(output, self.src, primPath='/' + self.arg.asset, rkind='assembly',
            vsets=[(var.T.VAR_BRANCH, self.arg.branch)], addChild='vset')
        self.src = output
        self.assetLightComp()


    def asset_normal(self):
        # collect version
        output = utl.SJoin(self.arg.D.TASK, self.arg.F.TASK)
        msg.debug('COMP VER\t:', output)
        msg.debug('')
        Packing(output, self.src, vsets=[(self.arg.N.USD.VAR_TASKVER, self.arg.N.USD.VAR_VER)])
        # CleanupVariant(output, self.arg.N.USD.VAR_TASKVER)
        self.src = output
        self.assetLightComp()

    def asset_groom(self):
        srclyr  = utl.AsLayer(self.src)
        srcdata = srclyr.customLayerData
        rigFile = srcdata.get('rigFile')
        if rigFile:
            decoded = var.D.Decode(rigFile)
            if decoded.has_key('task') and decoded.task == var.T.MODEL:
                decoded.ver = utl.Ver(0)
                rigVer = var.N.rig.RIGVER.Encode(**decoded)
            else:
                rigVer = utl.BaseName(utl.DirName(rigFile))
        else:
            rigVer = utl.Ver(0)
            # get model lastversion
            arg = Arguments(**self.arg.AsDict())
            arg.task = 'model'
            arg.ver  = utl.GetLastVersion(arg.D.TASK)
            rigFile  = utl.SJoin(arg.D.TASKV, arg.F.MASTER)

        # collect version
        output = utl.SJoin(self.arg.D.TASK, self.arg.F.TASK)
        msg.debug('COMP VER\t:', output)
        msg.debug('')
        vsets = [(var.T.VAR_RIGVER, rigVer), (self.arg.N.USD.VAR_TASKVER, self.arg.N.USD.VAR_VER)]
        Packing(output, self.src, vsets=vsets)
        # arc rigFile
        if rigFile and utl.AsLayer(rigFile):
            Packing(output, rigFile, vsets=vsets)
        self.src = output
        self.assetLightComp()

    def asset_crowd(self):
        # collect version
        output = utl.SJoin(self.arg.D.TASKN, self.arg.F.NSLYR)
        msg.debug('COMP VER\t:', output)
        msg.debug('')
        Packing(output, self.src, vsets=[(self.arg.N.USD.VAR_TASKVER, self.arg.N.USD.VAR_VER)])
        self.src = output
        self.assetLightComp()

        # collect layer (agent)
        output = utl.SJoin(self.arg.D.TASK, self.arg.F.TASK)
        msg.debug('COMP AGENT:\t', output)
        msg.debug('')
        # Packing(output, self.src, vsets=[(var.T.VAR_AGENT, self.arg.nslyr)])
        Packing(output, self.src, primPath='/' + self.arg.asset, vsets=[(var.T.VAR_AGENT, self.arg.nslyr)])
        self.src = output
        self.assetLightComp()

    def asset_clip(self):
        # collect version
        output = utl.SJoin(self.arg.D.TASKN, self.arg.F.NSLYR)
        msg.debug('COMP VER\t:', output)
        msg.debug('')
        Packing(output, self.src, vsets=[(self.arg.N.USD.VAR_TASKVER, self.arg.N.USD.VAR_VER)], timecode=True)
        self.src = output
        self.assetLightComp()

        # collect layer
        output = utl.SJoin(self.arg.D.TASK, self.arg.F.TASK)
        msg.debug('COMP CLIP\t:', output)
        msg.debug('')
        Packing(output, self.src, vsets=[(var.T.VAR_CLIP, self.arg.nslyr)], timecode=True)
        self.src = output
        self.assetLightComp()


    def ASSETPROC(self):
        self.assetLightComp()
        msg.debug('START\t\t:', self.arg.master)
        msg.debug('')

        if self.arg.task == var.T.GROOM:
            self.asset_groom()
        elif self.arg.task == var.T.CLIP:
            self.asset_clip()
        elif self.arg.task == var.T.AGENT:
            self.asset_crowd()
        elif self.arg.task == var.T.FEATHER:
            self.asset_feather()
        else:
            self.asset_normal()

        # branch
        self.asset_branchPack()
        # task
        self.asset_taskPack()


    #---------------------------------------------------------------------------
    # SHOT
    #   cam, lgt comp
    def shotLightComp(self, primPath=None, addCam=False):
        out = self.src.replace('.usd', '.prv.usd')
        if primPath:
            Packing(out, self.src, primPath=primPath, rkind='assembly', addChild='path', timecode=True)

        outlyr = GetLayer(out)

        # add light
        spec = utl.GetPrimSpec(outlyr, '/World/Lights', type='Scope')
        utl.ReferenceAppend(spec, _LGTUSD)

        # add shot cam
        if addCam:
            cam = utl.SJoin(self.arg.D.SHOT, 'cam', 'cam.usd')
            utl.SubLayersAppend(outlyr, utl.GetRelPath(out, cam))

        #   override fStop
        spec = utl.GetPrimSpec(outlyr, '/World/Cam/main_cam', specifier='over')
        attr = utl.GetAttributeSpec(spec, 'fStop', 0.0, Sdf.ValueTypeNames.Float)
        attr.default = 0.0

        if not primPath:
            srclyr = utl.AsLayer(self.src)
            outlyr.defaultPrim = srclyr.defaultPrim
            utl.UpdateLayerData(outlyr, srclyr).timecode()
            utl.SubLayersAppend(outlyr, utl.GetRelPath(out, self.src))

        outlyr.Save()
        del outlyr
        return out

    def addWorldXform(self, out):
        # get inputCache
        def get_inputcache(src):
            srclyr  = utl.AsLayer(src)
            inc = srclyr.customLayerData.get('inputCache')
            if not inc:
                return None
            tmp = Arguments()
            tmp.D.SetDecode(utl.DirName(inc))
            if tmp.task != 'ani':
                return get_inputcache(inc)
            else:
                return inc

        if not self.arg.has_attr('WorldXform'):
            incache = get_inputcache(self.src)
            if not incache:
                self.arg.WorldXform = ''
                return

            xfiles = glob.glob('%s/*.xform.usd' % utl.DirName(incache))
            if xfiles:
                self.arg.WorldXform = xfiles[0]

        if self.arg.WorldXform:
            outlyr = GetLayer(out)
            spec   = outlyr.GetPrimAtPath('/World/Rig/%s' % self.arg.nslyr)
            if not spec:
                spec = utl.GetPrimSpec(outlyr, '/World/Rig/%s' % self.arg.nslyr, specifier='over')
            utl.ReferenceAppend(spec, utl.GetRelPath(out, self.arg.WorldXform))
            outlyr.Save()
            del outlyr

    def shot_rigPack(self):
        # collect nslyr
        output = utl.SJoin(self.arg.D.TASK, self.arg.F.TASK)
        msg.debug('COMP NSLYR\t:', output)
        msg.debug('')
        SubLayerComp(output, self.src, update=True)
        # preview
        SubLayerComp(output.replace('.usd', '.prv.usd'), self.src.replace('.usd', '.prv.usd'), update=True)
        self.src = output

    def shot_taskPack(self):
        output = utl.SJoin(self.arg.D.SHOT, self.arg.F.SHOT)
        msg.debug('COMP TASK\t:', output)
        msg.debug('')
        relpath = utl.GetRelPath(output, self.src)
        outlyr  = GetLayer(output)
        outlyr.defaultPrim = 'World'

        # add current source
        utl.SubLayersAppend(outlyr, relpath)

        # re-order layers
        order  = ['fx', 'groom', 'sim', 'ani', 'layout', 'cam']
        srclyrs= [None] * len(order)
        layers = outlyr.subLayerPaths
        for lyr in layers:
            task = lyr.split('/')[1]
            if task in order:
                srclyrs[order.index(task)] = lyr
            else:
                srclyrs.append(lyr)
        layers.clear()
        for lyr in srclyrs:
            if lyr: layers.append(lyr)

        spec = utl.GetPrimSpec(outlyr, '/World', specifier='over')
        spec.SetInfo('kind', 'assembly')
        spec.assetInfo = {'name': self.arg.shotName}

        # update timecode
        utl.UpdateLayerData(outlyr, self.src).timecode()
        utl.GetAttributeSpec(spec, 'userProperties:inTime', int(outlyr.startTimeCode), Sdf.ValueTypeNames.Int, custom=True)
        utl.GetAttributeSpec(spec, 'userProperties:outTime',int(outlyr.endTimeCode),   Sdf.ValueTypeNames.Int, custom=True)

        # version override
        path = '/World'
        vset = None
        if self.arg.task == 'ani' or self.arg.task == 'sim' or self.arg.task == 'groom':
            path += '/Rig/' + self.arg.nslyr
            vset = (self.arg.task + 'Ver', self.arg.nsver)
        elif self.arg.task == 'cam':
            path += '/Cam'
            vset = (self.arg.task + 'Ver', self.arg.ver)
        elif self.arg.task == 'set':
            path += '/Layout/' + self.arg.nslyr
            vset = (self.arg.task + 'Ver', self.arg.nsver)

        if vset:
            spec = utl.GetPrimSpec(outlyr, path, specifier='over')
            spec.variantSelections.update({vset[0]: vset[1]})

        outlyr.Save()
        del outlyr

        self.src = output
        self.shotLightComp()

        # collect shot
        output = utl.SJoin(self.arg.D.SHOTS, self.arg.F.SHOTS)
        msg.debug('COMP SHOT\t:', output)
        msg.debug('')
        # Packing(output, self.src, vsets=[('seq', self.arg.seq), ('shot', self.arg.shotName)])
        Packing(output, self.src, vsets=[('shot', self.arg.shotName)])


    def shot_cam(self):
        # collect version
        output = utl.SJoin(self.arg.D.TASK, self.arg.F.TASK)
        msg.debug('COMP VER\t:', output)
        msg.debug('')
        vsets = [(self.arg.N.USD.VAR_TASKVER, self.arg.N.USD.VAR_VER)]
        Packing(output, self.src, primPath='/World', rkind='assembly',
                vsets=vsets, addChild='path', timecode=True)
        # CleanupVariant(output, self.arg.N.USD.VAR_TASKVER, primPath='/World/Cam')
        self.src = output

    def shot_layout(self):
        # collect version
        output = utl.SJoin(self.arg.D.TASKN, self.arg.F.NSLYR)
        msg.debug('COMP VER\t:', output)
        msg.debug('')
        vsets = [(self.arg.N.USD.VAR_TASKVER, self.arg.N.USD.VAR_VER)]
        Packing(output, self.src, primPath='/World/Layout', rkind='assembly',
                vsets=vsets, addChild='path', timecode=True)
        # preview
        Packing(output.replace('.usd', '.prv.usd'), self.src.replace('.usd', '.prv.usd'),
                vsets=vsets, timecode=True)
        self.src = output

        # collect nslyr
        output = utl.SJoin(self.arg.D.TASK, self.arg.F.TASK)
        msg.debug('COMP NSLYR\t:', output)
        msg.debug('')
        SubLayerComp(output, self.src, update=True)
        # preview
        SubLayerComp(output.replace('.usd', '.prv.usd'), self.src.replace('.usd', '.prv.usd'), update=True)
        self.src = output

    def shot_crowd(self):
        # collect version
        output = utl.SJoin(self.arg.D.TASK, self.arg.F.TASK)
        msg.debug('COMP VER:\t', output)
        msg.debug('')
        vsets = [(self.arg.N.USD.VAR_TASKVER, self.arg.N.USD.VAR_VER)]
        Packing(output, self.src, primPath='/World', rkind='assembly',
                vsets=vsets, addChild='path', timecode=True)
        # CleanupVariant(output, self.arg.N.USD.VAR_TASKVER, primPath='/World/Crowd')
        # preview
        Packing(output.replace('.usd', '.prv.usd'), self.src.replace('.usd', '.prv.usd'),
                vsets=vsets, timecode=True)
        self.src = output

    def shot_sim(self):
        # collect version
        output = utl.SJoin(self.arg.D.TASKN, self.arg.F.NSLYR)
        msg.debug('COMP VER\t:', output)
        msg.debug('')

        # get versions
        vdata = []
        vdata.append((self.arg.N.USD.VAR_TASKVER, self.arg.N.USD.VAR_VER))
        srclyr  = utl.AsLayer(self.src)
        incache = srclyr.customLayerData.get('inputCache')
        if incache:
            tmp = Arguments()
            tmp.D.SetDecode(utl.DirName(incache))
            vdata.append((tmp.N.USD.VAR_TASKVER, tmp.N.USD.VAR_VER))

        vdata = list(reversed(vdata))
        print(vdata)

        Packing(output, self.src, primPath='/World/Rig', rkind='assembly',
                vsets=vdata, addChild='path', timecode=True)
        return output

    def shot_groom(self):
        # collect version
        output = utl.SJoin(self.arg.D.TASKN, self.arg.F.NSLYR)
        msg.debug('COMP VER\t:', output)
        msg.debug('')

        # get versions
        vdata = []
        vdata.append((self.arg.N.USD.VAR_TASKVER, self.arg.N.USD.VAR_VER))

        def AddVersion(filename):
            srclyr = utl.AsLayer(filename)
            if srclyr:
                incache = srclyr.customLayerData.get('inputCache')
                if incache:
                    tmp = Arguments()
                    tmp.D.SetDecode(utl.DirName(incache))
                    # if tmp.N.USD.VAR_TASKVER == var.T.VAR_ANIVER and vdata[-1][0] != var.T.VAR_SIMVER:
                    #     vdata.append((var.T.VAR_SIMVER, 'v000'))
                    vdata.append((tmp.N.USD.VAR_TASKVER, tmp.N.USD.VAR_VER))
                    AddVersion(incache)

        AddVersion(self.src)
        vdata = list(reversed(vdata))

        Packing(output, self.src, primPath='/World/Rig', rkind='assembly',
                vsets=vdata, addChild='path', timecode=True)
        return output

    def shot_ani(self):
        # collect version
        output = utl.SJoin(self.arg.D.TASKN, self.arg.F.NSLYR)
        msg.debug('COMP VER\t:', output)
        msg.debug('')
        vsets = [(self.arg.N.USD.VAR_TASKVER, self.arg.N.USD.VAR_VER)]
        Packing(output, self.src, primPath='/World/Rig', rkind='assembly',
                vsets=vsets, addChild='path', timecode=True)
        # CleanupVariant(output, self.arg.N.USD.VAR_TASKVER, primPath='/World/Rig/' + self.arg.nslyr)
        return output


    def SHOTPROC(self):
        msg.debug('START\t\t:', self.arg.master)
        msg.debug('')

        self.arg.shotName = self.arg.seq + '_' + self.arg.shot
        # cam
        if self.arg.task == 'cam':
            self.shot_cam()
        # layout
        elif self.arg.task == 'layout':
            lgtusd = self.shotLightComp(primPath='/World/Layout', addCam=True)
            self.shot_layout()
        elif self.arg.task == 'crowd':
            lgtusd = self.shotLightComp(primPath='/World/Crowd', addCam=True)
            self.shot_crowd()
        # ani, sim, groom
        else:
            lgtusd = self.shotLightComp(primPath='/World/Rig', addCam=True)
            if self.arg.task == 'sim':
                output = self.shot_sim()
            elif self.arg.task == 'groom':
                output = self.shot_groom()
            else:
                output = self.shot_ani()
            # preview
            Packing(output.replace('.usd', '.prv.usd'), self.src.replace('.usd', '.prv.usd'),
                    vsets=[(self.arg.N.USD.VAR_TASKVER, self.arg.N.USD.VAR_VER)], timecode=True)
            self.src = output
            self.shot_rigPack()

        self.shot_taskPack()


    #---------------------------------------------------------------------------
    # MAIN
    def DoIt(self):
        if self.arg.asset:
            self.ASSETPROC()
        elif self.arg.shot:
            self.SHOTPROC()
