#coding:utf-8
from __future__ import print_function
import os

from pxr import Sdf, Usd

from .Tweaker import Tweaker, ATweaker

import DXUSD.Arcs as arc
import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg


class AExample_ExtractMesh(ATweaker):
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
        self.inputs.AddLayer('input')
        self.outputs.AddLayer('output')

    def Treat(self):
        # inputs 확인
        self.inputs[0] = utl.AsLayer(self.inputs[0])
        if not self.inputs[0]:
            msg.warning('Treat@%s'%self.__name__, 'No inputs.')
            return var.IGNORE

        # outputs 확인
        self.outputs[0] = utl.AsLayer(self.outputs[0], create=True)
        if not self.outputs[0]:
            msg.warning('Treat@%s'%self.__name__, 'No outputs.')
            return var.IGNORE

        return var.SUCCESS

class Example_ExtractMesh(Tweaker):
    ARGCLASS = AExample_ExtractMesh

    def DoIt(self):
        arcs = arc.Arcs(self.arg.outputs[0])

        with utl.OpenStage(self.arg.inputs[0]) as stage:
            dprim    = stage.GetDefaultPrim()
            treeIter = iter(Usd.PrimRange.AllPrims(dprim))
            meshPrim = None

            for p in treeIter:
                if p.GetTypeName() != 'Mesh':
                    continue

                attrs = list()
                for attr in p.GetAuthoredAttributes():
                    attrs.append(attr.GetName())

                primPath = '/geom/%s'%p.GetName()
                arcs.DefaultPrim('/geom', type='Xform', kind=var.KIND.COM)
                arcs.CopySpec(p, primPath, attrs=attrs,
                              specifier=var.DEF, type='Mesh')

                meshPrim = p.GetPath()
                break

            arcs.DoIt()

            if meshPrim:
                stage.RemovePrim(meshPrim)
                stage.Save()

        return var.SUCCESS
