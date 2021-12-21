import json
import maya.cmds as cmds
import maya.mel as mel
import os, re

from pxr import Sdf, Usd, UsdUtils

from DXUSD.Utils import *

import DXUSD_MAYA.Message as msg
import dxdict

#-------------------------------------------------------------------------------
#
#   Plugin Command
#
#-------------------------------------------------------------------------------
class UsdExport:
    '''
    attrMode
        0: nothing.
        1: compute attribute and clear
        2: not clear
    '''
    def __init__(self, filename, nodes, fr=[None, None], fs=0.0, customLayerData=dict(), **kwargs):
        self.nodes = nodes
        self.customLayerData = customLayerData.copy()
        if not self.customLayerData.has_key('sceneFile'):
            sceneFile = cmds.file(q=True, sn=True)
            if sceneFile: self.customLayerData['sceneFile'] = sceneFile

        self.opts = {
            'file': filename,
            'append': False,
            'exportColorSets': False,
            'defaultMeshScheme': 'none',
            'exportDisplayColor': False,
            'eulerFilter': True,
            'exportInstances': True,
            'exportRefsAsInstanceable': False,
            'exportReferenceObjects': True,
            'kind': 'component',
            'mergeTransformAndShape': True,
            'shadingMode': 'none',
            'exportSkels': 'none',
            'selection': True,
            'stripNamespaces': True,
            'exportUVs': True,
            'exportVisibility': True,
            'verbose': True
        }

        self.isConstant = True
        if fr[0] != None and fr[1] != None:
            self.opts['frameRange'] = fr
            self.opts['frameSample']= fs
            self.isConstant = False

        # Override export options:
        if kwargs:
            self.opts.update(kwargs)


    def doIt(self):
        cmds.select(self.nodes)
        cmds.usdExport(**self.opts)
        cmds.select(cl=True)
        # update layer info
        outLayer = AsLayer(self.opts['file'])
        if self.customLayerData:
            tmp = outLayer.customLayerData
            tmp.update(self.customLayerData)
            outLayer.customLayerData = tmp
        if not self.isConstant:
            fps = mel.eval('currentTimeUnitToFPS')
            outLayer.framesPerSecond    = fps
            outLayer.timeCodesPerSecond = fps
        outLayer.Save()
        del outLayer

class UsdImport:
    def __init__(self, filename, **kwargs):
        self.opts = {
            'file': filename,
            'assemblyRep': "",
            'shadingMode': "none",
            }

        # Override export options:
        if kwargs:
            self.opts.update(kwargs)

    def doIt(self):
        nodes = cmds.usdImport(**self.opts)
        # cmn.ImportGeomPostProcess(self.opts['file'], nodes[0]).doIt()
        return nodes

#-------------------------------------------------------------------------------
#
#   Extra Attributes
#
#-------------------------------------------------------------------------------
_RfMSubdiv = 'rman__torattr___subdivScheme'
_USDSubdiv = 'USD_subdivisionScheme'
_SubdivSchemeMap = {0: 'catmullClark', 1: 'loop', 100:'none'}
_USDJSON = 'USD_UserExportedAttributesJson'
class UsdUserAttributes:
    def __init__(self, nodes, update=False):
        self.nodes = cmds.ls(nodes, dag=True, s=True, ni=True, l=True)
        self.update= update

        self.update_nodes = list()

        self.prefix = ['tx*', 'rman*', 'modelVersion', 'MaterialSet']
        self.exclude= []

    def Clear(self):
        for shape in self.update_nodes:
            if cmds.attributeQuery(_USDJSON, n=shape, ex=True):
                cmds.deleteAttr('%s.%s' % (shape, _USDJSON))

    def Set(self):
        self.materialAttribute()

        for shape in self.nodes:
            # if not self.update and cmds.attributeQuery(_USDJSON, n=shape, ex=True):
            #     continue

            usdAttrs = dict()

            # rfm subdiv -> usd subdiv
            self.subdivAttribute(shape)

            self.updateShapeAttributes(shape, usdAttrs)
            if usdAttrs:
                if not cmds.attributeQuery(_USDJSON, n=shape, ex=True):
                    cmds.addAttr(shape, ln=_USDJSON, dt='string')
                    self.update_nodes.append(shape)
                else:
                    alreadyUsdAttrs = cmds.getAttr('%s.%s' % (shape, _USDJSON))
                    dxdict.deepupdate(usdAttrs, json.loads(alreadyUsdAttrs))
                cmds.setAttr('%s.%s' % (shape, _USDJSON), json.dumps(usdAttrs), type='string')


    def updateShapeAttributes(self, shape, data):
        userAttrs = cmds.listAttr(shape, st=self.prefix, ud=True)
        if userAttrs:
            for ln in userAttrs:
                if ln.startswith('rman__torattr'):
                    continue
                if ln.startswith('USD_'):
                    continue
                if ln.endswith('_AbcGeomScope'):
                    continue
                if ln in self.exclude:
                    continue

                attrName = ln
                attrType = 'primvar'

                # rfm ri-user attribute
                if ln.startswith('rman__riattr__user_'):
                    attrName = ln.replace('rman__riattr__user_', '')

                # rfm primvar
                interpolation = None
                if attrName.startswith('rman'):
                    tmp = attrName.replace('rman', '')
                    if tmp[0] == 'a':
                        tmp = tmp[1:]
                    attrName = tmp[2:]
                    if tmp[0] == 'c':
                        interpolation = 'constant'
                    elif tmp[0] == 'u':
                        interpolation = 'uniform'
                    elif tmp[0] == 'f':
                        interpolation = 'faceVarying'
                    elif tmp[0] == 'v':
                        interpolation = 'varying'
                    else:
                        interpolation = 'vertex'

                if ln == 'MaterialSet':
                    attrName = 'userProperties:MaterialSet'
                    attrType = 'userProperties'

                data[ln] = {'usdAttrName': attrName, 'usdAttrType': attrType}
                if interpolation:
                    data[ln]['interpolation'] = interpolation


    def materialAttribute(self):
        if not cmds.objExists('MaterialSet'):
            return
        for m in cmds.sets('MaterialSet', q=True):
            source = cmds.sets(m, q=True)
            memberShapes = cmds.ls(source, dag=True, type='surfaceShape', ni=True)
            for shape in memberShapes:
                if not cmds.attributeQuery('MaterialSet', n=shape, ex=True):
                    cmds.addAttr(shape, ln='MaterialSet', dt='string')
                cmds.setAttr('%s.MaterialSet' % shape, m, type='string')

    def subdivAttribute(self, shape):
        if cmds.attributeQuery(_RfMSubdiv, n=shape, ex=True):
            scheme = cmds.getAttr('%s.%s' % (shape, _RfMSubdiv))
            if not cmds.attributeQuery(_USDSubdiv, n=shape, ex=True):
                cmds.addAttr(shape, ln=_USDSubdiv, dt='string')
            cmds.setAttr('%s.%s' % (shape, _USDSubdiv), _SubdivSchemeMap[scheme], type='string')



#-------------------------------------------------------------------------------
#
#   USD Attribute
#
#-------------------------------------------------------------------------------
PURPOSEATTR = 'USD_ATTR_purpose'
def DelPurposeAttribute(objects):
    for o in objects:
        if cmds.attributeQuery(PURPOSEATTR, n=o, ex=True):
            cmds.deleteAttr('%s.%s' % (o, PURPOSEATTR))

def SetPurposeAttribute(objects, purpose='render', exclude=[]):
    for o in list(set(objects) - set(exclude)):
        if not cmds.attributeQuery(PURPOSEATTR, n=o, ex=True):
            cmds.addAttr(o, ln=PURPOSEATTR, nn='purpose', dt='string')
        cmds.setAttr('%s.%s' % (o, PURPOSEATTR), purpose, type='string')

def SetRigPurposeAttribute(renderObjects, proxyObjects):
    DelPurposeAttribute(list(set(renderObjects + proxyObjects)))
    if not proxyObjects:
        return
    intersectObjects = list(set(proxyObjects).intersection(set(renderObjects)))
    SetPurposeAttribute(renderObjects, 'render', intersectObjects)
    SetPurposeAttribute(proxyObjects,  'proxy',  intersectObjects)



#-------------------------------------------------------------------------------
#
#   Pxr Reference Data
#
#-------------------------------------------------------------------------------
class GetReferenceData:
    '''
    refData = {
        refName(Sdf.Path): {
            'filePath': reference file path,
            'nodes': [transform node, ...],
            'offset': dxTimeOffset node offset value,
            'primPath': get node attr,
            'excludePrimPaths': get node attr
        }
    }
    '''
    def __init__(self, selected=None):
        self.selected = selected

        # member variable
        self.refData   = dict()
        self.nullPrims = list()

    def getNodes(self):
        computeNodes = list()
        for n in cmds.ls(self.selected, dag=True, type=['pxrUsdProxyShape', 'pxrUsdReferenceAssembly'], l=True):
            node = n
            if cmds.nodeType(node) == 'pxrUsdProxyShape':
                trans = cmds.listRelatives(node, p=True, f=True)[0]
                if cmds.nodeType(trans) == 'pxrUsdReferenceAssembly':
                    node = trans
            if not node in computeNodes:
                computeNodes.append(node)
        return computeNodes

    def get(self, nodes=None):  # fullpath node list
        if not nodes:
            nodes = self.getNodes()

        refData   = dict()
        nullPrims = list()
        excludeNames = list()

        for node in nodes:
            trans = node
            if 'shape' in cmds.nodeType(node, i=True):
                trans = cmds.listRelatives(node, p=True, f=True)[0]
                nullPrims.append(node.replace('|', '/').replace(':', '_'))

            # reference source file
            filePath = cmds.getAttr('%s.filePath' % node)
            baseName = BaseName(filePath).split('.')[0]

            # primPath
            primPath = cmds.getAttr('%s.primPath' % node)
            if primPath:
                baseName += '_' + Sdf.Path(primPath).name

            # exclude prims
            exps = cmds.getAttr('%s.excludePrimPaths' % node)
            if exps:
                names = list()
                for p in exps.split(','):
                    names.append(Sdf.Path(p.strip()).name)
                name = '_'.join(names)
                if not name in excludeNames:
                    excludeNames.append(name)
                baseName += '_exp%s' % excludeNames.index(name)

            # frameOffset
            offset = self.getFrameOffset(node)
            if offset:
                prefix = 'p'
                if offset < 0:
                    prefix = 'm'
                baseName += '_{0}{1}f'.format(prefix, abs(int(offset)))

            # txVarNum
            txVarNum = 0
            if cmds.attributeQuery('rman__riattr__user_txVarNum', n=node, ex=True):
                txVarNum = cmds.getAttr('%s.rman__riattr__user_txVarNum' % node)
                if txVarNum:
                    baseName += '_tvn%d' % txVarNum

            refName = self.getRefName(trans, baseName)
            if not refData.has_key(refName):
                refData[refName] = {
                    'filePath': filePath, 'nodes': list(), 'offset': offset,
                }
                # primPath
                if primPath:
                    refData[refName]['primPath'] = primPath
                # exclude prims
                if exps:
                    refData[refName]['excludePrimPaths'] = exps

                if txVarNum:
                    refData[refName]['txVarNum'] = txVarNum

            refData[refName]['nodes'].append(trans)

        self.refData   = refData
        self.nullPrims = nullPrims

        return self.refData


    def getRefName(self, node, name):
        path  = Sdf.Path(name)
        attrs = cmds.listAttr(node, st='usdVariantSet_*')
        if attrs:
            for ln in attrs:
                key = ln.replace('usdVariantSet_', '')
                if key == 'preview':
                    continue
                val = cmds.getAttr('%s.%s' % (node, ln))
                if val:
                    path = path.AppendVariantSelection(key, val)
        return path

    def refNameToString(self, refName):
        names = list()
        for s in refName.GetPrefixes():
            if s.IsPrimVariantSelectionPath():
                key, val = s.GetVariantSelection()
                names += [key, val]
            else:
                names.append(s.name)
        return '_'.join(names)

    def getFrameOffset(self, node):
        offset = 0
        connected = cmds.listConnections(node, d=False, s=True, type='dxTimeOffset')
        if connected:
            offset = cmds.getAttr('%s.offset' % connected[0]) * -1.0
        return offset



def InsertInitFile(stage, refFile):
    frame = re.findall(r'\.(\d+)?\.', refFile)
    if frame:
        digit = len(frame[0])
        splitFile = refFile.split('.')
        splitFile[-2] = '0'.zfill(digit)
        initFile = '.'.join(splitFile)
        if os.path.exists(initFile):
            outLayer = stage.GetRootLayer()
            relpath  = GetRelPath(outLayer.identifier, initFile)
            SubLayersAppend(outLayer, relpath)
            outLayer.Save()

#-------------------------------------------------------------------------------
#
#   Coalesce per frame files
#
#-------------------------------------------------------------------------------
def CoalesceFiles(frameFiles, frameRange, step=1, outFile=None, activeOffset=0.0, clipSet='default'):
    msg.debug('CoalesceFiles')
    if outFile:
        topologyFile = outFile.replace('.usd', '.topology.usd')
    else:
        fileSplit = frameFiles[0].split('.')
        fileSplit[-2] = 'valueclip'
        outFile = '.'.join(fileSplit)
        topologyFile = outFile.replace('.valueclip.', '.topology.')

    topologyLayer = AsLayer(topologyFile, create=True, clear=True)
    UsdUtils.StitchClipsTopology(topologyLayer, frameFiles)

    clipPath = topologyLayer.rootPrims[0].path
    outLayer = AsLayer(outFile, create=True, clear=True)
    stride = 1
    baseName = os.path.basename(frameFiles[0])
    for i in range(2):
        m = re.search('(^|\.)([0-9]+)\.', baseName)
        if m:
            fstr = m.groups()[1]
            baseName = baseName.replace(fstr, '#' * len(fstr))
            if i == 1:
                stride = step
    templatePath = './' + baseName

    # msg.debug(outLayer, topologyLayer, clipPath, templatePath, frameRange[0], frameRange[1], stride, activeOffset, clipSet)
    UsdUtils.StitchClipsTemplate(
        outLayer, topologyLayer, clipPath, templatePath, frameRange[0], frameRange[1], stride, activeOffset, clipSet
    )
    stage = Usd.Stage.Open(outLayer, load=Usd.Stage.LoadNone)
    prim  = stage.GetPrimAtPath(clipPath)
    stage.SetDefaultPrim(prim)
    InsertInitFile(stage, frameFiles[0])
    outLayer.Save()
    return outFile, topologyFile


#---------------------------------------------------------------------------
#
#   COMMON
#
#---------------------------------------------------------------------------
# def refNameToString(refName):
#     names = list()
#     for s in refName.GetPrefixes():
#         if s.IsPrimVariantSelectionPath():
#             key, val = s.GetVariantSelection()
#             names += [key, val]
#         else:
#             names.append(s.name)
#     return '_'.join(names)

def SetVariantSelections(spec, refName):
    '''
    refName (Sdf.Path) :
    '''
    for s in refName.GetPrefixes():
        if s.IsPrimVariantSelectionPath():
            key, val = s.GetVariantSelection()
            spec.variantSelections.update({key: val})

def SetIncludePrim(spec, primPath, srcFile):
    if primPath == Sdf.Path.emptyPath or primPath.pathElementCount < 3:
        return

    # add custom data
    AddCustomData(spec, 'primPath', primPath.pathString)

    inActives = list()

    with OpenStage(srcFile) as stage:
        dpath  = stage.GetDefaultPrim().GetPath()
        parent = primPath.GetParentPath()
        # find parent paths
        prefixes = parent.GetParentPath().GetPrefixes()
        for p in prefixes:
            for c in stage.GetPrimAtPath(p).GetChildren():
                cpath = c.GetPath()
                if not cpath in prefixes and cpath != parent and cpath.name != 'Looks':
                    relpath = cpath.MakeRelativePath(dpath)
                    if not relpath in inActives:
                        inActives.append(relpath)
        # find children paths - primPath level
        for c in stage.GetPrimAtPath(parent).GetChildren():
            cpath = c.GetPath()
            if cpath != primPath:
                relpath = cpath.MakeRelativePath(dpath)
                if not relpath in inActives:
                    inActives.append(relpath)

    for p in inActives:
        over_spec = GetPrimSpec(spec.layer, spec.path.AppendPath(p), specifier='over')
        over_spec.SetInfo('active', False)

def SetExcludePrims(spec, data):    # data : refData value
    if data.has_key('excludePrimPaths'):
        # add custom data
        AddCustomData(spec, 'excludePrimPaths', data['excludePrimPaths'])
        
        for p in data['excludePrimPaths'].split(','):
            path  = Sdf.Path(p.strip())
            rpath = path.MakeRelativePath(path.GetPrefixes()[0])
            over_spec = GetPrimSpec(spec.layer, spec.path.AppendPath(rpath), specifier='over')
            over_spec.SetInfo('active', False)
