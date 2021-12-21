import os, sys
import re
import json
import string

from pxr import Usd, UsdGeom, Sdf

import maya.cmds as cmds

import CacheMerge
import common as cmn

import DXUSD.Utils as utl


def GetObject(obj, root=None):
    objects = cmds.ls(obj, r=True, l=True) # r : recursive, l : long
    if root:
        for o in objects:
            if o.find(root) == 0:
                return o
    else:
        return objects[0]


#-------------------------------------------------------------------------------
class UsdImport:
    def __init__(self, filename):
        self.inputfile = filename
        self.fileInfo  = self.filenameParse()

    def filenameParse(self):
        '''
        {'SHOWDIR': xxx, 'SHOT': xxx, 'TASK': xxx, 'LAYER': xxx}
        '''
        data = dict()
        splitPath = self.inputfile.split('/')
        if 'show' in splitPath:
            data['SHOWDIR'] = string.join(splitPath[:splitPath.index('show') + 2], '/')
        if 'shot' in splitPath:
            data['SHOT'] = splitPath[splitPath.index('shot') + 2]
        if 'ani' in splitPath:
            data['TASK'] = 'ani'
            data['LAYER'] = splitPath[splitPath.index('ani') + 1]
        return data

    @staticmethod
    def GetMetadata(filename):
        '''
        :return {
            'frameRange': (start, end, fps),
            'defaultPath': <Sdf.Path>,
            'fistRoot': <Sdf.Path>,
            'primType': <str>, # 'Xform', 'Mesh', ...
            'subLayers': [abspath, ...],
        }
        '''
        rootLayer = Sdf.Layer.FindOrOpen(filename)
        assert rootLayer, '# msg : could not open -> %s' % filename

        data = {
            'frameRange': None, 'defaultPath': None, 'firstRoot': None, 'primType': None, 'subLayers': list()
        }
        stage = Usd.Stage.Open(rootLayer, load=Usd.Stage.LoadNone)
        if stage.HasAuthoredTimeCodeRange():
            data['frameRange'] = (
                stage.GetStartTimeCode(), stage.GetEndTimeCode(), stage.GetFramesPerSecond()
            )
        if stage.HasDefaultPrim():
            defaultPrim = stage.GetDefaultPrim()
            data['defaultPrim'] = defaultPrim
            data['defaultPath'] = defaultPrim.GetPath()
            data['primType']    = defaultPrim.GetTypeName()
        else:
            firstRoot = rootLayer.rootPrims[0].path
            data['firstRoot']= firstRoot
            data['primType'] = stage.GetPrimAtPath(firstRoot).GetTypeName()

        for lyr in rootLayer.subLayerPaths:
            if os.path.isabs(lyr):
                data['subLayers'].append(lyr)
            else:
                fullpath = os.path.join(os.path.dirname(filename), lyr)
                fullpath = os.path.abspath(fullpath)
                data['subLayers'].append(fullpath)
        return data

    def doIt(self):
        # read meta data
        d = UsdImport.GetMetadata(self.inputfile)
        if d['frameRange']:
            if self.inputfile.find('/ani/') > -1 or self.inputfile.find('/sim/') > -1: # is animation data
                rigGeomFile= self.getRigGeomFilename()
                blockNode  = self.importGeom(rigGeomFile)
                CacheMerge.UsdMerge(self.inputfile, [blockNode]).doIt()
        else:
            blockNode = self.importGeom(self.inputfile, d)


    def importGeom(self, filename, meta=None):
        if not meta:
            meta = UsdImport.GetMetadata(filename)

        nodes = cmds.usdImport(f=filename, shd='none')

        cmn.ImportGeomPostProcess(filename, nodes[0]).doIt()

        shortName = cmds.ls(nodes)[0]
        blockNode = cmds.createNode('dxBlock')
        cmds.parent(cmds.listRelatives(nodes, c=True, f=True), blockNode)
        cmds.delete(nodes)
        blockNode = cmds.rename(blockNode, shortName)

        # SetAttribute
        primPath = meta['defaultPath'] if meta['defaultPath'] else meta['firstRoot']
        primPath = primPath.pathString
        cmds.setAttr('%s.rootPrimPath' % blockNode, primPath, type='string')
        cmds.setAttr('%s.importFile' % blockNode, filename, type='string')
        cmds.setAttr('%s.importFile' % blockNode, l=True)

        for lyr in meta['subLayers']:
            if lyr.find('_attr.usd') > -1:
                atfile = lyr.replace('_attr.usd', '_attr.json')
                # Won't use attr.json file
                # JsonImportAttribute(atfile, blockNode)
        self.SetPrimPath(blockNode, filename)
        cmds.select(cl=True)

        return blockNode


    def getRigGeomFilename(self):
        rootLayer = Sdf.Layer.FindOrOpen(self.inputfile)
        if '/sim/' in self.inputfile:
            if rootLayer.customLayerData.has_key('rigFile'):
                rigFile = rootLayer.customLayerData['rigFile']
                return rigFile
        elif '/ani/' in self.inputfile:
            if rootLayer.customLayerData.has_key('rigFile'):
                rigFile = rootLayer.customLayerData['rigFile']
                rigRootDir = os.path.dirname(os.path.dirname(rigFile))
                rigVer = utl.BaseName(rigFile).split('.')[0]
                rigFile = os.path.join(rigRootDir, rigVer, rigRootDir.split('/')[-2] + '_rig.usd')
                return rigFile

        cmds.error('No rig subLayer >> %s'%self.inputfile)


    def SetPrimPath(self, blockNode, filename):
        root  = cmds.ls(blockNode, l=True)[0]
        stage = Usd.Stage.Open(filename)
        for p in stage.Traverse():
            primPath = p.GetPath().pathString
            splitPath= primPath.split('/')
            splitPath[1] = blockNode.split('|')[-1].split(':')[-1]
            objPathStr = string.join(splitPath, '|')
            objPath = GetObject(objPathStr, root)
            if objPath:
                if not cmds.attributeQuery('primPath', n=objPath, ex=True):
                    cmds.addAttr(objPath, ln='primPath', dt='string')
                cmds.setAttr('%s.primPath' % objPath, primPath, type='string')


def UsdImportDialog():
    fn = cmds.fileDialog2(fm=1, ff='USD (*.usd)', cap='Import USD by dxBlock')
    if not fn:
        return
    UsdImport(fn[0]).doIt()


#-------------------------------------------------------------------------------
class JsonImportAttribute:
    def __init__(self, filename, root=None):
        self.data = None
        body = json.loads(open(filename, 'r').read())
        if body.has_key('Attributes'):
            self.data = body['Attributes']

        self.root = None
        if root:
            self.root = cmds.ls(root, l=True)[0]
        self.doIt()

    def doIt(self):
        if not self.data:
            print '# Error : not found attributes data!'
            return

        for shape in self.data:
            shapePath = GetObject(shape, self.root)
            if shapePath:
                self.DelUserAttr(shapePath)
                for ln in self.data[shape]:
                    val = self.data[shape][ln]
                    self.SetAttr(shapePath, ln, val)


    def DelUserAttr(self, shape):
        attrs = cmds.listAttr(shape, ud=True)
        if attrs:
            for ln in attrs:
                cmds.deleteAttr('%s.%s' % (shape, ln))


    def SetAttr(self, shape, ln, val):
        vtype = type(val).__name__
        dtype = 'float'
        if vtype == 'int':
            dtype = 'long'
        elif vtype == 'unicode':
            dtype = 'string'
        elif vtype == 'string':
            dtype = 'string'

        # add
        if not cmds.attributeQuery(ln, n=shape, ex=True):
            if dtype == 'string':
                cmds.addAttr(shape, ln=ln, dt=dtype)
            else:
                cmds.addAttr(shape, ln=ln, at=dtype)
        # set
        if dtype == 'string':
            cmds.setAttr('%s.%s' % (shape, ln), val, type='string')
        else:
            cmds.setAttr('%s.%s' % (shape, ln), val)



#-------------------------------------------------------------------------------
def ImportPxrReferenceDialog():
    fn = cmds.fileDialog2(
        fm=1, caption='Import USD for ReferenceAssembly - Select File', okc='import'
    )
    if not fn:
        return
    ImportPxrReference(fn[0])

def ImportPxrReference(filename):
    stage = Usd.Stage.Open(filename, load=Usd.Stage.LoadNone)
    dprim = stage.GetDefaultPrim()
    defaultName = dprim.GetName()

    node = cmds.assembly(name=defaultName, type='pxrUsdReferenceAssembly')
    # cmds.connectAttr('time1.outTime', '%s.time' % node)
    cmds.setAttr('%s.filePath' % node, filename, type='string')
    cmds.assembly(node, edit=True, active='Collapsed')
    return node



#-------------------------------------------------------------------------------
def ImportPxrProxyDialog():
    fn = cmds.fileDialog2(
        fm=1, caption='Import USD for pxrProxyShape - Select File', okc='import'
    )
    if not fn:
        return
    ImportPxrProxy(fn[0])

def ImportPxrProxy(filename):
    stage = Usd.Stage.Open(filename, load=Usd.Stage.LoadNone)
    dprim = stage.GetDefaultPrim()
    dname = dprim.GetName()

    node = cmds.createNode('pxrUsdProxyShape', name='%sShape' % dname)
    cmds.connectAttr('time1.outTime', '%s.time' % node)
    cmds.setAttr('%s.filePath' % node, filename, type='string')
    return cmds.listRelatives(node, p=True)[0]
