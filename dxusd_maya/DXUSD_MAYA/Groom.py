#coding:utf-8
from __future__ import print_function

from pxr import Sdf, Usd, UsdGeom

from DXUSD.Structures import Arguments
import DXUSD.Vars as var

import maya.cmds as cmds
import maya.mel as mel

import DXUSD_MAYA.Message as msg
import DXUSD_MAYA.Exporters as exp
import DXUSD_MAYA.MUtils as mutl
import DXUSD_MAYA.Utils as utl

import os
import glob
import shutil
import sys


def GetZennBodyMeshMap(nodes, root=None):
    if root:
        root = cmds.ls(root, l=True)[0]
    result = dict()     # {meshape: [ZN_Deform, ...]}
    for z in nodes:
        connected = cmds.listHistory(z, bf=True)
        for n in connected:
            if cmds.nodeType(n) == 'ZN_Import':
                shapes = cmds.listConnections('%s.inBodyMesh' % n)
                if shapes:
                    fullpath = cmds.ls(shapes, dag=True, type='surfaceShape', l=True, ni=True)[0]
                    if root:
                        if fullpath.startswith(root):
                            if not result.has_key(fullpath):
                                result[fullpath] = list()
                            result[fullpath].append(z)
                    else:
                        if not result.has_key(fullpath):
                            result[fullpath] = list()
                        result[fullpath].append(z)
                    break
    return result

def GetBodyMeshAttributes(nodes):
    result = {}
    for n in nodes:
        data = {}
        for ln in [var.T.TXBASEPATH, var.T.TXLAYERNAME, var.T.MODELVER]:
            if cmds.attributeQuery(ln, n=n, ex=True):
                val = cmds.getAttr('%s.%s' % (n, ln))
                if ln == var.T.TXLAYERNAME:
                    val += '_ZN'
                data[ln] = val
        result[n] = data
    return result


# ZN_Import initialize for batchmode
def ZN_Initialize(nodes):
    for z in nodes:
        for n in cmds.listHistory(z):
            if cmds.nodeType(n) == 'ZN_Import':
                restTime = cmds.getAttr('%s.restTime' % n)
                cmds.currentTime(restTime)
                cmds.setAttr('%s.updateMesh' % n, 1)
        cmds.dgeval(z)

class ZN_SourceImage:
    def __init__(self, znodes):
        self.DATA = dict()  # {"node.ln": val, ...}

        for z in znodes:
            for n in cmds.listHistory(z):
                if cmds.nodeType(n).startswith('ZN_'):
                    self.queryAttr(n)
        for z in cmds.ls(type='ZN_StrandsViewer'):
            self.queryAttr(z)

    def queryAttr(self, node):
        for ln in cmds.listAttr(node):
            if 'Map' in ln or 'file' in ln:
                attr = node + '.' + ln
                val  = cmds.getAttr(attr)
                if val:
                    self.DATA[attr] = val

    def reset(self):
        for attr, val in self.DATA.items():
            cmds.setAttr(attr, val, type='string')

    def set(self, sceneFile):
        msg.debug(' ZN_SourceImage to :', sceneFile)
        baseName = utl.BaseName(sceneFile).split('.')[0]
        texDir   = utl.SJoin(utl.DirName(sceneFile), 'sourceimages', baseName)
        if not os.path.exists(texDir):
            os.makedirs(texDir)

        for attr, val in self.DATA.items():
            val = val.replace('/mach/show', '/show')
            newpath = utl.SJoin(texDir, utl.BaseName(val))
            newpath = newpath.replace('/mach/show', '/show')
            if val != newpath:
                msg.debug(' source image copy to :', newpath)
                shutil.copy(val, newpath)
            cmds.setAttr(attr, newpath, type='string')

def GetGroomFile(rigFile, variant=None):    # rigFile is *.usd or *.mb
    msg.debug('Groom.GetGroomFile >>> rigFile :', rigFile)
    arg = Arguments()
    arg.D.SetDecode(utl.DirName(rigFile))
    arg.task = 'groom'
    if variant and arg.asset != variant:
        arg.branch = variant
    gmaster = utl.SJoin(arg.D.TASK, arg.F.TASK)
    srclyr  = utl.AsLayer(gmaster)
    if not srclyr:
        msg.debug('Groom.GetGroomFile >>> not found groom :', gmaster)
        return

    if rigFile.split('.')[-1] == 'usd':
        rig_version = arg.nslyr
    else:
        rig_version = utl.BaseName(rigFile).split('.')[0]

    primPath = Sdf.Path('/' + srclyr.defaultPrim)
    primPath = primPath.AppendVariantSelection(var.T.VAR_RIGVER, rig_version)
    spec = srclyr.GetPrimAtPath(primPath)
    if not spec:
        msg.debug('Groom.GetGroomFile >>> not found prim :', primPath.pathString)
        return

    gfile = None
    vsetSpec = spec.variantSets.get(var.T.VAR_GROOMVER)
    if vsetSpec:
        data = vsetSpec.variants
        vers = data.keys()
        vers.sort()
        gfile = utl.SJoin(arg.D.TASK, 'scenes', vers[-1] + '.mb')
        arg.nslyr = vers[-1]

    # Find MasterFile
    gvmaster = utl.SJoin(arg.D.TASKN, arg.F.MASTER)
    msg.debug(gvmaster)
    gvlyr = utl.AsLayer(gvmaster)

    if gvlyr.customLayerData.has_key('sceneFile') and gvlyr.customLayerData['sceneFile'].endswith('.hip'):
        gfile = gvlyr.customLayerData['sceneFile']

    if gfile:
        msg.debug('Groom.GetGroomFile >>> Find groom file :', gfile)
        if os.path.exists(arg.D.TASKN):
            return gfile
        else:
            msg.warning('Groom.GetGroomFile >>> Find Groom USD. But not exists file :', arg.D.TASKN)


#-------------------------------------------------------------------------------
#
#   Groom Asset
#
#-------------------------------------------------------------------------------
class GroomAssetExport(exp.GroomAssetExporter):
    def Exporting(self):
        if self.arg.node:
            self.arg.rigFile = cmds.getAttr('%s.importFile' % self.arg.node)
        else:
            self.arg.rigFile = ''
        self.arg.customData = {'sceneFile': self.arg.scene, 'rigFile': self.arg.rigFile}

        # mesh attributes
        self.arg.bodyMeshAttrData = GetBodyMeshAttributes(self.arg.bodyMeshLayerData.keys())

        # groom node attributes
        for n in self.arg.groom_nodes:
            if cmds.attributeQuery('MaterialSet', n=n, ex=True):
                mtlname = cmds.getAttr('%s.MaterialSet' % n)
                if mtlname:
                    if not self.arg.groomAttrData.has_key(n):
                        self.arg.groomAttrData[n] = dict()
                    self.arg.groomAttrData[n][var.T.ATTR_MATERIALSET] = {'value': mtlname, 'type': Sdf.ValueTypeNames.String}

        jobCmd = list()
        for i in range(len(self.arg.groom_nodes)):
            command = '-f %s' % self.arg.groom_outs[i]
            command+= ' -n %s' % self.arg.groom_nodes[i]
            command+= ' -ct both -mgf'
            jobCmd.append(command)

        frame = cmds.currentTime(q=True)
        cmds.ZN_ExportUSDCmd(j=jobCmd, startFrame=frame, endFrame=frame, v=True)

        # update customLayerData
        for out in self.arg.groom_outs:
            for suffix in ['.high_geom.usd', '.low_geom.usd']:
                gfile  = out + suffix
                dstlyr = utl.AsLayer(gfile)
                utl.UpdateLayerData(dstlyr, self.arg.customData).doIt()
                dstlyr.Save()

        # Groom Asset Scene Copy
        if self.arg.customdir:
            if not 'assetlib/_3d' in  self.arg.customdir:
                return
        pubSceneFile = utl.SJoin(utl.DirName(self.arg.dstdir), 'scenes', utl.BaseName(self.arg.scene))
        msg.debug(' Groom Scene :', pubSceneFile)
        IMG = ZN_SourceImage(self.arg.groom_nodes)
        IMG.set(pubSceneFile)
        currentFile = cmds.file(save=True)
        # Copy pubSceneFile
        if os.path.exists(pubSceneFile):
            os.remove(pubSceneFile)
        shutil.copy(currentFile, pubSceneFile)
        os.chmod(pubSceneFile, 0555)
        IMG.reset()
        cmds.file(save=True)

    # def Tweaking(self):
    #     return var.SUCCESS
    # def Compositing(self):
    #     return var.SUCCESS


def assetExport(node=None, show=None, shot=None):
    if not node:
        return '# message : select node.'
    if cmds.nodeType(node) != 'dxBlock':
        assert False, 'node type error.'
    if not cmds.objExists('ZN_ExportSet'):
        assert False, 'not exists "ZN_ExportSet".'

    zdeforms = cmds.sets('ZN_ExportSet', q=True)

    bodyMeshLayerData = GetZennBodyMeshMap(zdeforms, root=node)
    if not bodyMeshLayerData:
        assert False, 'not found export "ZN_Deform".'

    export_grooms = []
    for shape, znodes in bodyMeshLayerData.items():
        export_grooms += znodes

    # current scene filename
    sceneFile = cmds.file(q=True, sn=True)

    arg = exp.AGroomAssetExporter()
    arg.scene = sceneFile
    arg.node  = node
    # arg.node  = nodeName.replace('_rig_', '_ZN_')
    arg.bodyMeshLayerData = bodyMeshLayerData
    arg.groom_nodes = export_grooms

    # override
    if show: arg.ovr_show = show
    if shot: arg.ovr_shot = shot

    GroomAssetExport(arg)


def mtkExport(node=None, customdir=None):
    # if not node:
    #     return '# message : not found node. skip groom export.'
    # if cmds.nodeType(node) != 'dxBlock':
    #     assert False, 'node type error.'
    if not cmds.objExists('ZN_ExportSet'):
        return '# message : not found "ZN_ExportSet". skip groom export.'

    zdeforms = cmds.sets('ZN_ExportSet', q=True)

    bodyMeshLayerData = GetZennBodyMeshMap(zdeforms, root=node)
    if not bodyMeshLayerData:
        assert False, 'not found export "ZN_Deform".'

    export_grooms = []
    selList = cmds.ls(sl=True, type='ZN_Deform') + cmds.ls(sl=True, type='ZN_FeatherInstance')

    if not selList:
        for shape, znodes in bodyMeshLayerData.items():
            export_grooms += znodes
    else:
        for shape, znodes in bodyMeshLayerData.items():
            for znode in znodes:
                if znode in selList:
                    export_grooms.append(znode)

    # current scene file
    sceneFile = cmds.file(q=True, sn=True)

    arg = exp.AGroomAssetExporter()
    arg.scene = sceneFile
    if cmds.nodeType(node) == 'dxBlock':
        arg.node  = node
    else:
        arg.mtkNode = node
    arg.bodyMeshLayerData = bodyMeshLayerData
    arg.groom_nodes = export_grooms
    arg.customdir   = customdir

    GroomAssetExport(arg)


#-------------------------------------------------------------------------------
#
#   Groom Shot
#
#-------------------------------------------------------------------------------
class GroomShotGeomExport(exp.GroomShotExporter):
    def mergeCache(self):
        import dxBlockUtils
        if not self.arg.rigNode and self.arg.inputcache:
            xBlockImport = dxBlockUtils.UsdImport(self.arg.inputcache)
            rigGeomFile  = xBlockImport.getRigGeomFilename()
            xBlockNode   = xBlockImport.importGeom(rigGeomFile)
            for destMesh in self.arg.bodyMeshMap:
                mutl.ConnectBlendShape(destination=destMesh, sourceroot=xBlockNode).doIt()
        else:
            self.arg.inputRigFile = cmds.getAttr('%s.importFile' % self.arg.rigNode)

        if not self.arg.inputcache: # hairSim
            self.arg.inputcache = cmds.getAttr('%s.mergeFile' % self.arg.rigNode)

            if not self.arg.inputcache:
                msg.error('not found animation cache')

        dxBlockUtils.CacheMerge.UsdMerge(self.arg.inputcache, [self.arg.rigNode]).doIt()


    def MergeExport(self):
        srclyr  = utl.AsLayer(self.arg.inputcache)
        srcdata = srclyr.customLayerData
        rigFile = srcdata.get('rigFile')
        if not rigFile:
            return var.FAILED

        if not self.arg.groomfile:
            self.arg.groomfile = GetGroomFile(rigFile)
        if not self.arg.groomfile:
            return var.FAILED

        # frameRange
        fr = (srcdata['start'], srcdata['end'])
        if self.arg.frameRange != [0, 0]:
            fr = self.arg.frameRange
        if self.arg.exportRange == [0, 0]:
            self.arg.exportRange= (fr[0] - 1, fr[1] + 1)
        msg.debug('ExportRange :', self.arg.exportRange)

        # step
        step = srcdata.get('step')
        if step: self.arg.step = step

        # File Open
        cmds.file(self.arg.groomfile, o=True, f=True)

        # set fps
        mutl.SetFPS(srclyr.framesPerSecond)

        # Rig Check
        self.arg.rigNode = cmds.ls(type='dxBlock', l=True)[0]

        zdeforms = cmds.sets('ZN_ExportSet', q=True)
        if not zdeforms:
            msg.errorQuit('GroomExporter.MergeExport()', 'not found "ZN_Deform" nodes in %s' % self.arg.groomfile)

        # groom_nodes
        self.arg.bodyMeshLayerData = GetZennBodyMeshMap(zdeforms, root=self.arg.rigNode)
        for shape, znodes in self.arg.bodyMeshLayerData.items():
            self.arg.groom_nodes += znodes

        for s in self.arg.groom_nodes:
            self.arg.subdir = s
            self.arg.groom_outs.append(utl.SJoin(self.arg.D.TASKNVS, self.arg.subdir))

        # initialize ZN_Import
        ZN_Initialize(self.arg.groom_nodes)

        self.mergeCache()

        # Walking pre-frame
        startTime = int(cmds.currentTime(q=True))
        for i in range(startTime, self.arg.exportRange[0]):
            cmds.currentTime(i)

        # Make ZN_ExportSet Command
        jobCmd = list()
        for index, node in enumerate(self.arg.groom_nodes):
            cmd  = '-f %s' % self.arg.groom_outs[index]
            cmd += ' -n %s' % node
            if self.arg.mergeCache:
                cmd += ' -ct both -mgf'
            else:
                cmd += ' -ct dynamic'
            jobCmd.append(cmd)

        msg.debug(jobCmd)
        cmds.ZN_ExportUSDCmd(j=jobCmd, startFrame=self.arg.exportRange[0], endFrame=self.arg.exportRange[1], step=self.arg.step, v=True)

        return var.SUCCESS


    def SceneExport(self):
        if not self.arg.groomfile:
            return var.FAILED

        if self.arg.frameRange != [0, 0]:
            fr = self.arg.frameRange
        if self.arg.exportRange == [0, 0]:
            self.arg.exportRange = (fr[0] - 1, fr[1] + 1)
        msg.debug('ExportRange :', self.arg.exportRange)

        # File Open
        cmds.file(self.arg.groomfile, o=True, f=True)

        # set fps
        fps = mel.eval('currentTimeUnitToFPS')
        self.arg.framesPerSecond = fps
        self.arg.timeCodesPerSecond = fps

        # Rig Check
        self.arg.rigNode = cmds.ls(type='dxBlock', l=True)[0]
        nslyr = cmds.getAttr('%s.nsLayer' % self.arg.rigNode)
        self.arg.nslyr = nslyr
        self.arg.inputcache = cmds.getAttr('%s.mergeFile' % self.arg.rigNode)
        self.arg.inputRigFile = cmds.getAttr('%s.importFile' % self.arg.rigNode)

        zdeforms = cmds.sets('ZN_ExportSet', q=True)
        if not zdeforms:
            msg.errorQuit('GroomExporter.MergeExport()', 'not found "ZN_Deform" nodes in %s' % self.arg.groomfile)

        # groom_nodes
        self.arg.bodyMeshLayerData = GetZennBodyMeshMap(zdeforms, root=self.arg.rigNode)
        for shape, znodes in self.arg.bodyMeshLayerData.items():
            self.arg.groom_nodes += znodes

        for s in self.arg.groom_nodes:
            self.arg.subdir = s
            self.arg.groom_outs.append(utl.SJoin(self.arg.D.TASKNVS, self.arg.subdir))

        # initialize ZN_Import
        ZN_Initialize(self.arg.groom_nodes)

        # Walking pre-frame
        startTime = int(cmds.currentTime(q=True))
        for i in range(startTime, self.arg.exportRange[0]):
            cmds.currentTime(i)

        # Make ZN_ExportSet Command
        jobCmd = list()
        for index, node in enumerate(self.arg.groom_nodes):
            cmd = '-f %s' % self.arg.groom_outs[index]
            cmd += ' -n %s' % node
            if self.arg.mergeCache:
                cmd += ' -ct both -mgf'
            else:
                cmd += ' -ct dynamic'
            jobCmd.append(cmd)

        msg.debug(jobCmd)
        cmds.ZN_ExportUSDCmd(j=jobCmd, startFrame=self.arg.exportRange[0], endFrame=self.arg.exportRange[1],
                             step=self.arg.step, v=True)

        return var.SUCCESS


    def Exporting(self):
        msg.warning(self.arg.nsver)
        # CacheMerge Process
        if self.arg.inputcache:
            res = self.MergeExport()
            if res != var.SUCCESS:
                return res
        # hairSim Process
        else:
            self.SceneExport()


    def Arguing(self):
        # msg.warning(self.arg.nsver)
        return var.SUCCESS
    def Tweaking(self):
        return var.SUCCESS
    def Compositing(self):
        return var.SUCCESS


class GroomShotCompositor(exp.GroomShotExporter):
    def DataCollapsed(self):
        msg.debug('DataCollapsed')
        geomfiles = list()
        for index, node in enumerate(self.arg.groom_nodes):
            gfn = self.arg.groom_outs[index]
            # high
            srcfile = gfn + '.high_geom.*.usd'
            highfile = gfn + '.high_geom.usd'
            frameFiles = utl.GetPerFrameFiles(srcfile, self.arg.exportRange)
            utl.CoalesceFiles(frameFiles, self.arg.exportRange, step=self.arg.step, outFile=highfile)
            geomfiles.append(highfile)
            # low
            srcfile = gfn + '.low_geom.*.usd'
            lowfile = gfn + '.low_geom.usd'
            frameFiles = utl.GetPerFrameFiles(srcfile, self.arg.exportRange)
            utl.CoalesceFiles(frameFiles, self.arg.exportRange, step=self.arg.step, outFile=lowfile)
            geomfiles.append(lowfile)
        # update customLayerData
        for f in geomfiles:
            dstlyr = utl.AsLayer(f)
            utl.UpdateLayerData(dstlyr, self.arg.customData).doIt()
            if 'framesPerSecond' in self.arg:
                dstlyr.framesPerSecond = self.arg.framesPerSecond
            if 'timeCodesPerSecond' in self.arg:
                dstlyr.timeCodesPerSecond = self.arg.timeCodesPerSecond
            dstlyr.Save()


    def MergeExport(self):
        srclyr  = utl.AsLayer(self.arg.inputcache)
        srcdata = srclyr.customLayerData
        rigFile = srcdata.get('rigFile')
        if not rigFile:
            return var.FAILED

        if not self.arg.groomfile:
            self.arg.groomfile = GetGroomFile(rigFile)
        if not self.arg.groomfile:
            return var.FAILED

        # File Open
        cmds.file(self.arg.groomfile, o=True, f=True)

        # frameRange
        fr = (srcdata['start'], srcdata['end'])
        if self.arg.frameRange != [0, 0]:
            fr = self.arg.frameRange
        self.arg.exportRange = (fr[0] - 1, fr[1] + 1)
        self.arg.framesPerSecond    = srclyr.framesPerSecond
        self.arg.timeCodesPerSecond = srclyr.timeCodesPerSecond

        # step
        step = srcdata.get('step')
        if step: self.arg.step = step

        # customData
        self.arg.customData = {
            'groomFile': self.arg.groomfile,
            'inputCache': self.arg.inputcache,
            'start': fr[0], 'end': fr[1], 'step': self.arg.step
        }

        zdeforms = cmds.sets('ZN_ExportSet', q=True)
        if not zdeforms:
            msg.errorQuit('GroomExporter.MergeExport()', 'not found "ZN_Deform" nodes in %s' % self.arg.groomfile)

        # groom_nodes
        self.arg.bodyMeshLayerData = GetZennBodyMeshMap(zdeforms, root=self.arg.rigNode)
        for shape, znodes in self.arg.bodyMeshLayerData.items():
            self.arg.groom_nodes += znodes

        for s in self.arg.groom_nodes:
            self.arg.subdir = s
            self.arg.groom_outs.append(utl.SJoin(self.arg.D.TASKNVS, self.arg.subdir))

        # initialize ZN_Import
        ZN_Initialize(self.arg.groom_nodes)

        # Walking pre-frame
        startTime = int(cmds.currentTime(q=True))
        for i in range(startTime, self.arg.exportRange[0]):
            cmds.currentTime(i)

        # Make ZN_ExportSet Command
        jobCmd = list()
        for index, node in enumerate(self.arg.groom_nodes):
            cmd = '-f %s' % self.arg.groom_outs[index]
            cmd += ' -n %s' % node
            if self.arg.mergeCache:
                cmd += ' -ct both -mgf'
            else:
                cmd += ' -ct static'
            jobCmd.append(cmd)

        msg.debug(jobCmd)
        cmds.ZN_ExportUSDCmd(j=jobCmd, startFrame=self.arg.exportRange[0], endFrame=self.arg.exportRange[1],
                             step=self.arg.step, v=True)

        # mesh attributes
        self.arg.bodyMeshAttrData = GetBodyMeshAttributes(self.arg.bodyMeshLayerData.keys())

        # groom node attributes
        for n in self.arg.groom_nodes:
            if cmds.attributeQuery('MaterialSet', n=n, ex=True):
                mtlname = cmds.getAttr('%s.MaterialSet' % n)
                if mtlname:
                    if not self.arg.groomAttrData.has_key(n):
                        self.arg.groomAttrData[n] = dict()
                    self.arg.groomAttrData[n][var.T.ATTR_MATERIALSET] = {'value': mtlname,
                                                                         'type': Sdf.ValueTypeNames.String}

        # asset file
        arg = Arguments()
        arg.D.SetDecode(utl.DirName(self.arg.groomfile))
        arg.nslyr = utl.BaseName(self.arg.groomfile).split('.')[0]
        # high_ref  = utl.SJoin(arg.D.TASKN, arg.F.MASTER.replace('.usd', '.high.usd'))
        # low_ref   = utl.SJoin(arg.D.TASKN, arg.F.MASTER.replace('.usd', '.low.usd'))
        # self.arg.groom_reference  = {'high': high_ref, 'low': low_ref}
        self.arg.groom_collection = utl.SJoin(arg.D.TASKN, arg.F.COLLECTION)

        # # search groom_nodes by directory
        # for s in os.listdir(self.arg.dstdir):
        #     subdir = utl.SJoin(self.arg.dstdir, s)
        #     if os.path.isdir(subdir):
        #         files = glob.glob('%s/*_geom.*.usd' % subdir)
        #         if files:
        #             self.arg.groom_nodes.append(s)

        self.DataCollapsed()

        return var.SUCCESS


    def SceneExport(self):
        if not self.arg.groomfile:
            return var.FAILED

        if self.arg.frameRange != [0, 0]:
            fr = self.arg.frameRange
        if self.arg.exportRange == [0, 0]:
            self.arg.exportRange = (fr[0] - 1, fr[1] + 1)
        msg.debug('ExportRange :', self.arg.exportRange)

        # File Open
        cmds.file(self.arg.groomfile, o=True, f=True)

        # set fps
        fps = mel.eval('currentTimeUnitToFPS')
        self.arg.framesPerSecond = fps
        self.arg.timeCodesPerSecond = fps

        # Rig Check
        self.arg.rigNode = cmds.ls(type='dxBlock', l=True)[0]
        nslyr = cmds.getAttr('%s.nsLayer' % self.arg.rigNode)
        self.arg.inputcache = cmds.getAttr('%s.mergeFile' % self.arg.rigNode)
        self.arg.inputRigFile = cmds.getAttr('%s.importFile' % self.arg.rigNode)

        self.arg.nslyr = nslyr
        self.arg.dstdir = self.arg.D[self.arg.taskProduct]
        self.arg.master = utl.SJoin(self.arg.dstdir, self.arg.F.MASTER)

        zdeforms = cmds.sets('ZN_ExportSet', q=True)
        if not zdeforms:
            msg.errorQuit('GroomExporter.MergeExport()', 'not found "ZN_Deform" nodes in %s' % self.arg.groomfile)

        # groom_nodes
        self.arg.bodyMeshLayerData = GetZennBodyMeshMap(zdeforms, root=self.arg.rigNode)
        for shape, znodes in self.arg.bodyMeshLayerData.items():
            self.arg.groom_nodes += znodes

        for s in self.arg.groom_nodes:
            self.arg.subdir = s
            self.arg.groom_outs.append(utl.SJoin(self.arg.D.TASKNVS, self.arg.subdir))

        # initialize ZN_Import
        ZN_Initialize(self.arg.groom_nodes)

        # Walking pre-frame
        startTime = int(cmds.currentTime(q=True))
        for i in range(startTime, self.arg.exportRange[0]):
            cmds.currentTime(i)

        # Make ZN_ExportSet Command
        jobCmd = list()
        for index, node in enumerate(self.arg.groom_nodes):
            cmd = '-f %s' % self.arg.groom_outs[index]
            cmd += ' -n %s' % node
            if self.arg.mergeCache:
                cmd += ' -ct both -mgf'
            else:
                cmd += ' -ct static'
            jobCmd.append(cmd)

        msg.debug(jobCmd)
        cmds.ZN_ExportUSDCmd(j=jobCmd, startFrame=self.arg.exportRange[0], endFrame=self.arg.exportRange[1],
                             step=self.arg.step, v=True)

        # mesh attributes
        self.arg.bodyMeshAttrData = GetBodyMeshAttributes(self.arg.bodyMeshLayerData.keys())

        # groom node attributes
        for n in self.arg.groom_nodes:
            if cmds.attributeQuery('MaterialSet', n=n, ex=True):
                mtlname = cmds.getAttr('%s.MaterialSet' % n)
                if mtlname:
                    if not self.arg.groomAttrData.has_key(n):
                        self.arg.groomAttrData[n] = dict()
                    self.arg.groomAttrData[n][var.T.ATTR_MATERIALSET] = {'value': mtlname,
                                                                         'type': Sdf.ValueTypeNames.String}
        # customData
        self.arg.customData = {
            'groomFile': self.arg.groomfile,
            'inputCache': self.arg.inputcache,
            'start': fr[0], 'end': fr[1], 'step': self.arg.step
        }

        # asset file
        arg = Arguments()
        arg.D.SetDecode(utl.DirName(self.arg.groomfile))
        arg.pop('departs')
        arg.nslyr = self.arg.nslyr
        # high_ref = utl.SJoin(arg.D.TASKN, arg.F.MASTER.replace('.usd', '.high.usd'))
        # low_ref = utl.SJoin(arg.D.TASKN, arg.F.MASTER.replace('.usd', '.low.usd'))
        # self.arg.groom_reference = {'high': high_ref, 'low': low_ref}
        self.arg.groom_collection = utl.SJoin(arg.D.TASKN, arg.F.COLLECTION)

        # search groom_nodes by directory
        for s in os.listdir(self.arg.dstdir):
            subdir = utl.SJoin(self.arg.dstdir, s)
            if os.path.isdir(subdir):
                files = glob.glob('%s/*_geom.*.usd' % subdir)
                if files:
                    self.arg.groom_nodes.append(s)

        for s in self.arg.groom_nodes:
            self.arg.subdir = s
            self.arg.groom_outs.append(utl.SJoin(self.arg.D.TASKNVS, self.arg.subdir))

        self.DataCollapsed()

        return var.SUCCESS


    def Exporting(self):
        # CacheMerge Process
        if self.arg.inputcache:
            res = self.MergeExport()
            if res != var.SUCCESS:
                return res
        # hairSim Process
        else:
            self.SceneExport()


    # def Tweaking(self):
    #     return var.SUCCESS
    #
    # def Compositing(self):
    #     return var.SUCCESS


def shotCacheMergeExport(inputCache, groomFile=None, fr=[0, 0], efr=[0, 0], step=1.0,
                         overwrite=False, show=None, seq=None, shot=None, version='', user='anonymous', process='geom'):
    if not os.path.exists(inputCache):
        msg.errorQuit('not found inputCache :', inputCache)
        return

    if not '/show/' in inputCache:
        msg.errorQuit("don't include show")
        return

    # Requires load ZENNForMaya plugin
    try:
        cmds.loadPlugin('ZENNForMaya')
    except:
        assert False, "not found ZENNForMaya plugin"

    if not cmds.pluginInfo('ZENNForMaya', q=True, l=True):
        assert False, "Failed Load ZENNForMaya Plugin"

    try:
        cmds.loadPlugin('DXUSD_Maya')
    except:
        assert False, "not found DXUSD_Maya plugin"

    if not cmds.pluginInfo('DXUSD_Maya', q=True, l=True):
        assert False, "Failed Load DXUSD_Maya Plugin"

    # shot
    arg = exp.AGroomShotExporter()
    arg.inputcache = inputCache
    arg.groomfile  = groomFile
    arg.step = step
    arg.overwrite = overwrite
    arg.simExport = False

    # frame range
    arg.frameRange = fr
    if efr != [0, 0]:
        arg.exportRange = efr

    # override
    if show: arg.ovr_show = show
    if seq: arg.ovr_seq = seq
    if shot: arg.ovr_shot = shot
    if version: arg.ovr_ver = version

    if process == 'treat':
        arg.Treat()
        return arg

    if process == "both":
        GroomShotGeomExport(arg)
        arg.overwrite = True
        GroomShotCompositor(arg)
    else:
        if process == 'geom':
            GroomShotGeomExport(arg)
        else:
            arg.overwrite = True
            GroomShotCompositor(arg)

def groomSimExport(groomFile=None, fr=[0, 0], efr=[0, 0], step=1.0,
                         overwrite=False, show=None, seq=None, shot=None, version='', user='anonymous', process='geom'):
    # Requires load ZENNForMaya plugin
    try:
        cmds.loadPlugin('ZENNForMaya')
    except:
        assert False, "not found ZENNForMaya plugin"

    if not cmds.pluginInfo('ZENNForMaya', q=True, l=True):
        assert False, "Failed Load ZENNForMaya Plugin"

    try:
        cmds.loadPlugin('DXUSD_Maya')
    except:
        assert False, "not found DXUSD_Maya plugin"

    if not cmds.pluginInfo('DXUSD_Maya', q=True, l=True):
        assert False, "Failed Load DXUSD_Maya Plugin"

    # shot
    arg = exp.AGroomShotExporter()
    arg.groomfile  = groomFile
    arg.step = step
    arg.overwrite = overwrite
    arg.simExport = True

    # frame range
    arg.frameRange = fr
    if efr != [0, 0]:
        arg.exportRange = efr

    # override
    if show: arg.ovr_show = show
    if seq: arg.ovr_seq = seq
    if shot: arg.ovr_shot = shot
    if version: arg.ovr_ver = version

    if process == 'treat':
        arg.Treat()
        return arg

    if process == "both":
        GroomShotGeomExport(arg)
        arg.overwrite = True
        GroomShotCompositor(arg)
    else:
        if process == 'geom':
            GroomShotGeomExport(arg)
        else:
            arg.overwrite = True
            GroomShotCompositor(arg)
