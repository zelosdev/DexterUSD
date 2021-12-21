#coding:utf-8
from __future__ import print_function

import DXRulebook as rb
import DXUSD_HOU.Message as msg
import DXUSD.Compositor as cmp

from DXUSD_HOU.Exporters.Export import Export, AExport

import DXUSD_HOU.Tweakers as twk
import DXUSD_HOU.Structures as srt
import DXUSD_HOU.Utils as utl
import DXUSD_HOU.Vars as var
import DXUSD_HOU.PostJobs as post


class AFeatherExporter(AExport):
    def __init__(self, **kwargs):
        # initialize
        AExport.__init__(self, **kwargs)

        # set default values
        self.task        = var.T.GROOM
        self.taskCode    = 'TASKNS'
        self.taskProduct = 'GEOM'
        self.lyrtype     = var.LYRFEATHER

        # add attrs for other layers
        self.geoms = srt.Layers()
        self.geoms.AddLayer('high')
        self.geoms.AddLayer('low')
        self.geoms.AddLayer('guide')

        # dependency attrs
        self.dependRigVer = None
        self.dependOrgFeather  = None
        self.dependHighFeather = None
        self.dependLowFeather  = None

    def Treat(self):
        # ----------------------------------------------------------------------
        # check arguments and source layer
        if not self.CheckSourceLayer(self.taskProduct):
            msg.errmsg('@%s :'%self.__name__,
                       'Failed checking source layer.')
            return var.FAILED

        # feather의 원본 layer는 항상 마스터 layer 경로 하위 폴더안에 들어 있다.
        # 예를 들어, asset일 경우 taskCode가 TASKNVS 이고, 원본 layer는 TASKVNS
        # 경로에, 마스터 layer는 TASKVN 이 된다. 따라서, srclyr를 확인한 이후에는
        # 마지막 S를 제거 한다.
        self.taskCode = self.taskCode[:-1]

        # ----------------------------------------------------------------------
        # set destination layers
        if not self.SetDestinationLayer('MASTER'):
            msg.errmsg('@%s :'%self.__name__,
                       'Failed setting destination layers.')
            return var.FAILED

        # ----------------------------------------------------------------------
        # check sequenced
        if not self.SetSequenced():
            msg.errmsg('@%s :'%self.__name__,
                       'Failed figuring sequenced.')
            return var.FAILED

        # ----------------------------------------------------------------------
        # set other layers

        self.isRigSrc = False
        # check is rig source file or not
        if self.meta.customData.has_key(var.T.CUS_RIGSOURCEFILE):
            rigSrcFile = self.meta.customData[var.T.CUS_RIGSOURCEFILE]
            if rigSrcFile == self.srclyr.realPath:
                self.isRigSrc = True

        path = self.D[self.taskCode]
        if self.isRigSrc:
            file = self.F.groom.RIGSOURCE
            self.geoms[var.T.HIGH] = utl.SJoin(path, file)
        else:
            # high, low, guide geom
            for lod in [var.T.HIGH, var.T.LOW, var.T.GUIDE]:
                self.lod = lod
                file = self.F.groom.LOD
                self.geoms[lod] = utl.SJoin(path, file)

        # ----------------------------------------------------------------------
        # check dependency to set customData.

        rigFile = self.FindRigFile()

        if not rigFile:
            msg.errmsg('@%s :'%self.__name__,
                       'Cannot find rig file')
            # return var.FAILED
        elif rigFile.task == var.T.MODEL:
            args = rigFile.CopyArgs()
            args.task = var.T.RIG
            args.ver = utl.Ver(0)
            self.dependRigVer = utl.FileName(args.F.MAYA.WORK)
        else:
            self.dependRigVer = rigFile.nslyr

        self.meta.customData[var.T.CUS_RIGFILE] = rigFile.file

        # for shot
        if self.sequenced:
            featherFile     = self.FindGroomFile()
            inputCacheFile  = self.FindInputCacheFile()

            # inputCache는 상황에 따라서 없을 수 도 있다. (feather만 따로 나갈경우)
            if not featherFile:
                msg.errmsg('@%s :'%self.__name__,
                           'Cannot find feather file.')
                return var.FAILED

            # find high, low feather lod file for reference
            try:
                high = featherFile.arg.F.LOD
                featherFile.arg.lod = var.T.LOW
                low  = featherFile.arg.F.LOD
                featherFile.arg.pop('lod')

                high = utl.AsLayer(utl.SJoin(featherFile.dirname, high))
                low  = utl.AsLayer(utl.SJoin(featherFile.dirname, low))
                if not high or not low:
                    raise Exception('Feather layer does not exist (%s)'%high)

                prim = high.GetPrimAtPath('/Groom')

                # find prim has the reference
                for p in prim.nameChildren:
                    lam = p.nameChildren[0] if p.nameChildren else None
                    if not lam or not lam.referenceList.prependedItems:
                        continue
                    else:
                        org  = lam.referenceList.prependedItems[0].assetPath
                        org  = high.FindRelativeToLayer(high, org)
                        if not org:
                            continue
                        else:
                            break

            except Exception as e:
                msg.errmsg(e)
                msg.errmsg('@%s :'%self.__name__,
                           'Failed finding feahter layers.')
                return var.FAILED

            self.dependOrgFeather  = org
            self.dependHighFeather = high
            self.dependLowFeather  = low

            self.meta.customData[var.T.CUS_INPUTCACHE] = inputCacheFile.file
            self.meta.customData[var.T.CUS_FEATHERFILE] = featherFile.file

        return var.SUCCESS


class FeatherExporter(Export):
    ARGCLASS = AFeatherExporter

    def Arguing(self):
        # cmArg gets prims from srclyr, fmArg is from asset feather layer
        sequenced = self.arg.sequenced

        self.cmArg = twk.ACombineLayers(**self.arg.AsDict())
        self.cmArg.inputs.Append(self.arg.srclyr)
        if sequenced:
            self.cmArg.inputs.Append(self.arg.dependOrgFeather)

        self.cmArg_high = twk.ACombineLayers(**self.cmArg.AsDict())
        self.cmArg_high.rules.append(['Laminations', None])
        self.cmArg_high.rules.append(['/.*/Feather', None, sequenced])
        self.cmArg_high.outputs.Append(self.arg.geoms[var.T.HIGH])

        if not self.arg.isRigSrc:
            self.cmArg_high.rules.append(['Laminations', None])
            self.cmArg_high.rules.append(['/.*/Feather', None, sequenced])
            self.cmArg_high.outputs.Append(self.arg.geoms[var.T.HIGH])

            self.cmArg_low = twk.ACombineLayers(**self.cmArg.AsDict())
            self.cmArg_low.rules.append(['Proxy=Laminations', None])
            self.cmArg_low.rules.append(['/.*/Feather', None, sequenced])
            self.cmArg_low.outputs.Append(self.arg.geoms[var.T.LOW])

            self.cmArg_guide = twk.ACombineLayers(**self.cmArg.AsDict())
            self.cmArg_guide.rules.append(['Guides', None])
            self.cmArg_guide.outputs.Append(self.arg.geoms[var.T.GUIDE])

            if sequenced:
                self.smArg_high = twk.AAddSublayers()
                self.smArg_high.inputs.Append(self.arg.dependHighFeather)
                self.smArg_high.outputs.Append(self.arg.geoms[var.T.HIGH])

                self.smArg_low = twk.AAddSublayers(**self.arg)
                self.smArg_low.inputs.Append(self.arg.dependLowFeather)
                self.smArg_low.outputs.Append(self.arg.geoms[var.T.LOW])

        self.mArg = twk.AMasterFeather(**self.arg)
        self.mArg.inputs.high  = self.arg.geoms.high
        self.mArg.inputs.low   = self.arg.geoms.low
        self.mArg.inputs.guide = self.arg.geoms.guide
        self.mArg.outputs.Append(self.arg.dstlyr)
        self.mArg.sequenced = sequenced
        self.mArg.isRigSrc = self.arg.isRigSrc

        return var.SUCCESS


    def Tweaking(self):
        # Packing
        twks = twk.Tweak()

        twks << twk.CombineLayers(self.cmArg_high)

        if not self.arg.isRigSrc:
            twks << twk.CombineLayers(self.cmArg_low)

            if self.arg.sequenced:
                twks << twk.AddSublayers(self.smArg_high)
                twks << twk.AddSublayers(self.smArg_low)
            else:
                twks << twk.CombineLayers(self.cmArg_guide)

            # twks << twk.CorrectBasisCurves(self.cbArg)

        twks << twk.MasterFeather(self.mArg)

        twks.DoIt()

        # # Shadering
        # twks = twk.Tweak()
        # for fn in self.texData:
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

        return var.SUCCESS


    def Compositing(self):
        cmp.Composite(self.arg.dstlyr).DoIt()
        return var.SUCCESS
