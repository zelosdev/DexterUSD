#coding:utf-8
from __future__ import print_function
import os

from pxr import Sdf, Usd, UsdGeom

from .Tweaker import Tweaker, ATweaker

import DXUSD.Arcs as arc
import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg

import DXRulebook.Interface as rb

class AMasterCameraPack(ATweaker):
    def __init__(self, **kwargs):
        ATweaker.__init__(self, **kwargs)

    def Treat(self):
        return var.SUCCESS

class MasterCameraPack(Tweaker):
    ARGCLASS = AMasterCameraPack

    def DoIt(self):
        outlyr = utl.AsLayer(self.arg.master, create=True, clear=True)
        outlyr.defaultPrim = 'Cam'

        self.main(outlyr)

        # Update layer data
        utl.UpdateLayerData(outlyr, self.arg.geomfiles[0]).doIt()

        # upAxis = "Y"
        with utl.OpenStage(outlyr) as stage:
            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)

        outlyr.Save()
        del outlyr
        return var.SUCCESS

    def main(self, outlyr):
        root = utl.GetPrimSpec(outlyr, '/Cam')

        maincamSpec = []
        for maincam in self.arg.maincam:
            camName = 'main_cam'
            if maincam.find('left') > -1:      camName += '_left'
            elif maincam.find('right') > -1:   camName += '_right'

            camSpec = utl.GetPrimSpec(outlyr, root.path.AppendPath(camName), type='Camera')
            if not camSpec in maincamSpec:
                maincamSpec.append(camSpec)

        extraSpec = utl.GetPrimSpec(outlyr, root.path.AppendPath('extra'))
        camsSpec = utl.GetPrimSpec(outlyr, extraSpec.path.AppendPath('Cameras'))

        # pack cameras
        for idx, geom in enumerate(self.arg.geomfiles):
            name = os.path.basename(geom).split('.')[0]
            camName = os.path.basename(name)
            exCamSpec = utl.GetPrimSpec(outlyr, camsSpec.path.AppendPath(camName), type='Camera')
            utl.ReferenceAppend(exCamSpec, './' + os.path.basename(geom))

            # mainCam variant Set
            for i, mCam in enumerate(maincamSpec):
                camVsSpec = utl.GetVariantSetSpec(mCam, var.T.VAR_CAMERA)
                vspec = Sdf.VariantSpec(camVsSpec, camName)
                vset = utl.GetPrimSpec(outlyr, vspec.primSpec.path)
                ref = Sdf.Payload('', exCamSpec.path)
                prependedItems = vset.payloadList.prependedItems
                if prependedItems.index(ref) == -1:
                    prependedItems.append(ref)
                mCam.variantSelections.update({var.T.VAR_CAMERA: self.arg.maincam[i]})

        # pack imageplanes
        if self.arg.imgPlanefiles:
            coder = rb.Coder('N', 'USD')
            attrs = ['camera', 'indirect', 'transmission']
            impRootSpec = utl.GetPrimSpec(outlyr, extraSpec.path.AppendPath('imageplanes'))
            for imgPlane in self.arg.imgPlanefiles:
                name = os.path.basename(imgPlane).split('.')[0].replace('_cam', '_imageplane')
                impSpec = utl.GetPrimSpec(outlyr, impRootSpec.path.AppendPath(name), type='Mesh')
                utl.ReferenceAppend(impSpec, './' + os.path.basename(imgPlane))

                for attr in attrs:
                    riAttr = coder.ATTR_RIVIS.Encode(name=attr)
                    utl.GetAttributeSpec(impSpec, riAttr, 0, Sdf.ValueTypeNames.Int)

        # pack dummy geom
        for dxnode in self.arg.dxnodes:
            if self.arg.dummyfiles.has_key(dxnode):
                for dummyGeo in self.arg.dummyfiles[dxnode]:
                    dummyRootSpec = utl.GetPrimSpec(outlyr, extraSpec.path.AppendPath(dxnode))
                    utl.ReferenceAppend(dummyRootSpec, './' + os.path.basename(dummyGeo))

        return var.SUCCESS
