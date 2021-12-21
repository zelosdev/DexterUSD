#coding:utf-8
from __future__ import print_function
from pxr import Sdf, Gf, Usd
import os, time, getpass, json
import math

import maya.cmds as cmds
import maya.mel as mel
import maya.api.OpenMaya as OpenMaya
import maya.api.OpenMayaAnim as OpenMayaAnim

import DXUSD.Vars as var
import DXUSD.Compositor as cmp

import DXUSD_MAYA.Message as msg
import DXUSD_MAYA.Exporters as exp
import DXUSD_MAYA.MUtils as mutl
import DXUSD_MAYA.Utils as utl


class CameraGeomExport:
    def __init__(self, filename, node, fr=[None, None], step=0.0, customLayerData=dict()):
        self.rotateOrder = {'xyz':0, 'yzx':1, 'zxy':2, 'xzy':3, 'yxz':4, 'zyx':5}
        self.radToDeg = 180.0 / math.pi

        self.filename = filename
        self.node = node
        self.camName = node.split('|')[-1]
        self.isPanzoom = False
        self.camshake = False
        if cmds.getAttr('%s.renderable' % self.node) and \
           cmds.getAttr('%s.panZoomEnabled' % self.node):
            self.camshake = True
            if cmds.getAttr('%s.renderPanZoom' % self.node):
                self.isPanzoom = True

        self.customLayerData = customLayerData.copy()
        if not self.customLayerData.has_key('sceneFile'):
            sceneFile = cmds.file(q=True, sn=True)
            if sceneFile: self.customLayerData['sceneFile'] = sceneFile

        self.isConstant = True
        if fr[0] != None and fr[1] != None:
            self.frameRange = fr
            self.step = step
            self.isConstant = False

    def doIt(self):
        outlyr = utl.AsLayer(self.filename, create=True, clear=True)
        if self.customLayerData:
                tmp = outlyr.customLayerData
                tmp.update(self.customLayerData)
                outlyr.customLayerData = tmp

        if not self.isConstant:
            fps = mel.eval('currentTimeUnitToFPS')
            outlyr.framesPerSecond    = fps
            outlyr.timeCodesPerSecond = fps

        camSpec = utl.GetPrimSpec(outlyr, '/%s' % self.camName, type='Camera')
        camSpec.SetInfo('kind', 'camera')

        outlyr.defaultPrim = self.camName
        outlyr.startTimeCode = self.frameRange[0]
        outlyr.endTimeCode = self.frameRange[1]
        tranList, rotList, frames = mutl.GetGfTransform(self.node, self.frameRange[0], self.frameRange[1])

        attrCR = Sdf.AttributeSpec(camSpec, 'clippingRange', Sdf.ValueTypeNames.Float2, Sdf.VariabilityVarying)
        self.SetAttribute(camSpec, attrCR, self.node, ['nearClipPlane', 'farClipPlane'], frames)

        attrFL = Sdf.AttributeSpec(camSpec, 'focalLength', Sdf.ValueTypeNames.Float, Sdf.VariabilityVarying)
        self.SetAttribute(camSpec, attrFL, self.node, 'focalLength', frames)

        attrFD = Sdf.AttributeSpec(camSpec, 'focusDistance', Sdf.ValueTypeNames.Float, Sdf.VariabilityVarying)
        self.SetAttribute(camSpec, attrFD, self.node, 'focusDistance', frames)

        attrFS = Sdf.AttributeSpec(camSpec, 'fStop', Sdf.ValueTypeNames.Float, Sdf.VariabilityVarying)
        self.SetAttribute(camSpec, attrFS, self.node, 'fStop', frames)

        attrHA = Sdf.AttributeSpec(camSpec, 'horizontalAperture', Sdf.ValueTypeNames.Float, Sdf.VariabilityVarying)
        self.SetAttribute(camSpec, attrHA, self.node, 'horizontalFilmAperture', frames)

        attrVA = Sdf.AttributeSpec(camSpec, 'verticalAperture', Sdf.ValueTypeNames.Float, Sdf.VariabilityVarying)
        self.SetAttribute(camSpec, attrVA, self.node, 'verticalFilmAperture', frames)

        attrXT = Sdf.AttributeSpec(camSpec, 'xformOp:translate', Sdf.ValueTypeNames.Float3, Sdf.VariabilityVarying)
        attrXO = Sdf.AttributeSpec(camSpec, 'xformOp:rotateZXY', Sdf.ValueTypeNames.Float3, Sdf.VariabilityVarying)

        for idx, frame in enumerate(frames):
            for s in mutl.GetFrameSample(self.step):
                frame = frame + s
                camSpec.layer.SetTimeSample(attrXT.path, frame, tranList[idx])
                camSpec.layer.SetTimeSample(attrXO.path, frame, rotList[idx])

        xfOrder = Sdf.AttributeSpec(camSpec, 'xformOpOrder', Sdf.ValueTypeNames.TokenArray, Sdf.VariabilityUniform)
        xfOrder.default = ['xformOp:translate', 'xformOp:rotateZXY']

        # panZoom
        if self.isPanzoom:
            attrHPan = Sdf.AttributeSpec(camSpec, 'horizontalApertureOffset', Sdf.ValueTypeNames.Float)
            self.SetAttribute(camSpec, attrHPan, self.node, 'horizontalPan', frames)

            attrVPan = Sdf.AttributeSpec(camSpec, 'verticalApertureOffset', Sdf.ValueTypeNames.Float)
            self.SetAttribute(camSpec, attrVPan, self.node, 'verticalPan', frames)

        if self.camshake:
            expPanzoom = PanZoom(self.node, frames)
            expPanzoom.exportNukeCamShake(self.filename.replace(".usd", "_shake.nk"))

        outlyr.Save()

        del outlyr

    def SetAttribute(self, primSpec, attrSpec, node, attrs, frames):
        objs = []
        if isinstance(attrs, list):
            for attr in attrs:
                objs.append('%s.%s' % (node, attr))
        else:
            objs.append('%s.%s' % (node, attrs))

        for f in frames:
            for s in mutl.GetFrameSample(self.step):
                frame = f + s
                zoom = 1.0
                values = []
                for obj in objs:
                    value = cmds.getAttr(obj, time=frame)
                    if 'Offset' in attrSpec.name:
                        value = value * 25.4
                    elif 'Aperture' in obj:
                        if self.isPanzoom:
                            zoom = cmds.getAttr('%s.zoom' % obj.split('.')[0], time=frame)
                        value = value * zoom * 25.4
                    values.append(value)
                self.SetAttrTimeSample(primSpec, attrSpec, frame, values)

    def SetAttrTimeSample(self, primSpec, spec, frame, values):
        if len(values) == 1:
            primSpec.layer.SetTimeSample(spec.path, frame, values[0])
        elif len(values) == 2:
            primSpec.layer.SetTimeSample(spec.path, frame, Gf.Vec2f(*values))
        elif len(values) == 3:
            primSpec.layer.SetTimeSample(spec.path, frame, Gf.Vec3f(*values))


class ImagePlaneExport:
    def __init__(self, filename, imagePlane, fr=[None, None], step=0.0, abcExport=False):
        self.filename = filename
        self.imagePlane = imagePlane
        self.planeName = ''
        self.polyPlane = ''
        self.abcExport = abcExport

        if fr[0] != None and fr[1] != None:
            self.frameRange = fr

        self.step = step
        self.frameSample= mutl.GetFrameSample(step)

    def doIt(self):
        planeName, polyPlane, tmpmesh = self.CreatePolyImgPlane(self.imagePlane)
        self.planeName = planeName
        self.polyPlane = polyPlane

        mtxList, self.frames = mutl.GetXformMatrix(tmpmesh, self.frameRange[0], self.frameRange[1])
        self.SetMatrix(polyPlane, mtxList, self.frames)

        cmds.select(polyPlane)
        cmds.filterCurve()

        self.geomExport()

        cmds.delete(polyPlane)
        cmds.delete(tmpmesh)

    def geomExport(self):
        utl.UsdExport(self.filename, [self.polyPlane], fr=self.frameRange, fs=self.frameSample, mergeTransformAndShape=True).doIt()
        msg.debug('> polyPlane UsdExport\t:', self.filename)
        if self.abcExport:
            abcfile = self.filename.replace('.usd', '.abc')
            mutl.AbcExport(abcfile, [self.polyPlane], fr=self.frameRange, step=self.step)
            msg.debug('> polyPlane AbcExport\t:', abcfile)

        outlyr = Sdf.Layer.FindOrOpen(self.filename)
        dprim = utl.GetDefaultPrim(outlyr)
        edit = Sdf.BatchNamespaceEdit()
        edit.Add(dprim.path, '/' + self.planeName)
        outlyr.Apply(edit)
        outlyr.defaultPrim = self.planeName
        self.setMaterial(outlyr)

        outlyr.Save()

    def setMaterial(self, outlyr):
        imgMtlFile = '/assetlib/_3d/asset/_global/material/preview/preview.usd'
        dprim = utl.GetDefaultPrim(outlyr)

        materialSpec = utl.GetPrimSpec(outlyr, dprim.path.AppendChild('preview'), type='Scope')
        utl.PayloadAppend(materialSpec, imgMtlFile)

        mtlSpec = utl.GetPrimSpec(outlyr, materialSpec.path.AppendPath('imagePlane'), specifier='over')
        imgSpec = utl.GetPrimSpec(outlyr, mtlSpec.path.AppendPath('Constant/PlateImage'), specifier='over')

        attrFile = Sdf.AttributeSpec(imgSpec, 'inputs:file', Sdf.ValueTypeNames.Asset, Sdf.VariabilityVarying)
        filename = cmds.getAttr('%s.imageName' % self.imagePlane)
        tmp = filename.split('.')

        if len(tmp) == 2:
            attrFile.default = filename
        elif len(tmp) == 3:
            if cmds.getAttr('%s.useFrameExtension' % self.imagePlane):
                for f in self.frames:
                    imgNumber = cmds.getAttr('%s.frameExtension' % self.imagePlane, time=f)
                    imgFile = '%s.%04d.%s' % (tmp[0], int(imgNumber), tmp[-1])
                    imgPath = utl.GetRelPath(outlyr.identifier, imgFile)
                    imgSpec.layer.SetTimeSample(attrFile.path, f, Sdf.AssetPath(imgPath))
            else:
                attrFile.default = filename

        # material binding
        relSpec = Sdf.RelationshipSpec(dprim, "material:binding", False, Sdf.VariabilityUniform)
        relSpec.targetPathList.explicitItems.append(mtlSpec.path)

    def CreatePolyImgPlane(self, imagePlane):
        camShape = cmds.listRelatives(imagePlane, p=True, f=True)[0]
        camTrans = cmds.listRelatives(camShape, p=True, f=True)[0]

        camName   = camTrans.split('|')[-1].split(':')[-1]
        planeName = imagePlane.split('->')[-1].split('|')[-1].split(':')[-1]

        hfa = cmds.camera(camShape, q=True, hfa=True)
        vfa = cmds.camera(camShape, q=True, vfa=True)
        fov = math.radians(cmds.camera(camShape, q=True, hfv=True))
        aspect = vfa / hfa

        pname = '%s_polyImagePlane_%s_tmp' % (camName, planeName)
        tmpPlane = cmds.polyPlane(name=pname, w=1.0, h=aspect, sx=1, sy=1, ax=(0, -1, 0), cuv=1, ch=1)[0]
        cmds.polyFlipUV(tmpPlane, ft=0)
        cmds.polyFlipUV(tmpPlane, ft=1)

        tmpPlane = cmds.parent(tmpPlane, camTrans)[0]

        expressionString = "float $hfa = `camera -q -hfa {camera}`;\n"
        expressionString += "float $vfa = `camera -q -vfa {camera}`;\n"
        expressionString += "float $fov = `camera -q -hfv {camera}`;\n"
        expressionString += "float $bbminx = {imageplane}.boundingBoxMinX;\n"
        expressionString += "float $bbmaxx = {imageplane}.boundingBoxMaxX;\n"
        expressionString += "float $bbminy = {imageplane}.boundingBoxMinY;\n"
        expressionString += "float $bbmaxy = {imageplane}.boundingBoxMaxY;\n\n"
        expressionString += "{polyplane}.scaleX = {polyplane}.scaleY = {polyplane}.scaleZ = 2*({imageplane}.depth)*(tand($fov/2.0));\n\n"
        # (offset 비율) * (imageplane boundingbox 크기)
        expressionString += "{polyplane}.translateX = ({imageplane}.offsetX / $hfa) * ($bbmaxx - $bbminx);\n"
        expressionString += "{polyplane}.translateY = ({imageplane}.offsetY / $vfa) * ($bbmaxy - $bbminy);\n"
        expressionString += "{polyplane}.translateZ = -1*{imageplane}.depth;\n"
        expressionString += "{polyplane}.rotateZ = 180 + -1*{imageplane}.rotate;\n"

        newPlaneList = list()

        depth = cmds.getAttr('%s.depth' % imagePlane) * -1.0
        cmds.setAttr('%s.rx' % tmpPlane, -90.0)
        cmds.setAttr('%s.ry' % tmpPlane, 0.0)

        imagePlaneShape = cmds.listRelatives(imagePlane, s=True, f=True, p=False)[0]
        exprString = expressionString.format(
            camera=camTrans,
            imageplane=imagePlaneShape,
            polyplane=tmpPlane
        )
        cmds.expression(s=exprString, o=tmpPlane, ae=True, uc='all')
        cmds.refresh()
        newPlane = cmds.duplicate(tmpPlane, name=tmpPlane.replace('_tmp', ''))[0]
        cmds.parent(newPlane, world=True)
        return camName + '_' + planeName, newPlane, tmpPlane

    def SetMatrix(self, node, mtxList, frmList, space=OpenMaya.MSpace.kWorld):
        size = len(frmList)
        if size == 1:
            if space == 2:  # kObject
                cmds.xform(node, m=mtxList[0], os=True)
            else:
                cmds.xform(node, m=mtxList[0], ws=True)
        else:
            # key data check
            mtxvals = list()
            for i in xrange(size):
                val = mtxList[i]
                if not val in mtxvals:
                    mtxvals.append(val)
            if len(mtxvals) == 1:
                if space == 2:
                    cmds.xform(node, m=mtxList[0], os=True)
                else:
                    cmds.xform(node, m=mtxList[0], ws=True)
                return

            dgmod = OpenMaya.MDGModifier()
            TL_list = ['translateX', 'translateY', 'translateZ', 'scaleX', 'scaleY', 'scaleZ']
            TA_list = ['rotateX', 'rotateY', 'rotateZ']

            objList = list()
            for i in TL_list:
                node_name = '%s_%s' % (node, i)
                if cmds.objExists(node_name):
                    cmds.delete(node_name)
                obj = dgmod.createNode('animCurveTL')
                dgmod.renameNode(obj, node_name)
                objList.append(obj)
            for i in TA_list:
                node_name = '%s_%s' % (node, i)
                if cmds.objExists(node_name):
                    cmds.delete(node_name)
                obj = dgmod.createNode('animCurveTA')
                dgmod.renameNode(obj, node_name)
                objList.append(obj)
            dgmod.doIt()

            keyObjList = list()
            for o in objList:
                obj = OpenMayaAnim.MFnAnimCurve()
                obj.setObject(o)
                keyObjList.append(obj)

            rotateOrder = cmds.getAttr('%s.rotateOrder' % node)

            for i in xrange(size):
                mtx  = OpenMaya.MMatrix(mtxList[i])
                tmtx = OpenMaya.MTransformationMatrix(mtx)
                mtime= OpenMaya.MTime(frmList[i], OpenMaya.MTime.uiUnit())

                tr = tmtx.translation(space)
                for x in range(3):
                    keyObjList[x].addKey(mtime, tr[x])

                sc = tmtx.scale(space)
                for x in range(3):
                    keyObjList[x+3].addKey(mtime, sc[x])

                ro = tmtx.rotation()
                ro.reorderIt(rotateOrder)
                for x in range(3):
                    keyObjList[x+6].addKey(mtime, ro[x])

            curveNames = list()
            for i in TL_list:
                index = TL_list.index(i)
                mfn   = OpenMaya.MFnDependencyNode(objList[index])
                name  = mfn.name()
                curveNames.append(name)
                cmds.connectAttr('%s.output' % name, '%s.%s' % (node, i), f=True)
            for i in TA_list:
                index = TA_list.index(i)
                mfn   = OpenMaya.MFnDependencyNode(objList[index+6])
                name  = mfn.name()
                curveNames.append(name)
                cmds.connectAttr('%s.output' % name, '%s.%s' % (node, i), f=True)

    @staticmethod
    def getImagePlaneAttributes(shapeName):
        attrs = [ 'displayMode', 'type', 'textureFilter', 'imageName',
                  'offsetX', 'offsetY', 'useFrameExtension', 'frameOffset', 'frameCache',
                  'fit', 'displayOnlyIfCurrent', 'depth', 'frameExtension',
                  'coverageX', 'coverageY', 'coverageOriginX', 'coverageOriginY',
                  'imageCenterX', 'imageCenterY', 'imageCenterZ',
                  'width', 'height', 'maintainRatio', 'alphaGain' ]

        connected = cmds.listConnections(shapeName, plugs=True, type='animCurve')
        if connected:
            for i in connected:
                plug = cmds.connectionInfo(i, dfs=True)
                if plug:
                    attrs.append(plug[0].split('.')[-1])

        data = ImagePlaneExport.attributesKeyDump(shapeName, list(set(attrs)))
        return data

    @staticmethod
    def coreKeyDump(node, attr):
        connections = cmds.listConnections('%s.%s' % (node, attr), type='animCurve', s=True, d=False) # add destination, source options
        if connections:
            result = dict()
            result['frame'] = cmds.keyframe(node, at=attr, q=True)
            result['value'] = cmds.keyframe(node, at=attr, q=True, vc=True)
            result['angle'] = cmds.keyTangent(node, at=attr, q=True, ia=True, oa=True)
            if cmds.keyTangent(node, at=attr, q=True, wt=True)[0]:
                result['weight'] = cmds.keyTangent(node, at=attr, q=True, iw=True, ow=True)
            result['infinity'] = cmds.setInfinity(node, at=attr, q=True, pri=True, poi=True)
            return result
        else:
            gv = cmds.getAttr('%s.%s' % (node, attr))
            gt = cmds.getAttr('%s.%s' % (node, attr), type=True)
            return {'value':gv, 'type':gt}

    @staticmethod
    def attributesKeyDump(node, attrs):
        result = dict()
        for ln in attrs:
            result[ln] = ImagePlaneExport.coreKeyDump(node, ln)
        return result


class DummyExport:
    def __init__(self, filename, node, fr=[None, None], step=0.0, abcExport=False):
        self.filename = filename
        self.node = node
        self.frameRange = fr
        self.frameSample = mutl.GetFrameSample(step)
        self.step = step
        self.abcExport = abcExport

    def doIt(self):
        utl.UsdExport(self.filename, [self.node], fr=self.frameRange, fs=self.frameSample).doIt()
        msg.debug('> dummy UsdExport\t:', self.filename)
        if self.abcExport:
            abcfile = self.filename.replace('.usd', '.abc')
            mutl.AbcExport(abcfile, [self.node], fr=self.frameRange, step=self.step)
            msg.debug('> dummy AbcExport\t:', abcfile)


class PanZoom:
    def __init__(self, node, frames):
        self.node  = node
        self.frames= frames

        keyData = dict()
        additiveData = dict()
        shakeData    = dict()

        shapeSourceH = cmds.listConnections(node + '.horizontalPan', s=True, d=False)
        shapeSourceV = cmds.listConnections(node + '.verticalPan', s=True, d=False)
        if shapeSourceH:
            if cmds.nodeType(shapeSourceH[0]) == 'animBlendNodeAdditive':
                shakeDataH = self.getKeyData(shapeSourceH[0], 'inputB')
                shakeDataV = self.getKeyData(shapeSourceV[0], 'inputB')
                panDataH = self.getKeyData(shapeSourceH[0], 'inputA')
                panDataV = self.getKeyData(shapeSourceV[0], 'inputA')
                zomData = self.getKeyData(node, 'zom')
                additiveData = {'hpn': panDataH, 'vpn': panDataV, 'zom': zomData}
                shakeData    = {'horizontal': shakeDataH, 'vertical': shakeDataV}

        if additiveData:
            keyData = additiveData
        else:
            keyData['hpn'] = self.getKeyData(node, 'hpn')
            keyData['vpn'] = self.getKeyData(node, 'vpn')
            keyData['zom'] = self.getKeyData(node, 'zom')

        self.keyData = keyData
        self.shakeData = shakeData

    def exportPanZoomData(self, filename, user=''):
        if self.keyData:
            body = dict()
            body["_Header"] = {"created" : time.asctime(),
                               "author" : getpass.getuser(),
                               "context" : cmds.file(q=True, sn=True)}
            body["2DPanZoom"] = self.keyData

            with open(filename, "w") as f:
                json.dump(body, f, indent = 4)

    def exportNukeCamShake(self, filename):
        hfa = cmds.getAttr('%s.hfa' % self.node)

        # Nuke Camera
        nukeNode = 'Camera {\n'
        nukeNode += '  inputs 0\n'
        # horizontalPan
        if self.shakeData.has_key('horizontal'):
            tx = '{curve'
            for index, f in enumerate(self.shakeData['horizontal']['frames']):
                # attr = panzoomShakeAttr.get('attr', '.hpn')
                value = self.shakeData['horizontal']['value'][index]
                tx += ' x%d' % f
                tx += ' %.8f' % (value / hfa * 2)
            tx += '}'
        else:
            value = cmds.getAttr(self.node + '.hpn')
            tx = '%.8f' % (value / hfa * 2)
        # verticalPan
        if self.shakeData.has_key('vertical'):
            ty = '{curve'
            for index, f in enumerate(self.shakeData['vertical']['frames']):
                # attr = panzoomShakeAttr.get('attr', '.vpn')
                value = self.shakeData['vertical']['value'][index]
                ty += ' x%d' % f
                ty += ' %.8f' % (value / hfa * 2)
            ty += '}'
        else:
            value = cmds.getAttr(self.node + '.vpn')
            ty = '%.8f' % (value / hfa * 2)
        nukeNode += '  win_translate {%s %s}\n' % (tx, ty)
        # zoom
        sc = '%.8f' % cmds.getAttr('%s.zom' % self.node)

        nukeNode += '  win_scale {%s %s}\n' % (sc, sc)
        nukeNode += '  name {0}_Shake\n'.format(self.node)
        nukeNode += '}\n'

        f = open(filename, "w")
        f.write(nukeNode)
        f.close()

    def exportNuke2DPanZoom(self, filename, user=''):
        cameraName = self.node
        hfa = cmds.getAttr('%s.hfa' % self.node)

        # Nuke Camera
        nukeNode = 'Camera {\n'
        nukeNode += '  inputs 0\n'

        # horizontalPan
        connections = cmds.listConnections('%s.hpn' % self.node, type='animCurve')
        if connections:
            tx = '{curve'
            for f in self.frames:
                value = cmds.getAttr('%s.hpn' % self.node, t=f)
                tx += ' x%d' % f
                tx += ' %.8f' % (value / hfa * 2)
            tx += '}'
        else:
            value = cmds.getAttr('%s.hpn' % self.node)
            tx = '%.8f' % (value / hfa * 2)

        # verticalPan
        connections = cmds.listConnections('%s.vpn' % self.node, type='animCurve')
        if connections:
            ty = '{curve'
            for f in self.frames:
                value = cmds.getAttr('%s.vpn' % self.node, t=f)
                ty += ' x%d' % f
                ty += ' %.8f' % (value / hfa * 2)
            ty += '}'
        else:
            value = cmds.getAttr('%s.vpn' % self.node)
            ty = '%.8f' % (value / hfa * 2)

        nukeNode += '  win_translate {%s %s}\n' % (tx, ty)

        # zoom
        connections = cmds.listConnections('%s.zom' % self.node, type='animCurve')
        if connections:
            sc = '{curve'
            for f in self.frames:
                value = cmds.getAttr('%s.zom' % self.node, t=f)
                sc += ' x%d' % f
                sc += ' %.8f' % value
            sc += '}'
        else:
            sc = '%.8f' % cmds.getAttr('%s.zom' % self.node)

        nukeNode += '  win_scale {%s %s}\n' % (sc, sc)

        nukeNode += '  name %s_2DPanZoom\n' % cameraName
        nukeNode += '}\n'

        f = open(filename, "w")
        f.write(nukeNode)
        f.close()

    def getKeyData(self, node, attr):
        data = {'frames': list(), 'value': list(), 'infinity': ['constant', 'constant']}
        # time wrap
        timeWrap = cmds.listConnections('time1', d=False, s=True)
        for f in self.frames:
            wrapframe = f
            if timeWrap:
                wrapframe = cmds.getAttr('%s.output' % timeWrap[0], time=f)
            value = cmds.getAttr(node + '.' + attr, t=wrapframe)
            data['frames'].append(f)
            data['value'].append(value)
        return data


class CameraCompositor(exp.CameraExporter):
    def Exporting(self):
        return var.SUCCESS

    def Tweaking(self):
        return var.SUCCESS


#-------------------------------------------------------------------------------
#
#   Shot Camera Export
#
#-------------------------------------------------------------------------------
class CameraExport(exp.CameraExporter):
    def Exporting(self):
        abcExport = self.arg.abcExport
        frameRange = self.arg.frameRange
        self.impAttrs = dict()

        for i in range(len(self.arg.nodes)):
            node = self.arg.nodes[i]
            camName = node.split('|')[-1]
            camfile = self.arg.geomfiles[i]
            msg.debug('> node\t\t:', node)
            msg.debug('> camName\t:', camName)
            msg.debug('> camfile\t:', camfile)

            if cmds.getAttr('%s.renderable' % node):
                if not camName in self.arg.maincam:
                    self.arg.maincam.append(camName)

            if '_left' in node or '_right' in node:
                self.arg.isStereo = True

            if cmds.fileInfo("overscan_value", query=True):
                self.arg.isOverscan = True
                self.arg.overscanValue = cmds.fileInfo("overscan_value", query=True)[0]

            self.customLayerData = {
                'sceneFile': self.arg.scene,
                'start': self.arg.frameRange[0],
                'end': self.arg.frameRange[1],
                'step': self.arg.step
            }

            # show-isolate mode on
            if not cmds.about(batch=True):
                for panName in cmds.getPanel(all=True):
                    if 'modelPanel' in panName:
                        cmds.isolateSelect(panName, state=1)

            # export camera geom
            expfr = [frameRange[0]-1,  frameRange[1]+1]
            CameraGeomExport(camfile, node, fr=expfr, step=self.arg.step,
                             customLayerData=self.customLayerData).doIt()

            # export imageplanes geom
            shape = cmds.ls(node, dag=True, type='camera', l=True)[0]
            imagePlanes = cmds.listConnections(shape, type='imagePlane', d=False)
            if imagePlanes:
                for imgplane in list(set(imagePlanes)):
                    msg.debug('> imgplane\t:', imgplane)
                    impGeom = utl.SJoin(self.arg.dstdir, '%s.imp.usd' % camName)
                    ImagePlaneExport(impGeom, imgplane, fr=expfr, step=self.arg.step, abcExport=abcExport).doIt()
                    self.arg.imgPlanefiles.append(impGeom)

                    attr = ImagePlaneExport.getImagePlaneAttributes(imgplane)
                    if attr:
                        name = shape.split('|')[-1].split(':')[-1]
                        if not self.impAttrs.has_key(name):
                            self.impAttrs[name] = dict()
                        self.impAttrs[name][imgplane.split(':')[-1]] = attr

            # export dummy geom
            for dxnode in self.arg.dxnodes:
                camGeo = [i for i in cmds.listRelatives(dxnode, f=True) if i.endswith('cam_geo')]
                camLoc = [i for i in cmds.listRelatives(dxnode, f=True) if i.endswith('cam_loc')]
                assetGeo = [i for i in cmds.listRelatives(dxnode, f=True) if (i.endswith('_geo') and not (i.endswith('cam_geo')))]
                assetLoc = [i for i in cmds.listRelatives(dxnode, f=True) if (i.endswith('_loc') and not (i.endswith('cam_loc')))]

                self.arg.dummyfiles[dxnode] = []
                self.arg.dummyAbc[dxnode] = []
                if camGeo:
                    camgeoName = camGeo[0].split('|')[-1].split(':')[-1]
                    camgeoFile = utl.SJoin(self.arg.dstdir, '{NAME}.geom.usd'.format(NAME=dxnode))
                    DummyExport(camgeoFile, camGeo[0], abcExport=abcExport).doIt()
                    self.arg.dummyfiles[dxnode].append(camgeoFile)

                if camLoc:
                    camlocName = camLoc[0].split('|')[-1].split(':')[-1]
                    camlocFile = utl.SJoin(self.arg.dstdir, '{NAME}.loc.abc'.format(NAME=dxnode))
                    if abcExport:
                        mutl.AbcExport(camlocFile, [camLoc[0]])
                        self.arg.dummyAbc[dxnode].append(camlocFile)

                for ageo in assetGeo:
                    ageoName = ageo.split('|')[-1].split(':')[-1].replace('_geo', '')
                    ageoFile = utl.SJoin(self.arg.dstdir, '{NAME}.geom.usd'.format(NAME=ageoName))
                    DummyExport(ageoFile, ageo, fr=frameRange, step=self.arg.step, abcExport=abcExport).doIt()
                    self.arg.dummyfiles[dxnode].append(ageoFile)

                for alog in assetLoc:
                    alogName = alog.split('|')[-1].split(':')[-1].replace('_loc', '')
                    alogFile = utl.SJoin(self.arg.dstdir, '{NAME}.loc.abc'.format(NAME=alogName))
                    if abcExport:
                        mutl.AbcExport(alogFile, [alog], fr=frameRange, step=self.arg.step)
                        self.arg.dummyAbc[dxnode].append(alogFile)

            # show-isolate mode off
            if not cmds.about(batch=True):
                for panName in cmds.getPanel(all=True):
                    if 'modelPanel' in panName:
                        cmds.isolateSelect(panName, state=0)

        # imageplane export attr json
        if self.impAttrs:
            file = utl.SJoin(self.arg.dstdir, '%s_%s.imp.json' % (self.arg.seq, self.arg.shot))
            self.arg.impAttrfile = file

            f = open(file, 'w')
            json.dump({'ImagePlane': self.impAttrs}, f, indent=4)
            f.close()

        newScenes = '%s_%s_%s_camera_%s.mb' % (self.arg.seq, self.arg.shot, self.arg.desc, self.arg.ver)
        self.arg.pubScene = utl.SJoin(utl.DirName(self.arg.dstdir), 'scenes', newScenes)
        cmds.select(self.arg.dxnodes)
        if not os.path.exists(os.path.dirname(self.arg.pubScene)):
            os.mkdir(os.path.dirname(self.arg.pubScene))
        msg.debug('> Save As maya scene\t:', self.arg.pubScene)
        cmds.file(self.arg.pubScene, pr=True, typ='mayaBinary', options='v=0;', es=True, f=True)
        cmds.file(rn=self.arg.pubScene)
        cmds.file(s=1)
        cmds.select(cl=True)
        # File Mode Change (only read)
        # os.chmod(pubSceneFile, 0555)

    def Compositing(self):
        return var.SUCCESS


#-------------------------------------------------------------------------------
#
#   Asset Camera Export
#
#-------------------------------------------------------------------------------
class CameraExportAsset(exp.CameraExporterAsset):
    def Exporting(self):
        for i in range(len(self.arg.nodes)):
            node = self.arg.nodes[i]
            camName = node.split('|')[-1]
            camfile = self.arg.geomfiles[i]
            msg.debug('> node\t\t:', node)
            msg.debug('> camName\t:', camName)
            msg.debug('> camfile\t:', camfile)

            if cmds.getAttr('%s.renderable' % node):
                if not camName in self.arg.maincam:
                    self.arg.maincam.append(node)

            # show-isolate mode on
            if not cmds.about(batch=True):
                for panName in cmds.getPanel(all=True):
                    if 'modelPanel' in panName:
                        cmds.isolateSelect(panName, state=1)

            # export camera geom
            CameraGeomExport(camfile, node, fr=self.arg.frameRange).doIt()

            # show-isolate mode off
            if not cmds.about(batch=True):
                for panName in cmds.getPanel(all=True):
                    if 'modelPanel' in panName:
                        cmds.isolateSelect(panName, state=0)

    def Compositing(self):
        cmp.Composite(self.arg.master).DoIt()
        return var.SUCCESS

def getCamNodes(dxNodes):
    nodes = []
    for dxcam in dxNodes:
        if cmds.nodeType(dxcam) == 'dxCamera':
            cShapes = cmds.listRelatives(dxcam, type="camera", f=True, ad=True)
            for shape in cShapes:
                cam = cmds.listRelatives(shape, p=True, f=True)[0]
                if not cam in nodes:
                    nodes.append(cam)
        # else:
        #     nodes.append(cmds.listRelatives(dxcam, p=True, f=True)[0])
    if not nodes:
        msg.error('have to select group node.')
    else:
        return nodes


def cameraExportAsset(dxNodes=[], overwrite=False, show=None, seq=None, shot=None,
                      version=None, user='anonymous', fr=[1, 1]):
    if not dxNodes:
        dxNodes = cmds.ls(type='dxCamera')

    sceneFile = cmds.file(q=True, sn=True)
    for dxnode in dxNodes:
        arg = exp.ACameraExporterAsset()
        nodes = getCamNodes([dxnode])
        arg.scene = sceneFile
        arg.dxnodes = [dxnode]
        arg.nodes = nodes
        arg.overwrite = overwrite

        # override
        if show: arg.ovr_show = show
        if seq: arg.ovr_seq = seq
        if shot: arg.ovr_shot = shot
        if version: arg.ovr_ver = version
        if fr != [0, 0]:
            arg.frameRange = fr

        CameraExportAsset(arg)


def cameraExport(dxNodes=[], abcExport=True, overwrite=False,
                 show=None, seq=None, shot=None, version=None, user='anonymous', fr=[0, 0], step=0.0, process='geom'):
    if not dxNodes:
        dxNodes = cmds.ls(type='dxCamera')
    nodes = getCamNodes(dxNodes)

    sceneFile = cmds.file(q=True, sn=True)
    arg = exp.ACameraExporter()
    arg.scene = sceneFile
    arg.dxnodes = dxNodes
    arg.nodes = nodes
    arg.maincam = []
    arg.frameRange = mutl.GetFrameRange()
    arg.overwrite = overwrite
    arg.abcExport = abcExport
    arg.isStereo = False
    arg.isOverscan = False
    arg.step = step

    # override
    if show: arg.ovr_show = show
    if seq: arg.ovr_seq = seq
    if shot: arg.ovr_shot = shot
    if version: arg.ovr_ver = version
    if fr != [0, 0]:
        arg.frameRange = fr
        arg.autofr = False

    if process == 'both':
        CameraExport(arg)
        arg.overwrite = True
        CameraCompositor(arg)
    else:
        if process == 'geom':
            CameraExport(arg)
        else:
            arg.overwrite = True
            CameraCompositor(arg)
