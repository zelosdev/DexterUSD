#coding:utf-8
from __future__ import print_function
import os

from pxr import Sdf, Usd

from .Tweaker import Tweaker, ATweaker

import DXUSD.Arcs as arc
import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg


class AExample_PackGeom(ATweaker):
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
        self.outputs.AddLayer('output')

    def Treat(self):
        # inputs 확인
        self.inputs.place = utl.AsLayer(self.inputs.place)

        if not self.inputs.place:
            msg.warning('Treat@%s'%self.__name__, 'No inputs.')
            return var.IGNORE

        # outputs 확인
        self.outputs[0] = utl.AsLayer(self.outputs[0], create=True, clear=True)
        if not self.outputs[0]:
            msg.warning('Treat@%s'%self.__name__, 'No outputs.')
            return var.IGNORE

        # self.asset 플래그가 없으면 input에서 decoding 한다.
        if not self.asset:
            self.D.SetDecode(self.inputs.place)

        return var.SUCCESS

class Example_PackGeom(Tweaker):
    ARGCLASS = AExample_PackGeom

    def DoIt(self):
        arcs = arc.Arcs(self.arg.outputs[0])

        arcs.DefaultPrim(self.arg.asset, specifier=var.DEF, type='Xform')
        arcs.Reference(self.arg.inputs.place, '/$D/Geom',
                       specifier=var.DEF, type='Xform')
        arcs.DoIt()

        return var.SUCCESS
