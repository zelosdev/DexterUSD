#coding:utf-8
from __future__ import print_function
import pprint

import DXUSD.Vars as var
import DXUSD.Utils as utl

from DXUSD.Exporters.Export import Export, AExport
import DXUSD.Compositor as cmp

import DXUSD_MAYA.Message as msg
import DXUSD_MAYA.Tweakers as twk

#-------------------------------------------------------------------------------
#
#   Rig Asset
#
#-------------------------------------------------------------------------------
class ARigAssetExporter(AExport):
    def __init__(self, **kwargs):
        # input argument
        self.scene   = ''
        self.node    = ''
        self.variant = ''

        # treat compute
        self.dstdir   = ''
        self.master   = ''

        # exporter compute
        self.geomfiles = []             # exported geom filename.

        # initialize
        AExport.__init__(self, **kwargs)

        # attributes
        self.taskProduct = 'TASKN'

    def Treat(self):
        self.N.rig.SetDecode(self.node)
        self.desc = self.node
        self.D.SetDecode(utl.DirName(self.scene), 'SHOW')
        self.nslyr = utl.BaseName(self.scene).split('.')[0]
        if self.variant and self.variant != self.asset:
            self.branch = self.variant

        # override show
        if self.has_attr('ovr_show'):
            if self.ovr_show == var.T.ASSETLIB3D:
                self.pop('root')
                self.pop('show')
                self.customdir = self.ovr_show
            else:
                self.show = self.ovr_show

        # seq or shot asset
        if self.has_attr('ovr_shot'): self.N.SetDecode(self.ovr_shot, 'SHOTNAME')
        
        res = AExport.Treat(self)
        if res != var.SUCCESS:
            return res

        self.dstdir = self.D[self.taskProduct]
        self.master = utl.SJoin(self.dstdir, self.F.MASTER)

        return var.SUCCESS

class RigAssetExporter(Export):
    ARGCLASS = ARigAssetExporter
    def Arguing(self):
        self.texData = dict()                   # GeomAttrs result for texture process

        self.gArg = twk.AGeomAttrs()            # GeomAttrs, PrmanMaterial, GeomAttrsCompTex arguments
        self.gArg.extracts += ['purpose', var.T.ATTR_ST]
        self.gArg.extracts += self.arg.uvSetList
        self.gArg.inputs = self.arg.geomfiles
        self.tArg = twk.ATexture()              # Texture, ProxyMaterial arguments
        return var.SUCCESS

    def Tweaking(self):
        # 1
        twks = twk.Tweak()
        twks << twk.ModifyMayaReference(self.arg)       # modify reference. pxrUsdReferenceAssembly, pxrUsdProxyShape
        twks << twk.ModifyMayaNurbsAddWidths(self.arg)  # add widths attribute for nurbsCurve
        twks << twk.GeomAttrs(self.gArg, self.texData)  # geom attribute extract
        twks.DoIt()

        if msg.DEV:
            print('>>> Result texData :')
            pprint.pprint(self.texData, width=20)

        # 2
        twks = twk.Tweak()
        for fn in self.texData:
            self.tArg.texAttrUsd = fn
            self.tArg.texData    = self.texData[fn]

            twks << twk.Texture(self.tArg)              # create or update tex.attr.usd
            twks << twk.ProxyMaterial(self.tArg)        # create or update proxy.mtl.usd

        twks << twk.PrmanMaterial(self.gArg)            # create prman material
        twks << twk.GeomAttrsCompTex(self.gArg)         # composite tex.usd by assetInfo
        twks << twk.MasterRigPack(self.arg)             # master rig geom package
        twks << twk.Collection(self.arg)                # create collection
        twks << twk.PrmanMaterialOverride(self.arg)     # referenced asset material override
        twks.DoIt()
        return var.SUCCESS

    def Compositing(self):
        cmp.Composite(self.arg.master).DoIt()
        return var.SUCCESS


#-------------------------------------------------------------------------------
#
#   Rig Shot
#
#-------------------------------------------------------------------------------
class ARigShotExporter(AExport):
    def __init__(self, **kwargs):
        # input argument
        self.scene  = ''
        self.node   = ''
        self.step   = 1.0
        self.autofr = False
        self.frameRange  = (0, 0)
        self.isRigUpdate = False
        self.overwrite = False
        self.user = 'anonymous'

        # treat compute
        self.dstdir = ''
        self.master = ''

        # exporter compute
        self.geomfiles = []             # exported geom filename.
        self.subframe_geomfiles = []    # exported subframe geom filename.
        self.separate_geomfiles = []     # exported separate geom filename.

        # initialize
        AExport.__init__(self, **kwargs)

        # attributes
        self.task = 'ani'
        self.taskProduct = 'TASKN'

    def Treat(self):
        self.N.ani.SetDecode(self.node, 'SHOT')
        self.D.SetDecode(utl.DirName(self.scene), 'SHOW')
        ret = self.F.MAYA.Decode(utl.BaseName(self.scene), 'BASE')
        self.seq = ret.seq
        self.shot = ret.shot

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

        self.namespace = self.nslyr

        msg.debug(self.F)

        return var.SUCCESS

class RigShotBase(Export):
    ARGCLASS = ARigShotExporter
    def Arguing(self):
        self.gArgs = twk.AGeomRigAttrs()        # GeomRigAttrs arguments
        self.gArgs.inputs = self.arg.geomfiles
        return var.SUCCESS

    def Tweaking(self):
        twks = twk.Tweak()
        twks << twk.MashVelocities(self.arg)            # Mash Velocities compute
        twks << twk.SeparateCombineGeom(self.arg)       # separate stitch files
        twks << twk.SubFrameMesh(self.arg)              # subframe stitch files
        twks << twk.GeomRigAttrs(self.gArgs)            # rig geom attributes
        twks << twk.PurposeAttrSetup(self.arg)
        twks << twk.ModifyMayaReference(self.arg)
        twks << twk.ModifyMayaNurbsClearWidths(self.arg)
        twks << twk.MasterRigPack(self.arg)             # master rig geom package
        twks << twk.PrmanMaterialOverride(self.arg)     # material override
        twks.DoIt()
        return var.SUCCESS

    def Compositing(self):
        cmp.Composite(self.arg.master).DoIt()
        return var.SUCCESS
