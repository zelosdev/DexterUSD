#coding:utf-8
from __future__ import print_function
import os

from pxr import Sdf, Usd

from .Tweaker import Tweaker, ATweaker

import DXUSD.Arcs as arc
import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg


class AExample_RefereceToXform(ATweaker):
    '''
    [Input Layers]
    0-input (str) : input layer

    [Output Layers]
    0-output (str): output layer
    '''
    def __init__(self, **kwargs):
        # initialize
        ATweaker.__init__(self, **kwargs)

        # add input and output attributes
        self.inputs.AddLayer('place')
        self.inputs.AddLayer('mesh')

    def Treat(self):
        # inputs, outpus 확인
        self.inputs.place = utl.AsLayer(self.inputs.place)
        self.inputs.mesh  = utl.AsLayer(self.inputs.mesh)

        if not self.inputs.place or not self.inputs.mesh:
            msg.warning('Treat@%s'%self.__name__, 'No inputs.')
            return var.IGNORE

        return var.SUCCESS

class Example_RefereceToXform(Tweaker):
    ARGCLASS = AExample_RefereceToXform
    def DoIt(self):

        arcs = arc.Arcs(self.arg.inputs.place)

        with utl.OpenStage(self.arg.inputs.place) as stage:
            dprim    = stage.GetDefaultPrim()
            treeIter = iter(Usd.PrimRange.AllPrims(dprim))
            meshPrim = None

            treeIter.next() # skip the root prim
            for p in treeIter:
                if p.GetTypeName() != 'Xform':
                    continue

                arcs.Reference(self.arg.inputs.mesh, p.GetPath())

        arcs.DoIt()

        return var.SUCCESS
