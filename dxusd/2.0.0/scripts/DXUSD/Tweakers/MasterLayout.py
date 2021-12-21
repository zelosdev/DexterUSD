#coding:utf-8
from __future__ import print_function
import os, glob

from pxr import Sdf, Usd, UsdGeom

from .Tweaker import Tweaker, ATweaker
from DXUSD.Structures import Arguments
import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg


class AMasterLayoutPack(ATweaker):
    def __init__(self, **kwargs):
        self.geomfiles =[]

        # initialize
        ATweaker.__init__(self, **kwargs)


    def Treat(self):

        if not self.master:
            msg.errmsg('Treat@%s' % self.__name__, 'No master.')
            return var.FAILED

        self.dstdir = utl.DirName(self.master)
        self.D.SetDecode(self.dstdir)

        for file in glob.glob('%s/*.geom.usd' % self.dstdir):
            self.geomfiles.append(file)

        return var.SUCCESS


class MasterLayoutPack(Tweaker):
    ARGCLASS = AMasterLayoutPack

    def DoIt(self):
        if not self.arg.geomfiles:
            msg.error('%s.Doit : ' % self.__name__, 'Not found geomfiles.')
        msg.debug( 'MasterLayout files :', self.arg.geomfiles)

        outlyr = utl.AsLayer(self.arg.master, create=True, clear=True)
        self.main(outlyr)

        utl.UpdateLayerData(outlyr, self.arg.geomfiles[0]).doIt()
        # remove 'importFile'
        if outlyr.customLayerData.has_key('importFile'):
            data = outlyr.customLayerData
            data.pop('importFile')
            outlyr.customLayerData = data

        # upAxis = "Y"
        with utl.OpenStage(outlyr) as stage:
            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)

        outlyr.Save()
        del outlyr

        return var.SUCCESS


    def main(self, outlyr):
        root = utl.GetPrimSpec(outlyr, self.arg.nslyr)
        outlyr.defaultPrim = self.arg.nslyr
        root.SetInfo('kind', 'assembly')
        utl.AddCustomData(root, 'groupName', self.arg.nslyr)

        if self.arg.nslyr == 'extra':   # only one geomfile
            f = self.arg.geomfiles[0]
            self.geomArc(root, f)
            self.setExtraCustomData(root, f)
        else:
            for f in self.arg.geomfiles:
                srclyr   = utl.AsLayer(f)
                primName = srclyr.defaultPrim
                if primName == 'World':
                    for s in srclyr.GetPrimAtPath(primName).nameChildren:
                        self.geomLayerArc(root, f, s.path.name, s.path)
                else:
                    self.geomLayerArc(root, f, primName)
        return var.SUCCESS


    def geomLayerArc(self, parent, filename, name, primPath=Sdf.Path.emptyPath):
        res = self.arg.N.layout.Decode(name)
        if res.desc:
            name = res.desc
        spec = parent
        if self.arg.nslyr != name:
            spec = utl.GetPrimSpec(parent.layer, parent.path.AppendChild(name), specifier='over')
            utl.AddCustomData(spec, 'groupName', name)
        self.geomArc(spec, filename, primPath)


    def geomArc(self, spec, filename, primPath=Sdf.Path.emptyPath):
        relpath = utl.GetRelPath(spec.layer.identifier, filename)
        utl.ReferenceAppend(spec, relpath, path=primPath)


    def getAbsPath(self, relPath):
        if relPath.startswith('/'):
            return relPath
        else:
            return os.path.abspath(os.path.join(self.arg.dstdir, relPath))

    # Add Custom Data - extra layer
    def setExtraCustomData(self, parent, filename): # filename is source
        srclyr = utl.AsLayer(filename)
        for c in srclyr.rootPrims[0].nameChildren:
            for ref in c.referenceList.prependedItems:
                assetPath = ref.assetPath
                if assetPath:
                    fullPath = self.getAbsPath(assetPath)
                    arg = Arguments()
                    arg.D.SetDecode(utl.DirName(fullPath))
                    spec = utl.GetPrimSpec(parent.layer, parent.path.AppendChild(c.name), specifier='over')
                    if arg.assetName:
                        utl.AddCustomData(spec, 'groupName', arg.assetName)
                    else:
                        utl.AddCustomData(spec, 'source', filename)
