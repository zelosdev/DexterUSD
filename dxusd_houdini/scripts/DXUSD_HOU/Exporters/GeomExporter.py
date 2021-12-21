#coding:utf-8
from __future__ import print_function

from pxr import Sdf

import DXRulebook as rb
import DXUSD_HOU.Message as msg
import DXUSD.Compositor as cmp
from DXUSD.Structures import Arguments

from DXUSD_HOU.Exporters.Export import Export, AExport

import DXUSD_HOU.Tweakers as twk
import DXUSD_HOU.Structures as srt
import DXUSD_HOU.Utils as utl
import DXUSD_HOU.Vars as var

import os
import shutil


class AGeomExporter(AExport):
    def __init__(self, **kwargs):
        # initialize
        AExport.__init__(self, **kwargs)

        # set default values
        self.task        = var.T.MODEL
        self.taskCode    = 'TASKVS'
        self.taskProduct = 'GEOM'
        self.lyrtype     = var.LYRGEOM

        # add attrs for other layers
        self.geoms = srt.Layers()
        self.geoms.AddLayer('high')
        self.geoms.AddLayer('low')
        self.geoms.AddLayer('guide')

        # dependency attrs
        self.dependRigVer = None
        self.dependOrgGroom  = None
        self.dependHighGroom = None
        self.dependLowGroom  = None


    def Treat(self):
        # ----------------------------------------------------------------------
        # check arguments and source layer
        if not self.CheckSourceLayer(self.taskProduct):
            msg.errmsg('Failed "CheckSourceLayer"')
            return var.FAILED
        self.taskCode = self.taskCode[:-1]
        # ----------------------------------------------------------------------
        # set destination layers
        if not self.SetDestinationLayer('MASTER'):
            msg.errmsg('Failed "SetDestinationLayer"')
            return var.FAILED

        # ----------------------------------------------------------------------
        # check sequenced
        if not self.SetSequenced():
            msg.errmsg('Failed "SetSequenced"')
            return var.FAILED



        # ----------------------------------------------------------------------
        # set other layers
        # high, low, guide geom

        # find high, low, guide prim to set LOD
        if not self.LODs:
            self.LODs = [var.T.HIGH]

        for lod in self.LODs:
            self.lod = lod
            path = self.D[self.taskCode]
            if self.task == var.T.MODEL:
                file = self.F[self.task].LOD
            else:
                file = self.F[self.task].GEOM

            self.geoms[lod] = utl.SJoin(path, file)

        # ----------------------------------------------------------------------
        # set default prim

        if self.sequenced:
            if self.nslyr:
                self.dprim = Sdf.Path('/%s'%self.nslyr)
            else:
                msg.errmsg('Cannot find defaultPrim')
                return var.FAILED
        else:
            self.dprim = Sdf.Path('/Geom')

        return var.SUCCESS



class GeomExporter(Export):
    ARGCLASS = AGeomExporter

    def Arguing(self):
        # combines
        self.cmArg = twk.ACombineLayers(**self.arg.AsDict())
        self.cmArg.inputs.Append(self.arg.srclyr)

        self.cmArgs = dict()
        for lod in self.arg.LODs:
            self.cmArgs[lod] = twk.ACombineLayers(**self.cmArg.AsDict())
            print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>self.arg.subdir:',self.arg.subdir)
            s = "(/.*/(Geom|Render|Proxy))|(/Geom/%s/%s)"%(lod, str(self.arg.subdir))
            #s = "(/.*/(Geom|Render))|(/Geom/%s/%s)|(/%s/*)" % (lod, str(self.arg.subdir), str(self.arg.dprim))
            d = '/.' if self.arg.sequenced else '/'
            self.cmArgs[lod].rules.append([s, d])
            self.cmArgs[lod].outputs.Append(self.arg.geoms[lod])
            self.cmArgs[lod].flatten = True
            self.arg.flattenlyrs.append(self.arg.geoms[lod])

        # dxusd
        self.texData    = dict()
        self.mArg = twk.AMasterPack(**self.arg)
        self.tArg = twk.ATexture()

        if self.arg.sequenced:
            self.gArg = twk.AGeomRigAttrs()

            if self.arg.IsShot():
                self.mArg.master = utl.SJoin(self.arg.D[self.arg.taskCode],
                                             self.arg.F.MASTER)
            else:
                _task = self.arg.task
                self.mArg.master = utl.SJoin(self.arg.D[self.arg.taskCode],
                                             self.arg.F.rig.MASTER)
                self.arg.task = _task
        else:
            self.gArg = twk.AGeomAttrs()
            self.mArg.master = self.arg.dstlyr

        self.gArg.inputs = [_.outputs[0] for _ in self.cmArgs.values()]

        # self.mArg.dstdir = utl.DirName(self.cmArg_high.outputs[0])
        self.mArg.geomfiles = [_.outputs[0] for _ in self.cmArgs.values()]

        # delete source layers
        self.rmArg = twk.ARemoveLayers()
        self.rmArg.inputs.Append(self.arg.srclyr)

        return var.SUCCESS


    def Tweaking(self):
        # ----------------------------------------------------------------------
        # Combining
        twks = twk.Tweak()
        for arg in self.cmArgs.values():
            twks << twk.CombineLayers(arg)

        # ----------------------------------------------------------------------
        # Mastering
        if self.arg.sequenced:
            cliptwks = twk.Tweak()
            if self.arg.simprc:
                cliptwks << twk.MasterSimPack(self.mArg)
            else:
                if self.arg.FindRigFile():
                    twks << twk.GeomRigAttrs(self.gArg)

                cliptwks << twk.MasterRigPack(self.mArg)
                cliptwks << twk.PrmanMaterialOverride(self.mArg)

            if self.AddClipPack(cliptwks) == var.FAILED:
                return var.FAILED

            twks << cliptwks
        else:
            twks << twk.GeomAttrs(self.gArg, self.texData)
            twks << twk.MasterModelPack(self.mArg)

        twks << twk.RemoveLayers(self.rmArg)
        twks.DoIt()

        # ----------------------------------------------------------------------
        # material tweaks for model task
        if self.arg.task == var.T.MODEL:
            twks = twk.Tweak()
            for fn in self.texData:
                self.tArg.texAttrUsd = fn
                self.tArg.texData = self.texData[fn]
                # create or update tex.attr.usd
                twks << twk.Texture(self.tArg)
                # create or update proxy.mtl.usd
                twks << twk.ProxyMaterial(self.tArg)

            # create prman material
            twks << twk.PrmanMaterial(self.gArg)
            twks << twk.GeomAttrsCompTex(self.gArg)
            twks << twk.Collection(self.mArg)
            twks << twk.PrmanMaterialOverride(self.mArg)
            twks.DoIt()

        return var.SUCCESS


    def Compositing(self):
        cmp.Composite(self.arg.dstlyr).DoIt()
        return var.SUCCESS