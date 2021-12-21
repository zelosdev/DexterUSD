#coding:utf-8
from __future__ import print_function

import re

import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg
import DXUSD.Structures as srt

from .Tweaker import Tweaker, ATweaker

from pxr import Sdf, Usd


class AMasterFeather(ATweaker):
    def __init__(self, **kwargs):
        self.sequenced = False
        self.isRigSrc  = False

        ATweaker.__init__(self, **kwargs)

        self.inputs.AddLayer('high')
        self.inputs.AddLayer('low')
        self.inputs.AddLayer('guide')


    def Treat(self):
        if not (self.inputs and self.outputs):
            msg.errmsg('Set inputs and outputs')
            return var.FAILED

        return var.SUCCESS


class MasterFeather(Tweaker):
    ARGCLASS = AMasterFeather

    def DoIt(self):
        dstlyr = utl.AsLayer(self.arg.outputs[0], create=True)
        utl.UpdateLayerData(dstlyr, self.arg.inputs[0]).doIt(up=True)

        if self.arg.sequenced:
            dprim = '/%s'%self.arg.nslyr
        else:
            dprim = '/%s'%self.arg.ABName()

        dprim = utl.GetPrimSpec(dstlyr, dprim)
        dprim.kind = var.KIND.ASB
        dprim.asseteInfo = {'name':dprim.name}
        dstlyr.defaultPrim = dprim.name

        # collection layer
        if not self.arg.sequenced:
            dirname = utl.DirName(self.arg.outputs[0])
            collyr = utl.AsLayer(utl.SJoin(dirname, self.arg.F.COLLECTION))
            if collyr:
                utl.AddCustomData(dprim, 'groupName', dprim.name)

        # create children
        rootName = utl.FirstUpper(var.T.GROOM)
        feather = utl.GetPrimSpec(dstlyr, dprim.path.AppendChild(rootName))
        feather.kind = var.KIND.COM

        if self.arg.isRigSrc:
            # render
            spec = utl.GetPrimSpec(dstlyr, feather.path.AppendChild('Render'))
            path = utl.GetRelPath(dstlyr.realPath, self.arg.inputs.high)
            vset = utl.GetVariantSetSpec(spec, 'rigSource')
            vspec = utl.GetVariantSpec(vset, 'off')
            spec.variantSelections['rigSource'] = 'off'
            vspec = utl.GetVariantSpec(vset, 'on')
            utl.PayloadAppend(vspec.primSpec, path)

        else:
            # render
            spec = utl.GetPrimSpec(dstlyr, feather.path.AppendChild('Render'))
            path = utl.GetRelPath(dstlyr.realPath, self.arg.inputs.high)
            utl.PayloadAppend(spec, path)
            utl.SetPurpose(spec, 'render')

            # proxy
            spec = utl.GetPrimSpec(dstlyr, feather.path.AppendChild('Proxy'))
            path = utl.GetRelPath(dstlyr.realPath, self.arg.inputs.low)
            utl.PayloadAppend(spec, path)
            utl.SetPurpose(spec, 'proxy')

            # guide
            if not self.arg.sequenced:
                spec = feather.path.AppendChild('Guide')
                spec = utl.GetPrimSpec(dstlyr, spec)
                path = utl.GetRelPath(dstlyr.realPath, self.arg.inputs.guide)
                utl.PayloadAppend(spec, path)
                utl.SetPurpose(spec, 'guide')

        # ----------------------------------------------------------------------
        # Save layer
        dstlyr.Save()
        del dstlyr
