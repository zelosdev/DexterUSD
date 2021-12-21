#coding:utf-8
from __future__ import print_function
import os

from pxr import Sdf, Usd

from DXUSD.Structures import Arguments
from .Tweaker import Tweaker, ATweaker
import DXUSD.Arcs as arc
import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg


class ACollection(ATweaker):
    def __init__(self, **kwargs):
        '''
        [Arguments]
        master (str) : geom package output name
        '''

        self.inputRigFile = ''

        # initialize
        ATweaker.__init__(self, **kwargs)

    def Treat(self):
        self.output = self.master.replace('.usd', '.collection.usd')
        if self.inputRigFile:
            self.D.SetDecode(utl.DirName(self.inputRigFile))
        else:
            self.D.SetDecode(utl.DirName(self.master))

        return var.SUCCESS


class Collection(Tweaker):
    ARGCLASS = ACollection

    def composite(self, output, input, remove=False):
        outlyr = utl.AsLayer(output)
        root   = outlyr.rootPrims[0]
        source = Sdf.Reference('./' + utl.BaseName(input))
        items  = root.referenceList.prependedItems
        if remove:
            items.remove(source)
        else:
            if items.index(source) == -1:
                items.insert(0, source)

        vset = root.variantSets.get(var.T.VAR_LOD)
        if vset:
            root.variantSelections.update({var.T.VAR_LOD: var.T.HIGH})

        outlyr.Save()
        del outlyr

    def IsGeom(self, prim):
        gtyp = prim.GetTypeName()
        if gtyp == 'Mesh':
            return True
        elif gtyp == 'BasisCurves':
            return True
        else:
            return False

    def walk(self, prim):
        for p in prim.GetAllChildren():
            self.compute(p)
            if p.GetTypeName() == 'SkelRoot':
                self.walk_agent(p)
            elif not self.IsGeom(p) and p.HasAuthoredReferences():
                self.previewOverride(p)
                if p.HasAuthoredReferences():
                    self.walk(p)
            else:
                self.walk(p)

    def walk_agent(self, prim):
        for p in prim.GetAllChildren():
            self.compute(p)
            self.walk_agent(p)

    def DoIt(self):
        self._ifever  = 0
        self._ifprman = 0
        self._ifpreview = 0

        # source
        srclyr = utl.AsLayer(self.arg.master)
        root = srclyr.GetPrimAtPath('/' + srclyr.defaultPrim)
        root.referenceList.prependedItems.clear()

        # create collection layer
        output = self.arg.master.replace('.usd', '.collection.usd')
        outlyr = utl.AsLayer(output, create=True, clear=True)
        with utl.OpenStage(srclyr) as stage:
            dprim = stage.GetDefaultPrim()

            # write
            self.rootSpec = utl.GetPrimSpec(outlyr, dprim.GetPath(), specifier='over')
            outlyr.defaultPrim = self.rootSpec.name
            vsets = dprim.GetVariantSets()
            if vsets.HasVariantSet(var.T.VAR_LOD):
                # write
                vsetSpec = utl.GetVariantSetSpec(self.rootSpec, var.T.VAR_LOD)
                vset = vsets.GetVariantSet(var.T.VAR_LOD)
                for name in vset.GetVariantNames():
                    vset.SetVariantSelection(name)

                    # write
                    vspec = Sdf.VariantSpec(vsetSpec, name)
                    self.parentSpec = vspec.primSpec
                    self.walk(vset.GetPrim())
            else:
                self.parentSpec = self.rootSpec
                self.walk(dprim)

        # Looks
        if self._ifprman > 0 or self._ifpreview > 0:
            lookSpec = utl.GetPrimSpec(outlyr, root.path.AppendChild('Looks'), type='Scope')
            # outlyr.GetPrimAtPath(root.path.AppendChild('Looks'))
            lookSpec.specifier = Sdf.SpecifierDef
            lookSpec.typeName  = 'Scope'

        # prman
        if self._ifprman > 0:
            spec = utl.GetPrimSpec(outlyr, lookSpec.path.AppendChild('prman'), type='Scope')
            utl.ReferenceAppend(spec, utl.GetRelPath(output, utl.SJoin(self.arg.assetDir, 'material', 'prman', 'prman.usd')))

        # preview
        if self._ifpreview > 0:
            spec = outlyr.GetPrimAtPath(lookSpec.path.AppendChild('preview'))
            spec.specifier = Sdf.SpecifierDef
            spec.typeName  = 'Scope'
            self.previewBindingSetup()

        if self._ifever == 0 and self._ifprman == 0 and self._ifpreview == 0:
            os.remove(output)
            self.composite(self.arg.master, output, remove=True)
            return

        outlyr.Save()
        del outlyr
        self.composite(self.arg.master, output)
        return var.SUCCESS


    def compute(self, prim):
        # full binding collection
        if prim.HasProperty(var.T.ATTR_MATERIALSET):
            mtlname = prim.GetAttribute(var.T.ATTR_MATERIALSET).Get()
            if mtlname:
                self._ifprman += 1
                name = 'fb_' + mtlname
                utl.CollectionTargetAppend(self.parentSpec, name, prim.GetPath())
                self.bindMaterial(self.parentSpec, name, 'Looks/prman/' + mtlname, 'full')

        # preview binding collection
        if prim.HasProperty(var.T.ATTR_TXBASEPATH) and prim.HasProperty(var.T.ATTR_TXLAYERNAME):
            txLayerName = prim.GetAttribute(var.T.ATTR_TXLAYERNAME).Get()
            txBasePath  = prim.GetAttribute(var.T.ATTR_TXBASEPATH).Get()
            if txLayerName and txBasePath:
                self._ifpreview += 1
                mtlname = '{ASSET}_{LAYER}'.format(ASSET=self.arg.assetName, LAYER=txLayerName)
                name = 'pb_' + mtlname
                utl.CollectionTargetAppend(self.parentSpec, name, prim.GetPath())
                self.createPreviewMaterial(prim, txLayerName)


    def bindMaterial(self, spec, name, mtlpath, purpose):
        attrName = 'material:binding:collection:{PURPOSE}:{NAME}'.format(PURPOSE=purpose, NAME=name)
        attrSpec = spec.properties.get(attrName)
        if not attrSpec:
            attrSpec = Sdf.RelationshipSpec(spec, attrName, False)
            rootPath = spec.path.StripAllVariantSelections()
            attrSpec.targetPathList.explicitItems.append(rootPath.AppendPath('.collection:%s' % name))
            attrSpec.targetPathList.explicitItems.append(rootPath.AppendPath(mtlpath))


    def createPreviewMaterial(self, prim, txLayerName):
        mtlname  = '{ASSET}_{LAYER}'.format(ASSET=self.arg.assetName, LAYER=txLayerName)
        primPath = self.rootSpec.path.AppendPath('Looks/preview/%s' % mtlname)
        if self.rootSpec.layer.GetPrimAtPath(primPath):
            return

        proxyMtl = self.getProxyFile(prim.GetAttribute(var.T.ATTR_TXBASEPATH).GetPropertyStack(0)[0])
        if not proxyMtl:
            return

        spec = utl.GetPrimSpec(self.rootSpec.layer, primPath, specifier='over')
        utl.ReferenceAppend(spec, utl.GetRelPath(self.arg.master, proxyMtl), path='/' + txLayerName, clear=True)
        modelver = prim.GetAttribute(var.T.ATTR_MODELVER).Get()
        spec.variantSelections.update({var.T.VAR_MODELVER: modelver})

    def getProxyFile(self, spec):   # var.T.ATTR_TXBASEPATH attribute spec
        texAttrUsd = spec.layer.identifier
        arg = Arguments()
        arg.D.SetDecode(utl.DirName(texAttrUsd))
        arg.nslyr = 'proxy'
        if 'texture' in arg.D.TASKN:
            proxyMtl = utl.SJoin(arg.D.TASKN, arg.F.PROXY)
            if os.path.exists(proxyMtl):
                return proxyMtl

    def createPreviewRoot(self):
        vsetSpec = utl.GetVariantSetSpec(self.rootSpec, var.T.VAR_PREVIEW)
        if not vsetSpec.variants.has_key('off'):
            vspec = Sdf.VariantSpec(vsetSpec, 'off')
        if not vsetSpec.variants.has_key('on'):
            vspec = Sdf.VariantSpec(vsetSpec, 'on')
        self.rootSpec.variantSelections.update({var.T.VAR_PREVIEW: 'off'})
        primPath = self.rootSpec.path.AppendVariantSelection(var.T.VAR_PREVIEW, 'on')
        return self.rootSpec.layer.GetPrimAtPath(primPath)

    def previewBinding(self, src, dst): # both primSpec
        for c in src.GetInfo('apiSchemas').prependedItems:
            if c.startswith('CollectionAPI:pb_'):
                mtlname = c.replace('CollectionAPI:pb_', '')
                self.bindMaterial(dst, 'pb_' + mtlname, 'Looks/preview/' + mtlname, 'preview')

    def previewBindingSetup(self):
        prvSpec  = self.createPreviewRoot()
        vsetSpec = self.rootSpec.variantSets.get(var.T.VAR_LOD)
        if vsetSpec:
            # write
            lod_vsetSpec = utl.GetVariantSetSpec(prvSpec, var.T.VAR_LOD)

            for name, vspec in vsetSpec.variants.items():
                # write
                lod_vspec = Sdf.VariantSpec(lod_vsetSpec, name)
                self.previewBinding(vspec.primSpec, lod_vspec.primSpec)
        else:
            self.previewBinding(self.rootSpec, prvSpec)

    def previewOverride(self, prim):
        hasprv = 0
        for item in prim.GetMetadata('references').prependedItems:
            assetPath = item.assetPath
            if assetPath:
                fullPath = os.path.abspath(utl.SJoin(utl.DirName(self.arg.master), assetPath))
                srclyr = utl.AsLayer(fullPath)
                if srclyr:
                    with utl.OpenStage(srclyr) as stage:
                        dprim = stage.GetDefaultPrim()
                        try:
                            vsets = dprim.GetVariantSets()
                            if vsets.HasVariantSet(var.T.VAR_PREVIEW):
                                hasprv += 1
                        except:
                            pass

        if hasprv == 0:
            return

        self._ifever += 1
        prvSpec = self.createPreviewRoot()
        relpath = prim.GetPath().MakeRelativePath(self.rootSpec.path)
        spec = utl.GetPrimSpec(self.rootSpec.layer, prvSpec.path.AppendPath(relpath), specifier='over')
        spec.variantSelections.update({var.T.VAR_PREVIEW: 'on'})
