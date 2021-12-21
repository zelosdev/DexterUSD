#coding:utf-8
from __future__ import print_function

import os, glob

import DXUSD.Vars as var
import DXUSD.Utils as utl

from DXUSD.Structures import Arguments
from DXUSD.Exporters.Export import Export, AExport
import DXUSD.Compositor as cmp

import DXUSD_MAYA.Message as msg
import DXUSD_MAYA.Tweakers as twk

import maya.cmds as cmds
#-------------------------------------------------------------------------------
#
#   Env Shot
#
#-------------------------------------------------------------------------------
class ALayoutExporter(AExport):
    def __init__(self, **kwargs):

        # input argument
        self.scene  = ''
        self.overwrite = False
        self.nodes = []
        self.step = 1.0
        self.frameRange  = [0, 0]
        self.frameSample = [0.0]

        # treat compute
        self.master = ''

        # exporter compute
        self.ptNodes = []
        self.customData = ''
        self.geomfiles = []
        self.invNodes = []

        # initialize
        AExport.__init__(self, **kwargs)

        # attributes
        self.task = 'layout'
        self.taskProduct = 'TASKNV'

    def Treat(self):

        self.D.SetDecode(utl.DirName(self.scene), 'SHOW')
        # get seq, shot
        ret = self.F.MAYA.layout.Decode(utl.BaseName(self.scene))
        self.seq  = ret.seq
        self.shot = ret.shot

        ret = self.N.layout.Decode(self.nodes[0])
        if cmds.nodeType(self.nodes[0]) != 'dxBlock':
            ret.nslyr = 'extra'
        self.update(ret)

        # override show
        if self.has_attr('ovr_show'): self.show = self.ovr_show
        if self.has_attr('ovr_seq'):  self.seq  = self.ovr_seq
        if self.has_attr('ovr_shot'): self.shot = self.ovr_shot

        if self.has_attr('ovr_ver'):
            self.nsver = self.ovr_ver
        else:
            if self.overwrite:
                self.nsver = utl.GetLastVersion(self.D.TASKN)
            else:
                self.nsver = utl.GetNextVersion(self.D.TASKN)

        res = AExport.Treat(self)
        if res != var.SUCCESS:
            return res

        self.dstdir = self.D.TASKNV
        self.master = utl.SJoin(self.dstdir, self.F.MASTER)

        return var.SUCCESS


class LayoutExporter(Export):
    ARGCLASS = ALayoutExporter
    def Arguing(self):
        return var.SUCCESS

    def Tweaking(self):
        twks = twk.Tweak()
        twks << twk.ModifyMayaReference(self.arg)
        twks << twk.PointInstancer(self.arg)
        twks << twk.InvisibleIds(self.arg)
        twks << twk.MasterLayoutPack(self.arg)
        twks << twk.PrmanMaterialOverride(self.arg)     # referenced asset material override
        twks.DoIt()
        return var.SUCCESS

    def Compositing(self):
        cmp.Composite(self.arg.master).DoIt()
        return var.SUCCESS
