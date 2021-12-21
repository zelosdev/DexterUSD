#coding:utf-8
from __future__ import print_function

import os, re, string, gc, copy, types, json, glob
from pxr import Usd, UsdGeom, UsdShade, UsdUtils, Sdf, Kind

import DXUSD.Vars as var
import DXUSD.Message as msg

# ------------------------------------------------------------------------------
# USD Utils
# ------------------------------------------------------------------------------

def AsLayer(path, create=False, clear=False, format=var.USDC, error=False):
    '''
    Get layer.

    [Arguments]
    path (str, Sdf.Layer, Usd.Stage) : layer path
    create (bool) : if True and the file doesn't exist at the path, it creates.
    clear (bool)  : clear the layer
    format (str)  : set usd format ('usd', 'usda')
    error (bool)  : if True, when failed to get the layer, raise error.

    [Return]
    Sdf.Layer or None
    '''
    layer = None
    if isinstance(path, (str, unicode)):
        layer = Sdf.Layer.FindOrOpen(path)
        if not layer and create:
            layer = Sdf.Layer.CreateNew(path, args={'format':format})
            layer.customLayerData = {'dxusd': var._DXVER}
    elif isinstance(path, Sdf.Layer):
        layer = path
    elif isinstance(path, Usd.Stage):
        layer = path.GetRootLayer()

    if not layer:
        if error:
            msg.Error('AsLayer@Utils :',
                      'Given "path" type is not available. (%s)'%str(path))
        else:
            return

    if clear:
        layer.Clear()
        layer.customLayerData = {'dxusd': var._DXVER}

    if not layer.permissionToEdit:
        layer.SetPermissionToEdit(True)

    return layer


class OpenStage:
    '''
    Open usd stage with 'with' statement. When leave 'with' statement, it will
    delete opened stage.

    [Usage]
    with OpenStage(layer) as stage:
        ... do something with stage
    '''
    def __init__(self, layer, loadAll=True):
        '''
        [Arguments]
        layer (Sdf.Layer)
        loadAll (bool)    : if False, open stage with Usd.Stage.LoadNone
        '''
        _load = Usd.Stage.LoadAll if loadAll else Usd.Stage.LoadNone
        self.stage  = Usd.Stage.Open(layer, load=_load)

    def __enter__(self):
        return self.stage

    def __exit__(self, type, value, traceback):
        self.free(self.stage)

    def free(self, obj):
        for ref in gc.get_referrers(obj):
            if isinstance(ref, dict):
                for key, value in ref.items():
                    if value is obj:
                        ref[key] = None
        del obj
        gc.collect()


class StageMetadata(object):
    '''
    It contains scene information such as frame, upAxis, etc. It can also get
    the scene information from layer's stage metadata, and set to layer.

    [Members]
    self.sf / ef (float)   : start-end frame
    self.frame (tuple-2)   : start-end frame
    self.fps / tps (float) : framesPerSecond / timeCodesPerSecond
    self.up (str)          : up axis (UsdGeom.Tokens.x, y, z)
    '''
    def __init__(self, layer=None,
                 sf=0.0, ef=0.0, fps=24.0, tps=None, up=UsdGeom.Tokens.y):
        '''
        Set init values. If give a layer, it will set from the layer.
        '''
        self.sf  = sf; self.ef  = ef
        self.fps = fps
        self.tps = fps if tps == None else tps
        self.up  = up
        self.customData = dict()

        if layer != None:
            self.Get(layer)

    def __repr__(self):
        res  = '[Stage Metadata]\n'
        res += '\t\t  frames : %d - %d\n'%(self.frame)
        res += '\t\t  fps : %d\n'%self.fps
        res += '\t\t  tps : %d\n'%self.tps
        res += '\t\t  up axis : %s\n'%self.up
        res += '\t\t  customData : %s\n'%str(self.customData)
        return res

    @property
    def frame(self):
        return self.sf, self.ef

    @frame.setter
    def frame(self, v):
        self.sf, self.ef = v

    def IsSequenced(self):
        return self.sf != self.ef

    def Get(self, layer, compare=False):
        '''
        Get metadata from given layer

        [Arguments]
        layer (Sdf.Layer)
        compare (bool) : If True, it compares its frame range and the given
                         layer's, then choose wider frame range.
        '''
        layer = AsLayer(layer)
        with OpenStage(layer, False) as stage:
            sf  = stage.GetStartTimeCode()
            ef  = stage.GetEndTimeCode()

            if compare:
                self.frame = (min(self.sf, sf), max(self.ef, ef))
            else:
                self.frame = (sf, ef)

            self.fps = stage.GetFramesPerSecond()
            self.tps = stage.GetTimeCodesPerSecond()
            self.up  = stage.GetMetadata(UsdGeom.Tokens.upAxis)

        self.customData = layer.customLayerData

    def Set(self, layer, dprim=None, comment=None, customData=None,
            save=True, yup=True):
        '''
        Set metadata to given layer with more informations.

        [Arguments]
        layer (Sdf.Layer)
        dprim (Usd.Prim, Sdf.PrimSpec, str) : default prim
        comment (str) : add comment to layer
        customData (dict) : add customData to layer
        save (bool) : if False, it won't save the layer after setting
        '''
        with OpenStage(layer, False) as stage:
            if self.sf != 0:
                stage.SetStartTimeCode(self.sf)
            if self.ef != 0:
                stage.SetEndTimeCode(self.ef)
            if self.sf != 0 or self.ef != 0:
                stage.SetFramesPerSecond(self.fps)
                stage.SetTimeCodesPerSecond(self.tps)
            if yup:
                stage.SetMetadata(UsdGeom.Tokens.upAxis, self.up)

            if isinstance(dprim, Usd.Prim):
                stage.DefaultPrim(dprim)
            elif isinstance(dprim, Sdf.PrimSpec):
                layer.defaultPrim = dprim.name
            elif isinstance(dprim, (str, unicode)):
                layer.defaultPrim = str(dprim).split('/')[1]

            if comment != None:
                layer.comment = comment

            # update custom layer data
            orgCusData = layer.customLayerData
            if isinstance(customData, dict) and customData:
                orgCusData.update(customData)
            elif self.customData:
                orgCusData.update(self.customData)
            layer.customLayerData = orgCusData

        if save:
            layer.Save()

    def Copy(self):
        '''
        Return copy of this
        '''
        return copy.copy(self)


def GetDefaultPrim(layer, sublayer=False):
    '''
    [Arguments]
    layer (Sdf.Layer) : find default prim in the layer
    sublayer (bool)   : if True, find default prim in sublayers
    '''
    spec = None
    layer = AsLayer(layer)

    # 1. get primSpec from defaultPrim
    if layer.HasDefaultPrim():
        spec = layer.GetPrimAtPath(layer.defaultPrim)

    # 2. get primSpec from the first rootPrim
    if not spec:
        spec = layer.rootPrims[0] if layer.rootPrims else None

    # 3. get primSpec from subLayer
    if not spec and sublayer:
        for sub in layer.subLayerPaths:
            sub = SJoin(DirName(layer.realPath), sub)
            sub = os.path.abspath(sub)
            sub = Sdf.Layer.FindOrOpen(sub)
            if not sub:
                continue
            if not sub.defaultPrim:
                continue
            spec = sub.GetPrimAtPath()
            if spec:
                break

    return spec


def AsSdfDPrim(dprim):
    if isinstance(dprim, Usd.Prim):
        return dprim.GetName()
    elif isinstance(dprim, (Sdf.PrimSpec, Sdf.Path)):
        return dprim.name
    else:
        return str(dprim)


def AsSdfPath(prim):
    if isinstance(prim, Sdf.Path):
        return prim
    elif isinstance(prim, Sdf.PrimSpec):
        return prim.path
    elif isinstance(prim, Usd.Prim):
        return prim.GetPath()
    elif isinstance(prim, (str, unicode)):
        if not prim.startswith('/'):
            prim = '/%s'%prim
        return Sdf.Path(prim)
    else:
        return Sdf.Path.emptyPath


def ExtractAttr(spec, attr=None, save=False):
    v = None
    if isinstance(spec, Sdf.AttributeSpec):
        v = spec.default
        attr = spec
        spec = spec.layer.GetPrimAtPath(spec.path.GetParentPath())
    elif isinstance(spec, Sdf.PrimSpec) and attr:
        if attr in spec.attributes.keys():
            attr = spec.attributes[attr]
            v = attr.default
        else:
            return None
    else:
        return None

    spec.RemoveProperty(attr)
    if save:
        spec.layer.Save()

    return v

def SetModelAPI(prim, kind=None, name=None, identifier=None):
    '''
    Set prim's kind, assetName or identifier.

    [Arguments]
    prim (Usd.Prim, Sdf.PrimSpec)
    kind (str)       : set kind of prim ('component', 'assembly', 'group', ...)
    name (str)       : set assetName of prim
    identifier (str) : set identifier of prim
    '''
    if isinstance(prim, Usd.Prim):
        api = Usd.ModelAPI(prim)
        if kind:       api.SetKind(kind)
        if name:       api.SetAssetName(name)
        if identifier: api.SetAssetIdentifier(identifier)
    elif isinstance(prim, Sdf.PrimSpec):
        if kind: prim.kind = kind
        if name: prim.assetInfo.update({'name':name})
        if identifier:
            prim.assetInfo.update({'identifier':Sdf.AssetPath(identifier)})


def SetPayload(prim, payload, identifier=True, type=None):
    '''
    Set reference

    [Arguments]
    prim (Usd.Prim, Sdf.PrimSpec)
    payload (Sdf.Payload)
    identifier (bool) : if True, set identifier to prim
    type (str)        : reference type. (only support if prim is PrimSpec)
                        [type list]
                        add, append, prepend, delete, order, explicit[None]
    '''
    if isinstance(prim, Usd.Prim):
        prim.SetPayload(payload)
    elif isinstance(prim, Sdf.PrimSpec):
        attr = 'explicitItems'
        if type in ['add', 'append', 'prepend', 'delete', 'order']:
            attr = '%sedItems'%(type[:-1] if type[-1] == 'e' else type)
        getattr(prim.payloadList, attr).clear()
        getattr(prim.payloadList, attr).append(payload)
    else:
        return

    if identifier:
        SetModelAPI(prim, identifier=payload.assetPath)

def PayloadAppend(spec, filename, path=Sdf.Path.emptyPath, clear=False):
    '''
    [Arguments]
    spec     (Sdf.PrimSpec)
    filename (str)
    path     (str, Sdf.Path) : payload target prim path
    clear    (bool)
    '''
    ref = Sdf.Payload(filename, primPath=path)
    prependedItems = spec.payloadList.prependedItems
    if clear:
        prependedItems.clear()
    if prependedItems.index(ref) == -1:
        prependedItems.append(ref)


def SetReference(prim, reference, identifier=False, type='prepend'):
    '''
    Set reference

    [Arguments]
    prim (Usd.Prim, Sdf.PrimSpec)
    reference (Sdf.Reference)
    identifier (bool) : if True, set identifier to prim
    type (str)        : reference type. (only support if prim is PrimSpec)
                        [type list]
                        add, append, prepend, delete, order, explicit[None]
    '''
    if isinstance(prim, Usd.Prim):
        prim.GetReferences().AddReference(reference)
    elif isinstance(prim, Sdf.PrimSpec):
        attr = 'explicitItems'
        if type in ['add', 'append', 'prepend', 'delete', 'order']:
            attr = '%sedItems'%(type[:-1] if type[-1] == 'e' else type)
        refs = getattr(prim.referenceList, attr)
        if reference not in refs:
            refs.append(reference)
    else:
        return

    if identifier:
        SetModelAPI(prim, identifier=reference.assetPath)

def ReferenceAppend(spec, filename, path=Sdf.Path.emptyPath, offset=Sdf.LayerOffset(), clear=False):
    '''
    [Arguments]
    spec (Sdf.PrimSpec)
    filename (str)
    path (str, Sdf.Path) : reference target prim path
    offset (Sdf.LayerOffset) : frame offset
    clear (bool)
    '''
    ref = Sdf.Reference(filename, primPath=path, layerOffset=offset)
    prependedItems = spec.referenceList.prependedItems
    if clear:
        prependedItems.clear()
    if prependedItems.index(ref) == -1:
        prependedItems.append(ref)


def SetSublayer(layer, src, idx=0):
    '''
    Set sublayer

    [Arguments]
    layer (Sdf.Layer)                  : sublayer set to this layer
    src (Sdf.Layer, Sdf.PrimSpec, str) : sublayer path
    idx (int)                          : insert at the index
    '''
    sublayers = list()
    for lyr in layer.subLayerPaths:
        lyr = lyr if lyr[0] in './' else './%'%lyr
        if lyr not in sublayers:
            sublayers.append(lyr)

    # check src
    if isinstance(src, Sdf.PrimSpec):
        src = src.layer.realPath
    elif isinstance(src, Sdf.Layer):
        src = src.realPath
    # elif not isinstance(src, str):    <--- sometimes str or unicode
    #     return

    if not src in sublayers:
        sublayers.insert(idx, src)

    layer.subLayerPaths.clear()
    for i in sublayers:
        layer.subLayerPaths.append(i)

def SubLayersAppend(layer, filename):
    if layer.subLayerPaths.index(filename) == -1:
        layer.subLayerPaths.insert(0, filename)


def SetInherit(src, dst, idx=0):
    '''
    Set inherits

    [Arguments]
    src (Sdf.PrimSpec, Sdf.Path, str) : inherit source path
    dst (Sdf.PrimSpec)                : inherited path
    idx (int)          : insert at the index
    '''
    if isinstance(src, Sdf.PrimSpec):
        src = src.path
    elif isinstance(src, (str, unicode)):
        src = Sdf.Path(src)

    if dst.inheritPathList and src not in dst.inheritPathList.explicitItems:
        dst.inheritPathList.explicitItems.insert(idx, src)


def SetSpecialize(src, dst, idx=0, clear=False):
    '''
    Set Specialize

    [Arguments]
    src (Sdf.PrimSpec, Sdf.Path, str) : specialize source path
    dst (Sdf.PrimSpec)                : specialized path
    idx (int)   : insert at the index
    '''
    if isinstance(src, Sdf.PrimSpec):
        src = src.path
    elif isinstance(src, (str, unicode)):
        src = Sdf.Path(src)

    if clear:
        dst.specializesList.explicitItems.clear()

    if dst.specializesList and src not in dst.specializesList.explicitItems:
        dst.specializesList.explicitItems.insert(idx, src)


def VariantSelection(prim, name, value):
    '''
    Select variant. If there is no variantSet, add and selet it.

    [Arguments]
    prim (Usd.Prim)
    name (str)      : variantSet name
    value (str)     : variant name
    '''
    vset = prim.GetVariantSets().GetVariantSet(name)
    if not vset:
        vset = prim.GetVariantSets().AddVariantSet(name)

    if not vset.HasAuthoredVariant(value):
        vset.AddVariant(value)

    vset.SetVariantSelection(value)

    return vset


def VariantSelectAndEditContext(prim, vsel):
    '''
    Select variant, and return VariantEditContext. If vsel is None, it will
    return NullContext for 'with' statement.

    [Usage]
    (legacy)
    if sdfpath.ContainsPrimVariantSelection():
        ...
        with varaint.GetVariantEditContext():
            ... [same code]
    else:
        ... [same code]

    (use this function)
    with VariantSelectAndEditContext(prim, vsel):
        ... [same code]

    [Arguments]
    prim (Usd.Prim) : prim
    vsel (tuple)    : variant selection (name, value)
    '''
    vset = VariantSelection(prim, *vsel) if vsel else None
    if vset:
        return vset.GetVariantEditContext()
    else:
        class NullContext:
            def __enter__(self):
                pass
            def __exit__(self, type, value, traceback):
                pass
        return NullContext()


def GetVariantSetSpec(spec, name):
    vset = spec.variantSets.get(name)
    if not vset:
        vset = Sdf.VariantSetSpec(spec, name)
        spec.variantSetNameList.prependedItems.append(name)
    return vset

def GetVariantSpec(vsetSpec, value):
    vspec = vsetSpec.variants.get(value)
    if not vspec:
        vspec = Sdf.VariantSpec(vsetSpec, value)
    return vspec

# ------------------------------------------------------------------------------
def CheckPipeLineLayerVersion(layer):
    customLayerData = layer.customLayerData
    dxusd = customLayerData.get('dxusd')
    if not dxusd:
        layer.Clear()
    if dxusd != var._DXVER:
        layer.Clear()
    customLayerData['dxusd'] = var._DXVER
    layer.customLayerData = customLayerData
    return layer

def GetPrimSpec(layer, path, specifier='def', type='Xform'):
    spec = layer.GetPrimAtPath(path)
    if not spec:
        spec = Sdf.CreatePrimInLayer(layer, path)
        if specifier == 'def':
            spec.specifier = Sdf.SpecifierDef
            spec.typeName  = type
        elif specifier == 'over':
            spec.specifier = Sdf.SpecifierOver
        elif specifier == 'class':
            spec.specifier = Sdf.SpecifierClass
        else:
            assert False, '# Error : specifier'
    return spec

def GetAttributeSpec(spec, name, value, type, variability=Sdf.VariabilityVarying, custom=False, info=dict()):
    attrSpec = spec.properties.get(name)
    if not attrSpec:
        attrSpec = Sdf.AttributeSpec(spec, name, type, variability, declaresCustom=custom)
    if value or value == 0:
        attrSpec.default = value
    if info:
        for k, v in info.items():
            attrSpec.SetInfo(k, v)
    return attrSpec

def DelAttributeSpec(spec, name):
    attrSpec = spec.properties.get(name)
    if attrSpec:
        spec.RemoveProperty(attrSpec)


def CollectionTargetAppend(spec, name, primPath):
    '''
    [Arguments]
    spec (Sdf.PrimSpec)
    name (str) : collection name
    primPath (str, Sdf.Path) : target prim path
    '''
    ruleName = 'collection:%s:expansionRule' % name
    attrSpec = spec.properties.get(ruleName)
    if not attrSpec:
        attrSpec = Sdf.AttributeSpec(spec, ruleName, Sdf.ValueTypeNames.Token, Sdf.VariabilityUniform)
        attrSpec.default = Usd.Tokens.expandPrims
        # First create add apiSchemas
        apiColName = 'CollectionAPI:%s' % name
        infoList   = spec.GetInfo('apiSchemas').prependedItems
        if not apiColName in infoList:
            infoList.append(apiColName)

        # for USD-19.06
        listOp = Sdf.TokenListOp()
        listOp.prependedItems = listOp.ApplyOperations(infoList)
        spec.SetInfo('apiSchemas', listOp)

        # for USD-19.11 or higher
        # spec.SetInfo('apiSchemas', Sdf.TokenListOp.Create(prependedItems=infoList))

    includeName = 'collection:%s:includes' % name
    attrSpec    = spec.properties.get(includeName)
    if not attrSpec:
        attrSpec = Sdf.RelationshipSpec(spec, includeName, False)
    attrSpec.targetPathList.prependedItems.append(primPath)


def SetPurpose(spec, purpose):  # purpose = render, proxy
    GetAttributeSpec(spec, 'purpose', purpose, Sdf.ValueTypeNames.Token, variability=Sdf.VariabilityUniform)


def CreateRelationshipSpec(spec, name, value, variability):
    attrSpec = Sdf.RelationshipSpec(spec, name, False, variability)
    if isinstance(attrSpec, list):
        for v in value:
            attrSpec.targetPathList.explicitItems.append(v)
    else:
        attrSpec.targetPathList.explicitItems.append(value)


def CreateSkelBindingAPI(spec):
    # for USD-19.06
    listOp = Sdf.TokenListOp()
    listOp.prependedItems = listOp.ApplyOperations(['SkelBindingAPI'])
    spec.SetInfo('apiSchemas', listOp)

    # for USD-19.11 or higher
    # spec.SetInfo('apiSchemas', Sdf.TokenListOp.Create(prependedItems=['SkelBindingAPI']))


class UpdateLayerData:
    '''
    src (str, Sdf.Layer, dict)
    '''
    def __init__(self, layer, src):
        self.outlyr = layer
        self.srclyr = None
        self.srcdata= {}

        if isinstance(src, Sdf.Layer):
            self.srclyr  = src
            self.srcdata = self.srclyr.customLayerData
        elif isinstance(src, dict):
            self.srcdata = src.copy()
        else:
            self.srclyr  = AsLayer(src)
            if self.srclyr:
                self.srcdata = self.srclyr.customLayerData
            else:
                msg.warning('UpdateLayerData : not found ->', src)

    def custom(self):
        data = self.outlyr.customLayerData
        data.update(self.srcdata)
        self.outlyr.customLayerData = data

    def timecode(self):
        if self.srclyr and (self.srclyr.startTimeCode or self.srclyr.endTimeCode):
            start = self.srclyr.startTimeCode
            end   = self.srclyr.endTimeCode
            if self.srcdata.has_key('start'):
                start = self.srcdata['start']
            if self.srcdata.has_key('end'):
                end   = self.srcdata['end']
            self.outlyr.startTimeCode = start
            self.outlyr.endTimeCode   = end
            self.outlyr.framesPerSecond    = self.srclyr.framesPerSecond
            self.outlyr.timeCodesPerSecond = self.srclyr.timeCodesPerSecond

    def upAxis(self):
        up = UsdGeom.Tokens.y
        with OpenStage(self.outlyr) as stg:
            UsdGeom.SetStageUpAxis(stg, up)

    def doIt(self, up=False):
        self.custom()
        self.timecode()
        if up:
            self.upAxis()


def AddCustomData(spec, key, value):
    data = spec.customData
    if data.has_key(key):
        data[key] = value
    else:
        data.update({key: value})

def DelCustomData(spec, key):
    data = spec.customData
    if data.has_key(key):
        data.pop(key)


# ------------------------------------------------------------------------------
# Path Utils
# ------------------------------------------------------------------------------

SJoin = lambda *args: var.SEP.join(args)
UJoin = lambda *args: '_'.join(args)
DJoin = lambda *args: '.'.join(args)

DirName  = lambda *args: os.path.dirname(args[0])
BaseName = lambda *args: os.path.basename(args[0])
FileName = lambda *args: '.'.join(args[0].split('.')[:-1])

Ver      = lambda *args: 'v%03d'%(args[0])
IsVer    = lambda *args: var.rb.MatchFlag('ver', args[0])
VerAsInt = lambda *args: int(re.search('\d{3}', args[0]).group())
RiUsr    = lambda *args: 'ri:attributes:user:%s'%(':'.join(args))
RiVis    = lambda *args: 'ri:attributes:visibility:%s'%(':'.join(args))

FirstUpper = lambda *args: '%s%s'%(args[0][0].upper(), args[0][1:])

def GetSharedDirs(configDir):
    dirs = list()
    jsonPath = SJoin(configDir, var.F.CONFIG.PATHRULE.Encode())

    if not os.path.exists(jsonPath):
        return dirs

    with open(jsonPath) as jsn:
        data   = json.load(jsn)
        shares = data.get(var.T.JSON.SHARED)

        if not isinstance(shares, (list, tuple)):
            if isinstance(shares, (str, unicode)):
                shares = [shares]
            else:
                return dirs

        for d in shares:
            if d.startswith(var.SEP):
                prs = var.rb.DecodeDir(d)
                # if the directory doens't have pub (_3d)
                if prs.has_key('show') and not prs.has_key('pub'):
                    d = SJoin(d, var.T.PUB3)
                dirs.append(d)
            else:
                # d : pipe > /show/pipe/_3d
                dirs.append(var.D.PUB.Encode(show=d))
    return dirs

def GetRelPath(current, target):
    '''
    [Arguments]
    current (str) : file or directory
    target (str)  : file
    '''
    comp = os.path.commonprefix([current, target])
    # if comp is '' or '/' or '/show/'
    if comp == '' or comp == var.SEP or comp == '/%s/'%var.T.SHOW:
        return target

    def isfile(path):
        return '.' in os.path.basename(path)

    curdir = os.path.dirname(current) if isfile(current) else current
    tardir = os.path.dirname(target)  if isfile(target)  else target

    if curdir == tardir:
        if isfile(target):
            return var._SEP+os.path.basename(target)
        else:
            return var._SEP
    else:
        rel = os.path.relpath(target, start=curdir)
        if rel[0] != '.':
            rel = var._SEP+rel
        return rel


def SearchInDirs(dirs, path, defaultDir=0):
    '''
    [Arguments]
    dirs (str, list)       : directories
    path (str)             : file or path
    defaultDir (int, None) : if not exist, combind the path with given indexed
                             directory in "dirs" list. When None is set, it will
                             return None if cannot find.
    '''
    if path.startswith(var.SEP):
        print("1")
        return path

    if not isinstance(dirs, (list, tuple)):
        print("5")
        dirs = [dirs]

    isCustom = 0
    for d in dirs:
        if '/assetlib' in d:
            isCustom = 1

    if isCustom:
        p = os.path.abspath(SJoin('/assetlib/_3d', path))
        print('path:',p)
        return p

    for d in dirs:
        p = os.path.abspath(SJoin(d, path))
        if os.path.exists(p):
            print("2")
            return p

    if defaultDir == None:
        print("3")
        return None
    else:
        print("4")
        return SJoin(dirs[defaultDir], path)


def GetVersions(dirpath, withNext=False, reverse=False):
    vers = list()
    if os.path.exists(dirpath):
        for d in os.listdir(dirpath):
            if IsVer(d):
                vers.append(d)

    if withNext:
        vers.append(Ver(VerAsInt(vers[-1])+1) if vers else Ver(1))

    if reverse:
        vers.reverse()

    return vers


def GetLastVersion(dirpath, default=1):
    versions = GetVersions(dirpath)
    if versions:
        return sorted(versions)[-1]
    else:
        return Ver(default)


def GetNextVersion(dirpath):
    ver = VerAsInt(GetLastVersion(dirpath, default=0))
    return Ver(ver + 1)


def NotExist(f):
    if isinstance(f, (str, unicode)):
        return not f or not os.path.exists(f)
    elif isinstance(f, (list, tuple)):
        for v in f:
            if not os.path.exists(str(v)):
                return True
        return False
    else:
        return True


def GetFilesInDir(path, ext=''):
    if not os.path.exists(path):
        return []

    files = []
    for f in os.listdir(path):
        if not f.startswith('.') and f.split('.')[-1] == ext:
            if '(' in f:
                continue
            files.append(f)
    files.sort()

    res = []
    vsn = None
    for n in files:
        base = n.split('.')[0]
        if vsn:
            if vsn != base:
                res.append(n)
        else:
            res.append(n)
        vsn = base
    return res


def GetGeomFiles(path):
    result = {}
    files  = glob.glob('%s/*_geom.usd' % path)
    for f in files:
        if '.high_geom.' in f:
            result['high'] = f
        if '.mid_geom.' in f:
            result['mid'] = f
        if '.low_geom.' in f:
            result['low'] = f
        if '.sim_geom.' in f:
            result['sim'] = f
    if result.has_key('high'):
        xformfile = result['high'].replace('.high_geom.', '.xform.')
        if os.path.exists(xformfile):
            result['xform'] = xformfile
    return result


# ------------------------------------------------------------------------------
# For ETC.
# ------------------------------------------------------------------------------

def CheckRes(name, res, message='', tcnt=1, args=[], kwargs={}):
    msg.debug('%s'%name)
    if message:
        message += ' : '

    if isinstance(res, (types.FunctionType, types.MethodType)):
        res = res(*args, **kwargs)

    if res == var.FAILED:
        msg.error('\t'*tcnt, ' >>> %s Failed'%message)
    elif res == var.IGNORE:
        msg.warning('\t'*tcnt, ' >>> %s Ignored'%message)
    else:
        msg.debug('\t'*tcnt, ' >>> %s Complete'%message)

    return res

def GetPerFrameFiles(ruleStr, fr):
    '''
    Args
        ruleStr (str): find file rule. /path/filename.*.usd
        fr (tuple): (start, end)
    '''
    msg.debug('GetPerFrameFiles')
    source = glob.glob(ruleStr)
    source.sort()

    start_digit = len(str(int(fr[0])))
    end_digit   = len(str(int(fr[1])))
    if start_digit != end_digit or start_digit > 4:
        for f in source:
            frame = re.findall(r'\.(\d+)?\.', f)
            if frame and len(frame[0]) < end_digit:
                splitFile = f.split('.')
                splitFile[-2] = splitFile[-2].zfill(end_digit)
                newFileName   = '.'.join(splitFile)
                os.rename(f, newFileName)

    source = glob.glob(ruleStr)
    source.sort()

    frames = list()
    files  = list()
    for f in source:
        frame = re.findall(r'\.(\d+)?\.', f)
        if frame:
            iframe = int(frame[0])
            if not iframe in frames:
                frames.append(iframe)
                if fr[0] <= iframe <= fr[1]:
                    files.append(f)
    return files

# ------------------------------------------------------------------------------
# For ETC : Copy Utils
# ------------------------------------------------------------------------------

def renameAsset(name):
    splitName = name.split('_')
    name = splitName[0]
    for i in splitName[1:]:
        if i[0].islower():
            for index, s in enumerate(i):
                if index == 0:
                    s = s.upper()
                name += s
        else:
            name += i
    return name

def GetUsdPath(setpath):
    layer = AsLayer(setpath)
    pathList = []
    with OpenStage(layer) as stage:
        dprim = stage.GetDefaultPrim()
        for p in dprim.GetChildren():
            for c in p.GetChildren():
                if c.GetName() == 'scatter':
                    prototypes = UsdGeom.PointInstancer(c).GetPrototypesRel().GetTargets()
                    for i in range(len(prototypes)):
                        prim = stage.GetPrimAtPath(prototypes[i])
                        refs = prim.GetMetadata('references')
                        if refs:
                            filePath = refs.GetAddedOrExplicitItems()[0].assetPath
                            if '/mach/' in filePath:
                                filePath = filePath.split('/mach')[-1]
                            pathList.append(filePath)
                else:
                    refs = c.GetMetadata('references')
                    if refs:
                        filePath = refs.GetAddedOrExplicitItems()[0].assetPath
                        pathList.append(filePath)
    return pathList

def SetModelVersion(spec):
    spec.variantSelections.update({'modelVer': 'v001'})
    GetAttributeSpec(spec, 'primvars:modelVersion', 'v001', Sdf.ValueTypeNames.String,
                         info={'interpolation': 'constant'})

def MakeDir(dstdir):
    if not os.path.exists(dstdir):
        os.system("mkdir -p %s" % dstdir)
        msg.debug('Make Directory : %s' % dstdir)

def CopyFile(source, dstdir):
    if os.path.exists(source):
        os.system("cp -rf %s %s" % (source, dstdir))
        msg.debug('Copy file : %s' % os.path.join(dstdir,source ))

def GetBasePath(asset, branch=''):
    basepath = "asset/%s/texture" %asset
    if branch:
        basepath = "asset/%s/branch/%s/texture" %(asset, branch)

    return basepath

def texAttr(txPath):
    import DXUSD.Tweakers as twk
    arg = twk.ATexture()
    arg.texAttrDir = txPath
    if arg.Treat():
        TT = twk.Texture(arg)
        TT.DoIt()
        msg.debug('Tex Update : %s' % TT.arg.texData)

def proxyMtl(dirpath):
    import DXUSD.Tweakers as twk
    arg = twk.AProxyMaterial()
    arg.mtlDir = dirpath
    if arg.Treat():
        TPM = twk.ProxyMaterial(arg)
        TPM.DoIt()
