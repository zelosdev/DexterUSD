#coding:utf-8
from __future__ import print_function
import os
from pxr import Usd, Sdf

from DXUSD.Tweakers.Tweaker import Tweaker, ATweaker
import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD_MAYA.Message as msg


#-------------------------------------------------------------------------------
#
#   Crowd Agent
#
#-------------------------------------------------------------------------------
class AGeomAgentAttrs(ATweaker):
    def __init__(self, **kwargs):
        '''
        [Arguments]
        inputs  (list)
        outputs (list)
        '''

        # self.inputs = list()
        # self.outputs= list()

        # initialize
        ATweaker.__init__(self, **kwargs)

    def Treat(self):
        if not self.inputs:
            msg.errmsg('Treat@%s' % self.__name__, 'No inputs.')
            return var.FAILED

        # inputs exists check for standalone tweaker
        for input in self.inputs:
            if not os.path.exists(input):
                msg.errmsg('Treat@%s' % self.__name__, 'not found file : %s' % input)
                return var.FAILED

        self.D.SetDecode(utl.DirName(self.inputs[0]))
        return var.SUCCESS

class GeomAgentAttrs(Tweaker):
    ARGCLASS = AGeomAgentAttrs
    def DoIt(self):
        for f in self.arg.inputs:
            self.TreatAttrs(f)
        return var.SUCCESS

    def TreatAttrs(self, input):
        outlyr = utl.AsLayer(input)
        with utl.OpenStage(outlyr) as stage:
            dprim = stage.GetDefaultPrim()

            for p in iter(Usd.PrimRange.AllPrims(dprim)):
                if p.GetTypeName() == 'Mesh':
                    p.RemoveProperty('extent')

            randomroots = self.getRandomizeRoot(dprim)
            if len(randomroots) > 1:
                for root in randomroots:
                    for c in root.GetAllChildren():
                        c.SetActive(False)

        outlyr.Save()
        del outlyr
        return var.SUCCESS


    def getRandomizeRoot(self, parent):
        result = list()
        for p in parent.GetAllChildren():
            if p.GetTypeName() == 'Xform':
                err = 0
                for c in p.GetAllChildren():
                    if c.GetTypeName() != 'Xform':
                        err += 1
                if err == 0:
                    result.append(p)
        return result
