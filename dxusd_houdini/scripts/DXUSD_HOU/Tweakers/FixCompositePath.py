#coding:utf-8
from __future__ import print_function
import os

from pxr import Sdf, Usd

import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD_HOU.Message as msg
from DXUSD.Tweakers import Tweaker, ATweaker

from DXUSD_HOU.Structures import Arguments


class AFixCompositePath(ATweaker):
    def __init__(self, **kwargs):
        ATweaker.__init__(self, **kwargs)

    def Treat(self):
        if not self.inputs:
            msg.warning('No inputs')
            return var.IGNORE
        return var.SUCCESS


class FixCompositePath(Tweaker):
    ARGCLASS = AFixCompositePath
    def DoIt(self):
        for input in self.arg.inputs:
            lyr = utl.AsLayer(input)
            if not lyr:
                continue

            # check sublayer path
            for i in range(len(lyr.subLayerPaths)):
                lyr.subLayerPaths[i] = self.FixPath(lyr.subLayerPaths[i])

            for prim in lyr.rootPrims:
                self.DoFixAllPaths(prim)

            lyr.Save()

        return var.SUCCESS

    def FixPath(self, path):
        if var.T.ASSETLIB in path:
            path = utl.SJoin(var.T.ASSETLIB, path.split(var.T.ASSETLIB)[-1])
        return path

    def DoFixAllPaths(self, prim):
        # fix references
        for ref in prim.referenceList.GetAddedOrExplicitItems():
            if var.T.ASSETLIB in ref.assetPath:
                _path = ref.assetPath.split(var.T.ASSETLIB)[-1]
                _path = utl.SJoin(var.T.ASSETLIB, _path)
                _ref  = Sdf.Reference(_path,
                                     ref.primPath,
                                     ref.layerOffset,
                                     ref.customData)
                prim.referenceList.ReplaceItemEdits(ref, _ref)

        # fix payloads
        for pay in prim.payloadList.GetAddedOrExplicitItems():
            if var.T.ASSETLIB in pay.assetPath:
                _path = pay.assetPath.split(var.T.ASSETLIB)[-1]
                _path = utl.SJoin(var.T.ASSETLIB, _path)
                _pay  = Sdf.Reference(_path,
                                      pay.primPath,
                                      pay.layerOffset)
                prim.payloadList.ReplaceItemEdits(pay, _pay)

        for child in prim.nameChildren:
            self.DoFixAllPaths(child)






















#
