#coding:utf-8
from __future__ import print_function

import re

import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg
import DXUSD.Structures as srt

from .Tweaker import Tweaker, ATweaker

from pxr import Sdf, Usd


class AAddSublayers(ATweaker):
    def __init__(self, **kwargs):
        self.clear = True
        ATweaker.__init__(self, **kwargs)


    def Treat(self):
        if not (self.inputs and self.outputs):
            msg.errmsg('Set inputs and outputs')
            return var.FAILED

        return var.SUCCESS


class AddSublayers(Tweaker):
    ARGCLASS = AAddSublayers

    def DoIt(self):
        sublyrs = []
        for sublyr in self.arg.inputs:
            sublyrs.append(utl.AsLayer(sublyr))

        sublyrs.reverse()

        for dstlyr in self.arg.outputs:
            dstlyr = utl.AsLayer(dstlyr, create=True)

            if self.arg.clear:
                dstlyr.subLayerPaths.clear()

            for sublyr in sublyrs:
                utl.SetSublayer(dstlyr, sublyr)

            dstlyr.Save()

        return var.SUCCESS
