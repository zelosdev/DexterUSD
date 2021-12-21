#coding:utf-8
from __future__ import print_function
import os

from pxr import Sdf, Usd

from DXUSD.Structures import Arguments
from .Tweaker import Tweaker, ATweaker
import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg

class AGeomRigAttrs(ATweaker):
    def __init__(self, **kwargs):
        '''
        [Arguments]
        inputs (list) : input geom files
        '''

        # initialize
        ATweaker.__init__(self, **kwargs)

    def Treat(self):
        if not self.inputs:
            msg.errmsg('Treat@%s' % self.__name__, 'No inputs.')
            return var.FAILED
        self.geomfiles = self.inputs
        return var.SUCCESS


class GeomRigAttrs(Tweaker):
    ARGCLASS = AGeomRigAttrs
    def DoIt(self):
        for fn in self.arg.geomfiles:
            res = self.TreatAttrs(fn)
            if res == var.FAILED:
                return res
        return var.SUCCESS


    def TreatAttrs(self, inPath):
        msg.warning(inPath)
        outlyr = utl.AsLayer(inPath)
        custom = outlyr.customLayerData
        if not custom.has_key('rigFile'):
            msg.warning('Treat@%s' % self.__name__, 'Not found rigFile customLayerData.')
            return
        if custom['rigFile'] == '':
            msg.warning('Treat@%s' % self.__name__, 'Not found rigFile customLayerData.')
            return

        rigFile = custom['rigFile']
        arg = Arguments()
        arg.D.SetDecode(utl.DirName(rigFile))
        rigVariant = custom.get('variant')
        if rigVariant and arg.asset != rigVariant:
            arg.branch = rigVariant
        arg.nslyr = utl.BaseName(rigFile).split('.')[0]

        baseName = utl.BaseName(inPath).replace('_geom.usd', '_attr.usd')
        attrFile = utl.SJoin(arg.D.TASKN, baseName)
        if not os.path.exists(attrFile):
            return

        dspec = utl.GetDefaultPrim(outlyr)

        arg = Arguments()
        arg.name = dspec.name
        attrClassPrimPath = arg.N.PRIM_ATTR

        relpath  = utl.GetRelPath(inPath, attrFile)
        utl.SetSublayer(outlyr, relpath)
        utl.SetInherit(attrClassPrimPath, dspec)
        outlyr.Save()
        del outlyr
        return var.SUCCESS
