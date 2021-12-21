#coding:utf-8
from __future__ import print_function
import glob, pprint

from pxr import Sdf, Usd, UsdGeom

from .Tweaker import Tweaker, ATweaker
import DXUSD.Arcs as arc
import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg


class AMasterFxPack(ATweaker):
    def __init__(self, **kwargs):
        '''
        dstdir (str) : target dirpath
        master (str) : package output name
        '''
        # initialize
        ATweaker.__init__(self, **kwargs)

        self.geomfiles = {}     # {'high': [], ...}

    def Treat(self):
        if not self.master:
            msg.errmsg('Treat@%s' % self.__name__, 'No master.')
            return var.FAILED

        if not self.has_attr('dstdir'):
            self.dstdir = utl.DirName(self.master)

        self.D.SetDecode(self.dstdir)

        # get geomfiles
        files = glob.glob('%s/*_geom.usd' % self.dstdir)
        for f in files:
            for gtyp in [var.T.HIGH, var.T.MID, var.T.LOW]:
                if '%s_geom.usd' % gtyp in f:
                    if not self.geomfiles.has_key(gtyp):
                        self.geomfiles[gtyp] = list()
                    self.geomfiles[gtyp].append(f)

        return var.SUCCESS


class MasterFxPack(Tweaker):
    ARGCLASS = AMasterFxPack
    def DoIt(self):
        if not self.arg.geomfiles:
            msg.error('%s.DoIt :' % self.__name__, 'Not found geomfiles.')
        # msg.debug(' MasterModel files :', self.arg.geomfiles)
        if msg.DEV:
            print('>>> MasterModel Files :')
            pprint.pprint(self.arg.geomfiles, width=20)

        outlyr = utl.AsLayer(self.arg.master, create=True, clear=True)
        # outlyr.defaultPrim = self.arg.assetName
        outlyr.defaultPrim = self.arg.assetName
        root   = utl.GetPrimSpec(outlyr, '/' + self.arg.assetName)
        root.SetInfo('kind', 'assembly')
        root.assetInfo = {'name': self.arg.assetName}

        if len(self.arg.geomfiles.keys()) == 3:
            # LOD Variant
            vsetSpec = utl.GetVariantSetSpec(root, var.T.VAR_LOD)
            for gtyp in self.arg.geomfiles:
                vspec = Sdf.VariantSpec(vsetSpec, gtyp)
                spec  = utl.GetPrimSpec(outlyr, vspec.primSpec.path.AppendChild('Geom'))
                self.geomArc(spec, self.arg.geomfiles[gtyp], self.arg.geomfiles[var.T.LOW])
            # variant select
            root.variantSelections.update({var.T.VAR_LOD: var.T.HIGH})
        else:
            spec = utl.GetPrimSpec(outlyr, root.path.AppendChild('Geom'))
            self.geomArc(spec, self.arg.geomfiles.get(var.T.HIGH), self.arg.geomfiles.get(var.T.LOW))

        # Update layer data
        files = self.arg.geomfiles.get(var.T.HIGH)
        if files:
            utl.UpdateLayerData(outlyr, files[0]).doIt()

        # upAxis
        with utl.OpenStage(outlyr) as stage:
            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)

        outlyr.Save()
        del outlyr
        return var.SUCCESS

    def geomArc(self, spec, render, proxy):     # render, proxy is filenames
        if render and proxy:
            renderSpec = utl.GetPrimSpec(spec.layer, spec.path.AppendChild('Render'))
            utl.SetPurpose(renderSpec, 'render')
            self.setReference(renderSpec, render)
            proxySpec  = utl.GetPrimSpec(spec.layer, spec.path.AppendChild('Proxy'))
            utl.SetPurpose(proxySpec, 'proxy')
            self.setReference(proxySpec, proxy)
        else:
            self.setReference(spec, render)

    def setReference(self, spec, files):
        for f in files:
            # utl.ReferenceAppend(spec, './' + utl.BaseName(f))
            utl.PayloadAppend(spec, './' + utl.BaseName(f))
