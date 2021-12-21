from pxr import Sdf, Usd, UsdGeom

import maya.cmds as cmds
import random

import Import
import Represent
import DXUSD_MAYA.Message as msg


# PURA : pxrUsdReferenceAssembly
def unpackPURATodxBlock():
    selected = cmds.ls(sl=True)
    for n in selected:
        if cmds.nodeType(n) == 'pxrUsdReferenceAssembly':
            Represent.Expanded(n).doIt()
            msg.message('info', '// Result dxBlockUtils: pxrUsdReferenceAssembly to dxBlock. //')


def packPURATodxBlock():
    selected = cmds.ls(sl=True)
    for n in selected:
        if cmds.nodeType(n) == 'dxBlock':
            Represent.Collapsed(node=n, ntype=1).doIt()
            msg.message('info', '// Result dxBlockUtils: dxBlock to pxrUsdReferenceAssembly. //')

# def xBlockRepresentCtrl():
#     selected = cmds.ls(sl=True)
#     for n in selected:
#         if cmds.nodeType(n) == 'xBlock':
#             Represent.Collapsed(node=n, ntype=1).doIt()
#             msg.debug('info', '// Result dxBlockUtils: xBlock to pxrUsdReferenceAssembly. //')
#         elif cmds.nodeType(n) == 'pxrUsdReferenceAssembly':
#             Represent.Expanded(n).doIt()
#             msg.debug('info', '// Result dxBlockUtils: pxrUsdReferenceAssembly to xBlock. //')


def puraCollapsed():
    selected = cmds.ls(sl=True, type='pxrUsdReferenceAssembly')
    if not selected:
        selected = cmds.ls(type='pxrUsdReferenceAssembly')

    for selNode in selected:
        if cmds.assembly(selNode, query=True, active=True) != 'Collapsed':
            cmds.assembly(selNode, edit=True, active='Collapsed')

def reloadReferenceAssembly():
    from pxr import UsdMaya
    selNodes = cmds.ls(sl=True, type='pxrUsdReferenceAssembly', l=True)
    if not selNodes:
        selNodes = cmds.ls(type='pxrUsdReferenceAssembly', l=True)
    for node in selNodes:
        UsdMaya.ReloadStage(node)


def dxBlockImport():
    selected = cmds.ls(sl = True, type = "pxrUsdReferenceAssembly")
    for n in selected:
        Represent.Full(n).doIt()


#-------------------------------------------------------------------------------
#
#   pxrUsdProxyShape
#
#-------------------------------------------------------------------------------
class ProxyShapeToSceneAssembly:
    def __init__(self):
        for shape in cmds.ls(sl=True, dag=True, type='pxrUsdProxyShape'):
            self.getAttr(shape)
            transNode = cmds.listRelatives(shape, p=True, f=True)[0]
            xb = Represent.XformBlock(transNode)
            parentNode= cmds.listRelatives(transNode, p=True, f=True)

            # delete
            cmds.delete(transNode)

            # create
            node = cmds.assembly(name=transNode.split('|')[-1], type='pxrUsdReferenceAssembly')
            self.setAttr(node)
            if parentNode:
                cmds.parent(node, parentNode[0])
            xb.Set(node)
            cmds.assembly(node, edit=True, active='Collapsed')


    def getAttr(self, node):
        self.filePath = cmds.getAttr('%s.filePath' % node)

    def setAttr(self, node):
        cmds.setAttr('%s.filePath' % node, self.filePath, type='string')


# -------------------------------------------------------------------------------
#
#   pxrUsdProxyShape
#
# -------------------------------------------------------------------------------
class SceneAssemblyToProxyShape:
    def __init__(self):
        for shape in cmds.ls(sl=True, dag=True, type='pxrUsdReferenceAssembly'):
            self.getAttr(shape)
            # transNode = cmds.listRelatives(shape, p=True, f=True)[0]
            xb = Represent.XformBlock(shape)
            parentNode = cmds.listRelatives(shape, p=True, f=True)

            # delete
            cmds.delete(shape)

            # create
            # node = cmds.assembly(name=shape.split('|')[-1], type='pxrUsdReferenceAssembly')
            node = cmds.createNode('pxrUsdProxyShape', name=shape.split('|')[-1])
            self.setAttr(node)
            if parentNode:
                cmds.parent(node, parentNode[0])
            xb.Set(node)
            # cmds.assembly(node, edit=True, active='Collapsed')

    def getAttr(self, node):
        self.filePath = cmds.getAttr('%s.filePath' % node)

    def setAttr(self, node):
        cmds.setAttr('%s.filePath' % node, self.filePath, type='string')


class ProxyShapeToMesh:
    def __init__(self, gtype='Proxy'):
        self.gtype = gtype

        for shape in cmds.ls(sl=True, dag=True, type='pxrUsdProxyShape'):
            filePath  = cmds.getAttr('%s.filePath' % shape)
            modelFile = self.GetModelFile(filePath)
            # print '# Debug - Reference File :', filePath
            # print '# Debug - Import Model File :', modelFile

            transNode = cmds.listRelatives(shape, p=True, f=True)[0]
            xb = Represent.XformBlock(transNode)

            parentNode = cmds.listRelatives(transNode, p=True, f=True)
            if parentNode:
                parentNode = parentNode[0]
            else:
                parentNode = None

            inodes = cmds.usdImport(f=modelFile, p=parentNode)
            if len(inodes) > 1:
                cmds.delete(inodes)
                print '# ERROR : model data has one more root group.'
            else:
                cmds.delete(transNode)

                root = cmds.rename(inodes[0], transNode.split('|')[-1])
                xb.Set(root)


    def GetModelFile(self, filename):
        stage = Usd.Stage.Open(filename)
        dprim = stage.GetDefaultPrim()
        mstacks = list()
        for p in dprim.GetPrimStack():
            lfn = p.layer.identifier
            if lfn.find('/model/') > -1 and len(lfn.split('.')) == 2:
                if lfn.find('/materials') > -1 or lfn.find('/collection') > -1:
                    continue
                mstacks.append(p)

        geomFiles = list()
        fn = mstacks[-1].layer.identifier
        # print '# Debug - Last Stack Layer :', fn
        stage = Usd.Stage.Open(fn)
        for p in stage.Traverse():
            if p.GetName() == self.gtype:
                for s in p.GetPrimStack():
                    lfn = s.layer.identifier
                    if lfn.find('geom.usd') > -1:
                        geomFiles.append(lfn)
        if not geomFiles:
            return fn
        return geomFiles[-1]




#-------------------------------------------------------------------------------
def updateAttribute():
    nodes = cmds.ls(sl=True, type='dxBlock')
    if not nodes:
        msg.warning('warning', 'have to select "dxBlock"')
        return
    for n in nodes:
        imfn = cmds.getAttr('%s.importFile' % n)
        if imfn:
            meta = Import.UsdImport.GetMetadata(imfn)
            for lyr in meta['subLayers']:
                if lyr.find('_attr.usd') > -1:
                    atfile = lyr.replace('_attr.usd', '_attr.json')
                    Import.JsonImportAttribute(atfile, n)
    msg.message('info', '// Result dxBlockUtils: Attribute update complete. //')


#-------------------------------------------------------------------------------
#
#   Randomize Offset
#
#-------------------------------------------------------------------------------
def RandomizeOffsetByDxTimeOffset(nodes, minOffset=0.0, maxOffset=0.0, step=1.0):
    # setup offset type
    offsetStepList = [minOffset]
    while (True):
        value = offsetStepList[-1] + step
        if value > maxOffset:
            break
        offsetStepList.append(value)

    for node in nodes:
        if cmds.nodeType(node) == "pxrUsdReferenceAssembly":
            timeOffsetNode = cmds.listConnections("%s.time" % node, s=True, d=False)
            if not timeOffsetNode:
                timeOffsetNode = cmds.createNode("dxTimeOffset")
                cmds.connectAttr("time1.outTime", "%s.time" % timeOffsetNode)
                cmds.connectAttr("%s.outTime" % timeOffsetNode, "%s.time" % node)
            else:
                timeOffsetNode = timeOffsetNode[0]
            cmds.setAttr("%s.offset" % timeOffsetNode, offsetStepList[random.randint(0, len(offsetStepList) - 1)])

def ConnectTimeOffset(selected=None):
    if not selected:
        selected = cmds.ls(sl=True, type='pxrUsdReferenceAssembly')
        if not selected:
            selected = cmds.ls(sl=True, type='pxrUsdProxyShape')
    selected = cmds.ls(selected)
    for node in selected:
        name = node.split(':')[-1].split('|')[-1]
        connected = cmds.listConnections('%s.time' % node, s=True, d=False)
        if connected:
            ctype = cmds.nodeType(connected[0])
            if ctype != 'dxTimeOffset':
                offsetNode = cmds.createNode('dxTimeOffset', n='%s_TimeOffset' % name)
                cmds.connectAttr('%s.outTime' % connected[0], '%s.time' % offsetNode, f=True)
                cmds.connectAttr('%s.outTime' % offsetNode, '%s.time' % node, f=True)
        else:
            offsetNode = cmds.createNode('dxTimeOffset', n='%s_TimeOffset' % name)
            cmds.connectAttr('time1.outTime', '%s.time' % offsetNode, f=True)
            cmds.connectAttr('%s.outTime' % offsetNode, '%s.time' % node, f=True)



#-------------------------------------------------------------------------------
#
#   pxrUsdReferenceAssembly clip timeline Edit
#
#-------------------------------------------------------------------------------
class ClipEdit:
    '''
    pxrUsdReferenceAssembly clip timeline Edit by visibility.
    Args:
        rootNode (str)  - root group node
        firstLoop (int) - loop count
        setTimes (list) - specified edit point
    '''
    def __init__(self, rootNode=None, firstLoop=2, setTimes=list()):
        if not rootNode:
            selected = cmds.ls(sl=True)
            if not selected:
                assert False, '# ERROR : select root node.'
            rootNode = selected[0]
        self.firstLoop = firstLoop
        self.setTimes  = setTimes

        # member variables
        self.source  = list()
        self.rootNode= rootNode
        if rootNode:
            self.source = cmds.listRelatives(rootNode, c=True, type='pxrUsdReferenceAssembly')
        self.globalOffset = 0
        if cmds.attributeQuery('GlobalOffset', n=self.rootNode, ex=True):
            self.globalOffset = cmds.getAttr('%s.GlobalOffset' % self.rootNode)
            cmds.setAttr('%s.GlobalOffset' % self.rootNode, 0)

    def doIt(self):
        if not self.source:
            assert False, '# Error : Not found source nodes.'
            return
        self.clearRig()

        editPoint = None    # clip start frame
        for i in range(len(self.source)):
            node = self.source[i]
            ClipEdit.ClearVisibility(node)
            ConnectTimeOffset(node)

            times = ClipEdit.GetClipTime(node)

            index, next = self.getClipInfo(times)
            startFrame = times[index][0]
            endFrame   = times[next][0]
            duration   = endFrame - startFrame

            if not editPoint:
                startFrame = int(times[index * self.firstLoop][0])
                endFrame   = int(times[next * self.firstLoop][0])
                if self.setTimes and len(self.setTimes) > i:
                    endFrame = self.setTimes[i]

            if editPoint:
                offset = editPoint + 1 - startFrame
                ClipEdit.SetOffset(node, offset * -1)
                ClipEdit.SetVisibility(node, editPoint, 0, 1)
                editPoint += duration
            else:
                editPoint = endFrame

            if self.source[-1] != node:
                ClipEdit.SetVisibility(node, editPoint, 1, 0)

        self.rigSetup()
        cmds.setAttr('%s.GlobalOffset' % self.rootNode, self.globalOffset)
        cmds.select(self.rootNode)


    def getClipInfo(self, times):
        clipTimes = list()
        print times
        for i in range(len(times)):
            clipTimes.append(times[i][1])
        clipTimes = list(set(clipTimes))
        clipTimes.sort()
        clipRange = (int(clipTimes[0]), int(clipTimes[-1]))

        index = 0
        for i in range(1, len(times)):
            if times[0][1] == times[i][1]:
                index = i
                break
        next = 1
        for i in range(index, len(times)):
            if clipRange[1] == times[i][1]:
                next = i
                break
        return index, next

    @staticmethod
    def GetClipTime(node):
        filePath = cmds.getAttr('%s.filePath' % node)
        stage = Usd.Stage.Open(filePath)
        dprim = stage.GetDefaultPrim()

        variantAttrs = cmds.listAttr(node, st='usdVariantSet_*')
        if variantAttrs:
            for attr in variantAttrs:
                variantSetName = attr.replace('usdVariantSet_', '')
                variantName    = cmds.getAttr('%s.%s' % (node, attr))
                vset = dprim.GetVariantSets().GetVariantSet(variantSetName)
                vset.SetVariantSelection(variantName)

        clipApi = Usd.ClipsAPI(dprim.GetChild("Geom"))
        times = clipApi.GetClipTimes()
        print times
        return times

    @staticmethod
    def SetVisibility(node, frame, cval, nval):
        # cval : current frame, nval : next frame
        cmds.setKeyframe(node, at='visibility', t=frame, v=cval, s=False)
        cmds.setKeyframe(node, at='visibility', t=frame+1, v=nval, s=False)

    @staticmethod
    def ClearVisibility(node):
        animCurve = cmds.listConnections('%s.visibility' % node, type='animCurve')
        if animCurve:
            cmds.delete(animCurve)
            cmds.setAttr('%s.visibility' % node, 1)

    @staticmethod
    def SetOffset(node, offset):
        offsetNode = cmds.listConnections('%s.time' % node, s=True, d=False, type='dxTimeOffset')
        if offsetNode:
            cmds.setAttr('%s.offset' % offsetNode[0], offset)


    #---------------------------------------------------------------------------
    def SetAttr(self, node, name, value=0.0):
        if not cmds.attributeQuery(name, n=node, ex=True):
            cmds.addAttr(node, ln=name, at='double')
        cmds.setAttr('%s.%s' % (node, name), value)

    def rigSetup(self):
        rootName = self.rootNode.split(':')[-1].split('|')[-1]

        visAnimNodes = list()
        offsetNodes  = list()
        for n in self.source:
            animCurve = cmds.listConnections('%s.visibility' % n, s=True, d=False, type='animCurve')
            if animCurve:
                visAnimNodes += animCurve
            offsetNode= cmds.listConnections('%s.time' % n, s=True, d=False, type='dxTimeOffset')
            if offsetNode:
                offsetNodes += offsetNode

        self.SetAttr(self.rootNode, 'GlobalOffset', 0.0)

        # GlobalOffset - Visibility
        globalOffset_pmaNode = cmds.createNode('plusMinusAverage', name='%s_Visibility_GlobalOffset' % rootName)
        cmds.setAttr('%s.operation' % globalOffset_pmaNode, 2)
        cmds.connectAttr('time1.outTime', '%s.input1D[0]' % globalOffset_pmaNode, f=True)
        cmds.connectAttr('%s.GlobalOffset' % self.rootNode, '%s.input1D[1]' % globalOffset_pmaNode, f=True)
        for n in visAnimNodes:
            cmds.connectAttr('%s.output1D' % globalOffset_pmaNode, '%s.input' % n, f=True)

        # dxTimeOffset
        for offsetNode in offsetNodes:
            name = offsetNode.split(':')[-1].split('|')[-1]
            value= cmds.getAttr('%s.offset' % offsetNode)

            pmaNode = cmds.createNode('plusMinusAverage', name=name.replace('TimeOffset', 'plusMinusAverage'))
            cmds.setAttr('%s.operation' % pmaNode, 2)
            cmds.setAttr('%s.input1D[0]' % pmaNode, value)
            cmds.connectAttr('%s.GlobalOffset' % self.rootNode, '%s.input1D[1]' % pmaNode, f=True)
            cmds.connectAttr('%s.output1D' % pmaNode, '%s.offset' % offsetNode, f=True)

    def clearRig(self):
        targetNodes = list()
        initAttrs   = dict()
        historyNodes= cmds.listHistory(self.rootNode, future=True, bf=True)
        for n in historyNodes[1:]:
            ntype = cmds.nodeType(n)
            if ntype.find('pxrUsd') == -1 and ntype.find('animCurve') == -1 and ntype.find('dxTime') == -1:
                targetNodes.append(n)
            if ntype == 'plusMinusAverage':
                connected = cmds.listConnections(n, s=False, d=True, p=True, type='dxTimeOffset')
                if connected:
                    value = cmds.getAttr('%s.input1D[0]' % n)
                    initAttrs[connected[0]] = value

        cmds.delete(targetNodes)
        for ln in initAttrs:
            cmds.setAttr(ln, initAttrs[ln])
