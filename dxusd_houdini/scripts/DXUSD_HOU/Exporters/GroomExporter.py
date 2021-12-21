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




class AGroomExporter(AExport):
    def __init__(self, **kwargs):
        # initialize
        AExport.__init__(self, **kwargs)

        # set default values
        self.task        = var.T.GROOM
        self.taskCode    = 'TASKNS'
        self.taskProduct = 'GEOM'
        self.lyrtype     = var.LYRGROOM

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
            return var.FAILED

        # feather의 원본 layer는 항상 마스터 layer 경로 하위 폴더안에 들어 있다.
        # 예를 들어, asset일 경우 taskCode가 TASKNVS 이고, 원본 layer는 TASKVNS
        # 경로에, 마스터 layer는 TASKVN 이 된다. 따라서, srclyr를 확인한 이후에는
        # 마지막 S를 제거 한다.
        self.taskCode = self.taskCode[:-1]

        # ----------------------------------------------------------------------
        # set destination layers
        if not self.SetDestinationLayer('MASTER'):
            return var.FAILED

        # ----------------------------------------------------------------------
        # check sequenced
        if not self.SetSequenced():
            return var.FAILED

        # ----------------------------------------------------------------------
        # set other layers
        # high, low, guide geom
        for lod in [var.T.HIGH, var.T.LOW, var.T.GUIDE]:
            self.lod = lod
            path = self.D[self.taskCode]
            file = self.F.groom.LOD
            self.geoms[lod] = utl.SJoin(path, file)

        # ----------------------------------------------------------------------
        # check dependency to set customData.

        rigFile = self.FindRigFile()

        if not rigFile:
            return var.FAILED
        elif rigFile.task == var.T.MODEL:
            args = rigFile.CopyArgs()
            args.task = var.T.RIG
            args.ver = utl.Ver(0)
            self.dependRigVer = utl.FileName(args.F.MAYA.WORK)
        else:
            self.dependRigVer = rigFile.nslyr

        self.meta.customData[var.T.CUS_RIGFILE] = rigFile.file

        # ----------------------------------------------------------------------
        # set default prim
        if self.srclyr.defaultPrim:
            self.dprim = Sdf.Path('/%s'%self.srclyr.defaultPrim)
        elif self.srclyr.rootPrims:
            self.dprim = self.srclyr.rootPrims[0].path
        else:
            msg.errmsg('Cannot find defaultPrim')
            return var.FAILED

        customData = utl.AsLayer(self.srclyr).customLayerData
        sceneFile = customData[var.T.CUS_SCENEFILE]


        # for shot
        if self.sequenced:
            groomFile     = self.FindGroomFile()
            inputCacheFile = self.FindInputCacheFile()
            if not groomFile:
                return var.FAILED

            # find high, low feather lod file for reference
            try:
                high = groomFile.arg.F.LOD
                groomFile.arg.lod = var.T.LOW
                low  = groomFile.arg.F.LOD
                groomFile.arg.pop('lod')

                high = utl.AsLayer(utl.SJoin(groomFile.dirname, high))
                low  = utl.AsLayer(utl.SJoin(groomFile.dirname, low))
                if not high or not low:
                    raise Exception('Groom layer does not exist (%s)'%high)

                prim = high.GetPrimAtPath('/Groom')
                prim = prim.nameChildren[0]
                org  = prim.referenceList.prependedItems[0].assetPath
                # org  = high.FindRelativeToLayer(high, org)
                # print('high:', high)
                # print('org:', org)

            except Exception as e:
                msg.errmsg(e)
                msg.errmsg('Failed finding groom layers.')
                return var.FAILED

            # self.dependOrgGroom  = org
            self.dependHighGroom = high
            self.dependLowGroom  = low

            self.meta.customData[var.T.CUS_INPUTCACHE] = inputCacheFile.file
            self.meta.customData[var.T.CUS_GROOMFILE] = customData[var.T.CUS_GROOMFILE]

        #for asset
        else:
            self.SceneExport(sceneFile)


        return var.SUCCESS


    def SceneExport(self, sceneFile):
        # publish hip file
        arg = Arguments()
        arg.D.SetDecode(utl.DirName(self.FindRigFile().file))
        arg.task = 'groom'
        pubSceneFile = utl.SJoin(arg.D.TASK, 'scenes', self.nslyr + '.hip')


        if not os.path.exists(utl.DirName(pubSceneFile)):
            os.mkdir(utl.DirName(pubSceneFile))

        if os.path.exists(pubSceneFile):
            os.remove(pubSceneFile)

        shutil.copy(sceneFile, pubSceneFile)
        os.chmod(pubSceneFile, 0555)



class GroomExporter(Export):
    ARGCLASS = AGroomExporter

    def Arguing(self):

        # cmArg gets prims from srclyr, fmArg is from asset feather layer
        self.cmArg = twk.ACombineLayers(**self.arg.AsDict())
        self.cmArg.inputs.Append(self.arg.srclyr)

        # if self.arg.sequenced:
        #     self.cmArg.inputs.Append(self.arg.dependOrgGroom)

        self.cmArg_high = twk.ACombineLayers(**self.cmArg.AsDict())
        # self.cmArg_high.rules.append(['/.*/high/.*', self.arg.dprim, self.arg.sequenced])
        self.cmArg_high.rules.append(['/.*/high/.*', self.arg.dprim])
        self.cmArg_high.outputs.Append(self.arg.geoms[var.T.HIGH])

        self.cmArg_low = twk.ACombineLayers(**self.cmArg.AsDict())
        # self.cmArg_low.rules.append(['/.*/low/.*', self.arg.dprim, self.arg.sequenced])
        self.cmArg_low.rules.append(['/.*/low/.*', self.arg.dprim])
        self.cmArg_low.outputs.Append(self.arg.geoms[var.T.LOW])

        self.cmArg_guide = twk.ACombineLayers(**self.cmArg.AsDict())
        self.cmArg_guide.rules.append(['/.*/guides/.*', self.arg.dprim])
        self.cmArg_guide.outputs.Append(self.arg.geoms[var.T.GUIDE])

        self.mArg = twk.AMasterGroomPack(**self.arg)
        self.mArg.master= self.arg.dstlyr

        if self.arg.sequenced:
            self.smArg_high = twk.AAddSublayers()
            self.smArg_high.inputs.Append(self.arg.dependHighGroom)
            self.smArg_high.outputs.Append(self.arg.geoms[var.T.HIGH])

            self.smArg_low = twk.AAddSublayers(**self.arg)
            self.smArg_low.inputs.Append(self.arg.dependLowGroom)
            self.smArg_low.outputs.Append(self.arg.geoms[var.T.LOW])

        self.texData = dict()
        # self.tArg = twk.ATexture()              # Texture, ProxyMaterial arguments
        self.pArg = twk.APrmanMaterial()        # PrmanMaterial arguments
        self.pArg.inputs = [self.cmArg_high.outputs[0],self.cmArg_low.outputs[0]]
        self.cArg = twk.ACollection()           # Collection arguments
        self.cArg.master = self.arg.dstlyr

        return var.SUCCESS


    def Tweaking(self):
        # Packing
        twks = twk.Tweak()
        twks << twk.CombineLayers(self.cmArg_high)
        twks << twk.CombineLayers(self.cmArg_low)

        if self.arg.sequenced:
            twks << twk.AddSublayers(self.smArg_high)
            twks << twk.AddSublayers(self.smArg_low)
        else:
            twks << twk.CombineLayers(self.cmArg_guide)

        # twks << twk.CorrectBasisCurves(self.cbArg)
        for arg in [self.cmArg_high,self.cmArg_low]:
            twks << twk.HCombineGroomLayers(arg, self.texData)
        twks << twk.MasterGroomPack(self.mArg)
        twks.DoIt()

        # Shader
        twks = twk.Tweak()
        twks << twk.PrmanMaterial(self.pArg)
        # twks << twk.GroomLayerCompTex(self.cmArg)
        twks << twk.Collection(self.cArg)
        twks.DoIt()

        # # Shadering
        # twks = twk.Tweak()
        # print('self.texData:',self.texData)
        # for fn in self.texData:
        #
        #     self.tArg.texAttrUsd = fn
        #     self.tArg.texData    = self.texData[fn]
        #
        #     twks << twk.Texture(self.tArg)          # create or update tex.attr.usd
        #     twks << twk.ProxyMaterial(self.tArg)    # create or update proxy.mtl.usd
        #
        # twks << twk.PrmanMaterial(self.pArg)        # create prman material
        # # twks << twk.GroomLayerCompTex(self.cmArg)   # composite tex.usd by assetInfo
        # twks << twk.GeomAttrsCompTex(self.gArg)
        # twks << twk.Collection(self.cArg)           # create collection by master
        #
        # twks.DoIt()
        #print('//////////////////////////self.cmArg_high',self.cmArg_high)

        return var.SUCCESS


    def Compositing(self):
        cmp.Composite(self.arg.dstlyr).DoIt()
        return var.SUCCESS
