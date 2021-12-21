#coding:utf-8
from __future__ import print_function

import DXUSD.Vars as var
import DXUSD.Utils as utl

from DXUSD.Exporters.Export import Export, AExport

import DXUSD_MAYA.Tweakers as twk


class ASampleExporter(AExport):
    def __init__(self, **kwargs):
        '''
        [Input Arguments]
        0-SourceLayer (bool)   : Input Source Layer
        '''
        # initialize
        AExport.__init__(self, **kwargs)

        # pre flags
        self.task = 'model'

        # attributes
        self.nameProduct = 'SRC_MODEL'
        self.taskProduct = 'TASKV'

        # set srclyr
        self.srclyr.AddLayer('SourceLayer')


    def Treat(self):
        res = AExport.Treat(self)
        if res != var.SUCCESS:
            return res

        # ----------------------------------------------------------------------
        # Set output layer
        dstdir       = self.D[self.taskProduct]
        self.dstlyr  = utl.SJoin(dstdir, self.F.FINAL)

        # ----------------------------------------------------------------------
        # Set source layers
        self.srclyr['SourceLayer'] = utl.SJoin(dstdir, self.F.GEOM)

        return var.SUCCESS


class SampleExporter(Export):
    ARGCLASS = ASampleExporter

    def Arguing(self):
        # ----------------------------------------------------------------------
        # Declare tweaker arguments
        self.spArg = twk.ASample(**self.arg)

        # ----------------------------------------------------------------------
        # compositor
        return var.SUCCESS


    def Tweaking(self):
        twks = twk.Tweak()

        twks << twk.Sample(self.spArg)
        # twks << twk.NurbsToBasis(self.arg)

        twks.DoIt()
        return var.SUCCESS


    def Compositing(self):
        return var.SUCCESS
