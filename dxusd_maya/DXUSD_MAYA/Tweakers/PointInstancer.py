#coding:utf-8
from __future__ import print_function
import pprint
import os

from pxr import Usd, UsdGeom, Sdf, Gf, Vt

import maya.api.OpenMaya as OpenMaya
import maya.cmds as cmds

import DXUSD.Vars as var

from DXUSD.Tweakers.Tweaker import Tweaker, ATweaker

import DXUSD_MAYA.Message as msg
import DXUSD_MAYA.MUtils as mutl
import DXUSD_MAYA.Utils as utl

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

class APointInstancer(ATweaker):
    def __init__(self, **kwargs):
        '''
        [Arguments]
        ptNodes (list): compute nodes. fullpath
        dstdir  (str) : output directory
        '''
        self.ptNodes = []

        # initialize
        ATweaker.__init__(self, **kwargs)

    def Treat(self):
        if not self.dstdir:
            msg.errmsg('Treat@%s' % self.__name__, 'no dstdir argument.')
        if not self.ptNodes:
            return var.IGNORE
        return var.SUCCESS


class PointInstancer(Tweaker):
    ARGCLASS = APointInstancer
    def DoIt(self):
        print('#### Create PointInstancer ####')
        print('ptNodes:',self.arg.ptNodes)
        for node in self.arg.ptNodes:
            if self.arg.task == 'model':
                src = node.split('|')
                self.arg.N.model.SetDecode(src[1])
                if not self.arg.lod:
                    self.arg.lod = var.T.HIGH
                if len(src) > 2:
                    self.arg.desc += '_' + src[-1]
                ofile = utl.SJoin(self.arg.dstdir, self.arg.F.GEOM)

                if cmds.nodeType(node) == 'TN_TaneTransform':
                    self.exportTane(node, ofile)
                else:
                    self.ptGeom(node, ofile)

            elif self.arg.task == 'layout':
                self.arg.N.layout.SetDecode(node)
                ofile = utl.SJoin(self.arg.dstdir, self.arg.F.GEOM)
                self.ptGeom(node, ofile)
        return var.SUCCESS

    def getGroupName(self, basename):
        name = basename.split('_')[0]
        if self.arg.task == 'layout':
            res = self.arg.N.layout.Decode(basename)
            if res.desc: name = res.desc
        return name


    def exportTane(self,node, ofile):
        cmds.TN_ExportTane(fn=ofile, nn=cmds.ls(node, dag=True, type='TN_Tane')[0])

        dstLayer = utl.AsLayer(ofile)
        dPrimPath = dstLayer.defaultPrim
        spec = dstLayer.GetPrimAtPath(dPrimPath + '/scatter')
        attrSpec = spec.properties.get('prototypes')
        editPath = []
        for i in attrSpec.targetPathList.explicitItems:
            editPath.append('/World' + str(i))
        attrSpec.targetPathList.explicitItems = editPath

        utl.GetPrimSpec(dstLayer, '/World')
        editor = Sdf.BatchNamespaceEdit()
        editor.Add('/' + dPrimPath, '/World/' + dPrimPath)
        dstLayer.Apply(editor)

        customData = {'dxusd':'2.0.0', 'sceneFile': self.arg.scene}
        utl.UpdateLayerData(dstLayer, customData).doIt()
        dstLayer.defaultPrim = 'World'

        # custom data
        spec = dstLayer.GetPrimAtPath('/World/' + dPrimPath)
        utl.AddCustomData(spec, 'groupName', self.getGroupName(dPrimPath))

        tmpfile = ofile.replace('.usd', '_tmp.usd')
        dstLayer.Export(tmpfile, args={'format': 'usdc'})
        os.remove(ofile)
        os.rename(tmpfile, ofile)

    def ptGeom(self, node, ofile):
        # reference file data
        self.RDATA = utl.GetReferenceData(node)
        refData    = self.RDATA.get()
        if not refData:
            return
        rootName = node.split('|')[-1]

        # Create Geom
        dstlyr = utl.AsLayer(ofile, create=True, clear=True)
        dstlyr.defaultPrim = 'World'
        root = utl.GetPrimSpec(dstlyr, '/World')
        root = utl.GetPrimSpec(dstlyr, root.path.AppendChild(rootName))

        customData = {'sceneFile': self.arg.scene}
        if self.arg.task == 'layout' and cmds.nodeType(node) == 'dxBlock':
            importFile = cmds.getAttr('%s.importFile' % node)
            if importFile:
                customData['importFile'] = importFile

        utl.UpdateLayerData(dstlyr, customData).doIt()

        # custom data
        # root.SetInfo('kind', 'component')
        utl.AddCustomData(root, 'groupName', self.getGroupName(node.split('|')[-1]))

        with utl.OpenStage(dstlyr) as stage:
            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)

        proto_keys = refData.keys()
        proto_keys.sort()

        pitSpec = utl.GetPrimSpec(dstlyr, root.path.AppendChild('scatter'), type='PointInstancer')
        protorel = list()
        for key in proto_keys:
            src = refData[key]
            protopath = self.AddPrototype(pitSpec, key, src)
            protorel.append(protopath)

        scales   = list()
        orients  = list()
        positions= list()
        protoIndices = list()
        ids   = list()
        index = 0
        for key, src in refData.items():
            for n in src['nodes']:
                S, O, T = mutl.getGfXform(n)
                scales.append(S)
                orients.append(O)
                positions.append(T)
                protoIndices.append(proto_keys.index(key))
                ids.append(index)
                index += 1
        utl.GetAttributeSpec(pitSpec, 'ids', ids, Sdf.ValueTypeNames.Int64Array)
        utl.GetAttributeSpec(pitSpec, 'scales', scales, Sdf.ValueTypeNames.Float3Array)
        utl.GetAttributeSpec(pitSpec, 'orientations', orients, Sdf.ValueTypeNames.QuathArray)
        utl.GetAttributeSpec(pitSpec, 'positions', positions, Sdf.ValueTypeNames.Point3fArray)
        utl.GetAttributeSpec(pitSpec, 'protoIndices', protoIndices, Sdf.ValueTypeNames.IntArray)

        if self.arg.task == 'layout':
            self.ptTimeSample(refData, dstlyr, pitSpec)

        relspec = Sdf.RelationshipSpec(pitSpec, 'prototypes', False, Sdf.VariabilityUniform)
        for t in protorel:
            relspec.targetPathList.explicitItems.append(t)

        dstlyr.Save()
        del dstlyr


    def AddPrototype(self, parent, refName, data):  # data is refData value
        '''
        parent  (Sdf.PrimSpec) :
        refName (Sdf.Path) :
        '''
        layer = parent.layer
        root  = utl.GetPrimSpec(layer, parent.path.AppendChild('Prototypes'))
        # archive source spec
        name = self.RDATA.refNameToString(refName)
        spec = utl.GetPrimSpec(layer, root.path.AppendChild(name),specifier='over')
        relpath  = utl.GetRelPath(layer.identifier, data['filePath'])
        primPath = Sdf.Path.emptyPath
        if data.has_key('primPath'):
            primPath = Sdf.Path(data['primPath'])
        utl.ReferenceAppend(spec, relpath, offset=Sdf.LayerOffset(data['offset']), clear=True)
        # variant selection
        utl.SetVariantSelections(spec, refName)
        # setup include prim
        utl.SetIncludePrim(spec, primPath, data['filePath'])
        # setup exclude prims
        utl.SetExcludePrims(spec, data)
        return spec.path

    def ptTimeSample(self, refData, dstlyr, ptSpec):
        utl.UpdateLayerData(dstlyr, self.arg.customData).doIt()
        dstlyr.startTimeCode = self.arg.frameRange[0] - 1
        dstlyr.endTimeCode = self.arg.frameRange[1] + 1

        scale_attrSpec = utl.GetAttributeSpec(ptSpec, 'scales', None, Sdf.ValueTypeNames.Float3Array)
        orient_attrSpec = utl.GetAttributeSpec(ptSpec, 'orientations', None, Sdf.ValueTypeNames.QuathArray)
        position_attrSpec = utl.GetAttributeSpec(ptSpec, 'positions', None, Sdf.ValueTypeNames.Point3fArray)

        for frame in range(self.arg.frameRange[0] - 1, self.arg.frameRange[1] + 1):
            for sample in mutl.GetFrameSample(self.arg.step):
                frameSample = frame + sample
                cmds.currentTime(frameSample)
                scales = list()
                orients = list()
                positions = list()
                for key, src in refData.items():
                    for node in src['nodes']:
                        S, O, P = mutl.getGfXform(node)
                        scales.append(S)
                        orients.append(O)
                        positions.append(P)
                dstlyr.SetTimeSample(scale_attrSpec.path, frameSample, Vt.Vec3fArray(scales))
                dstlyr.SetTimeSample(orient_attrSpec.path, frameSample, Vt.QuathArray(orients))
                dstlyr.SetTimeSample(position_attrSpec.path, frameSample, Vt.Vec3fArray(positions))
