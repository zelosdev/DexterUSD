#coding:utf-8
from __future__ import print_function

import os
import glob
import pprint
import dxdict   # pylibs module

from pxr import Sdf, Usd

from DXUSD.Structures import Arguments
from .Tweaker import Tweaker, ATweaker
import DXUSD.Arcs as arc
import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg


#-------------------------------------------------------------------------------
#
#   COMMON
#
#-------------------------------------------------------------------------------
class CreateMaterials:
    def __init__(self, output, materials):
        self.rootDir = utl.DirName(output)

        arg = Arguments()
        arg.D.SetDecode(utl.DirName(output))
        tmp_fn = utl.SJoin(arg.D.ROOTS, 'asset', '_global', 'material', 'prman', 'prman.usd')
        if os.path.exists(tmp_fn):
            self.BASEPRMAN = tmp_fn
        else:
            self.BASEPRMAN = '/assetlib/_3d/asset/_global/material/prman/prman.usd'

        outlyr = utl.AsLayer(output, create=True)
        outlyr.defaultPrim = 'prman'

        root = utl.GetPrimSpec(outlyr, '/prman', type='Scope')
        for name in materials:
            self.doIt(name, root)

        outlyr.Save()
        del outlyr

    def IsPrim(self, primPath):
        with utl.OpenStage(self.BASEPRMAN) as stage:
            if stage.GetPrimAtPath(primPath):
                return True

    def modifyPrimSpec(self, spec):
        if len(spec.referenceList.prependedItems) == 0:
            spec.specifier = Sdf.SpecifierDef
            spec.typeName  = 'Material'
        else:
            spec.specifier = Sdf.SpecifierOver
            spec.typeName  = ''

    def doIt(self, name, parent):
        spec = utl.GetPrimSpec(parent.layer, parent.path.AppendChild(name), specifier='over')

        relPath  = utl.SJoin('shaders', name, name + '.usd')
        fullPath = utl.SJoin(self.rootDir, relPath)
        if os.path.exists(fullPath):
            ref = Sdf.Reference('./' + relPath)
            if spec.referenceList.prependedItems.index(ref) == -1:
                spec.referenceList.prependedItems.insert(0, ref)

        # cleanup global materials
        for r in spec.referenceList.prependedItems:
            if r.assetPath.endswith('_global/material/prman/prman.usd'):
                spec.referenceList.prependedItems.remove(r)
        if self.IsPrim(spec.path):
            utl.ReferenceAppend(spec, utl.GetRelPath(self.rootDir, self.BASEPRMAN), path=spec.path)

        # prim modify
        self.modifyPrimSpec(spec)



#-------------------------------------------------------------------------------
#
#   Create Material by Geometry Attribute ( var.T.ATTR_MATERIALSET )
#
#-------------------------------------------------------------------------------
class APrmanMaterial(ATweaker):
    def __init__(self, **kwargs):
        '''
        [Arguments]
        dstdir (str)  : target directory
        inputs (list) : geom files
        '''
        self.dstdir = ''

        # initialize
        ATweaker.__init__(self, **kwargs)

    def Treat(self):
        if not (self.inputs or self.dstdir):
            msg.errmsg('Treat@%s' % self.__name__, 'not found inputs or dstdir.')
            return var.FAILED

        if not self.inputs:
            for f in glob.glob('%s/*_geom.usd' % self.dstdir):
                self.inputs.Append(f)

        self.D.SetDecode(utl.DirName(self.inputs[0]))
        self.task   = 'material'
        self.render = 'prman'

        if self.has_attr('ovr_show'): self.show = self.ovr_show     # for MTK

        return var.SUCCESS


class PrmanMaterial(Tweaker):
    ARGCLASS = APrmanMaterial

    def DoIt(self):
        # material list
        self.materials = list()

        for f in self.arg.inputs:
            res = self.TreatFile(f)
            if res == var.FAILED:
                return res

        if self.materials:
            msg.debug(' Materials :', self.materials)
            output = utl.SJoin(self.arg.D.TASKR, 'prman.usd')
            if self.arg.customdir:
                if not '/assetlib/_3d' in self.arg.D.TASKR:
                    showTemp = self.arg.show
                    self.arg.pop('show')
                    output = utl.SJoin(self.arg.D.TASKR, 'prman.usd')
                    self.arg.show=showTemp
            CreateMaterials(output, self.materials)

            # for MTK
            if self.arg.customdir:
                if not '/assetlib/_3d' in self.arg.customdir:
                    self.arg.pop('show')
                    custom_output = utl.SJoin(self.arg.D.TASKR, 'prman.usd')
                    outlyr = utl.AsLayer(custom_output, create=True)
                    outlyr.defaultPrim = 'prman'
                    utl.SubLayersAppend(outlyr, utl.GetRelPath(custom_output, output))
                    outlyr.Save()
                    del outlyr

        return var.SUCCESS

    def TreatFile(self, input):
        '''
        input : geom filename
        '''
        srclyr = utl.AsLayer(input)
        if not srclyr:
            return

        with utl.OpenStage(srclyr) as stage:
            self.walk(stage.GetDefaultPrim())

        del srclyr
        return var.SUCCESS


    def walk(self, prim):
        for p in prim.GetChildren():
            if not p.HasAuthoredInherits() and p.HasAuthoredReferences():
                pass
            else:
                # print('>', p.GetPath().pathString)
                if p.HasProperty(var.T.ATTR_MATERIALSET):
                    name = p.GetAttribute(var.T.ATTR_MATERIALSET).Get()
                    if name and not name in self.materials:
                        self.materials.append(name)
                self.walk(p)




#-------------------------------------------------------------------------------
#
#   Override Material Referenced Asset
#
#-------------------------------------------------------------------------------
class APrmanMaterialOverride(ATweaker):
    def __init__(self, **kwargs):
        '''
        [Arguments]
        dstdir (str)  : target directory
        master (str)  : task master filename
        '''
        self.dstdir = ''
        self.master = ''

        # initialize
        ATweaker.__init__(self, **kwargs)

    def Treat(self):
        if not (self.master or self.dstdir):
            msg.errmsg('Treat@%s' % self.__name__, 'not found dstdir or master.')
            return var.FAILED

        if not self.master:
            self.D.SetDecode(self.dstdir)
            self.master = utl.SJoin(self.dstdir, self.F.MASTER)

        self.output = self.master.replace('.usd', '.omtl.usd')

        self.task   = 'material'
        self.render = 'prman'

        # material roots
        self.materialRoots = list()
        self.materialRoots.append(self.D.TASK)
        if self.shot:
            dir = utl.SJoin(self.D.SEQ, var.T.ASSET, var.T.GLOBAL, var.T.MATERIAL)
            self.materialRoots.append(dir)

        return var.SUCCESS


class PrmanMaterialOverride(Tweaker):
    ARGCLASS = APrmanMaterialOverride

    def DoIt(self):
        self.srclyr = utl.AsLayer(self.arg.master)
        if not self.srclyr:
            return

        self.specializeSpecs = list()
        self._ifever = 0
        self.dstlyr  = utl.AsLayer(self.arg.output, create=True, clear=True)

        with utl.OpenStage(self.srclyr) as stage:
            self.walk(stage.GetDefaultPrim())

        # specializes
        data = dict()   # {filename: [primPath, ...]}
        for spec in self.specializeSpecs:
            filename = spec.layer.identifier
            primPath = spec.path
            if not data.has_key(filename):
                data[filename] = list()
            data[filename].append(primPath)
        for f, paths in data.items():
            with utl.OpenStage(f) as stage:
                for p in paths:
                    prim = stage.GetPrimAtPath(p)
                    self.override(prim, prmanPath='source/Looks/prman')

        if self._ifever > 0:
            self.dstlyr.Save()
            del self.dstlyr
            self.composite()
            msg.debug('>>> PrmanMaterialOverride :', self.arg.output)
        else:
            os.remove(self.arg.output)
            self.composite(remove=True)

        return var.SUCCESS

    def composite(self, remove=False):
        relpath = utl.GetRelPath(self.arg.master, self.arg.output)
        outlyr  = utl.AsLayer(self.arg.master)
        if remove:
            outlyr.subLayerPaths.remove(relpath)
        else:
            if outlyr.subLayerPaths.index(relpath) == -1:
                outlyr.subLayerPaths.append(relpath)
        outlyr.Save()
        del outlyr

    def walk(self, prim):
        for p in prim.GetAllChildren():
            if p.IsInstance() and p.HasAuthoredSpecializes():
                # print('>', p.GetPath().pathString)
                spec = self.getSpecializeSpec(p)
                if spec:
                    if not spec in self.specializeSpecs:
                        self.specializeSpecs.append(spec)

            if p.GetName() == 'Looks':
                # print('> ovr prim :', p.GetParent().GetPath().pathString)
                self.override(p.GetParent())
            else:
                self.walk(p)


    def getSpecializeSpec(self, prim):
        primPath = prim.GetMetadata('specializes').explicitItems[0]
        for s in prim.GetPrimStack():
            if s.path == primPath:
                return s

    def searchPrman(self, subdirs):
        for root in self.arg.materialRoots:
            arg = Arguments()
            arg.D.SetDecode(root)
            arg.render = 'prman'
            prmanfile  = ''
            for dir in subdirs:
                arg.subdir = dir
                tmpfn = utl.SJoin(arg.D.TASKSR, 'prman.usd')
                if os.path.exists(tmpfn):
                    prmanfile = tmpfn
                    break

            if not prmanfile and self.arg.shot:
                tmpfn = utl.SJoin(arg.D.TASKR, 'prman.usd')
                if os.path.exists(tmpfn):
                    prmanfile = tmpfn
            if prmanfile:
                return prmanfile

    def getModelName(self, prim):
        model = Usd.ModelAPI(prim)
        asset = model.GetAssetName()
        if asset:
            return asset.split('_')[0]
        else:
            return prim.GetName()

    def getModelGroupName(self, prim):
        if prim.GetPath() == Sdf.Path('/'):
            return
        gname = prim.GetCustomDataByKey('groupName')
        if gname:
            return gname
        return self.getModelGroupName(prim.GetParent())


    def override(self, prim, prmanPath='Looks/prman'):
        modelName = self.getModelName(prim)

        subdirs = list()
        #   sudir order
        #       1. (groupName)_(modelName)
        #       2. (groupName)
        #       3. (modelName)
        # groupName = self.getModelGroupName(prim.GetParent())  # why using parent?
        groupName = self.getModelGroupName(prim)
        if groupName:
            if modelName:
                subdirs.append('%s_%s' % (groupName, modelName))
            subdirs.append(groupName)
        if modelName:
            if self.arg.assetName:
                if self.arg.assetName != modelName:
                    subdirs.append(modelName)
            else:
                subdirs.append(modelName)

        prman = self.searchPrman(subdirs)
        if prman:
            self._ifever += 1
            spec = utl.GetPrimSpec(self.dstlyr, prim.GetPath().AppendPath(prmanPath), specifier='over')
            utl.ReferenceAppend(spec, utl.GetRelPath(self.dstlyr.identifier, prman))
