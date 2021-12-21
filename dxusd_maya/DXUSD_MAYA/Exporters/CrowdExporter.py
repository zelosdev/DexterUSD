#coding:utf-8
from __future__ import print_function

import DXUSD.Vars as var
import DXUSD.Utils as utl

from DXUSD.Exporters.Export import Export, AExport
import DXUSD.Compositor as cmp

import DXUSD_MAYA.Message as msg
import DXUSD_MAYA.Tweakers as twk


#-------------------------------------------------------------------------------
#
#   Golaem Asset
#
#-------------------------------------------------------------------------------
class AGolaemAssetExporter(AExport):
    def __init__(self, **kwargs):
        # export source data
        self.node   = ''
        self.scene  = ''
        self.gchafile = ''
        self.gcgfile = ''
        self.geomfile  = ''
        self.rigfile   = ''
        self.master = ''
        self.overwrite = False

        # initialize
        AExport.__init__(self, **kwargs)

        self.taskProduct = 'TASKNV'

    def Treat(self):
        self.D.SetDecode(utl.DirName(self.scene), 'SHOW')
        self.N.agent.SetDecode(self.node, 'ASSET')
        self.N.agent.SetDecode(self.nslyr, 'SETASSET')

        # override show
        if self.has_attr('ovr_show'): self.show = self.ovr_show

        if self.has_attr('ovr_ver'):
            self.nsver = self.ovr_ver
        else:
            if self.overwrite:
                self.nsver = utl.GetLastVersion(self.D.TASKN)
            else:
                self.nsver = utl.GetNextVersion(self.D.TASKN)

        self.dstdir = self.D[self.taskProduct]
        self.gchafile = utl.SJoin(self.dstdir, 'character', self.F.GCHA)
        self.gcgfile = utl.SJoin(self.dstdir, 'character', self.F.GCG)
        self.geomfile = utl.SJoin(self.dstdir, self.F.GEOM)
        self.rigfile  = self.geomfile.replace('.geom.usd', '.rig.usd')
        self.master = utl.SJoin(self.dstdir, self.F.MASTER)
        return var.SUCCESS


class GolaemAssetExporter(Export):
    ARGCLASS = AGolaemAssetExporter
    def Arguing(self):
        self.texData = dict()                   # GeomAttrs result for texture process

        self.gArg = twk.AGeomAttrs()            # GeomAttrs, PrmanMaterial, GeomAttrsCompTex arguments
        self.gArg.inputs = [self.arg.geomfile]
        self.tArg = twk.ATexture()              # Texture, ProxyMaterial arguments
        return var.SUCCESS

    def Tweaking(self):
        twks = twk.Tweak()
        twks << twk.GeomAttrs(self.gArg, self.texData)  # geom attribute extract
        twks.DoIt()

        # 2
        twks = twk.Tweak()
        for f in self.texData:
            self.tArg.texAttrUsd = f
            self.tArg.texData    = self.texData[f]

            twks << twk.Texture(self.tArg)          # create or update tex.attr.usd
            twks << twk.ProxyMaterial(self.tArg)    # create or update proxy.mtl.usd

        twks << twk.PrmanMaterial(self.gArg)        # create prman material
        twks << twk.GeomAttrsCompTex(self.gArg)     # composite tex.usd by assetInfo
        twks << twk.Collection(self.arg)            # create collection
        twks.DoIt()
        return var.SUCCESS

    def Compositing(self):
        cmp.Composite(self.arg.master).DoIt()
        return var.SUCCESS


#-------------------------------------------------------------------------------
#
#   Golaem Shot
#
#-------------------------------------------------------------------------------
class AGolaemShotExporter(AExport):
    def __init__(self, **kwargs):
        # input argument
        self.scene = ''
        self.gscb = None
        self.glmCaches = list()
        self.frameRange  = [0, 0]
        self.exportRange = [0, 0]
        self.overwrite = False
        self.user = 'anonymous'

        # treat compute
        self.dstdir = ''
        self.master = ''

        # initialize
        AExport.__init__(self, **kwargs)

        # attribute
        self.task = 'crowd'
        self.taskProduct = 'TASKV'

    def Treat(self):
        self.D.SetDecode(utl.DirName(self.scene), 'SHOW')
        ret = self.F.MAYA.Decode(utl.BaseName(self.scene), 'BASE')
        self.seq  = ret.seq
        self.shot = ret.shot

        # override show, seq, shot
        if self.has_attr('ovr_show'): self.show = self.ovr_show
        if self.has_attr('ovr_seq'):  self.seq  = self.ovr_seq
        if self.has_attr('ovr_shot'): self.shot = self.ovr_shot

        res = AExport.Treat(self)
        if res != var.SUCCESS:
            return res

        if not isinstance(self.ver, str):
            if self.overwrite:
                self.ver = utl.GetLastVersion(self.D.TASK)
            else:
                self.ver = utl.GetNextVersion(self.D.TASK)

        self.dstdir = self.D[self.taskProduct]
        self.skelfile = utl.SJoin(self.dstdir, self.F.SKEL)
        self.master = utl.SJoin(self.dstdir, self.F.MASTER)

        return var.SUCCESS


class GolaemShotExporter(Export):
    ARGCLASS = AGolaemShotExporter
    def Arguing(self):
        return var.SUCCESS

    def Tweaking(self):
        return var.SUCCESS

    def Compositing(self):
        cmp.Composite(self.arg.master).DoIt()
        return var.SUCCESS


#-------------------------------------------------------------------------------
#
#   Miarmy Asset
#
#-------------------------------------------------------------------------------
class AMiarmyAssetExporter(AExport):
    def __init__(self, **kwargs):
        # export source data
        self.node   = ''
        self.scene  = ''
        self.master = ''
        self.geomfile  = ''
        self.rigfile   = ''
        self.overwrite = False

        # initialize
        AExport.__init__(self, **kwargs)

        self.taskProduct = 'TASKNV'

    def Treat(self):
        self.D.SetDecode(utl.DirName(self.scene), 'SHOW')
        self.N.agent.SetDecode(self.node, 'ASSET')
        self.N.agent.SetDecode(self.nslyr, 'SETASSET')

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

        self.dstdir = self.D.TASKNV
        self.master = utl.SJoin(self.dstdir, self.F.MASTER)
        self.geomfile = utl.SJoin(self.dstdir, self.F.GEOM)
        self.rigfile  = self.geomfile.replace('.geom.usd', '.rig.usd')
        return var.SUCCESS


class MiarmyAssetExporter(Export):
    ARGCLASS = AMiarmyAssetExporter
    def Arguing(self):
        self.texData = dict()                   # GeomAttrs result for texture process

        self.gArg = twk.AGeomAttrs()            # GeomAttrs, PrmanMaterial, GeomAttrsCompTex arguments
        self.gArg.inputs = [self.arg.geomfile]
        self.tArg = twk.ATexture()              # Texture, ProxyMaterial arguments
        return var.SUCCESS

    def Tweaking(self):
        # 1
        twks = twk.Tweak()
        twks << twk.GeomAttrs(self.gArg, self.texData)  # geom attribute extract
        twks.DoIt()

        # 2
        twks = twk.Tweak()
        for f in self.texData:
            self.tArg.texAttrUsd = f
            self.tArg.texData    = self.texData[f]

            twks << twk.Texture(self.tArg)          # create or update tex.attr.usd
            twks << twk.ProxyMaterial(self.tArg)    # create or update proxy.mtl.usd

        twks << twk.PrmanMaterial(self.gArg)        # create prman material
        twks << twk.GeomAttrsCompTex(self.gArg)     # composite tex.usd by assetInfo
        twks << twk.Collection(self.arg)            # create collection
        twks << twk.GeomAgentAttrs(self.gArg)       # remove mesh extent, mesh randomize active setup for miarmy
        twks.DoIt()
        return var.SUCCESS

    def Compositing(self):
        cmp.Composite(self.arg.master).DoIt()
        return var.SUCCESS


#-------------------------------------------------------------------------------
#
#   Miarmy Shot
#
#-------------------------------------------------------------------------------
class AMiarmyShotExporter(AExport):
    def __init__(self, **kwargs):
        # input argument
        self.scene = ''
        self.frameRange  = [0, 0]
        self.exportRange = [0, 0]
        self.overwrite = False
        self.user = 'anonymous'

        self.selAgents = []     # if selected agnets

        # treat compute
        self.dstdir = ''
        self.master = ''

        # initialize
        AExport.__init__(self, **kwargs)

        # attribute
        self.task = 'crowd'
        self.taskProduct = 'TASKV'

    def Treat(self):
        self.D.SetDecode(utl.DirName(self.scene), 'SHOW')
        ret = self.F.MAYA.Decode(utl.BaseName(self.scene), 'BASE')
        self.seq  = ret.seq
        self.shot = ret.shot

        # override show, seq, shot
        if self.has_attr('ovr_show'): self.show = self.ovr_show
        if self.has_attr('ovr_seq'):  self.seq  = self.ovr_seq
        if self.has_attr('ovr_shot'): self.shot = self.ovr_shot

        res = AExport.Treat(self)
        if res != var.SUCCESS:
            return res

        if not isinstance(self.ver, str):
            if self.overwrite:
                self.ver = utl.GetLastVersion(self.D.TASK)
            else:
                self.ver = utl.GetNextVersion(self.D.TASK)

        self.dstdir = self.D[self.taskProduct]
        self.master = utl.SJoin(self.dstdir, self.F.MASTER)

        return var.SUCCESS


class MiarmyShotExporter(Export):
    ARGCLASS = AMiarmyShotExporter
    def Arguing(self):
        return var.SUCCESS

    def Tweaking(self):
        return var.SUCCESS

    def Compositing(self):
        cmp.Composite(self.arg.master).DoIt()
        return var.SUCCESS
