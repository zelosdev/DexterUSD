#coding:utf-8
from __future__ import print_function

import os, re
import maya.cmds as cmds

import DXUSD.Vars as var
import DXUSD.Utils as utl

from DXUSD.Structures import Arguments
from DXUSD.Exporters.Export import Export, AExport
import DXUSD.Compositor as cmp

import DXUSD_MAYA.Message as msg
import DXUSD_MAYA.Tweakers as twk


#-------------------------------------------------------------------------------
#
#   Rig Clip
#
#-------------------------------------------------------------------------------
class ARigClipExporter(AExport):
    def __init__(self, **kwargs):
        '''
        override option
            ovr_show
            ovr_ver
        '''
        # input argument
        self.scene = ''
        self.node  = ''     # node type is dxRig
        self.timeScales = [0.8, 1.0, 1.2]
        self.loopRange  = (1001, 2000)
        self.step = 1.0
        self.overwrite = False

        # treat compute
        self.org_show  = ''     # for MTK
        self.master    = ''
        self.timeLayers= []

        # exporter compute
        self.geomfiles = []

        # initialize
        AExport.__init__(self, **kwargs)

        # attribute
        self.taskProduct = 'TASKNVC'

    def Treat(self):
        nsName, nodeName = self.node.split(':')
        self.N.clip.SetDecode(nodeName, 'ASSET')
        self.desc  = nodeName
        self.nslyr = nsName

        self.clip = 'base'
        self.task = 'clip'

        self.D.SetDecode(utl.DirName(self.scene), 'SHOW')

        # override show
        if self.has_attr('ovr_show'): self.show = self.ovr_show

        # seq or shot asset
        if self.has_attr('ovr_shot'): self.N.SetDecode(self.ovr_shot, 'SHOTNAME')    

        res = AExport.Treat(self)
        if res != var.SUCCESS:
            return res

        if self.has_attr('ovr_ver'):
            self.nsver = self.ovr_ver
        else:
            if self.overwrite:
                self.nsver = utl.GetLastVersion(self.D.TASKN)
            else:
                self.nsver = utl.GetNextVersion(self.D.TASKN)

        # for MTK
        if self.customdir:
            self.org_show = self.show
            self.nsver = 'v000'
            self.pop('show')

        # timeScale clip layers
        for ts in self.timeScales:
            self.timeLayers.append(str(ts).replace('.', '_'))

        self.dstdir = self.D.TASKNV
        self.master = utl.SJoin(self.dstdir, self.F.MASTER)

        return var.SUCCESS

class RigClipExporter(Export):
    ARGCLASS = ARigClipExporter
    def Arguing(self):
        self.grArg  = twk.AGeomRigAttrs()       # GeomRigAttrs arguments
        self.grArg.inputs = self.arg.geomfiles
        self.mrpArg = twk.AMasterRigPack()      # MasterRigPack arguments for clip layers
        self.cgArg  = twk.AClipGeomPack()       # ClipGeomPack arguments
        return var.SUCCESS

    def Tweaking(self):
        twks = twk.Tweak()
        twks << twk.GeomRigAttrs(self.grArg)    # rig geom attributes
        twks << twk.LoopClip(self.arg)          # create loop clip

        clips = ['base'] + self.arg.timeLayers
        for c in clips:
            self.arg.clip = c
            tmp = Arguments()
            tmp.N.rig.SetDecode(self.arg.desc, 'ASSET')
            self.mrpArg.master = utl.SJoin(self.arg.D.TASKNVC, tmp.F.MASTER)
            twks << twk.MasterRigPack(self.mrpArg)  # per clip master rig package
            self.cgArg.output = utl.SJoin(self.arg.D.TASKNVC, self.arg.F.CLIP)
            twks << twk.ClipGeomPack(self.cgArg)    # per clip layer geom package

        twks << twk.MasterClipPack(self.arg)    # master clip package
        twks.DoIt()
        return var.SUCCESS

    def Compositing(self):
        cmp.Composite(self.arg.master).DoIt()
        return var.SUCCESS


#-------------------------------------------------------------------------------
#
#   Groom Clip
#
#-------------------------------------------------------------------------------
class AGroomClipExporter(AExport):
    def __init__(self, **kwargs):
        '''
        not support override.
            inputcache based version, timeScales, loopRange
        '''
        # input argument
        self.scene = ''
        self.node  = ''             # node type is dxBlock
        self.bodyMeshLayerData = {} # {shapename: [ZN_Deform, ...]}
        self.groom_nodes = []
        self.inputcache  = ''

        # treat compute
        self.dstdir = ''
        self.master = ''
        self.timeLayers  = []
        self.groom_outs  = []
        self.geomfiles   = []

        # exporter compute
        self.org_show   = ''    # for MTK. find original show by rigFile
        self.timeScales = []
        self.loopRange  = (1001, 2000)
        self.step = 1.0
        self.customData = {}
        self.bodyMeshAttrData = {}
        self.groom_collection = ''

        # initialize
        AExport.__init__(self, **kwargs)

        # attribute
        self.taskProduct = 'TASKNVC'

    def Treat(self):
        self.node = cmds.ls(self.node, l=True)[0]
        self.D.SetDecode(utl.DirName(self.inputcache), 'WORK')

        self.clip = 'base'
        self.task = 'clip'

        res = AExport.Treat(self)
        if res != var.SUCCESS:
            return res

        self.dstdir = self.D.TASKNV
        self.master = utl.SJoin(self.dstdir, self.F.MASTER)

        # timeScale Layers
        for d in os.listdir(self.dstdir):
            if os.path.isdir(utl.SJoin(self.dstdir, d)):
                if re.match('[0-9]+_[0-9]+', d):
                    self.timeLayers.append(d)
        # timeScales
        for n in self.timeLayers:
            ts = n.replace('_', '.')
            self.timeScales.append(float(ts))
        # loopRange
        if os.path.exists(self.master):
            srclyr = utl.AsLayer(self.master)
            start  = int(srclyr.startTimeCode)
            end    = int(srclyr.endTimeCode)
            self.loopRange = (start, end)

        for n in self.groom_nodes:
            out = utl.SJoin(self.D.TASKNVC, n, n)
            self.groom_outs.append(out)
            self.geomfiles.append(out + '.high_geom.usd')
            self.geomfiles.append(out + '.low_geom.usd')

        return var.SUCCESS

class GroomClipExporter(Export):
    ARGCLASS = AGroomClipExporter
    def Arguing(self):
        self.cmArg = twk.ACombineGroomLayers(**self.arg.AsDict())   # CombineGroomLayers arguments
        if self.arg.org_show:
            self.cmArg.ovr_show = self.arg.org_show
        self.cgArg = twk.AClipGeomPack()                            # ClipGeomPack arguments
        return var.SUCCESS

    def Tweaking(self):
        twks = twk.Tweak()
        twks << twk.LoopClip(self.arg)                  # create loop clip

        clips = ['base'] + self.arg.timeLayers
        for c in clips:
            self.arg.clip = c
            tmp = Arguments()
            tmp.N.groom.SetDecode(self.arg.node.split('|')[-1], 'ASSET')
            self.cmArg.master = utl.SJoin(self.arg.D.TASKNVC, tmp.F.MASTER)
            twks << twk.CombineGroomLayers(self.cmArg)  # per clip composite groom layers
            twks << twk.GroomLayerCompTex(self.cmArg)   # composite tex.usd by assetInfo
            twks << twk.MasterGroomPack(self.cmArg)     # per clip master groom package
            self.cgArg.output = utl.SJoin(self.arg.D.TASKNVC, self.arg.F.CLIP)
            twks << twk.ClipGeomPack(self.cgArg)        # per clip layer geom package

        # twks << twk.MasterClipPack(self.arg)          # master clip package is skiped
        twks.DoIt()
        return var.SUCCESS

    def Compositing(self):
        return var.SUCCESS
