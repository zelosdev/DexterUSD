#coding:utf-8
from __future__ import print_function
import os, re, glob, copy
from pxr import Sdf, Gf

import maya.cmds as cmds
import maya.mel as mel

from DXUSD.Structures import Arguments
import DXUSD.Vars as var

import DXUSD_MAYA.Message as msg
import DXUSD_MAYA.Exporters as exp
import DXUSD_MAYA.MUtils as mutl
import DXUSD_MAYA.Utils as utl

# InitScaleAttributes = ['initScale']

# COMMON
def JoinNsNameAndNode(nsName, nodeName):
    return nodeName if not nsName else '%s:%s' % (nsName, nodeName)

def GetObjects(node):
    '''
    return
        {'high': [], 'mid': [], 'low': [], 'sim': []}
    '''
    result = dict()
    attrMap= {'high': 'renderMeshes', 'mid': 'midMeshes', 'low': 'lowMeshes', 'sim': 'simMeshes'}
    nsname, nodename = mutl.GetNamespace(node)
    for gt, ln in attrMap.items():
        objects = list()
        for o in cmds.getAttr('%s.%s' % (node, ln)):
            prefix  = nsname + ':' if nsname else ''
            dagPath = prefix + o

            if '|' in o and nsname:
                splitObjName = o.split('|')
                dagPath = ''
                for objName in splitObjName:
                    dagPath += '%s:%s|' % (nsname, objName)

            fullpath= cmds.ls(dagPath, l=True)
            if fullpath:
                objects += fullpath
        result[gt] = objects
    return result

def GetRigVariant(node):
    data = dict()   #{ln: [(name, index), ...]}
    chnode = cmds.listConnections('%s.variant' % node)
    if chnode:
        chnode = chnode[0]
        inputs = cmds.getAttr('%s.input' % chnode, mi=True)
        ctrln  = cmds.listConnections('%s.selector' % chnode, p=True, s=True, d=False)
        if inputs and ctrln:
            ctrln = ctrln[0]
            sels  = list()
            for i in inputs:
                out = cmds.getAttr('%s.input[%d]' % (chnode, i))
                sels.append(out)
            variants = list(set(sels))
            if len(variants) > 1:
                data[ctrln] = list()
                for v in variants:
                    data[ctrln].append((v, sels.index(v)))
    return data

def GetSubFrameObjects(node, data):
    result = {'high': [], 'mid': [], 'sim': []}
    nsname, nodename = mutl.GetNamespace(node)
    # current objects
    objects = list()
    for o in cmds.getAttr('%s.stepMeshes' % node):
        prefix = nsname + ':' if nsname else ''
        fullpath = cmds.ls(prefix + o, l=True)
        if fullpath:
            objects += fullpath

    for gt in ['high', 'mid', 'sim']:
        if data[gt]:
            for obj in data[gt]:
                for tar in objects:
                    if obj.startswith(tar):
                        if not cmds.ls(obj, dag=True, io=True):
                            continue

                        result[gt].append(obj)
    return result



class RigNodeInspect:
    '''
    Args:
        fr(tuple) : base input is (start, end)
    '''
    def __init__(self, node, fr=(None, None), autofr=False):
        self.node = node
        self.fr = fr
        self.autofr = autofr
        self.ctrls = self.getRigControllers(self.node)
        self.objects = GetObjects(self.node)
        self.exportRange = self.fr
        self.restFrame = None # if task exists simulation, set restFrame

        # need Tweak nodes
        self.extraRigNodes = None
        self.extraObjects = None

        # rigType : {0:'Biped', 1:'Quad', 2:'prop', 3:vehicle, 4:'etc'}
        self.rigType = cmds.getAttr('%s.rigType' % self.node)
        self.rigBake = cmds.getAttr('%s.rigBake' % self.node)
        self.rigRootCon = cmds.getAttr('%s.rootCon' % self.node)

        # Checking
        self.meshChecking()
        self.keyFrameChecking()
        self.ctrlsChecking()

    def getRigControllers(self, node):
        nsName, nodeName = mutl.GetNamespace(node)
        result = list()
        for ctrl in cmds.getAttr('%s.controllers' % node):
            name = JoinNsNameAndNode(nsName, ctrl)
            if cmds.objExists(name):
                result.append(name)
        return result

    def meshChecking(self):
        '''
        mesh & extra rig object and controllers update
        :return:
        '''
        # check extra object
        extraRigNodes = list()
        for shape in cmds.ls(self.objects['high'], dag=True, type='pxrUsdProxyShape'):
            transformNode = cmds.listRelatives(shape, p=True, f=True)[0]
            # if has attr rigNode, convert proxyShape to dxRig node
            if cmds.attributeQuery('rigNode', n=transformNode, ex=True):
                fullPath = cmds.ls(cmds.getAttr('%s.rigNode' % transformNode), l=True)
                if fullPath and mutl.GetViz(fullPath[0]):
                    extraRigNodes.append(fullPath[0])
            # if has attr refNode, con
            elif cmds.attributeQuery('refNode', n=transformNode, ex=True):
                refNodes = cmds.referenceQuery(cmds.getAttr('%s.refNode' % transformNode), n=True)
                if cmds.nodeType(refNodes[0]) == 'dxRig':
                    cmds.addAttr(transformNode, ln='rigNode', dt='string')
                    cmds.setAttr('%s.rigNode' % transformNode, refNodes[0], type='string')
                    fullPath = cmds.ls(refNodes[0], l=True)
                    if mutl.GetViz(fullPath[0]):
                        extraRigNodes.append(fullPath[0])

        if not extraRigNodes:
            return
        self.extraRigNodes = extraRigNodes
        self.extraObjects = GetObjects(self.node)
        for rigNode in extraRigNodes:
            extraObj = GetObjects(rigNode)
            for lod in extraObj.keys():
                self.extraObjects[lod] = extraObj[lod]
            self.ctrls += self.getRigControllers(rigNode)

    def keyFrameChecking(self):
        self.exportRange = (self.fr[0] - 1, self.fr[1] + 1) # requires motion blur offset -1, +1
        allFrames = list()

        for ctrl in self.ctrls:
            for node in cmds.listHistory(ctrl, lf=False):
                if cmds.nodeType(node).find('animCurve') > -1: # animCurveLU LT
                    frames = cmds.keyframe(node, q=True)
                    if frames:
                        allFrames += frames
        allFrames.sort()
        if self.autofr and allFrames:
            restFrame = self.fr[0] - 51
            if allFrames[0] <= restFrame:
                self.restFrame = restFrame
                self.exportRange = (restFrame, self.exportRange[1])
        if not allFrames and self.rigType != 4: # if rigType isn't etc and not set keyframe, export just frame
            self.exportRange = (self.fr[0], self.fr[0])

    def ctrlsChecking(self):
        if self.extraRigNodes:
            worldCons = list()
            for node in self.extraRigNodes:
                ns, name = mutl.GetNamespace(node)
                for ctrl in ['mov_CON', 'direction_CON', 'place_CON']:
                    obj = JoinNsNameAndNode(ns, ctrl)
                    worldCons.append(obj)

            self.ctrls = list(set(self.ctrls) - set(worldCons))

    def selectAnimLayer(self):
        rootLayer = cmds.animLayer(q=True, root=True)
        if not rootLayer:
            return

        layers = cmds.animLayer(rootLayer, q=True, children=True)
        if layers:
            layers.insert(0, rootLayer)
            for i in layers[:-1]:
                cmds.animLayer(i, e=True, selected=False)
                cmds.animLayer(i, e=True, preferred=False)
            cmds.animLayer(layers[-1], e=True, selected=True)
            cmds.animLayer(layers[-1], e=True, preferred=True)

    def setKeyOffset(self, ctrlNode):
        if cmds.listAttr(ctrlNode, k=True):
            for ln in cmds.listAttr(ctrlNode, k=True):
                typeln = cmds.getAttr('%s.%s' % (ctrlNode, ln), type=True)
                if re.findall(r'\d+', typeln):
                    continue

                plug = '%s.%s' % (ctrlNode, ln)
                frames = cmds.keyframe(plug, q=True, a=True)
                if not frames:
                    continue
                tangents = cmds.keyTangent(plug, q=True, ia=True, oa=True)
                tangents = list(set(tangents))
                if len(tangents) == 1:
                    continue

                # Start Frame
                refValue = cmds.getAttr(plug, t=frames[2])
                startValue = cmds.getAttr(plug, t=frames[1])
                setValue = cmds.getAttr(plug, t=frames[0])
                if startValue == setValue:
                    msg.debug('start offset value', plug, setValue, startValue)
                    offsetValue = refValue - startValue
                    setValue = startValue - offsetValue
                    cmds.setKeyframe(plug, itt='spline', ott='spline', t=frames[0], v=setValue)

                # End Frame
                refValue = cmds.getAttr(plug, t=frames[-3])
                endValue = cmds.getAttr(plug, t=frames[-2])
                setValue = cmds.getAttr(plug, t=frames[-1])
                if endValue == setValue:
                    msg.debug('end offset value', plug, endValue, setValue)
                    offsetValue = endValue - refValue
                    setValue = endValue + offsetValue
                    cmds.setKeyframe(plug, itt='spline', ott='spline', t=frames[-1], v=setValue)

    def setInitializeControlers(self, node, initFrame):
        nsName, nodeName = mutl.GetNamespace(node)
        data = cmds.getAttr('%s.controllersData' % node)
        if not data:
            msg.error('not found controllers initialize data')
            return
        cmds.currentTime(initFrame)

        worldCons = list()
        for conName in ['move_CON', 'direction_CON', 'place_CON']:
            obj = JoinNsNameAndNode(nsName, conName)
            worldCons.append(obj)

        constraintedNodes = list()
        data = eval(data)
        for attrInfo in data:
            nodeName, attrName = attrInfo.split('.')
            nodeName = JoinNsNameAndNode(nsName, nodeName)
            if not nodeName in worldCons:
                ln = '%s.%s' % (nodeName, attrName)
                if cmds.objExists(nodeName) and cmds.getAttr(ln, k=True) and data[attrInfo]['type'] != 'string':
                    # Check Constrain
                    connectInfo = cmds.listConnections('%s.parentInverseMatrix[0]' % nodeName, type='constraint', s=False, d=True)
                    if connectInfo:
                        constraintedNodes.append(nodeName)
                    try:
                        cmds.setAttr(ln, data[attrInfo]['value'])
                        cmds.setKeyframe(ln)
                    except Exception as e:
                        msg.warning(e.message)

        if constraintedNodes:
            for node in constraintedNodes:
                attrList = cmds.listAttr(node, st='blend*')
                if attrList:
                    for attr in attrList:
                        ln = '%s.%s' % (node, attr)
                        cmds.setAttr(ln, 0)
                        cmds.setKeyframe(ln)

    def bake(self):
        '''
        Key Bake and +,-1 offset frame key control
        :return:
        '''
        if self.exportRange[0] == self.exportRange[1]:
            return
        if not self.rigBake:
            return

        bakeOnOverrideLayer = False
        animLayer = cmds.animLayer(q=True, root=True)
        if animLayer:
            if cmds.animLayer(animLayer, q=True, children=True):
                bakeOnOverrideLayer = True

        # retime process
        bakeRange = [self.exportRange[0], self.exportRange[1]]
        currentFrame = cmds.currentTime(q=True) # using Recovery
        isRetime = False

        if cmds.getAttr('time1.enableTimewarp'):
            isRetime = True
            cmds.currentTime(self.fr[1])
            bakeRange[1] = int(cmds.getAttr('time1.outTime')) + 1
            cmds.setAttr('time1.enableTimewarp', False)

        cmds.bakeResults(self.ctrls, simulation=True, t=tuple(bakeRange), bol=bakeOnOverrideLayer, dic=False, pok=False, mr=True)
        self.selectAnimLayer()

        # undo retime
        if isRetime:
            cmds.setAttr('time1.enableTimewarp', True)
            cmds.currentTime(currentFrame)

        # keyoffset value re-set
        for ctrl in self.ctrls:
            self.setKeyOffset(ctrl)

        # Rest Pose re-initial
        if self.restFrame:
            self.setInitializeControlers(self.node, self.restFrame)

        # Constant key check
        _valid = 0
        for c in self.ctrls:
            tangents = cmds.keyTangent(c, q=True, ia=True, oa=True)
            if tangents:
                tangents = list(set(tangents))
                if len(tangents) > 1:
                    _valid += 1
        if _valid == 0 and self.rigType != 4: # if rigType isn't etc
            self.exportRange = (self.fr[0], self.fr[0])



#-------------------------------------------------------------------------------
#
#   Rig Asset
#
#-------------------------------------------------------------------------------
class RigAssetExport(exp.RigAssetExporter):
    def geomExport(self, filename, renderMeshes, proxyMeshes):
        utl.SetRigPurposeAttribute(renderMeshes, proxyMeshes)
        utl.UsdExport(filename, renderMeshes + proxyMeshes).doIt()

    def getControllersData(self):
        ctrlData = dict()
        for i in cmds.getAttr('%s.controllers' % self.arg.node):
            attrs = cmds.listAttr(i, k=True)
            if attrs:
                for a in attrs:
                    gv = cmds.getAttr('%s.%s' % (i, a))
                    gt = cmds.getAttr('%s.%s' % (i, a), type=True)
                    ctrlData['%s.%s' % (i, a)] = {'value': gv, 'type': gt}
        return ctrlData

    def updateMeshes(self):
        for n in ['renderMeshes', 'midMeshes', 'lowMeshes']:
            ln = '%s.%s' % (self.arg.node, n)
            objs   = cmds.getAttr(ln)
            exists = cmds.ls(objs)
            cmds.setAttr(ln, *([len(exists)] + exists), type='stringArray')

    def selectedPublishGeom(self, LOD='high'):
        if LOD == 'high':
            return cmds.ls(type='dxRig')
        cmds.select(clear=True)
        selectedList = ['place_NUL', 'transform_GRP']
        noneXformChildren = cmds.listRelatives('noneTransform_GRP', c=True)
        for child in noneXformChildren:
            if child == 'geometry_GRP':
                # first simMesh append
                geomGrpChildren = cmds.listRelatives('geometry_GRP', c=True)
                for geomGrpChild in geomGrpChildren:
                    if "variant_GRP" == geomGrpChild:
                        continue
                    if '_model_' not in geomGrpChild:
                        if LOD != 'high' and '_muscle_' in geomGrpChild:
                            continue
                        selectedList.append(geomGrpChild)
                if LOD == 'high':
                    selectedList += cmds.getAttr('%s.renderMeshes' % self.arg.node)
                    selectedList += cmds.getAttr('%s.midMeshes' % self.arg.node)
                    selectedList += cmds.getAttr('%s.lowMeshes' % self.arg.node)
                elif LOD == 'mid':
                    selectedList += cmds.getAttr('%s.midMeshes' % self.arg.node)
                    selectedList += cmds.getAttr('%s.lowMeshes' % self.arg.node)
                else:
                    selectedList += cmds.getAttr('%s.lowMeshes' % self.arg.node)
            elif LOD == 'low' and 'facial' in child:
                msg.debug('low facail skip', child)
                continue
            else:
                selectedList.append(child)

        return selectedList

    def Exporting(self):
        # TEST
        print('#### RigAssetExport ####')
        print('> node\t:', self.arg.node)

        # CheckList
        # 1. Controller Attribute
        ctrlData = cmds.getAttr('%s.controllers' % self.arg.node)
        if not ctrlData:
            msg.errorQuit('not found controller attribute.', artist='daeseok.chae')
        # 2. Meshes exists
        self.updateMeshes()

        objects = GetObjects(self.arg.node)
        allobjs = list()
        for objs in objects.values():
            allobjs += objs

        # UVSet Check
        cmds.select(allobjs)
        uvSetList = cmds.polyUVSet(allUVSets=True, q=True)
        if uvSetList:
            self.arg.uvSetList = list(set(cmds.polyUVSet(allUVSets=True, q=True)))
            self.arg.uvSetList.remove('map1')
        else:
            self.arg.uvSetList = []
        cmds.select(clear=True)

        # Custom User Attributes
        UsdAttr = utl.UsdUserAttributes(allobjs)
        UsdAttr.Set()

        # HIGH GEOM
        if objects['high']:
            self.arg.lod = var.T.HIGH
            ofile = utl.SJoin(self.arg.D.TASKN, self.arg.F.GEOM)
            msg.debug('> GEOM FILE\t:', ofile)
            self.arg.geomfiles.append(ofile)
            self.geomExport(ofile, objects['high'], objects['low'])
        if objects['mid']:
            # MID GEOM
            self.arg.lod = var.T.MID
            ofile = utl.SJoin(self.arg.D.TASKN, self.arg.F.GEOM)
            msg.debug('> GEOM FILE\t:', ofile)
            self.arg.geomfiles.append(ofile)
            self.geomExport(ofile, objects['mid'], objects['low'])
            # LOW GEOM
            self.arg.lod = var.T.LOW
            ofile = utl.SJoin(self.arg.D.TASKN, self.arg.F.GEOM)
            msg.debug('> GEOM FILE\t:', ofile)
            self.arg.geomfiles.append(ofile)
            self.geomExport(ofile, objects['low'], [])
        # SIM GEOM
        if objects['sim']:
            ofile = utl.SJoin(self.arg.D.TASKN, self.arg.F.SIMGEOM)
            msg.debug('> GEOM FILE\t:', ofile)
            self.arg.geomfiles.append(ofile)
            self.geomExport(ofile, objects['sim'], [])

        # Custom User Attributes - Clear
        UsdAttr.Clear()

        # Initialize Controller Data
        initData = self.getControllersData()
        cmds.setAttr('%s.controllersData' % self.arg.node, str(initData), type='string')

        # Editable disable
        cmds.setAttr('%s.editable' % self.arg.node, False)

        # geoCache Publish
        cacheNodeList = cmds.ls(type='cacheFile')
        if cacheNodeList:
            sceneName = utl.BaseName(self.arg.scene)
            for cacheNode in cacheNodeList:
                baseName = cmds.getAttr("%s.cacheName" % cacheNode)
                baseDir = cmds.getAttr("%s.cachePath" % cacheNode)
                if baseDir.endswith('/'):
                    baseDir = baseDir[:-1]
                splitBaseDir = baseDir.split('/')
                if 'data' in splitBaseDir:
                    dataIndex = splitBaseDir.index('data')

                    folderName = '/'.join(splitBaseDir[dataIndex:])

                    msg.debug(baseDir, baseName, folderName)
                    cacheFilePath = os.path.join(baseDir, baseName)
                    if glob.glob("%s*" % cacheFilePath):
                        newCacheFileDir = utl.SJoin(utl.DirName(self.arg.dstdir), 'scenes', sceneName.split('.')[0], folderName)
                        if not os.path.exists(newCacheFileDir):
                            os.makedirs(newCacheFileDir)

                        cmd = 'cp -rf %s* %s/' % (cacheFilePath, newCacheFileDir)
                        msg.debug(cmd)
                        os.system(cmd)
                        cmds.setAttr('%s.cachePath' % cacheNode, str(newCacheFileDir), type='string')

        # abcFileNode Publish
        alembicNodeList = cmds.ls(type='AlembicNode')
        if alembicNodeList:
            sceneName = utl.BaseName(self.arg.scene)
            for alembicNode in alembicNodeList:
                layerFiles = cmds.getAttr('%s.abc_layerFiles' % alembicNode)
                for index, layerFile in enumerate(layerFiles):
                    splitBaseDir = layerFile.split('/')
                    if 'data' in splitBaseDir:
                        dataIndex = splitBaseDir.index('data')
                        pubSceneDir = utl.SJoin(utl.DirName(self.arg.dstdir), 'scenes', sceneName.split('.')[0])
                        newLayerFilePath = os.path.join(pubSceneDir, '/'.join(splitBaseDir[dataIndex:]))

                        if not os.path.exists(os.path.dirname(newLayerFilePath)):
                            os.makedirs(os.path.dirname(newLayerFilePath))

                        cmd = 'cp -rf %s %s' % (layerFile, newLayerFilePath)
                        msg.debug(cmd)
                        os.system(cmd)
                        cmds.setAttr("%s.abc_layerFiles" % alembicNode, index + 1, newLayerFilePath, type='stringArray')

                # abcFilePath = cmds.getAttr("%s.abc_File" % alembicNode)
                # splitBaseDir = abcFilePath.split('/')
                # if 'data' in splitBaseDir:
                #     dataIndex = splitBaseDir.index('data')
                #     pubSceneDir = utl.SJoin(utl.DirName(self.arg.dstdir), 'scenes', sceneName.split('.')[0])
                #     newAbcFilePath = os.path.join(pubSceneDir, '/'.join(splitBaseDir[dataIndex:]))
                #
                #     if not os.path.exists(os.path.dirname(newAbcFilePath)):
                #         os.makedirs(os.path.dirname(newAbcFilePath))
                #
                #     cmd = 'cp -rf %s %s' % (abcFilePath, newAbcFilePath)
                #     msg.debug(cmd)
                #     os.system(cmd)
                #     cmds.setAttr("%s.abc_File" % alembicNode, newAbcFilePath, type='string')

        # LOD_TYPE Check
        lodTypeList = ['high']
        variantConNode = None
        if cmds.objExists('variant_CONF'):
            variantConNode = cmds.ls('variant_CONF')[0]
            if cmds.attributeQuery('LOD_type', n=variantConNode, ex=True):
                lodTypeList = cmds.attributeQuery('LOD_type', n=variantConNode, listEnum=True)[0].split(':')

        # self.arg.asset : assetName
        # self.arg.branch : branchName

        # if self.arg.has_key('branch'):
        if self.arg.variant != "":
            # Variant is Not Exists : Asset Publish Not Branch
            cmds.undoInfo(openChunk=True, cn='delete branch node')
            geomGrpChildren = cmds.listRelatives('geometry_GRP', c=True)
            for geomGrpChild in geomGrpChildren:
                if '_model_' not in geomGrpChild:
                    continue
                else:
                    if '%s_%s_' % (self.arg.asset, self.arg.branch) in geomGrpChild:
                        continue
                    else:
                        msg.debug(geomGrpChild)
                        cmds.delete(geomGrpChild)

        for lodType in lodTypeList:
            # if lodType == 'mid':
            #     continue

            # Rigging Pub Scene Copy
            sceneName = utl.BaseName(self.arg.scene)
            if variantConNode:
                if cmds.attributeQuery('LOD_type', n=variantConNode, ex=True):
                    cmds.setAttr("%s.LOD_type" % variantConNode, lodTypeList.index(lodType))

            selectedList = []
            if lodType == 'high':
                selectedList = self.selectedPublishGeom('high')
            elif lodType == 'mid':
                sceneName = sceneName.replace('.mb', '_mid.mb')
                msg.debug(sceneName)
                selectedList = self.selectedPublishGeom('mid')
            else:
                sceneName = sceneName.replace('.mb', '_low.mb')
                msg.debug(sceneName)
                selectedList = self.selectedPublishGeom('low')

            if variantConNode and cmds.attributeQuery('modelType', n=variantConNode, ex=True):
                modelTypeConnectList = cmds.listConnections('%s.modelType' % variantConNode, type='condition')
                if modelTypeConnectList:
                    for condition in modelTypeConnectList:
                        if cmds.getAttr('%s.firstTerm' % condition) == cmds.getAttr('%s.secondTerm' % condition):
                            msg.debug(cmds.listConnections('%s.outColorR' % condition, d=True, s=False, skipConversionNodes=True))
                            selectedList += cmds.listConnections('%s.outColorR' % condition, d=True, s=False, skipConversionNodes=True)

            cleanupList = copy.deepcopy(selectedList)
            for selNode in selectedList:
                if not cmds.objExists(selNode):
                    cleanupList.remove(selNode)
            cmds.select(cleanupList)

            pubSceneFile = utl.SJoin(utl.DirName(self.arg.dstdir), 'scenes', sceneName)
            msg.debug(pubSceneFile)

            if os.path.exists(pubSceneFile):
                os.remove(pubSceneFile)
            cmds.file(pubSceneFile, es=True, pr=True, typ='mayaBinary', force=True, options='v=0;')
            cmds.select(cl=True)
            # File Mode Change (only read)
            if lodType == 'high':
                os.chmod(pubSceneFile, 0555)

        if self.arg.variant != "":
            cmds.undoInfo(closeChunk=True, cn='delete branch node')
            cmds.undo()

    # def Tweaking(self):
    #     return var.SUCCESS
    # def Compositing(self):
    #     return var.SUCCESS


def assetExport(node=None, show=None, shot=None):
    if not node:
        node = cmds.ls(type='dxRig')[0]
    # current scene filename
    sceneFile = cmds.file(q=True, sn=True)

    # variant query
    variantData = GetRigVariant(node)
    if variantData:
        print('> rig variants :', variantData)
        for ctrln, variants in variantData.items():
            for n, i in variants:
                cmds.setAttr(ctrln, i)
                arg = exp.ARigAssetExporter()
                arg.scene = sceneFile
                arg.node  = node
                arg.variant = n
                # override
                if show: arg.ovr_show = show
                if shot: arg.ovr_shot = shot
                RigAssetExport(arg)
    else:
        arg = exp.ARigAssetExporter()
        arg.scene = sceneFile
        arg.node  = node
        # override
        if show: arg.ovr_show = show
        if shot: arg.ovr_shot = shot
        RigAssetExport(arg)




#-------------------------------------------------------------------------------
#
#   Rig Shot
#
#-------------------------------------------------------------------------------
class RigShotGeomExport(exp.RigShotBase):
    def preProcess(self):
        if not cmds.objExists(self.arg.node):
            msg.errorQuit('not found rig node [%s]' % self.arg.node, artist='daeseok.chae')

        # RigFile LOD change low to high
        if cmds.referenceQuery(self.arg.node, inr=True):
            refFile = cmds.referenceQuery(self.arg.node, f=True, wcn=True)
            if not '/_3d/' in refFile:
                msg.errorQuit('[USD Asset]', "Rig asset not publish data =>", 'Rig File : %s' % refFile, artist='daeseok.chae')

            if '_low.mb' in refFile:
                newFile = refFile.replace('_low.mb', '.mb')
                if os.path.exists(newFile):
                    msg.message('[Rig Represent] %s -> %s' % (os.path.basename(refFile), os.path.basename(newFile)))
                    refNode = cmds.referenceQuery(self.arg.node, rfn=True)
                    cmds.file(newFile, loadReference=refNode)

            if '_mid.mb' in refFile:
                newFile = refFile.replace('_mid.mb', '.mb')
                if os.path.exists(newFile):
                    msg.message('[Rig Represent] %s -> %s' % (os.path.basename(refFile), os.path.basename(newFile)))
                    refNode = cmds.referenceQuery(self.arg.node, rfn=True)
                    cmds.file(newFile, loadReference=refNode)

            # if has True, Rig last version update
            if self.arg.isRigUpdate:
                refFile = cmds.referenceQuery(self.arg.node, f=True, wcn=True)
                refDir = os.path.dirname(refFile)
                refFileName = os.path.basename(refFile)
                rigFiles = list()

                for fn in sorted(os.listdir(refDir)):
                    if '.mb' in fn and not fn.startswith('.') and fn.split('_')[-2] == 'rig':
                        rigFiles.append(fn)

                # descrese
                rigFiles.sort(reverse=True)

                if rigFiles[0] != refFileName:
                    msg.message('[Rig update last version] : %s -> %s' % (refFileName, rigFiles[0]))

                    newFile = os.path.join(refDir, rigFiles[0])
                    refNode = cmds.referenceQuery(self.arg.node, rfn=True)
                    cmds.file(newFile, loadReference=refNode)

        # rig asset info
        rigFile = mutl.GetReferenceFile(self.arg.node)
        if rigFile:
            msg.message('%s-rigFile :' % self.__name__, rigFile)

        self.arg.customLayerData = {
            'sceneFile': self.arg.scene,
            'start': self.arg.frameRange[0],
            'end': self.arg.frameRange[1],
            'step': self.arg.step,
            'rigFile': rigFile
        }
        self.rigFile = rigFile

        # find rig usd asset attribute
        arg = Arguments()
        arg.D.SetDecode(utl.DirName(rigFile))
        arg.nslyr = utl.BaseName(rigFile).split('.')[0]

        # rig variant
        variant = cmds.getAttr('%s.variant' % self.arg.node)
        if variant and arg.assetName != variant:
            self.arg.customLayerData['variant'] = variant

        if os.path.exists(arg.D.TASKN):
            msg.message('[RigAssetDirectory]', ':', arg.asset, arg.D.TASKN)
        else:
            msg.errorQuit('[USD Asset]', 'First, you have to export RigAsset', 'Rig File : %s' % rigFile, 'RigAssetDir : %s' % arg.D.TASKN, artist='daeseok.chae')

    def preCompute(self):
        self.rigInspector = RigNodeInspect(self.arg.node, self.arg.frameRange, self.arg.autofr)
        self.rigInspector.bake()
        self.arg.frameRange = self.rigInspector.exportRange

    def separate_geomExport(self, filename, objects, frames):
        ovr_opts = {'exportUVs': cmds.getAttr('%s.exportUVs' % self.arg.node)}

        for start, end in frames:
            fn = filename.replace('.usd', '.%04d.usd' % start)
            msg.debug('> GEOM FILE\t:', fn)
            utl.UsdExport(fn, objects, fr=(start, end), fs=self.arg.frameSample, **ovr_opts).doIt()
            self.arg.separate_geomfiles.append(fn)

    def geomExport(self, filename, objects):
        ovr_opts = {'exportUVs': cmds.getAttr('%s.exportUVs' % self.arg.node)}
        utl.UsdExport(filename, objects, fr=self.arg.frameRange, fs=self.arg.frameSample,
                       customLayerData=self.arg.customLayerData, **ovr_opts).doIt()

    def subframe_geomExport(self, filename, objects, frameSample, fileStep):
        ovr_opts = {'exportUVs': False}

        for start, end in mutl.GetIterFrames(self.arg.frameRange, step=fileStep):
            fn = filename.replace('.usd', '.%04d.usd' % start)
            utl.UsdExport(fn, objects, fr=(start, end), fs=frameSample, **ovr_opts).doIt()


    def xformExport(self):
        rigConList, attrList = mutl.GetRigConData(self.arg.node)

        if not rigConList or cmds.getAttr('%s.rigType' % self.arg.node) == 4: # # if rigType is etc, don't export xform data
            return None, None, None
        xformFile = utl.SJoin(self.arg.D.TASKNV, self.arg.F.XFORM)

        # export Xform
        xformLayer = utl.AsLayer(xformFile, create=True)
        xformLayer = utl.CheckPipeLineLayerVersion(xformLayer)
        if self.arg.customLayerData:
            tmp = xformLayer.customLayerData
            tmp.update(self.arg.customLayerData)
            xformLayer.customLayerData = tmp

        rootPrimSpec = utl.GetPrimSpec(xformLayer, '/root')
        xformLayer.defaultPrim = 'root'
        xformLayer.startTimeCode = self.arg.frameRange[0]
        xformLayer.endTimeCode = self.arg.frameRange[1]
        fps = mel.eval('currentTimeUnitToFPS')
        xformLayer.framesPerSecond = fps
        xformLayer.timeCodesPerSecond = fps

        opOrderList = []
        opOrderSpec = utl.GetAttributeSpec(rootPrimSpec, 'xformOpOrder', None, Sdf.ValueTypeNames.TokenArray)
        opOrderList.append('xformOp:transform')
        matrixAttrSpec = utl.GetAttributeSpec(rootPrimSpec, 'xformOp:transform', None, Sdf.ValueTypeNames.Matrix4d, variability=Sdf.VariabilityUniform)

        matrixs, frames = mutl.GetXformMatrix(rigConList[-1], self.arg.frameRange[0], self.arg.frameRange[1], step=self.arg.step)

        # attribute name : .xformOp:transform {matrix}
        #                  .xformOpOrder
        for index in xrange(len(frames)):
            matrix = Gf.Matrix4d(*matrixs[index])
            xformLayer.SetTimeSample(matrixAttrSpec.path, frames[index], matrix)

        # initialize Scale Attr
        # attribute name : .xformOp:scale
        #                : .xformOpOrder
        for attr in mutl.InitScaleAttributes:
            if cmds.attributeQuery(attr, n=rigConList[0], ex=True):
                # utl.GetAttributeSpec(rootPrimSpec, 'xformOpOrder', 'xformOp:scale', Sdf.ValueTypeNames.TokenArray)
                opOrderList.append('xformOp:scale')
                scaleAttrSpec = utl.GetAttributeSpec(rootPrimSpec, 'xformOp:scale', None, Sdf.ValueTypeNames.Vector3f)
                for index in xrange(len(frames)):
                    initScale = cmds.getAttr('%s.%s' % (rigConList[0], attr), time=frames[index])
                    xformLayer.SetTimeSample(scaleAttrSpec.path, frames[index], Gf.Vec3f(initScale, initScale, initScale))

        opOrderSpec.default = opOrderList
        xformLayer.Save()
        del xformLayer
        return xformFile, rigConList, attrList

    def rootConExport(self):
        nsName, nodeName = mutl.GetNamespace(self.arg.node)
        rootConName = JoinNsNameAndNode(nsName, self.rigInspector.rigRootCon)
        rootConFile = utl.SJoin(self.arg.D.TASKNV, self.arg.F.ROOTCON)
        rootLayer = utl.AsLayer(rootConFile, create=True)
        rootLayer = utl.CheckPipeLineLayerVersion(rootLayer)
        if self.arg.customLayerData:
            tmp = rootLayer .customLayerData
            tmp.update(self.arg.customLayerData)
            rootLayer.customLayerData = tmp

        rootPrimSpec = utl.GetPrimSpec(rootLayer, '/root')
        rootLayer.defaultPrim = 'root'
        fps = mel.eval('currentTimeUnitToFPS')
        rootLayer.framesPerSecond = fps
        rootLayer.timeCodesPerSecond = fps
        rootLayer.startTimeCode = self.arg.frameRange[0]
        rootLayer.endTimeCode = self.arg.frameRange[1]

        # node info setup
        opOrderList = []
        opOrderSpec = utl.GetAttributeSpec(rootPrimSpec, 'xformOpOrder', None, Sdf.ValueTypeNames.TokenArray)
        opOrderList.append("xformOp:transform")
        matrixAttrSpec = utl.GetAttributeSpec(rootPrimSpec, 'xformOp:transform', None, Sdf.ValueTypeNames.Matrix4d, variability=Sdf.VariabilityUniform)

        matrixs, frames = mutl.GetXformMatrix(rootConName, self.arg.frameRange[0], self.arg.frameRange[1], step=self.arg.step)

        # attribute name : .xformOp:transform {matrix}
        #                  .xformOpOrder
        for index in xrange(len(frames)):
            matrix = Gf.Matrix4d(*matrixs[index])
            rootLayer.SetTimeSample(matrixAttrSpec.path, frames[index], matrix)

        opOrderSpec.default = opOrderList
        rootLayer.Save()
        del rootLayer

    def computeSeparateFrames(self, geomFile, objects, lod):
        '''

        :param geomFile: rig high Usd File
        :param objects: rig Shape Nodes
        :return: (list) [(1001, 1050), (1051, 1100), ...]
        '''
        arg = Arguments()
        arg.D.SetDecode(utl.DirName(geomFile))
        arg.nslyr = utl.BaseName(geomFile).split('.')[0]
        nsname, nodename = mutl.GetNamespace(self.arg.node)
        arg.desc = nodename
        arg.lod = lod
        refFile = os.path.join(arg.D.TASKN, arg.F.GEOM)

        refSize = os.path.getsize(refFile)
        refSize = refSize / (1000.0 * 1000.0 * 1000.0) # GB

        numframes = self.arg.frameRange[1] - self.arg.frameRange[0] + 1
        # deformed = cmds.ls(objects, dag=True, s=True, io=True)
        # totalSize = refSize * (float(len(deformed)) / float(len(objects))) * numframes

        totalSize = refSize * numframes
        limitSize = 20.0 # GB

        msg.debug('refFile :', refFile)
        msg.debug("refSize :", refSize)
        msg.debug("totalSize :", totalSize)
        msg.debug("limitSize :", limitSize)

        if totalSize > limitSize:
            framesPerFile = int(numframes / (totalSize / limitSize))
            frames = list()
            for frame in range(self.arg.frameRange[0], self.arg.frameRange[1] + 1, framesPerFile):
                endFrame = frame + (framesPerFile - 1)
                if endFrame >= self.arg.frameRange[1]:
                    endFrame = self.arg.frameRange[1]
                frames.append((frame, endFrame))

            msg.message('[Rig.computeSeparateFrames] estimate total size : %.2fGB, per file size : %.2fGB, frames: %s' % (totalSize, refSize * framesPerFile, frames))
            msg.debug(frames)
            return frames

    def Exporting(self):
        # override
        print('#### RigShotExport ####')
        print('> node\t:', self.arg.node)

        self.arg.frameSample = mutl.GetFrameSample(self.arg.step)

        # rig asset info process
        self.preProcess()

        # shot working pre process ( initilize, working style check, etc... )
        self.preCompute()

        # export process
        # first, Xform Export
        xformFile, rigConList, attrList = self.xformExport()

        if self.rigInspector.rigRootCon:
            self.rootConExport()

        muteCtrl = None
        if rigConList and attrList and xformFile:
            muteCtrl = mutl.MuteCtrl(rigConList, attrList)
            muteCtrl.getValue()
            muteCtrl.setMute()

        objects = GetObjects(self.arg.node)
        # HIGH GEOM
        if objects['high']:
            self.arg.lod = var.T.HIGH
            ofile = utl.SJoin(self.arg.D.TASKNV, self.arg.F.GEOM)
            exportObjects = objects['high'] + objects['low']
            frames = self.computeSeparateFrames(self.rigFile, exportObjects, var.T.HIGH)
            if frames:
                self.separate_geomExport(ofile, exportObjects, frames)
            else:
                msg.debug('> GEOM FILE\t:', ofile)
                self.geomExport(ofile, exportObjects)
            self.arg.geomfiles.append(ofile)
        if objects['mid']:
            # MID GEOM
            self.arg.lod = var.T.MID
            ofile = utl.SJoin(self.arg.D.TASKNV, self.arg.F.GEOM)
            exportObjects = objects['mid'] + objects['low']
            frames = self.computeSeparateFrames(self.rigFile, exportObjects, var.T.MID)
            if frames:
                self.separate_geomExport(ofile, exportObjects, frames)
            else:
                msg.debug('> GEOM FILE\t:', ofile)
                self.geomExport(ofile, exportObjects)
            self.arg.geomfiles.append(ofile)
            # LOW GEOM
            self.arg.lod = var.T.LOW
            ofile = utl.SJoin(self.arg.D.TASKNV, self.arg.F.GEOM)
            exportObjects = objects['low']
            frames = self.computeSeparateFrames(self.rigFile, exportObjects, var.T.LOW)
            if frames:
                self.separate_geomExport(ofile, exportObjects, frames)
            else:
                msg.debug('> GEOM FILE\t:', ofile)
                self.geomExport(ofile, objects['low'])
            self.arg.geomfiles.append(ofile)
        # SIM GEOM
        if objects['sim']:
            ofile = utl.SJoin(self.arg.D.TASKNV, self.arg.F.SIMGEOM)
            exportObjects = objects['sim']
            frames = self.computeSeparateFrames(self.rigFile, exportObjects, var.T.SIM)
            if frames:
                self.separate_geomExport(ofile, exportObjects, frames)
            else:
                msg.debug('> GEOM FILE\t:', ofile)
                self.geomExport(ofile, objects['sim'])
            self.arg.geomfiles.append(ofile)

        # SubFrameObjects
        if cmds.getAttr('%s.exportStep' % self.arg.node):
            filestep = cmds.getAttr('%s.fileStepSize' % self.arg.node)
            step = round(cmds.getAttr('%s.frameStepSize' % self.arg.node), 2)
            fs   = mutl.GetFrameSample(step)
            subobjects = GetSubFrameObjects(self.arg.node, objects)
            for gt, objs in subobjects.items():
                if objs:
                    self.arg.lod = gt
                    ofile = utl.SJoin(self.arg.D.TASKNV, self.arg.F.GEOM)
                    ofile = ofile.replace('_geom.usd', '_geomsub.usd')
                    self.subframe_geomExport(ofile, objs, fs, filestep)
                    self.arg.subframe_geomfiles.append(ofile)


        if muteCtrl:
            muteCtrl.setUnMute()

    def Compositing(self):
        return var.SUCCESS


class RigShotCompositor(exp.RigShotBase):
    def Exporting(self):
        return var.SUCCESS

    def Tweaking(self):
        return var.SUCCESS


def shotExport(node=None, isRigUpdate=False, overwrite=False, sceneFile=None,
               show=None, seq=None, shot=None, version=None, user='anonymous', fr=[0, 0], step=1.0, process='geom'):
    if not node:
        return
    
    if not sceneFile:
        # current scene filename
        sceneFile = cmds.file(q=True, sn=True)

    arg = exp.ARigShotExporter()
    arg.scene= sceneFile
    arg.node = node
    arg.frameRange = mutl.GetFrameRange()
    arg.autofr = True
    arg.overwrite = overwrite
    arg.isRigUpdate = isRigUpdate
    arg.step = step
    arg.user = user

    # override
    if show: arg.ovr_show = show
    if seq:  arg.ovr_seq  = seq
    if shot: arg.ovr_shot = shot
    if version: arg.nsver = version
    if fr != [0, 0]:
        arg.frameRange = fr
        arg.autofr = False

    # if arg.Treat():
    #     print(arg)

    if process == 'both':
        RigShotGeomExport(arg)
        arg.overwrite = True
        exporter = RigShotCompositor(arg)
    else:
        if process == 'geom':
            exporter = RigShotGeomExport(arg)
        else:
            arg.overwrite = True
            exporter = RigShotCompositor(arg)
    return exporter.arg.master
