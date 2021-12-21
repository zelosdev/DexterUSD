#coding:utf-8
from __future__ import print_function
import os, glob, re

from pxr import Sdf, Usd, UsdGeom

from .Tweaker import Tweaker, ATweaker
from DXUSD.Structures import Arguments
import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg


class AClipGeomPack(ATweaker):
    def __init__(self, **kwargs):
        '''
        [Arguments]
        output (str) : CLIP.F.CLIP
        '''
        # initialize
        ATweaker.__init__(self, **kwargs)

        self.geomfiles = []     # *_rig.usd, *_groom.usd

    def Treat(self):
        if not self.output:
            msg.error('Treat@%s' % self.__name__, 'Not found output argument.')

        self.D.SetDecode(utl.DirName(self.output))

        self.dstdir = utl.DirName(self.output)

        # rig, groom geom
        for suffix in ['*_rig.usd', '*_groom.usd']:
            files = glob.glob(self.dstdir + '/' + suffix)
            self.geomfiles += files

        if not self.geomfiles:
            return var.IGNORE

        return var.SUCCESS

class ClipGeomPack(Tweaker):
    ARGCLASS = AClipGeomPack
    def DoIt(self):
        dstlyr = utl.AsLayer(self.arg.output, create=True, clear=True)
        dstlyr.defaultPrim = self.arg.assetName

        for f in self.arg.geomfiles:
            utl.SubLayersAppend(dstlyr, './' + utl.BaseName(f))
            utl.UpdateLayerData(dstlyr, f).doIt()

        dstlyr.Save()
        del dstlyr

        return var.SUCCESS


class AMasterClipPack(ATweaker):
    def __init__(self, **kwargs):
        '''
        [Arguments]
        master (str) : CLIP.F.MASTER
        '''
        # initialize
        ATweaker.__init__(self, **kwargs)

        self.timeLayers = []    # ['0_8', '1_0', ...] timeScale Layers

    def Treat(self):
        if not self.master:
            msg.error('Treat@%s' % self.__name__, 'Not found master argument')

        self.D.SetDecode(utl.DirName(self.master))

        self.dstdir = utl.DirName(self.master)

        # timeScale Layers
        for d in os.listdir(self.dstdir):
            if os.path.isdir(utl.SJoin(self.dstdir, d)):
                if re.match('[0-9]+_[0-9]+', d):
                    self.timeLayers.append(d)

        if not self.timeLayers:
            msg.error('Treat@%s' % self.__name__, 'Not found timeScale Layers.')

        return var.SUCCESS

class MasterClipPack(Tweaker):
    ARGCLASS = AMasterClipPack
    def DoIt(self):
        dstlyr = utl.AsLayer(self.arg.master, create=True, clear=True)
        dstlyr.defaultPrim = self.arg.assetName

        starttimes = []
        endtimes   = []

        spec = utl.GetPrimSpec(dstlyr, '/' + self.arg.assetName)
        for name in self.arg.timeLayers:
            filename = utl.SJoin(self.arg.dstdir, name, name + '.usd')
            utl.UpdateLayerData(dstlyr, filename).timecode()
            # update times
            starttimes.append(dstlyr.startTimeCode)
            endtimes.append(dstlyr.endTimeCode)
            # variant setup
            vsetSpec = utl.GetVariantSetSpec(spec, var.T.VAR_TIMESCALE)
            vspec = utl.GetVariantSpec(vsetSpec, name)
            spec.variantSelections.update({var.T.VAR_TIMESCALE: name})
            # arc
            utl.ReferenceAppend(vspec.primSpec, utl.GetRelPath(self.arg.master, filename))

        starttimes.sort()
        endtimes.sort()
        dstlyr.startTimeCode = starttimes[0]
        dstlyr.endTimeCode = endtimes[-1]

        with utl.OpenStage(dstlyr) as stage:
            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)

        dstlyr.Save()
        del dstlyr
        return var.SUCCESS
