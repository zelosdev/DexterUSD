import string

from pxr import Usd, UsdGeom, UsdUtils, Sdf, Vt, Gf, UsdMaya
import maya.cmds as cmds

import importWorldCon
import common as cmn
import DXRulebook.Interface as rb
import DXUSD.Utils as utl
import DXUSD_MAYA.Message as msg

class UsdMerge:
    def __init__(self, filename, nodes=[]):
        self.inputfile = filename
        top = self.findTop(nodes)
        if not top:
            msg.error('msg : select dxBlock node or its children.')
        self.top = top[0]
        self.selNodes = self.checkSelNodes(nodes)

        self.rigVersion = self.getRigVersion()
        if not self.rigVersion:
            msg.error('msg : convention error.')

        self.fileInfo = self.filenameParse()
        self.nameSpace = None
        self.nodeParse()

    def findTop(self, nodes):
        if not nodes:
            top = cmds.ls(sl=True, l=True, type='dxBlock')
        else:
            for i in range(len(nodes)):
                if cmds.objectType(nodes[i]) == 'dxBlock':
                    top = [nodes[i]]
                    nodes.pop(i)
                    break
            else:
                top = nodes
                while top and cmds.objectType(top[0]) != 'dxBlock':
                    top = cmds.listRelatives(top[0], f=True, p=True)

        return top

    def checkSelNodes(self, nodes):
        res = []
        for node in nodes:
            if cmds.listRelatives(node, s=True):
                res.append(node)
            else:
                cmds.warning('%s ignored (must select transform of shape)'%node)

        return res

    def getRigVersion(self):
        importfile = cmds.getAttr('%s.importFile' % self.top)
        coder = rb.Coder('D')
        ret = coder.Decode(importfile)
        if ret.has_key('nslyr'):
            return ret.nslyr
        else:
            return None


    def getUsdRigVersion(self, usdfile):
        rootLayer = Sdf.Layer.FindOrOpen(usdfile)
        assert rootLayer, '# USD FileOpen Error -> %s' % usdfile
        # stage = Usd.Stage.Open(rootLayer, load=Usd.Stage.LoadNone)
        # defPrim = stage.GetDefaultPrim()
        # rigVer = None

        # if defPrim.HasCustomDataKey('rig'):
        #    rigVer = defPrim.GetCustomDataByKey('rig')
        rigVer = None
        if rootLayer.customLayerData.has_key('rigFile'):
            rigFile = rootLayer.customLayerData['rigFile']
            return utl.BaseName(rigFile).split('.')[0]

        return rigVer

    def filenameParse(self):
        '''
        {'SHOT': xxx, 'TASK': xxx, 'LAYER': xxx}
        '''
        data = dict()
        coder = rb.Coder('D')
        ret = coder.Decode(self.inputfile)
        if ret.has_key('nslyr'):
            data['LAYER'] = ret['nslyr']
        else:
            msg.error('msg : this inputcache not support!')

        if ret.has_key('shot'):
            data['SHOT'] = ret['shot']
        if ret.has_key('task'):
            data['TASK'] = ret['task']

        return data

    def nodeParse(self):
        tmp = self.top.split('|')[-1].split(':')
        if len(tmp) > 1:
            self.nameSpace = string.join(tmp[:-1], ':')
        self.topPath = self.top.replace('|', '/')


    def getSceneObject(self, childPath):
        '''
        childPath : primPath removed defaultPrimPath
        '''
        if self.nameSpace:
            childPath = childPath.replace('/', '/' + self.nameSpace + ':')
        objPath = self.topPath + childPath
        objPath = objPath.replace('/', '|')
        if cmds.objExists(objPath):
            return cmds.ls(objPath, dag=True, l=True)[0]

    def doIt(self):
        stage = Usd.Stage.Open(self.inputfile)
        defPrim = stage.GetDefaultPrim()
        defPath = defPrim.GetPath().pathString

        start = stage.GetStartTimeCode()
        end   = stage.GetEndTimeCode()
        fps   = stage.GetFramesPerSecond()

        # get ani usd to create worldXform ctr and check rig version
        aniUsd = self.inputfile
        simUsd = ""
        coder = rb.Coder('D')
        ret = coder.Decode(self.inputfile)
        if ret['task'] == 'sim': # if sim
            rootLayer = stage.GetRootLayer()
            customLayerData = rootLayer.customLayerData
            simUsd = self.inputfile
            if customLayerData.has_key('inputCache'):
                aniUsd = customLayerData['inputCache']
            else:
                aniUsd = defPrim.GetCustomDataByKey('inputCache')

        # get rig version
        rigVer = self.getUsdRigVersion(aniUsd)

        # Set playback options
        cmds.currentUnit(t='%dfps'%fps)
        cmds.playbackOptions(ast=start, aet=end, min=start, max=end)

        # get stageNode
        stageNode = self.getStageNode(self.top, aniUsd, 'ani')
        aniStage = Usd.Stage.Open(aniUsd)
        defPrim = aniStage.GetDefaultPrim()

        # only create worldCon if worldXform exists.
        if defPrim.GetVariantSets().HasVariantSet('WorldXform'):
            # set WorldXform
            defPrim.GetVariantSet('WorldXform').SetVariantSelection('off')

            # create worldXform controller
            importWorldCon.importWorldCon(self.top, aniUsd).doIt()

        if not rigVer:
            cmds.warning('Given usd does not have customData "rig".')
        else:
            if rigVer != self.rigVersion:
                m = 'Rig version is defferent. Do you want to keep merging?\n'
                m += '-xBlock rig ver.: %s\n' % self.rigVersion
                m += '-ani rig ver.: %s' % rigVer
                v = cmds.confirmDialog(t='DXBLOCK', m=m, b=['Yes', 'No'],
                                       db='Yes', cb='No', ds='No')
                assert (v!='No'), 'Canceled'

        for p in aniStage.Traverse():
            primPath = p.GetPath().pathString
            sceneObj = self.getSceneObject(primPath.replace(defPath, '', 1))
            if not sceneObj:
                continue
            primType = p.GetTypeName()

            if self.selNodes:
                for selNode in self.selNodes:
                    if sceneObj in selNode:
                        break
                else:
                    continue

            if sceneObj == self.top:
                continue

            # Get Extra Attributes
            usdAttrs = self.getAuthoredAttributes(p)

            if primType == 'Mesh':
                if not p.GetAttribute('points').HasValue():
                    continue

                shape = cmds.listRelatives(sceneObj, s=True, f=True, ni=True)
                if not shape:
                    continue
                else:
                    shape = shape[0]

                _pxrPBD = 'pxrUsdPointBasedDeformerNode'
                # check pbd connected
                if cmds.listConnections(shape, type=_pxrPBD, s=True):
                    defomer = cmds.listConnections(shape, type=_pxrPBD, s=True)[0]
                    if '_ani_' in defomer:
                        cmds.warning('%s already connected %s'%(shape, _pxrPBD))
                else:
                    node = cmds.deformer(shape, type=_pxrPBD, name='%s_ani_%s' % (shape.split('|')[-1], _pxrPBD))[0]
                    cmds.setAttr('%s.primPath' % node, primPath, type='string')
                    cmds.connectAttr('%s.outUsdStage' % stageNode, '%s.inUsdStage' % node)
                    cmds.connectAttr('time1.outTime', '%s.time' % node)
                    if usdAttrs:
                        cmn.SetUsdAttributes(shape, usdAttrs)


            # set trasform attribute (xform, visibility)
            mayaAttrs = cmn.GetMayaTransformAttrs(p)
            mayaAttrs.setAllAttrs(sceneObj)

            # import curves
            cmn.ImportCurveToMaya(p, self.top)

        if simUsd:
            # get stageNode
            stageNode = self.getStageNode(self.top, simUsd, 'sim')

            simStage = Usd.Stage.Open(simUsd)
            for p in simStage.Traverse():
                primPath = p.GetPath().pathString
                sceneObj = self.getSceneObject(primPath.replace(defPath, '', 1))
                if not sceneObj:
                    continue
                primType = p.GetTypeName()

                if self.selNodes:
                    for selNode in self.selNodes:
                        if sceneObj in selNode:
                            break
                    else:
                        continue


                if sceneObj == self.top:
                    continue

                # Get Extra Attributes
                usdAttrs = self.getAuthoredAttributes(p)

                if primType == 'Mesh':
                    if not p.GetAttribute('points').HasValue():
                        continue

                    shape = cmds.listRelatives(sceneObj, s=True, f=True, ni=True)
                    if not shape:
                        continue
                    else:
                        shape = shape[0]

                    _pxrPBD = 'pxrUsdPointBasedDeformerNode'
                    # check pbd connected
                    if cmds.listConnections(shape, type=_pxrPBD, s=True):
                        deformNode = cmds.listConnections(shape, type=_pxrPBD, s=True)[0]
                        if '_sim_' in deformNode:
                            cmds.warning('%s already connected %s'%(shape, _pxrPBD))
                        else:
                            cmds.disconnectAttr('%s.outputGeometry[0]' % deformNode, '%s.inMesh' % shape)
                            
                            node = cmds.deformer(shape, type=_pxrPBD, name='%s_sim_%s' % (shape.split('|')[-1], _pxrPBD))[0]
                            cmds.setAttr('%s.primPath' % node, primPath, type='string')
                            cmds.connectAttr('%s.outUsdStage' % stageNode, '%s.inUsdStage' % node)
                            cmds.connectAttr('time1.outTime', '%s.time' % node)
                            if usdAttrs:
                                cmn.SetUsdAttributes(shape, usdAttrs)
                    else:
                        node = cmds.deformer(shape, type=_pxrPBD, name='%s_sim_%s' % (shape.split('|')[-1], _pxrPBD))[0]
                        cmds.setAttr('%s.primPath' % node, primPath, type='string')
                        cmds.connectAttr('%s.outUsdStage' % stageNode, '%s.inUsdStage' % node)
                        cmds.connectAttr('time1.outTime', '%s.time' % node)
                        if usdAttrs:
                            cmn.SetUsdAttributes(shape, usdAttrs)


                # set trasform attribute (xform, visibility)
                mayaAttrs = cmn.GetMayaTransformAttrs(p)
                mayaAttrs.setAllAttrs(sceneObj)


        # set xBlock attributes
        cmds.setAttr('%s.nsLayer' % self.top, self.fileInfo['LAYER'], type='string')
        cmds.setAttr('%s.mergeFile' % self.top, self.inputfile, type='string')


    def getStageNode(self, obj, inputFile, task='ani'):
        stageNode = cmds.listConnections('%s.pxrStageNode'%obj, s=True, d=False)

        if not stageNode:
            _pxrSTG = 'pxrUsdStageNode'
            name = _pxrSTG
            if self.fileInfo.has_key('LAYER'):
                name = '%s_%s_%s'%(self.fileInfo['LAYER'], task, _pxrSTG)
            stageNode = cmds.createNode(_pxrSTG, name=name)
            cmds.connectAttr('%s.message' % stageNode, '%s.pxrStageNode'%obj, f=True)
        else:
            stageNode = stageNode[0]

        if task in stageNode:
            cmds.setAttr('%s.filePath' % stageNode, inputFile, type='string')
            return stageNode
        else:
            _pxrSTG = 'pxrUsdStageNode'
            name = _pxrSTG
            if self.fileInfo.has_key('LAYER'):
                name = '%s_%s_%s'%(self.fileInfo['LAYER'], task, _pxrSTG)
            stageNode = cmds.createNode(_pxrSTG, name=name)
            cmds.setAttr('%s.filePath' % stageNode, inputFile, type='string')
            return stageNode

    def getAuthoredAttributes(self, prim):
        targetAttrs = ['txBasePath', 'txLayerName', 'txVarNum']
        usdAttrs = list()
        for attr in prim.GetAuthoredPropertiesInNamespace('primvars'):
            if attr.GetBaseName() in targetAttrs:
                usdAttrs.append(attr)
        return usdAttrs



def UsdMergeDialog():
    fn = cmds.fileDialog2(
        fm=1, ff='USD (*.usd)',
        cap='Merge USD by xBlock'
    )
    if not fn:
        return

    UsdMerge(fn[0], cmds.ls(sl=True, l=True)).doIt()
