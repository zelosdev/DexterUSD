#coding:utf-8
from __future__ import print_function

from pxr import Sdf, Usd, UsdGeom

from .Tweaker import Tweaker, ATweaker
import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg


class AMasterSimPack(ATweaker):
    def __init__(self, **kwargs):
        '''
        dstdir (str): target dirpath
        master (str): package output name
        '''

        # initialize
        ATweaker.__init__(self, **kwargs)

    def Treat(self):
        if not self.master or not self.node:
            msg.errmsg('Treat@%s' % self.__name__, 'No master.')
            return var.FAILED
        if not self.has_attr('dstdir'):
            self.dstdir = utl.DirName(self.master)
        self.D.SetDecode(self.dstdir)
        return var.SUCCESS


class MasterSimPack(Tweaker):
    ARGCLASS = AMasterSimPack
    def DoIt(self):
        # print(self.arg)
        # geomfiles = {
        #     'high': high geom filename,
        #     'mid': ...,
        #     'low': ...,
        #     'xform': xform filename
        # }
        self.geomfiles = utl.GetGeomFiles(self.arg.dstdir)

        if not self.geomfiles.has_key('high'):
            msg.errmsg('Treat@%s' % self.__name__, 'Not found high_geom')
            return var.FAILED
        msg.debug('> Target Files :', self.geomfiles.values())

        outlyr = utl.AsLayer(self.arg.master, create=True, clear=True)

        # Update layer data
        upc = utl.UpdateLayerData(outlyr, self.geomfiles['high'])
        upc.doIt()

        self.main(outlyr)

        # upAxis = "Y"
        with utl.OpenStage(outlyr) as stage:
            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)

        outlyr.Save()
        del outlyr

        return var.SUCCESS

    def main(self, outlyr):
        defaultName = self.arg.nslyr
        if self.arg.assetName:
            defaultName = self.arg.assetName
        root = utl.GetPrimSpec(outlyr, '/' + defaultName)
        outlyr.defaultPrim = defaultName

        utl.ReferenceAppend(root, self.geomfiles['high'])

        # # if task is ani: arc collection.usd
        # if self.geomfiles.has_key('mid') or self.geomfiles.has_key('low'):
        #     # LOD Variant
        #     vsetSpec = utl.GetVariantSetSpec(root, var.T.VAR_LOD)
        #     # high
        #     vspec = Sdf.VariantSpec(vsetSpec, var.T.HIGH)
        #     spec  = utl.GetPrimSpec(outlyr, vspec.primSpec.path.AppendChild('Geom'))
        #     self.geomArc(spec, self.geomfiles['high'])
        #     # mid
        #     if self.geomfiles['mid']:
        #         vspec = Sdf.VariantSpec(vsetSpec, var.T.MID)
        #         spec  = utl.GetPrimSpec(outlyr, vspec.primSpec.path.AppendChild('Geom'))
        #         self.geomArc(spec, self.geomfiles['mid'])
        #     # low
        #     if self.geomfiles['low']:
        #         vspec = Sdf.VariantSpec(vsetSpec, var.T.LOW)
        #         spec  = utl.GetPrimSpec(outlyr, vspec.primSpec.path.AppendChild('Geom'))
        #         self.geomArc(spec, self.geomfiles['low'])
        #     # variant select
        #     root.variantSelections.update({var.T.VAR_LOD: var.T.HIGH})
        # else:
        #     spec = utl.GetPrimSpec(outlyr, root.path.AppendChild('Geom'))
        #     self.geomArc(spec, self.geomfiles['high'])


        return var.SUCCESS


    def geomArc(self, spec, filename):
        relpath = utl.GetRelPath(spec.layer.identifier, filename)
        utl.PayloadAppend(spec, relpath)
