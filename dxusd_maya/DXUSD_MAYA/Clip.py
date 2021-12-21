#coding:utf-8
from __future__ import print_function

from pxr import Sdf, Usd, UsdGeom

from DXUSD.Structures import Arguments
import DXUSD.Vars as var

import DXUSD_MAYA.Message as msg
import DXUSD_MAYA.Exporters as exp
import DXUSD_MAYA.MUtils as mutl
import DXUSD_MAYA.Utils as utl

import DXUSD_MAYA.Rig as Rig
import DXUSD_MAYA.Groom as Groom

import maya.cmds as cmds


#-------------------------------------------------------------------------------
#
#   Rig Clip
#
#-------------------------------------------------------------------------------
class RigClipExport(exp.RigClipExporter):
    def Exporting(self):
        # rig asset
        rigFile = mutl.GetReferenceFile(self.arg.node)
        if rigFile:
            msg.message('%s-rigFile :' % self.__name__, rigFile)

        # frameRange
        fr = mutl.GetFrameRange()
        self.frameSample = mutl.GetFrameSample(self.arg.step)
        self.exportRange = (fr[0] - 1, fr[1] + 1)

        self.customData = {
            'sceneFile': self.arg.scene,
            'start': fr[0], 'end': fr[1], 'step': self.arg.step,
            'rigFile': rigFile
        }

        objects = Rig.GetObjects(self.arg.node)

        rigConList, attrList = mutl.GetRigConData(self.arg.node)
        muteCtrl = None
        if rigConList:
            muteCtrl = mutl.MuteCtrl(rigConList, attrList)
            muteCtrl.getValue()
            muteCtrl.setMute()

        # HIGH GEOM
        if objects['high']:
            self.arg.lod = var.T.HIGH
            ofn = utl.SJoin(self.arg.D.TASKNVC, self.arg.F.GEOM)
            msg.debug('> GEOM FILE\t:', ofn)
            self.geomExport(ofn, objects['high'], objects['low'])
            self.arg.geomfiles.append(ofn)
        if objects['mid']:
        # MID GEOM
            self.arg.lod = var.T.MID
            ofn = utl.SJoin(self.arg.D.TASKNVC, self.arg.F.GEOM)
            msg.debug('> GEOM FILE\t:', ofn)
            self.geomExport(ofn, objects['mid'], objects['low'])
            self.arg.geomfiles.append(ofn)
        # LOW GEOM
            self.arg.lod = var.T.LOW
            ofn = utl.SJoin(self.arg.D.TASKNVC, self.arg.F.GEOM)
            msg.debug('> GEOM FILE\t:', ofn)
            self.geomExport(ofn, objects['low'], [])
            self.arg.geomfiles.append(ofn)
        # SIM GEOM
        if objects['sim']:
            ofn = utl.SJoin(self.arg.D.TASKNVC, self.arg.F.SIMGEOM)
            msg.debug('> GEOM FILE\t:', ofn)
            self.geomExport(ofn, objects['sim'], [])
            self.arg.geomfiles.append(ofn)

        if muteCtrl:
            muteCtrl.setUnMute()

    def geomExport(self, filename, renderMeshes, proxyMeshes):
        utl.SetRigPurposeAttribute(renderMeshes, proxyMeshes)
        utl.UsdExport(
            filename, renderMeshes + proxyMeshes,
            fr=self.exportRange, fs=self.frameSample, customLayerData=self.customData
        ).doIt()

    # def Tweaking(self):
    #     return var.SUCCESS
    # def Compositing(self):
    #     return var.SUCCESS


def rigExport(node=None, show=None, shot=None, version=None, overwrite=False,
              timeScales=[0.8, 1.0, 1.2], loopRange=(1001, 5000), step=1.0):
    if not node:
        node = cmds.ls(type='dxRig')[0]
    # current scene filename
    sceneFile = cmds.file(q=True, sn=True)

    arg = exp.ARigClipExporter()
    arg.scene = sceneFile
    arg.node  = node
    arg.timeScales = timeScales
    arg.loopRange  = loopRange
    arg.step = step
    arg.overwrite = overwrite

    # override
    if show: arg.ovr_show   = show
    if shot: arg.ovr_shot   = shot
    if version: arg.ovr_ver = version

    RigClipExport(arg)


def mtkRigExport(node=None, timeScales=[0.8, 1.0, 1.2], loopRange=(1001, 5000),
                 step=1.0, customdir=''):
    if not node:
        node = cmds.ls(type='dxRig')[0]
    # current scene filename
    sceneFile = cmds.file(q=True, sn=True)

    arg = exp.ARigClipExporter()
    arg.scene = sceneFile
    arg.node  = node
    arg.timeScales = timeScales
    arg.loopRange  = loopRange
    arg.step = step
    arg.customdir = customdir
    RigClipExport(arg)


#-------------------------------------------------------------------------------
#
#   Groom Clip
#
#-------------------------------------------------------------------------------
class GroomClipExport(exp.GroomClipExporter):
    def Exporting(self):
        # inputcache data
        srclyr = utl.AsLayer(self.arg.inputcache)
        srcdata= srclyr.customLayerData

        # for MTK
        if srcdata.has_key('rigFile'):
            arg = Arguments()
            arg.D.SetDecode(srcdata['rigFile'], 'SHOW')
            self.arg.org_show = arg.show

        # frameRange
        fr = (srcdata['start'], srcdata['end'])
        self.arg.frameRange = fr
        expfr = (fr[0] - 1, fr[1] + 1)
        self.arg.framesPerSecond = srclyr.framesPerSecond
        self.arg.timeCodesPerSecond = srclyr.timeCodesPerSecond

        # step
        step = srcdata.get('step')
        if step: self.arg.step = step

        # customData
        self.arg.customData = srcdata
        self.arg.customData['sceneFile'] = self.arg.scene
        self.arg.customData['inputCache'] = self.arg.inputcache

        # mesh attributes
        self.arg.bodyMeshAttrData = Groom.GetBodyMeshAttributes(self.arg.bodyMeshLayerData.keys())

        jobCmd = list()
        for index, node in enumerate(self.arg.groom_nodes):
            cmd  = '-f %s' % self.arg.groom_outs[index]
            cmd += ' -n %s' % node
            cmd += ' -ct both -mgf'
            jobCmd.append(cmd)
        msg.debug(jobCmd)
        cmds.ZN_ExportUSDCmd(j=jobCmd, startFrame=expfr[0], endFrame=expfr[1], step=self.arg.step, v=True)

        # update customLayerData
        for out in self.arg.groom_outs:
            for suffix in ['.high_geom.usd', '.low_geom.usd']:
                gfile  = out + suffix
                dstlyr = utl.AsLayer(gfile)
                utl.UpdateLayerData(dstlyr, self.arg.customData).doIt()
                dstlyr.Save()

        # collection
        rigfile = srcdata.get('rigFile')
        if not rigfile:
            msg.warning('GroomClipExport : not found rigFile')
            return
        groomfile = Groom.GetGroomFile(rigfile)
        if not groomfile:
            msg.warning('GroomClipExport : not found groomfile')
            return
        res = Arguments()
        res.D.SetDecode(utl.DirName(groomfile))
        res.nslyr = utl.BaseName(groomfile).split('.')[0]
        self.arg.groom_collection = utl.SJoin(res.D.TASKN, res.F.COLLECTION)

    # def Tweaking(self):
    #     return var.SUCCESS
    # def Compositing(self):
    #     return var.SUCCESS


def groomExport(node=None):     # depend by mergeFile
    if not node:
        node = cmds.ls(type='dxBlock')[0]
    if cmds.nodeType(node) != 'dxBlock':
        msg.error('GroomClipExport : not support this node!')

    # current scene filename
    sceneFile = cmds.file(q=True, sn=True)

    if not cmds.objExists('ZN_ExportSet'):
        msg.error('GroomClipExport : not found "ZN_ExportSet"')

    inputcache = cmds.getAttr('%s.mergeFile' % node)
    if not inputcache:
        msg.error('GroomClipExport : not found inputcache!')

    zdeforms = cmds.sets('ZN_ExportSet', q=True)

    bodyMeshLayerData = Groom.GetZennBodyMeshMap(zdeforms, root=node)
    if not bodyMeshLayerData:
        assert False, 'not found export "ZN_Deform".'

    export_grooms = []
    for shape, znodes in bodyMeshLayerData.items():
        export_grooms += znodes

    arg = exp.AGroomClipExporter()
    arg.scene = sceneFile
    arg.node  = node
    arg.inputcache  = inputcache
    arg.groom_nodes = export_grooms
    arg.bodyMeshLayerData = bodyMeshLayerData

    GroomClipExport(arg)
