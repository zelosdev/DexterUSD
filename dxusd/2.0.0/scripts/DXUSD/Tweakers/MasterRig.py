#coding:utf-8
from __future__ import print_function
import os, glob

from pxr import Sdf, Usd, UsdGeom

from .Tweaker import Tweaker, ATweaker
from DXUSD.Structures import Arguments
import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg


class AMasterRigPack(ATweaker):
    def __init__(self, **kwargs):
        '''
        dstdir (str): target dirpath
        master (str): package output name
        '''

        # initialize
        ATweaker.__init__(self, **kwargs)

    def Treat(self):
        if not self.master:
            msg.errmsg('Treat@%s' % self.__name__, 'No master.')
            return var.FAILED
        if not self.has_attr('dstdir'):
            self.dstdir = utl.DirName(self.master)
        self.D.SetDecode(self.dstdir)
        return var.SUCCESS


class MasterRigPack(Tweaker):
    ARGCLASS = AMasterRigPack
    def DoIt(self):
        # print(self.arg)
        self.geomfiles = utl.GetGeomFiles(self.arg.dstdir)
        # {
        #     'high': high geom filename,
        #     'mid': ...,
        #     'low': ...,
        #     'xform': xform filename
        # }
        if not self.geomfiles.has_key('high'):
            msg.errmsg('Treat@%s' % self.__name__, 'Not found high_geom')
            return var.FAILED
        msg.debug('> Target Files :', self.geomfiles.values())

        outlyr = utl.AsLayer(self.arg.master, create=True, clear=True)
        # Update layer data
        utl.UpdateLayerData(outlyr, self.geomfiles['high']).doIt()
        customData = outlyr.customLayerData

        # rig asset
        self.rigCollection = ''
        self.rigAssetName  = ''
        if customData.has_key('rigFile') and customData['rigFile'] != '':
            # self.rigCollection = self.getRigAssetCollection(customData.get('rigFile'), variant=customData.get('variant'))
            self.getRigAssetCollection(customData.get('rigFile'), variant=customData.get('variant'))    # result : self.rigCollection, self.rigAssetName

        self.main(outlyr)

        # upAxis = "Y"
        with utl.OpenStage(outlyr) as stage:
            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)

        outlyr.Save()
        del outlyr

        return var.SUCCESS


    def getRigAssetCollection(self, rigFile, variant=None):
        arg = Arguments()
        arg.D.SetDecode(utl.DirName(rigFile))
        if variant and arg.asset != variant:
            arg.branch = variant
        arg.nslyr = utl.BaseName(rigFile).split('.')[0]
        self.rigCollection = utl.SJoin(arg.D.TASKN, arg.F.COLLECTION)
        self.rigAssetName  = arg.assetName

    def main(self, outlyr):
        defaultName = self.arg.nslyr
        if self.arg.assetName:
            defaultName = self.arg.assetName
        root = utl.GetPrimSpec(outlyr, '/' + defaultName)
        outlyr.defaultPrim = defaultName
        root.SetInfo('kind', 'assembly')
        root.assetInfo = {'name': defaultName}

        # if task is ani: arc collection.usd
        if self.rigCollection:
            utl.ReferenceAppend(root, utl.GetRelPath(outlyr.identifier, self.rigCollection))
            utl.AddCustomData(root, 'groupName', self.rigAssetName)

        if self.geomfiles.has_key('mid') or self.geomfiles.has_key('low'):
            # LOD Variant
            vsetSpec = utl.GetVariantSetSpec(root, var.T.VAR_LOD)
            # high
            vspec = Sdf.VariantSpec(vsetSpec, var.T.HIGH)
            spec  = utl.GetPrimSpec(outlyr, vspec.primSpec.path.AppendChild('Geom'))
            self.geomArc(spec, self.geomfiles['high'])
            # mid
            if self.geomfiles.has_key('mid') and self.geomfiles['mid']:
                vspec = Sdf.VariantSpec(vsetSpec, var.T.MID)
                spec  = utl.GetPrimSpec(outlyr, vspec.primSpec.path.AppendChild('Geom'))
                self.geomArc(spec, self.geomfiles['mid'])
            # low
            if self.geomfiles.has_key('low') and self.geomfiles['low']:
                vspec = Sdf.VariantSpec(vsetSpec, var.T.LOW)
                spec  = utl.GetPrimSpec(outlyr, vspec.primSpec.path.AppendChild('Geom'))
                self.geomArc(spec, self.geomfiles['low'])
            # variant select
            root.variantSelections.update({var.T.VAR_LOD: var.T.HIGH})
        else:
            spec = utl.GetPrimSpec(outlyr, root.path.AppendChild('Geom'))
            self.geomArc(spec, self.geomfiles['high'])

        # sim geom
        if self.geomfiles.has_key('sim'):
            spec = utl.GetPrimSpec(outlyr, root.path.AppendChild('Sim'))
            utl.GetAttributeSpec(spec, 'visibility', 'invisible', Sdf.ValueTypeNames.Token)
            self.geomArc(spec, self.geomfiles['sim'])

        # WorldXform
        if self.geomfiles.has_key('xform'):
            vsetSpec = utl.GetVariantSetSpec(root, var.T.VAR_WORLDXFORM)
            # off
            vspec = Sdf.VariantSpec(vsetSpec, 'off')
            # on
            vspec = Sdf.VariantSpec(vsetSpec, 'on')
            self.geomArc(vspec.primSpec, self.geomfiles['xform'])
            # variant select
            root.variantSelections.update({var.T.VAR_WORLDXFORM: 'on'})

        return var.SUCCESS


    def geomArc(self, spec, filename):
        relpath = utl.GetRelPath(spec.layer.identifier, filename)
        utl.PayloadAppend(spec, relpath)
