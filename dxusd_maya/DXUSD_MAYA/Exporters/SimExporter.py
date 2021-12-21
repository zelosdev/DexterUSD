#coding:utf-8
from __future__ import print_function

import DXUSD.Vars as var
import DXUSD.Utils as utl

from DXUSD.Exporters.Export import Export, AExport
import DXUSD.Compositor as cmp

import DXUSD_MAYA.Message as msg
import DXUSD_MAYA.Tweakers as twk

import maya.cmds as cmds


class ASimExporter(AExport):
    def __init__(self, **kwargs):
        # input argument
        self.scene = ''
        self.node  = ''
        self.nslyr = ''
        self.overwrite = False
        self.autofr = False
        self.step = 1.0

        # treat compute
        self.dstdir = ''
        self.master = ''

        # exporter compute
        self.geomfiles = []     # exported geom filename.
        self.refNode = ''

        # initialize
        AExport.__init__(self, **kwargs)

        # attributes
        self.task = 'sim'
        self.taskProduct = 'TASKN'

    def Treat(self):
        # self.nslyr = cmds.getAttr('%s.nsLayer' % self.node)
        self.D.SetDecode(utl.DirName(self.scene), 'SHOW')
        self.F.MAYA.SetDecode(utl.BaseName(self.scene), 'WORK')
        self.desc = self.node

        # override show, seq, shot
        if self.has_attr('ovr_show'): self.show = self.ovr_show
        if self.has_attr('ovr_seq'):  self.seq  = self.ovr_seq
        if self.has_attr('ovr_shot'): self.shot = self.ovr_shot

        res = AExport.Treat(self)
        if res != var.SUCCESS:
            return res

        if not isinstance(self.nsver, str):
            if self.overwrite:
                self.nsver = utl.GetLastVersion(self.D.TASKN)
            else:
                self.nsver = utl.GetNextVersion(self.D.TASKN)

        self.dstdir = self.D.TASKNV
        self.master = utl.SJoin(self.D.TASKNV, self.F.MASTER)

        return var.SUCCESS

class SimBase(Export):
    ARGCLASS = ASimExporter

    def Arguing(self):
        self.gArgs = twk.AGeomRigAttrs()
        self.gArgs.inputs = self.arg.geomfiles
        return var.SUCCESS

    def Tweaking(self):
        twks = twk.Tweak()
        twks << twk.PathRepresent(self.arg)         # edit prim
        twks << twk.ModifyMayaNurbsAddWidths(self.arg)  # add widths attribute for nurbsCurve
        twks << twk.GeomRigAttrs(self.gArgs)        # rig geom attributes
        # twks << twk.PurposeAttrSetup(self.arg)   # purpose attr setup
        twks << twk.MasterSimPack(self.arg)         # master sim geom package
        twks.DoIt()
        return var.SUCCESS

    def Compositing(self):
        cmp.Composite(self.arg.master).DoIt()
        return var.SUCCESS
