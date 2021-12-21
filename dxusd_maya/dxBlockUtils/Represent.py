import os
import string
import pprint
from pxr import Usd, UsdGeom, Sdf
import maya.cmds as cmds
import DXUSD.Utils as utl
import DXUSD_MAYA.Message as msg
import extra as xbExtra

#-------------------------------------------------------------------------------
def GetNodeVariants(node):
    result = dict()
    attrs = cmds.listAttr(node, st='usdVariantSet_*')
    if attrs:
        for ln in attrs:
            val = cmds.getAttr('%s.%s' % (node, ln))
            if val:
                name = ln.split('_')[-1]
                result[name] = val
    return result

def SetNodeVariants(node, variants):
    '''
    :param
        -variants : {'taskVariant': 'element', 'lodVariant': 'low', ...}
    '''
    for n, v in variants.items():
        ln = 'usdVariantSet_' + n
        if not cmds.attributeQuery(ln, n=node, ex=True):
            cmds.addAttr(node, ln=ln, dt='string')
        cmds.setAttr('%s.%s' % (node, ln), v, type='string')

def GetConstraints(node):
    result = dict()
    for c in cmds.ls(node, dag=True, type='constraint'):
        ctype = cmds.nodeType(c)
        command   = 'cmds.%s("%s", q=True, tl=True)' % (ctype, c)
        targetList= eval(command)
        result[ctype] = targetList
    return result

def SetConstraints(node, data):
    '''
    :param
        - data : {constraint_type: [targetList], ...}
    '''
    for ctype in data:
        objs = data[ctype]
        objs.append(node)
        command = 'cmds.%s(%s, mo=True)' % (ctype, '"%s"' % string.join(objs, '", "'))
        # print command
        cn = eval(command)


#-------------------------------------------------------------------------------
class Collapsed:
    '''
    Args
        ntype : 0 pxrUsdProxyShape, 1 pxrUsdReferenceAssembly
    '''
    def __init__(self, node=None, ntype=0):
        self.ntype = ntype
        self.rootParent= None
        self.rootNode  = None
        self.rootVars  = dict()
        if node:
            nodes = cmds.ls(node, type='dxBlock')
        else:
            nodes = cmds.ls(sl=True, type='dxBlock')
        if nodes:
            self.rootNode = nodes[0]
        self.timeConnect = False

    def doIt(self):
        assert self.rootNode, '# msg : Select "dxBlock"!'
        self.rootVars = GetNodeVariants(self.rootNode)

        rootParent = cmds.listRelatives(self.rootNode, p=True, f=True)
        if rootParent:
            self.rootParent = rootParent[0]
        filename = cmds.getAttr('%s.importFile' % self.rootNode)
        self.db = DataBlock(filename)
        self.xb = XformBlock(self.rootNode)

        # Get Constraint data
        self.constraintData = GetConstraints(self.rootNode)

        if cmds.referenceQuery(self.rootNode, inr=True):    # is Reference scene
            viz = int(cmds.getAttr('%s.visibility' % self.rootNode))
            nsp = self.rootNode.split('|')[-1].split(':')[0]
            newNode = self.rootNode.replace('%s:' % nsp, '')
            if viz == 0 and cmds.objExists(newNode):
                msg.warning('warning', 'Is Collapsed.')
            elif viz == 0 and not cmds.objExists(newNode):
                self.rootNode = newNode
                self.importUsdReference()
                cmds.setAttr("%s.visibility" % self.rootNode, 0)
            else:
                cmds.setAttr('%s.visibility' % self.rootNode, 0)
                self.rootNode = newNode
                self.importUsdReference()
        else:
            cmds.delete(self.rootNode)
            self.importUsdReference()

    def importUsdReference(self):
        if self.ntype == 1:
            self.importPxrReferenceAssembly()
        else:
            self.importPxrProxyShape()

    def importPxrProxyShape(self):
        node = cmds.createNode('pxrUsdProxyShape')
        node = cmds.listRelatives(node, p=True)[0]
        if self.rootParent:
            cmds.parent(node, self.rootParent)
        if self.timeConnect:
            cmds.connectAttr('time1.outTime', '%s.time' % node)

        fileName = self.db.filename.replace('.usd', '.render.usd')
        if not os.path.exists(fileName):
            fileName = self.db.filename

        cmds.setAttr('%s.filePath' % node, fileName, type='string')
        SetNodeVariants(node, self.rootVars)

        node = cmds.rename(node, self.rootNode)
        self.xb.Set(node)
        if self.constraintData:
            SetConstraints(node, self.constraintData)
        cmds.select(node)

    def importPxrReferenceAssembly(self):
        node = cmds.assembly(type='pxrUsdReferenceAssembly')
        if self.rootParent:
            cmds.parent(node, self.rootParent)
        if self.timeConnect:
            cmds.connectAttr('time1.outTime', '%s.time' % node)

        fileName = self.db.filename.replace('.usd', '.render.usd')
        if not os.path.exists(fileName):
            fileName = self.db.filename

        cmds.setAttr('%s.filePath' % node, fileName, type='string')
        SetNodeVariants(node, self.rootVars)

        node = cmds.rename(node, self.rootNode)
        cmds.assembly(node, edit=True, active='Collapsed')
        self.xb.Set(node)
        if self.constraintData:
            SetConstraints(node, self.constraintData)
        cmds.select(node)



# -------------------------------------------------------------------------------
# class Expanded:
#     def __init__(self, node=None):
#         self.rootParent= None
#         self.rootNode  = None
#         self.rootVars  = dict()
#
#         if node:
#             nodes = cmds.ls(node, type='pxrUsdReferenceAssembly')
#         else:
#             nodes = cmds.ls(sl=True, type='pxrUsdReferenceAssembly')
#         if nodes:
#             self.rootNode = nodes[0]
#
#         self.timeConnect = False
#
#     def getVariants(self, filename):
#         stage = Usd.Stage.Open(filename)
#         defPrim = stage.GetDefaultPrim()
#         vsets = defPrim.GetVariantSets()
#         names = vsets.GetNames()
#         return names
#
#
#     def doIt(self):
#         assert self.rootNode, '# msg : Select "pxrUsdReferenceAssembly"!'
#         self.rootVars = GetNodeVariants(self.rootNode)
#
#         rootParent = cmds.listRelatives(self.rootNode, p=True, f=True)
#         if rootParent:
#             self.rootParent = rootParent[0]
#
#         filename = cmds.getAttr('%s.filePath' % self.rootNode)
#         name = self.rootNode.split('|')[-1]
#         self.db = DataBlock(filename, rootName=name, variants=self.rootVars)
#         self.xb = XformBlock(self.rootNode)
#
#         self.constraintData = GetConstraints(self.rootNode)
#         if self.constraintData:
#             cmds.delete(self.rootNode)
#         # delete current
#         if cmds.objExists(self.rootNode):
#             cmds.delete(self.rootNode)
#
#         if self.db.trees:
#             self.makeTree()
#         else:
#             self.importGeom()
#
#
#     def importGeom(self):
#         # reference nodes check
#         nodes = cmds.ls(self.rootNode, r=True)
#         if nodes:
#             rootNode = nodes[0]
#             rootVars = GetNodeVariants(rootNode)
#             _ifmake = -1
#             for n in rootVars:
#                 if self.rootVars.has_key(n): # and self.rootVars[n] == rootVars[n]:
#                     _ifmake += 0
#                 else:
#                     _ifmake += 1
#             if _ifmake == -1:
#                 cmds.setAttr('%s.visibility' % rootNode, 1)
#         else:
#             _ifmake = 1
#
#         if _ifmake != -1:
#             node = self.makeXBlock(name=self.rootNode, fn=self.db.filename)
#             if self.rootParent:
#                 cmds.parent(node, self.rootParent)
#             self.xb.Set(node)
#             if self.constraintData:
#                 SetConstraints(node, self.constraintData)
#             cmds.select(node)
#
#
#
#     def makeTree(self):
#         # root block
#         rootBlock = self.makeXBlock(name=self.db.trees[0].split('/')[1], parent=self.rootParent)
#         print '# makeTree :', rootBlock
#         cmds.setAttr('%s.importFile' % rootBlock, self.db.filename, type='string')
#
#         try:
#             for ep in self.db.trees:
#                 src = ep.split('/')
#                 for i in range(1, len(src)-1):
#                     c = string.join(src[:i+1], '|')
#                     p = string.join(src[:i], '|')
#                     if not cmds.objExists(c):
#                         cmds.group(name=src[i], p=p, em=True)
#
#                 currentPath = ep.replace('/', '|')
#                 parentPath  = string.join(src[:-1], '|')
#                 if not cmds.objExists(currentPath):
#                     if self.db.compMap.has_key(ep):
#                         n = self.makePxrReference(name=src[-1], fn=self.db.compMap[ep], parent=parentPath)
#                         if self.db.vsetMap.has_key(ep):
#                             SetNodeVariants(n, self.db.vsetMap[ep])
#                     else:
#                         n = cmds.gorup(name=src[-1], p=parentPath, em=True)
#
#             for ep in self.db.xformMap:
#                 n = ep.replace('/', '|')
#                 for attrDatas, extra in self.db.xformMap[ep]:
#                     for time, attrData in attrDatas.items():
#                         for attr, value in attrData.items():
#                             if time == None:
#                                 cmds.setAttr('%s.%s' % (n, attr), value)
#                             else:
#                                 cmds.setKeyframe(n, at=attr, v=value, t=time)
#
#                     for attr, v in extra.items():
#                         cmds.setAttr('%s.%s' % (n, attr), v)
#
#             cmds.select(rootBlock)
#         except:
#             # cmds.delete(rootBlock)
#             pass
#
#
#     def makePxrReference(self, name=None, fn=None, parent=None):
#         return self.makePxrProxyShape(name=name, fn=fn, parent=parent)
#
#     # def makePxrReferenceAssembly(self, name=None, fn=None, parent=None):
#     #     node = cmds.assembly(name=name, type='pxrUsdReferenceAssembly')
#     #     if self.timeConnect:
#     #         cmds.connectAttr('time1.outTime', '%s.time' % node)
#     #     cmds.setAttr('%s.filePath' % node, fn, type='string')
#     #     xx = cmds.parent(node, parent)
#     #     print '# parent :', xx
#     #     cmds.assembly(node, edit=True, active='Collapsed')
#     #     return node
#
#     def makePxrProxyShape(self, name=None, fn=None, parent=None):
#         shape= cmds.createNode('pxrUsdProxyShape')
#         node = cmds.listRelatives(shape, p=True)[0]
#         if parent:
#             cmds.parent(node, parent)
#         if self.timeConnect:
#             cmds.connectAttr('time1.outTime', '%s.time' % node)
#         cmds.setAttr('%s.filePath' % shape, fn, type='string')
#         node = cmds.rename(node, name)
#         return node
#
#
#     def makeXBlock(self, name=None, fn=None, parent=None):
#         if fn:
#             vsetNames = self.getVariants(fn)
#             nodes= cmds.usdImport(f=fn, shd='none', var=self.rootVars.items())
#             node = nodes[0]
#             children = cmds.listRelatives(node, c=True, f=True)
#
#         # create xblock
#         if parent:
#             xblock = cmds.createNode('dxBlock', p=parent)
#         else:
#             xblock = cmds.createNode('dxBlock')
#         cmds.setAttr('%s.type' % xblock, 1)
#         cmds.setAttr('%s.action' % xblock, 1)
#         if fn:
#             cmds.setAttr('%s.importFile' % xblock, fn, type='string')
#             if vsetNames:
#                 for n in vsetNames:
#                     ln = 'usdVariantSet_' + n
#                     cmds.addAttr(xblock, ln=ln, dt='string')
#             if self.rootVars:
#                 for n in self.rootVars:
#                     ln = 'usdVariantSet_' + n
#                     cmds.setAttr('%s.%s' % (xblock, ln), self.rootVars[n], type='string')
#             cmds.parent(children, xblock)
#             cmds.delete(node)
#
#         xblock = cmds.rename(xblock, name)
#         return xblock

#-------------------------------------------------------------------------------
class Full:
    def __init__(self, node=None):
        self.rootParent= None
        self.rootNode  = None
        self.rootVars  = dict()

        if node:
            nodes = cmds.ls(node, type='pxrUsdReferenceAssembly')
        else:
            nodes = cmds.ls(sl=True, type='pxrUsdReferenceAssembly')
        if nodes:
            self.rootNode = nodes[0]

    def getVariants(self, filename):
        stage = Usd.Stage.Open(filename)
        defPrim = stage.GetDefaultPrim()
        vsets = defPrim.GetVariantSets()
        names = vsets.GetNames()
        return names


    def doIt(self):
        assert self.rootNode, '# msg : Select "pxrUsdReferenceAssembly"!'
        self.rootVars = GetNodeVariants(self.rootNode)

        rootParent = cmds.listRelatives(self.rootNode, p=True, f=True)
        if rootParent:
            self.rootParent = rootParent[0]

        filename = cmds.getAttr('%s.filePath' % self.rootNode)
        self.db = DataBlock(filename)
        self.xb = XformBlock(self.rootNode)

        self.constraintData = GetConstraints(self.rootNode)
        if self.constraintData:
            cmds.delete(self.rootNode)
        # delete current
        cmds.delete(self.rootNode)

        self.importGeom()


    def importGeom(self):
        # reference nodes check
        node = self.makeXBlock(name=self.rootNode, fn=self.db.filename)
        if self.rootParent:
            cmds.parent(node, self.rootParent)
        self.xb.Set(node)
        if self.constraintData:
            SetConstraints(node, self.constraintData)
        cmds.select(node)



    def makeTree(self):
        # root block
        rootBlock = self.makeXBlock(name=self.db.trees[0].split('/')[1], parent=self.rootParent)
        cmds.setAttr('%s.importFile' % rootBlock, self.db.filename, type='string')

        for ep in self.db.trees:
            src = ep.split('/')
            for i in range(1, len(src)-1):
                c = string.join(src[:i+1], '|')
                p = string.join(src[:i], '|')
                if not cmds.objExists(c):
                    cmds.group(name=src[i], p=p, em=True)

            currentPath = ep.replace('/', '|')
            parentPath  = string.join(src[:-1], '|')
            if not cmds.objExists(currentPath):
                if self.db.compMap.has_key(ep):
                    n = self.makePxrReference(name=src[-1], fn=self.db.compMap[ep], parent=parentPath)
                    if self.db.vsetMap.has_key(ep):
                        SetNodeVariants(n, self.db.vsetMap[ep])
                else:
                    n = cmds.gorup(name=src[-1], p=parentPath, em=True)

        for ep in self.db.xformMap:
            n = ep.replace('/', '|')
            for attrDatas, extra in self.db.xformMap[ep]:
                for time, attrData in attrDatas.items():
                    for attr, value in attrData.items():
                        if time == None:
                            cmds.setAttr('%s.%s' % (n, attr), value)
                        else:
                            cmds.setKeyframe(n, at=attr, v=value, t=time)

                for attr, v in extra.items():
                    cmds.setAttr('%s.%s' % (n, attr), v)

        cmds.select(rootBlock)


    def makePxrReference(self, name=None, fn=None, parent=None):
        node = cmds.assembly(name=name, type='pxrUsdReferenceAssembly')
        cmds.connectAttr('time1.outTime', '%s.time' % node)
        cmds.setAttr('%s.filePath' % node, fn, type='string')
        cmds.parent(node, parent)
        cmds.assembly(node, edit=True, active='Collapsed')
        return node


    def makeXBlock(self, name=None, fn=None, parent=None):
        if fn:
            vsetNames = self.getVariants(fn)
            nodes= cmds.usdImport(f=fn, shd='none', var=self.rootVars.items())
            node = nodes[0]
            children = cmds.listRelatives(node, c=True, f=True)

        # create xblock
        if parent:
            xblock = cmds.createNode('dxBlock', p=parent)
        else:
            xblock = cmds.createNode('dxBlock')
        cmds.setAttr('%s.type' % xblock, 1)
        cmds.setAttr('%s.action' % xblock, 1)
        if fn:
            cmds.setAttr('%s.importFile' % xblock, fn, type='string')
            if vsetNames:
                for n in vsetNames:
                    ln = 'usdVariantSet_' + n
                    cmds.addAttr(xblock, ln=ln, dt='string')
            if self.rootVars:
                for n in self.rootVars:
                    ln = 'usdVariantSet_' + n
                    cmds.setAttr('%s.%s' % (xblock, ln), self.rootVars[n], type='string')
            cmds.parent(children, xblock)
            cmds.delete(node)

        xblock = cmds.rename(xblock, name)
        return xblock


class DataBlock:
    '''
    Args:
        filename (str) -
        rootName (str) - root node name
        variants (dict)- variant data
    '''
    def __init__(self, filename, rootName='', variants=dict()):
        self.filename = filename
        self.rootName = rootName
        self.variantsMap = variants
        self.defaultName = ''

        self.trees   = list()
        self.compMap = dict()
        self.xformMap= dict()
        self.vsetMap = dict()

        self.doIt()

    def doIt(self):
        # first
        self.lastfile = self.filename
        stage, defPrim = self.OpenStage(self.filename)
        self.defaultName = defPrim.GetName()
        if self.rootName:
            self.defaultName = self.rootName

        # variant selection
        if self.variantsMap:
            for key in self.variantsMap:
                val = self.variantsMap[key]
                vset = defPrim.GetVariantSets().GetVariantSet(key)
                vset.SetVariantSelection(val)

        modelStack = list()
        for s in defPrim.GetPrimStack():
            sfile = s.layer.identifier
            if sfile.find('/model/') > -1:
                modelStack.append(s)
        stackfile = modelStack[-1].layer.identifier
        if stackfile != self.filename:
            # Reopen
            self.lastfile = stackfile
            stage, defPrim = self.OpenStage(stackfile)

        self.traverseStage(defPrim)
        if self.trees:
            self.traverseXformStage(defPrim)


    def OpenStage(self, filename, load=Usd.Stage.LoadAll):
        stage = Usd.Stage.Open(filename, load=load)
        dprim = stage.GetDefaultPrim()
        return stage, dprim


    def traverseStage(self, prim):
        stage = prim.GetStage()
        primName = prim.GetName()
        treeIter = iter(Usd.PrimRange.AllPrims(prim))
        for p in treeIter:
            pathStr = p.GetPath().pathString
            pathStr = pathStr.replace(primName, self.defaultName, 1)
            stack = p.GetPrimStack()
            if len(stack) > 1 and stack[0].layer.identifier == self.lastfile:
                filename = stack[1].layer.identifier
                modelfile= os.path.join(os.path.dirname(os.path.dirname(filename)), 'model.usd')
                if os.path.exists(modelfile):
                    filename = modelfile
                self.compMap[pathStr] = filename
                self.trees.append(pathStr)
                if p.HasVariantSets():
                    self.updateVariants(p, pathStr)

    def updateVariants(self, prim, primStr):
        data = dict()
        vsets = prim.GetVariantSets()
        for n in vsets.GetNames():
            vs = vsets.GetVariantSet(n)
            data[n] = vs.GetVariantSelection()
        self.vsetMap[primStr] = data


    def traverseXformStage(self, prim):
        primName = prim.GetName()
        treeIter = iter(Usd.PrimRange.AllPrims(prim))
        for p in treeIter:
            stack = p.GetPrimStack()
            if stack[0].layer.identifier == self.lastfile:
                pathStr = p.GetPath().pathString
                pathStr = pathStr.replace(primName, self.defaultName, 1)
                data = list()
                for attr in p.GetPropertiesInNamespace('xformOp'):
                    if not attr.HasValue():
                        continue
                    attrData, extra = UsdXformToMayaAttr(UsdGeom.XformOp(attr))
                    data.append((attrData, extra))
                if data:
                    self.xformMap[pathStr] = data

# class XXXDataBlock:
#     def __init__(self, filename):
#         self.filename = filename
#         self.defaultName = ''
#
#         self.trees   = list()
#         self.compMap = dict()
#         self.xformMap= dict()
#         self.vsetMap = dict()
#
#         self.doIt()
#
#     def doIt(self):
#         # first
#         self.lastfile = self.filename
#         stage, defPrim = self.OpenStage(self.filename)
#         self.defaultName = defPrim.GetName()
#
#         stack  = defPrim.GetPrimStack()
#         stackfile = stack[-1].layer.identifier
#         if stackfile != self.filename:
#             # print '# Debug : reopen -> %s' % stackfile
#             self.lastfile = stackfile
#             stage, defPrim = self.OpenStage(stackfile)
#
#         self.traverseStage(defPrim)
#         if self.trees:
#             self.traverseXformStage(defPrim)
#
#
#     def OpenStage(self, filename, load=Usd.Stage.LoadAll):
#         stage = Usd.Stage.Open(filename, load=load)
#         dprim = stage.GetDefaultPrim()
#         return stage, dprim
#
#
#     def traverseStage(self, prim):
#         stage = prim.GetStage()
#         primName = prim.GetName()
#         treeIter = iter(Usd.PrimRange.AllPrims(prim))
#         for p in treeIter:
#             pathStr = p.GetPath().pathString
#             pathStr = pathStr.replace(primName, self.defaultName, 1)
#             stack = p.GetPrimStack()
#             if len(stack) > 1 and stack[0].layer.identifier == self.lastfile:
#                     self.compMap[pathStr] = stack[1].layer.identifier
#                     self.trees.append(pathStr)
#                     if p.HasVariantSets():
#                         self.updateVariants(p, pathStr)
#
#     def updateVariants(self, prim, primStr):
#         data = dict()
#         vsets = prim.GetVariantSets()
#         for n in vsets.GetNames():
#             vs = vsets.GetVariantSet(n)
#             data[n] = vs.GetVariantSelection()
#         self.vsetMap[primStr] = data
#
#
#     def traverseXformStage(self, prim):
#         primName = prim.GetName()
#         treeIter = iter(Usd.PrimRange.AllPrims(prim))
#         for p in treeIter:
#             stack = p.GetPrimStack()
#             if stack[0].layer.identifier == self.lastfile:
#                 pathStr = p.GetPath().pathString
#                 pathStr = pathStr.replace(primName, self.defaultName, 1)
#                 data = list()
#                 for attr in p.GetPropertiesInNamespace('xformOp'):
#                     if not attr.HasValue():
#                         continue
#                     attrData, extra = UsdXformToMayaAttr(UsdGeom.XformOp(attr))
#                     data.append((attrData, extra))
#                 if data:
#                     self.xformMap[pathStr] = data




class XformBlock:
    def __init__(self, node):
        self.m_translate = cmds.getAttr('%s.translate' % node)[0]
        self.m_rotate    = cmds.getAttr('%s.rotate' % node)[0]
        self.m_scale     = cmds.getAttr('%s.scale' % node)[0]

        self.m_rotatePivot = cmds.getAttr('%s.rotatePivot' % node)[0]
        self.m_scalePivot  = cmds.getAttr('%s.scalePivot' % node)[0]
        self.m_rotatePivotTranslate = cmds.getAttr('%s.rotatePivotTranslate' % node)[0]
        self.m_scalePivotTranslate = cmds.getAttr('%s.scalePivotTranslate' % node)[0]

    def Set(self, node):
        cmds.setAttr('%s.rotatePivot' % node, *self.m_rotatePivot)
        cmds.setAttr('%s.rotatePivotTranslate' % node, *self.m_rotatePivotTranslate)
        cmds.setAttr('%s.scalePivot' % node, *self.m_scalePivot)
        cmds.setAttr('%s.scalePivotTranslate' % node, *self.m_scalePivotTranslate)

        cmds.setAttr('%s.scale' % node, *self.m_scale)
        cmds.setAttr('%s.rotate' % node, *self.m_rotate)
        cmds.setAttr('%s.translate' % node, *self.m_translate)



def UsdXformToMayaAttr(Op):
    ns = Op.GetOpName().split(':')
    name = ns.pop(-1)
    type = Op.GetOpType()
    timeSamples = Op.GetTimeSamples()

    if len(timeSamples) <= 1:
        timeSamples = [None]

    attrList = []
    extra = {}
    '''
     1 : UsdGeom.XformOp.TypeTranslate
     2 : UsdGeom.XformOp.TypeScale
     3 : UsdGeom.XformOp.TypeRotateX
     4 : UsdGeom.XformOp.TypeRotateY
     5 : UsdGeom.XformOp.TypeRotateZ
     6 : UsdGeom.XformOp.TypeRotateXYZ    (ro:0)
     7 : UsdGeom.XformOp.TypeRotateXZY    (ro:3)
     8 : UsdGeom.XformOp.TypeRotateYXZ    (ro:4)
     9 : UsdGeom.XformOp.TypeRotateYZX    (ro:1)
    10 : UsdGeom.XformOp.TypeRotateZXY    (ro:2)
    11 : UsdGeom.XformOp.TypeRotateZYX    (ro:5)
    12 : UsdGeom.XformOp.TypeOrient
    13 : UsdGeom.XformOp.TypeTransform
    '''
    if type.value == 0: # ?
        pass

    elif type.value <= 2: # translate, scale
        _attrList = None
        if name == 'pivot':
            _attrList = ['rotatePivot', 'scalePivot']
        else:
            _attrList = [name]

        for item in _attrList:
            attrList.append(['%s%s'%(item, v) for v in 'XYZ'])

    elif type.value <= 5: # rotateX, rotateY, rotateZ
        xyz = type.displayName[-1]
        _attr = name
        if name != type.displayName: # except rotateX(Y, Z)
            _attr += xyz
        attrList.append([_attr])

    elif type.value <= 11: # rotateXYZ~ZYX
        xyz = type.name[-3:]
        _attr = name[:-3] if xyz in name else name
        attrList.append(['%s%s'%(_attr, v) for v in xyz])

        if name == type.displayName: # only rotate (except rotateAxis)
            extra.update({'ro':[0,3,4,1,2,5][type.value-6]})

    elif type.value == 12: # orient ?
        pass

    elif type.value == 13: # transform
        if name == 'shear':
            attrList.append(['shear%s'%v for v in ['XY', 'XZ', 'YZ']])
        else:
            # transform ?
            pass

    res = {}
    for i in range(len(timeSamples)):
        time = 0 if timeSamples[i] == None else Usd.TimeCode(timeSamples[i])
        value = Op.Get(time)
        _res = {}
        if name == 'shear':
            value = [value[1][0], value[2][0], value[2][1]]
        elif isinstance(value, float):
            value = [value]

        for attrs in attrList:
            for j in range(len(attrs)):
                _res.update({attrs[j]:value[j]})

        res.update({timeSamples[i]:_res})

    return res, extra

class Expanded:
    def __init__(self, node=None):
        if node:
            nodes = cmds.ls(node, type='pxrUsdReferenceAssembly')
        else:
            nodes = cmds.ls(sl=True, type='pxrUsdReferenceAssembly')
        if nodes:
            self.rootNode = nodes[0]

        self.specializes_DATA = {}
        self.geomList = []

    def setXformOp(self, prim, node):
        data = list()
        for attr in prim.GetPropertiesInNamespace('xformOp'):
            if not attr.HasValue():
                continue
            attrData, extra = UsdXformToMayaAttr(UsdGeom.XformOp(attr))
            data.append((attrData, extra))
        if data:
            for attrDatas, extra in data:
                for time, attrData in attrDatas.items():
                    for attr, value in attrData.items():
                        if time == None:
                            cmds.setAttr('%s.%s' % (node, attr), value)

                for attr, v in extra.items():
                    cmds.setAttr('%s.%s' % (node, attr), v)

    def setVariants(self, node, variantsSelection):
        # prim.GetVariantSets().GetAllVariantSelections()
        for vKey in variantsSelection:
            if not cmds.attributeQuery('usdVariantSet_%s' % vKey[0], n=node, ex=True):
                cmds.addAttr(node, ln='usdVariantSet_%s' % vKey[0], dt='string')
            cmds.setAttr('%s.usdVariantSet_%s' % (node, vKey[0]), vKey[1], type='string')

    def GetVariants(self, spec):
        result = []
        for k, v in spec.variantSelections.items():
            if k != 'preview':
                result.append((k, v))
        return result

    def IsGeom(self, prim):
        gtyp = prim.GetTypeName()
        if gtyp == 'Mesh':
            return True
        elif gtyp == 'BasisCurves':
            return True
        elif gtyp == 'PointInstancer':
            return True
        elif gtyp == 'Scope':
            return True
        else:
            return False

    def createReferenceNode(self, prim, filePath, primPath="", excludePrimPaths="", variants=[]):
        refNode = cmds.createNode('pxrUsdReferenceAssembly')
        refNode = cmds.rename(refNode, prim.GetName())
        cmds.setAttr('%s.filePath' % refNode, filePath, type='string')
        cmds.setAttr('%s.primPath' % refNode, primPath, type='string')
        cmds.setAttr('%s.excludePrimPaths' % refNode, excludePrimPaths, type='string')

        self.setVariants(refNode, variants)

        return refNode

    def pointInstancer_doIt(self, prim, parentNode):
        primPath  = prim.GetParent().GetPath().pathString
        msg.debug('>', primPath, 'pointInstancer')
        assetPath = prim.GetPrimStack()[0].layer.identifier
        msg.debug('\t assetPath :', assetPath)
        msg.debug('')

        pParentNode = cmds.listRelatives(parentNode, p=True)[0]
        cmds.delete(parentNode)
        pointInstNode = self.createReferenceNode(prim.GetParent(), assetPath)
        cmds.parent(pointInstNode, pParentNode)
        self.setXformOp(prim, pointInstNode)

    def references_doIt(self, prim, parentNode):
        msg.debug('>', prim.GetPath().pathString)
        stack = prim.GetPrimStack()
        # for s in stack:
        #     print('\t:', s)
        primPath = '' # stack[0].path
        info = self.references_getInfo(stack[0])
        msg.debug('\t:', primPath)
        pprint.pprint(info)
        msg.debug('')
        if info.has_key('primPath'):
            primPath = info['primPath']

        refNode = self.createReferenceNode(prim, filePath=info.get('assetPath', ''), primPath=primPath,
                                           excludePrimPaths=info.get('excludePrimPaths', ''),
                                           variants=info.get('variants', []))

        cmds.parent(refNode, parentNode)
        self.setXformOp(prim, refNode)

    def references_getInfo(self, spec):
        identifier = spec.layer.identifier
        assetPath  = spec.referenceList.prependedItems[0].assetPath
        fullPath   = os.path.abspath(os.path.join(utl.DirName(identifier), assetPath))
        data = {
            'assetPath': fullPath,
            'variants': self.GetVariants(spec)
        }
        # custom data
        if spec.customData.has_key('excludePrimPaths'):
            data['excludePrimPaths'] = spec.customData.get('excludePrimPaths')
        if spec.customData.has_key('primPath'):
            data['primPath'] = spec.customData.get('primPath')
        return data

    def specializes_doIt(self, prim, parentNode):
        if prim.IsInstanceable():
            msg.debug('>', prim.GetPath().pathString, 'instanceable')
            stack = prim.GetPrimStack()
            # for s in stack:
            #     print('\t', s)
            primPath = '' # stack[0].path
            info = self.specializes_getInfo(stack[1])
            msg.debug('\t:', primPath)
            pprint.pprint(info)
            msg.debug('')
            if info.has_key('primPath'):
                primPath = info['primPath']

            refNode = self.createReferenceNode(prim, filePath=info.get('assetPath', ''), primPath=primPath,
                                               excludePrimPaths=info.get('excludePrimPaths', ''),
                                               variants=info.get('variants', []))

            cmds.parent(refNode, parentNode)
            self.setXformOp(prim, refNode)

    def specializes_getInfo(self, spec):
        source = spec.nameChildren.get('source')
        if not source:
            return

        if not self.specializes_DATA.has_key(spec.path):
            info = self.references_getInfo(source)
            self.specializes_DATA[spec.path] = info

        return self.specializes_DATA[spec.path]

    def getGeomParent(self, primPath):
        parentPath = primPath.GetParentPath()

        count = 0
        for g in self.geomList:
            if g.pathString.startswith(parentPath.pathString):
                count += 1
        if count >= 1:
            return parentPath

    def getGeomRoots(self, rootNode, geomPrim):
        roots = []
        for p in self.geomList:
            parent = self.getGeomParent(p)
            if parent:
                name = parent.name
                if name == 'Proxy' or name == 'Render':
                    parent = parent.GetParentPath()
                if roots:
                    if not parent.pathString.startswith(roots[-1].pathString + '/'):
                        if not parent in roots:
                            roots.append(parent)
                else:
                    roots.append(parent)
            else:
                roots.append(p)

        msg.debug('# Geom List')
        for p in roots:
            msg.debug('>', p)
            prim = self.stage.GetPrimAtPath(p)
            assetPath = prim.GetPrimStack()[0].layer.identifier
            msg.debug('\t assetPath :', assetPath)
            msg.debug('')

            mayaPath = p.pathString.replace(geomPrim.GetPath().pathString, '/%s' % rootNode)
            meshGrpNode = cmds.ls(mayaPath.replace('/', '|'))
            if meshGrpNode:
                parentNode = cmds.listRelatives(meshGrpNode, p=True, f=True)[0]
                cmds.delete(meshGrpNode)

                refNode = self.createReferenceNode(prim, filePath=assetPath, primPath=p)
                cmds.parent(refNode, parentNode)
                self.setXformOp(prim, refNode)


    def walk(self, prim, rootNode, skipMakeNullNode=False):
        if not skipMakeNullNode:
            nullNode = cmds.createNode('transform', n=prim.GetName())
            
            if rootNode:
                nullNode = cmds.parent(nullNode, rootNode)[0]
            self.setXformOp(prim, nullNode)
        else:
            nullNode = rootNode

        for p in prim.GetAllChildren():
            if self.IsGeom(p):
                geomType = p.GetTypeName()
                if geomType == "PointInstancer":
                    self.pointInstancer_doIt(p, nullNode)
                elif geomType != "Scope":
                    self.geomList.append(p.GetPath())
            else:
                if p.HasAuthoredSpecializes():
                    self.specializes_doIt(p, nullNode)
                elif p.HasAuthoredReferences():
                    self.references_doIt(p, nullNode)
                else:
                    self.walk(p, nullNode)

    def doIt(self):
        self.filename = cmds.getAttr('%s.filePath' % self.rootNode)
        self.stage = Usd.Stage.Open(self.filename, load=Usd.Stage.LoadAll)
        dPrim = self.stage.GetDefaultPrim()

        vsets = cmds.listAttr(self.rootNode, ud=True, st='usdVariantSet*')
        if vsets:
            for ln in vsets:
                name = ln.replace('usdVariantSet_', '')
                value = cmds.getAttr(self.rootNode + '.' + ln)
                if value:
                    vset = dPrim.GetVariantSets().GetVariantSet(name)
                    vset.SetVariantSelection(value)

        cmds.delete(self.rootNode)
        rootNode = cmds.createNode('dxBlock', n=dPrim.GetName())
        cmds.setAttr('%s.importFile' % rootNode, self.filename, type='string')
        cmds.setAttr('%s.rootPrimPath' % rootNode, '/%s' % dPrim.GetName(), type='string')

        geomPrim = self.stage.GetPrimAtPath('/%s/Geom' % dPrim.GetName())
        self.walk(geomPrim, rootNode, skipMakeNullNode=True)

        if self.geomList:
            self.geomList.sort()
            # print('> Geom List')
            # pprint.pprint(self.geomList)
            self.getGeomRoots(rootNode, geomPrim)

        cmds.select(rootNode)
        xbExtra.puraCollapsed()

