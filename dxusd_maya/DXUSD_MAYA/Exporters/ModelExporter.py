#coding:utf-8
from __future__ import print_function
import pprint

import DXUSD.Vars as var
import DXUSD.Utils as utl

from DXUSD.Exporters.Export import Export, AExport
import DXUSD.Compositor as cmp

import DXUSD_MAYA.Message as msg
import DXUSD_MAYA.Tweakers as twk


class AModelExporter(AExport):
    def __init__(self, **kwargs):
        # input argument
        self.nodes  = []
        self.scene  = ''
        self.overwrite = False

        # treat compute
        self.org_show  = ''     # for MTK
        self.geomfiles = []     # export geom filename.
        self.master    = ''

        # exporter compute
        self.ptNodes = []       # compute pointInstance nodes (dxBlock)

        # initialize
        AExport.__init__(self, **kwargs)

        # attributes
        self.task = 'model'
        self.taskProduct = 'TASKV'

    def Treat(self):
        self.N.model.SetDecode(self.nodes[0])
        self.D.SetDecode(utl.DirName(self.scene), 'SHOW')

        if self.has_attr('ovr_show'):
            if var.T.ASSETLIB3D == self.ovr_show:
                self.customdir = self.ovr_show
            else:
                # override show
                self.show = self.ovr_show

        # seq or shot asset
        if self.has_attr('ovr_shot'): self.N.SetDecode(self.ovr_shot, 'SHOTNAME')

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

        # for MTK
        if self.customdir:
            self.org_show = self.show
            if not var.T.ASSETLIB3D == self.customdir:
                self.ver = 'v000'
            self.pop('show')

        self.dstdir = self.D[self.taskProduct]
        self.master = utl.SJoin(self.dstdir, self.F.MASTER)

        # geom filename map
        for node in self.nodes:
            self.N.model.SetDecode(node)
            if not self.lod:
                self.lod = var.T.HIGH
            self.geomfiles.append(utl.SJoin(self.dstdir, self.F.GEOM))
            self.lod = ''

        return var.SUCCESS


class ALidarExporter(AExport):
    def __init__(self, **kwargs):
        # input argument
        self.nodes  = []
        self.scene  = ''
        self.overwrite = False

        # treat compute
        self.org_show  = ''     # for MTK
        self.geomfiles = []     # export geom filename.
        self.master    = ''

        # initialize
        AExport.__init__(self, **kwargs)

        # attributes
        self.task = 'lidar'
        self.taskProduct = 'TASKV'

    def Treat(self):
        self.N.lidar.SetDecode(self.nodes[0])
        self.D.SetDecode(utl.DirName(self.scene), 'SHOW')

        if self.has_attr('ovr_show'):
            if var.T.ASSETLIB3D == self.ovr_show:
                self.customdir = self.ovr_show
            else:
                # override show
                self.show = self.ovr_show

        if self.has_attr('ovr_ver'):
            self.ver = self.ovr_ver
        else:
            if self.overwrite:
                self.ver = utl.GetLastVersion(self.D.TASK)
            else:
                self.ver = utl.GetNextVersion(self.D.TASK)

        self.dstdir = self.D[self.taskProduct]
        self.master = utl.SJoin(self.dstdir, self.F.MASTER)

        # geom filename map
        for node in self.nodes:
            self.N.lidar.SetDecode(node)

            if not self.lod:
                self.lod = var.T.HIGH
            self.geomfiles.append(utl.SJoin(self.dstdir, self.F.GEOM))
            self.lod = ''

        return var.SUCCESS


class ModelExporter(Export):
    ARGCLASS = AModelExporter
    def Arguing(self):
        self.texData = dict()                   # GeomAttrs result for texture process

        self.gArg = twk.AGeomAttrs()            # GeomAttrs, PrmanMaterial, GeomAttrsCompTex arguments
        self.gArg.inputs = self.arg.geomfiles
        if self.arg.org_show:
            self.gArg.ovr_show = self.arg.org_show
        self.tArg = twk.ATexture()              # Texture, ProxyMaterial arguments
        return var.SUCCESS

    def Tweaking(self):
        # 1
        twks = twk.Tweak()
        twks << twk.ModifyMayaReference(self.arg)           # modify reference. pxrUsdReferenceAssembly, pxrUsdProxyShape
        twks << twk.ModifyMayaNurbsAddWidths(self.arg)      # add widths attribute for nurbsCurve
        twks << twk.PointInstancer(self.arg)                # create pointInstancer by dxBlock
        twks << twk.GeomAttrs(self.gArg, self.texData)      # geom attribute extract
        twks.DoIt()

        if msg.DEV and self.texData:
            print('>>> Result texData :')
            pprint.pprint(self.texData, width=20)

        # 2
        twks = twk.Tweak()
        for fn in self.texData:
            self.tArg.texAttrUsd = fn
            self.tArg.texData = self.texData[fn]

            twks << twk.Texture(self.tArg)                  # create or update tex.attr.usd
            twks << twk.ProxyMaterial(self.tArg)            # create or update proxy.mtl.usd

        twks << twk.PrmanMaterial(self.gArg)                # create prman material
        twks << twk.GeomAttrsCompTex(self.gArg)             # composite tex.usd by assetInfo
        twks << twk.MasterModelPack(self.arg)               # master model geom package
        twks << twk.Collection(self.arg)                    # create collection by master
        twks << twk.PrmanMaterialOverride(self.arg)         # referenced asset material override
        twks.DoIt()
        return var.SUCCESS

    def Compositing(self):
        cmp.Composite(self.arg.master).DoIt()
        return var.SUCCESS


class LidarExporter(Export):
    ARGCLASS = ALidarExporter
    def Arguing(self):
        return var.SUCCESS

    def Tweaking(self):
        twks = twk.Tweak()
        twks << twk.MasterModelPack(self.arg)
        twks.DoIt()
        return var.SUCCESS

    def Compositing(self):
        cmp.Composite(self.arg.master).DoIt()
        return var.SUCCESS
