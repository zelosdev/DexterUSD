#coding:utf-8
from __future__ import print_function
import maya.cmds as cmds

import DXUSD.Vars as var
import DXUSD.Utils as utl

from DXUSD.Exporters.Export import Export, AExport
import DXUSD.Compositor as cmp

import DXUSD_MAYA.Message as msg
import DXUSD_MAYA.Tweakers as twk


class ACameraExporter(AExport):
    def __init__(self, **kwargs):
        self.nodes  = []
        self.scene  = ''
        self.geomfiles = []         # export geom filename.
        self.imgPlanefiles = []     # export imagePlane filename.
        self.dummyfiles = {}        # export dummy filename.
        self.dummyAbc = {}          # not exported to USD  ex) locator
        self.master = ''

        # initialize
        AExport.__init__(self, **kwargs)

        # attributes
        self.taskProduct = 'TASKV'

    def Treat(self):
        self.D.SetDecode(utl.DirName(self.scene), 'SHOW')
        self.F.MAYA.SetDecode(utl.BaseName(self.scene), 'BASE')
        self.task = 'cam'

        # override show, seq, shot
        if self.has_attr('ovr_show'): self.show = self.ovr_show
        if self.has_attr('ovr_seq'):  self.seq  = self.ovr_seq
        if self.has_attr('ovr_shot'): self.shot = self.ovr_shot

        res = AExport.Treat(self)
        if res != var.SUCCESS:
            return res

        if self.has_attr('ovr_ver'):
            self.ver = self.ovr_ver
        else:
            if self.overwrite:
                self.ver = utl.GetLastVersion(self.D.TASK)
            else:
                self.ver = utl.GetNextVersion(self.D.TASK)

        self.dstdir = self.D[self.taskProduct]
        self.master = utl.SJoin(self.dstdir, self.F.USD.cam.MASTER)

        for node in self.nodes:
            geomFile = '%s.geom.usd' % node.split('|')[-1]
            self.geomfiles.append(utl.SJoin(self.dstdir, geomFile))

        return var.SUCCESS


class CameraExporter(Export):
    ARGCLASS = ACameraExporter
    def Arguing(self):
        return var.SUCCESS

    def Tweaking(self):
        twks = twk.Tweak()
        twks << twk.MasterCameraPack(self.arg)
        if self.arg.abcExport:
            twks << twk.ConvertAlembic(self.arg)
        twks.DoIt()
        return var.SUCCESS

    def Compositing(self):
        cmp.Composite(self.arg.master).DoIt()
        return var.SUCCESS


class ACameraExporterAsset(AExport):
    def __init__(self, **kwargs):
        self.nodes  = []
        self.scene  = ''
        self.maincam = []
        self.geomfiles = []         # export geom filename.
        self.master = ''

        # not used on assetCamera
        self.imgPlanefiles = []
        self.dummyfiles = {}
        self.abcExport = False
        self.isStereo = False
        self.isOverscan = False

        # initialize
        AExport.__init__(self, **kwargs)

    def Treat(self):
        self.N.cam.SetDecode(self.dxnodes[0])
        if self.has_attr('ovr_show'):
            self.show = self.ovr_show
        else:
            self.D.SetDecode(utl.DirName(self.scene), 'SHOW')

        self.task = 'cam'
        self.taskProduct = 'TASKV'

        res = AExport.Treat(self)
        if res != var.SUCCESS:
            return res

        if self.has_attr('ovr_ver'):
            self.ver = self.ovr_ver
        else:
            if self.overwrite:
                self.ver = utl.GetLastVersion(self.D.TASK)
            else:
                self.ver = utl.GetNextVersion(self.D.TASK)

        self.dstdir = self.D[self.taskProduct]
        self.master = utl.SJoin(self.dstdir, self.F.USD.cam.MASTER)

        for node in self.nodes:
            geomFile = '%s.geom.usd' % node
            self.geomfiles.append(utl.SJoin(self.dstdir, geomFile))

        return var.SUCCESS


class CameraExporterAsset(Export):
    ARGCLASS = ACameraExporterAsset
    def Arguing(self):
        return var.SUCCESS

    def Tweaking(self):
        twks = twk.Tweak()
        twks << twk.MasterCameraPack(self.arg)
        twks.DoIt()
        return var.SUCCESS

    def Compositing(self):
        cmp.Composite(self.arg.master).DoIt()
        return var.SUCCESS
