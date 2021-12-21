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
#   Groom Asset
#
#-------------------------------------------------------------------------------
class AGroomAssetExporter(AExport):
    def __init__(self, **kwargs):
        # input argument
        self.scene = ''
        self.node  = ''             # node type is dxBlock
        self.bodyMeshLayerData = {} # {shapename: [ZN_Deform, ...]}
        self.groom_nodes = []

        # treat compute
        self.org_show = ''          # for MTK
        self.dstdir = ''
        self.master = ''
        self.groom_outs = []
        self.geomfiles  = []

        # exporter compute
        self.rigFile = ''   # base rig file
        self.customData = {}
        self.bodyMeshAttrData = {}    # {shapename: {txBasePath: '', txLayerName: '', modelVer: ''}}
        self.groomAttrData = {}
        # {
        #   ZN_Deform: {
        #       'userProperties:MaterialSet': {'value': '', 'type': ''},
        #       usdattrname: {'value': attr value, 'type': attr type}
        #   },
        #   ...
        # }

        # initialize
        AExport.__init__(self, **kwargs)

        self.taskProduct = 'TASKN'

    def Treat(self):
        if self.node:
            self.N.groom.SetDecode(self.node, 'ASSET')
        else:
            self.N.model.SetDecode(self.mtkNode, 'ASSET')
            self.task = 'groom'

        self.D.SetDecode(utl.DirName(self.scene), 'SHOW')
        self.nslyr = utl.BaseName(self.scene).split('.')[0]

        # override show
        if self.has_attr('ovr_show'):
            if var.T.ASSETLIB3D == self.ovr_show:
                self.customdir = self.ovr_show
            else:
                self.show = self.ovr_show

        # seq or shot asset
        if self.has_attr('ovr_shot'): self.N.SetDecode(self.ovr_shot, 'SHOTNAME')

        res = AExport.Treat(self)
        if res != var.SUCCESS:
            return res

        # for MTK
        if self.customdir:
            self.org_show = self.show
            if not var.T.ASSETLIB3D == self.customdir:
                self.ver = 'v000'
            self.pop('show')

        self.dstdir = self.D[self.taskProduct]
        self.master = utl.SJoin(self.dstdir, self.F.MASTER)

        for s in self.groom_nodes:
            self.subdir = s
            self.groom_outs.append(utl.SJoin(self.D.TASKNS, self.subdir))

        hgeom = self.master.replace('.usd', '.high.usd')
        lgeom = self.master.replace('.usd', '.low.usd')
        self.geomfiles = [hgeom, lgeom]

        return var.SUCCESS

class GroomAssetExporter(Export):
    ARGCLASS = AGroomAssetExporter
    def Arguing(self):
        self.texData   = dict()                   # CombineGroomLayers result for texture process
        self.meshFiles = list()

        self.cmArg = twk.ACombineGroomLayers(**self.arg.AsDict())   # CombineGroomLayers arguments

        self.gArg = twk.AGeomAttrs()
        self.gArg.extract = [var.T.ATTR_MATERIALSET]

        self.tArg = twk.ATexture()              # Texture, ProxyMaterial arguments
        self.pArg = twk.APrmanMaterial()        # PrmanMaterial arguments
        self.pArg.inputs = self.arg.geomfiles
        self.cArg = twk.ACollection()           # Collection arguments
        self.cArg.master = self.arg.master

        if self.arg.org_show:
            self.cmArg.ovr_show = self.arg.org_show
            self.pArg.ovr_show = self.arg.org_show
            self.gArg.ovr_show = self.arg.org_show

        return var.SUCCESS

    def Tweaking(self):
        # 1
        twks = twk.Tweak()
        twks << twk.CombineGroomLayers(self.cmArg, self.texData, self.meshFiles)    # create
        twks << twk.MasterGroomPack(self.arg)                       # master groom package
        twks.DoIt()

        # 2 : if ZN_FeatherInstance
        if self.meshFiles:
            if msg.DEV:
                print('>>> Result Groom Mesh :')
                pprint.pprint(self.meshFiles, width=20)

            self.gArg.inputs = self.meshFiles
            twks = twk.Tweak()
            twks << twk.GeomAttrs(self.gArg, self.texData)
            twks.DoIt()

        if msg.DEV:
            print('>>> Result texData :')
            pprint.pprint(self.texData, width=20)

        # 3
        twks = twk.Tweak()
        for fn in self.texData:
            self.tArg.texAttrUsd = fn
            self.tArg.texData    = self.texData[fn]

            twks << twk.Texture(self.tArg)          # create or update tex.attr.usd
            twks << twk.ProxyMaterial(self.tArg)    # create or update proxy.mtl.usd

        twks << twk.PrmanMaterial(self.pArg)        # create prman material
        twks << twk.GroomLayerCompTex(self.cmArg)   # composite tex.usd by assetInfo

        if self.meshFiles:
            twks << twk.GeomAttrsCompTex(self.gArg)

        twks << twk.Collection(self.cArg)           # create collection by master
        twks.DoIt()
        return var.SUCCESS

    def Compositing(self):
        cmp.Composite(self.arg.master).DoIt()
        return var.SUCCESS



#-------------------------------------------------------------------------------
#
#   Groom Shot
#
#-------------------------------------------------------------------------------
class AGroomShotExporter(AExport):
    def __init__(self, **kwargs):
        '''
        override options
            ovr_show, ovr_seq, ovr_shot, ovr_ver
        '''
        # input argument
        self.inputcache = ''
        self.groomfile  = ''        # if not, find by inputcache
        self.overwrite  = False
        self.step   = 1.0
        self.autofr = True
        self.mergeCache  = False    # groom cache with static and dynamic
        self.frameRange  = [0, 0]   # scene just duration. export to +,- 1 offset.
        self.exportRange = [0, 0]   # real export range

        self.node    = ''   # ???

        # treat compute
        self.master = ''

        # exporter compute
        self.customData  = {}

        self.rigNode = ''               # fullpath. if MergeExport
        self.bodyMeshLayerData = {}     # {shapename: [ZN_Deform, ...]}
        self.groomAttrData = {}
        self.groom_nodes = []
        self.groom_outs  = []
        self.groom_reference  = {}      # asset collect-geom file. {'high': filename, 'low': filename}
        self.groom_collection = ''
        self.geomfiles = []

        # initialize
        AExport.__init__(self, **kwargs)

        # attributes
        self.task = 'groom'
        self.taskProduct = 'TASKNV'

    def Treat(self):
        # CacheMerge Process
        if self.inputcache:
            self.D.SetDecode(utl.DirName(self.inputcache))
            self.nsver = None
        # hairSim Process
        else:
            self.D.SetDecode(utl.DirName(self.groomfile))
            self.pop('departs')

        self.task = 'groom'

        # override show, seq, shot
        if self.has_attr('ovr_show'): self.show = self.ovr_show
        if self.has_attr('ovr_seq'):  self.seq  = self.ovr_seq
        if self.has_attr('ovr_shot'): self.shot = self.ovr_shot
        if self.has_attr('ovr_ver'):  self.nsver= self.ovr_ver

        if not isinstance(self.nsver, str):
            if self.overwrite:
                self.nsver = utl.GetLastVersion(self.D.TASKN)
            else:
                self.nsver = utl.GetNextVersion(self.D.TASKN)

        res = AExport.Treat(self)
        if res != var.SUCCESS:
            return res

        self.dstdir = self.D[self.taskProduct]
        self.master = utl.SJoin(self.dstdir, self.F.MASTER)

        return var.SUCCESS


class GroomShotExporter(Export):
    ARGCLASS = AGroomShotExporter
    def Arguing(self):
        if self.arg.simExport:
            self.cArg = twk.ACollection()  # Collection arguments
            self.cArg.master = self.arg.master
            self.cArg.inputRigFile = self.arg.inputRigFile

        return var.SUCCESS

    def Tweaking(self):
        twks = twk.Tweak()
        twks << twk.CombineGroomLayers(self.arg)
        twks << twk.MasterGroomPack(self.arg)
        twks.DoIt()

        if self.arg.simExport:
            twks = twk.Tweak()
            twks << twk.Collection(self.cArg)  # create collection by master
            twks.DoIt()

        return var.SUCCESS

    def Compositing(self):
        cmp.Composite(self.arg.master).DoIt()
        return var.SUCCESS
