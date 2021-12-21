#coding:utf-8
from __future__ import print_function

import shutil
import os
import copy
import pprint
import dxdict   # pylibs module

from pxr import Sdf, Usd

import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg
import DXUSD.Compositor as cmp

from DXUSD.Structures import Arguments
from .Tweaker import Tweaker, ATweaker


class AGeomAttrs(ATweaker):
    def __init__(self, **kwargs):
        '''
        [Arguments]
        extracts (list) : extract attributes
        inputs   (list) : input geom files
        outputs  (list)(optional) : output attr files
        '''

        # attributes
        self.extracts = [
            var.T.ATTR_MATERIALSET,
            'widths',
            # var.T.ATTR_ST
        ]
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

        self.extracts = list(set(self.extracts))

        # outputs
        if not self.outputs:
            self.outputs = []
            for input in self.inputs:
                self.outputs.append(input.replace('geom.usd', 'attr.usd'))

        self.D.SetDecode(utl.DirName(self.inputs[0]))

        if self.has_attr('ovr_show'): self.show = self.ovr_show     # for MTK

        self.searchPath = self.GetSearchPath()
        return var.SUCCESS



class GeomAttrs(Tweaker):
    ARGCLASS = AGeomAttrs
    def __init__(self, arg, texData={}):
        '''
        [Arguments]
        texData (dict)(return value) : texture information data of tex.attr.usd, using other tweakers
        '''
        self.resTexData = texData
        # {'tex.attr.usd' (fullpath):
        #     {$txLayerName :
        #         {'attrs':
        #             {var.T.ATTR_MODELVER: ['v001', 'v001'],   >>>> result : not list, string value
        #              var.T.ATTR_TXMULTIUV: 0
        #             }
        #          'classPath': $txClassPath
        #         }
        #     }
        # }
        Tweaker.__init__(self, arg)

    def DoIt(self):
        for i in range(len(self.arg.inputs)):
            msg.debug('%s.TreatAttrs :' % self.__name__, self.arg.inputs[i])
            self.texData = dict()
            self.editor = Sdf.BatchNamespaceEdit()  # srclyr remove attributes
            res = self.TreatAttrs(self.arg.inputs[i], self.arg.outputs[i])
            if res == var.FAILED:
                return res
            # update
            dxdict.deepupdate(self.resTexData, self.texData)
        # Rebuild self.resTexData
        for f in self.resTexData:
            for layer in self.resTexData[f]:
                attrs = self.resTexData[f][layer]['attrs']
                # if task is model, modelversion set to none
                if self.arg.task == var.T.MODEL:
                    mver = None
                else:
                    mver = attrs[var.T.ATTR_MODELVER][-1]
                attrs[var.T.ATTR_MODELVER] = mver
        return var.SUCCESS


    def AddRemover(self, specPath):
        self.editor.Add(specPath, Sdf.Path.emptyPath)

    def CopySpec(self, dst, attrs):
        for a in attrs:
            Sdf.CopySpec(a.layer, a.path, dst.layer, dst.path.AppendPath('.' + a.name))
            # srclyr remove attribute
            self.AddRemover(a.path)


    def TreatAttrs(self, inPath, outPath):
        '''
        inPath : geom usd filename
        outPath: attr usd filename
        '''
        tmpPath = outPath.replace(var._USD, var._TMPUSD)

        srclyr = utl.AsLayer(inPath)
        outlyr = utl.AsLayer(tmpPath, create=True, clear=True)
        dspec  = utl.GetDefaultPrim(srclyr)

        self.arg.name = dspec.name
        attrClassPrimPath = self.arg.N.PRIM_ATTR
        rootSpec = utl.GetPrimSpec(outlyr, attrClassPrimPath, specifier='class')

        with utl.OpenStage(srclyr, loadAll=False) as stage:
            dprim = stage.GetPrimAtPath(dspec.path)
            It = iter(Usd.PrimRange.AllPrims(dprim))
            It.next()
            refPath = ''
            for p in It:
                #---------------------------------------------------------------
                # skip referenced prims
                primPath = p.GetPrimPath().pathString
                if 'Looks' in primPath:
                    continue
                if not p.HasAuthoredInherits() and p.HasAuthoredReferences():
                    refPath = primPath
                if refPath and primPath.startswith(refPath):
                    continue
                if p.GetSpecifier() == Sdf.SpecifierClass:
                    continue
                # if p.GetTypeName() == 'Xform':
                #     continue
                if p.GetTypeName() == 'PointInstancer':
                   continue
                #---------------------------------------------------------------
                relpath = p.GetPath().MakeRelativePath(dprim.GetPath())
                specPath= rootSpec.path.AppendPath(relpath)

                spec = utl.GetPrimSpec(outlyr, specPath, specifier='over')
                spec.SetInfo('kind', 'component')

                attrs = []  # source attributeSpec list
                for attrName in self.arg.extracts:
                    if not p.HasProperty(attrName):
                        continue
                    stacks = p.GetProperty(attrName).GetPropertyStack(0)
                    if stacks:
                        attrs.append(stacks[-1])
                        for usdattr in p.GetPropertiesInNamespace(attrName):
                            attrs.append(usdattr.GetPropertyStack(0)[-1])
                # CopySpec
                if attrs:
                    self.CopySpec(spec, attrs)

                # Extract texture attributes
                if (p.HasProperty(var.T.ATTR_TXBASEPATH) and p.GetAttribute(var.T.ATTR_TXBASEPATH).Get()) and (p.HasProperty(var.T.ATTR_TXLAYERNAME) and p.GetAttribute(var.T.ATTR_TXLAYERNAME).Get()):
                    txClassPath = self.TreatPrimTxAttrs(p, outlyr)
                    utl.SetInherit(txClassPath, spec)

                if (p.HasProperty('prereferenceLayer') and p.GetAttribute('prereferenceLayer').Get()) and \
                     (p.HasProperty('prereferencePrim') and p.GetAttribute('prereferencePrim').Get()):
                     self.TreatPrereferenceAttr(p, spec, outlyr)

        if not rootSpec.nameChildren:
            del outlyr
            os.remove(tmpPath)
            return var.SUCCESS

        self.modelVersionInspect(outlyr)
        outlyr.Save()
        del outlyr

        # srclyr remove attributes
        srclyr.Apply(self.editor)
        srclyr.Save()

        # rename tmp.usd to usd
        if os.path.exists(outPath):
            os.remove(outPath)
        os.rename(tmpPath, outPath)

        # attrUsd inherit to geomUsd
        relpath = utl.GetRelPath(srclyr.identifier, outPath)
        utl.SetSublayer(srclyr, relpath)
        utl.SetInherit(attrClassPrimPath, dspec)
        srclyr.Save()
        del srclyr
        return var.SUCCESS


    def TreatPrimTxAttrs(self, prim, outlyr):
        basePathAttr = prim.GetAttribute(var.T.ATTR_TXBASEPATH)
        basePath     = basePathAttr.Get()
        self.AddRemover(basePathAttr.GetPropertyStack(0)[0].path)

        layerNameAttr= prim.GetAttribute(var.T.ATTR_TXLAYERNAME)
        layerName    = layerNameAttr.Get()
        self.AddRemover(layerNameAttr.GetPropertyStack(0)[0].path)

        rootDir = utl.SearchInDirs(self.arg.searchPath, basePath.replace('/texture', ''))
        texDir  = utl.SJoin(rootDir, 'texture', var.T.TEX)
        texVer  = utl.GetLastVersion(texDir)

        arg = AGeomAttrs()
        arg.D.SetDecode(texDir)
        arg.name = layerName

        texUsd = utl.SJoin(texDir, arg.F.MASTER)
        texAttr= utl.SJoin(texDir, texVer, arg.F.ATTR)

        txClassPath = arg.N.PRIM_TXATTR

        # prim texData
        primData = {
            texAttr: {layerName: {'attrs': {var.T.ATTR_MODELVER: [],
                                            var.T.ATTR_TXMULTIUV: 0},
                                  'classPath': txClassPath}}
        }
        data = primData[texAttr][layerName]['attrs']

        # UDIM
        udimAttr = prim.GetAttribute(var.T.ATTR_TXMULTIUV)
        if udimAttr:
            data[var.T.ATTR_TXMULTIUV] = udimAttr.Get()
            self.AddRemover(udimAttr.GetPropertyStack(0)[0].path)

        # ModelVersion
        mverAttr = prim.GetAttribute(var.T.ATTR_MODELVER)
        if mverAttr:
            mver = mverAttr.Get()
            if not mver in data[var.T.ATTR_MODELVER]:
                data[var.T.ATTR_MODELVER].append(mver)
            self.AddRemover(mverAttr.GetPropertyStack(0)[0].path)

        # create texture attribute classprim
        spec = outlyr.GetPrimAtPath(txClassPath)
        if not spec:
            spec = utl.GetPrimSpec(outlyr, txClassPath, specifier='class')
            relpath = utl.GetRelPath(outlyr.identifier, texUsd)
            spec.assetInfo = {'name': '/' + layerName, 'identifier': Sdf.AssetPath(relpath)}
            # utl.SetReference(spec, Sdf.Reference(relpath, '/' + layerName))   >>>> doit GeomAttrsComposite

        # update texData
        dxdict.deepupdate(self.texData, primData)
        return txClassPath

    def TreatPrereferenceAttr(self, prim, spec, outlyr):
         preRefLayerAttr = prim.GetAttribute('prereferenceLayer')
         preRefLayer     = preRefLayerAttr.Get()
         self.AddRemover(preRefLayerAttr.GetPropertyStack(0)[0].path)
 
         preRefPrimAttr  = prim.GetAttribute('prereferencePrim')
         preRefPrim      = preRefPrimAttr.Get()
         self.AddRemover(preRefPrimAttr.GetPropertyStack(0)[0].path)
 
         # spec = outlyr.GetPrimAtPath(prim.GetPath().pathString)
         # if not spec:
         #     spec = utl.GetPrimSpec(outlyr, prim.GetPath().pathString, specifier='over')
         relpath = utl.GetRelPath(outlyr.identifier, preRefLayer)
 
         msg.debug(preRefLayer, preRefPrim, prim.GetPath().pathString, relpath, spec)
         utl.SetReference(spec, Sdf.Reference(relpath, preRefPrim))   # >>>> doit GeomAttrsComposite

    def modelVersionInspect(self, outlyr):
        for f in self.texData:
            txarg = Arguments()
            txarg.D.SetDecode(utl.DirName(f))
            for layerName in self.texData[f]:
                attrs = self.texData[f][layerName]['attrs']
                # find last modelversion
                if self.arg.assetDir.startswith(txarg.assetDir) and self.arg.task == var.T.MODEL:   # current task is model
                    modelVer = self.arg.ver
                else:
                    if attrs[var.T.ATTR_MODELVER]:
                        modelVer = attrs[var.T.ATTR_MODELVER][-1]
                    else:
                        modelVer = utl.GetLastVersion(utl.SJoin(txarg.assetDir, var.T.MODEL))
                        attrs[var.T.ATTR_MODELVER] = [modelVer]

                # ModelVersion
                #   variant selection
                spec = outlyr.GetPrimAtPath(self.texData[f][layerName]['classPath'])
                spec.variantSelections.update({var.T.VAR_MODELVER: modelVer})
                #   set attribute
                utl.GetAttributeSpec(spec, var.T.ATTR_MODELVER, modelVer, Sdf.ValueTypeNames.String, info={'interpolation': 'constant'})

                # check model usd
                if self.arg.task == var.T.MODEL:
                    continue

                txarg.task = var.T.MODEL
                txarg.ver  = modelVer
                if not os.path.exists(txarg.D.TASKV):
                    msg.debug('[ UpdateModelVersion ] : %s' % txarg.D.TASKV)
                    self.updateModelVersion(txarg.D.TASKV)

    def updateModelVersion(self, dirpath):
        # create directory
        os.makedirs(dirpath)

        arg = Arguments()
        arg.D.SetDecode(dirpath)

        output = utl.SJoin(arg.D.TASK, arg.F.TASK)
        cmp.Packing(output, '', primPath='/' + arg.assetName, vsets=[(arg.N.USD.VAR_TASKVER, arg.N.USD.VAR_VER)])


class AGeomAttrsCompTex(ATweaker):
    def __init__(self, **kwargs):
        '''
        Composite texture tex.usd

        [Arguments]
        inputs (list) : input geom files
        '''
        self.inputs  = []
        # initialize
        ATweaker.__init__(self, **kwargs)

        self.outputs = []

    def Treat(self):
        if not self.inputs:
            return var.IGNORE

        # outputs
        for input in self.inputs:
            output = input.replace('geom.usd', 'attr.usd')
            if os.path.exists(output):
                self.outputs.append(output)
        return var.SUCCESS

class GeomAttrsCompTex(Tweaker):
    ARGCLASS = AGeomAttrsCompTex
    def DoIt(self):
        for f in self.arg.outputs:
            self.Treat(f)

    def Treat(self, output):
        outlyr = utl.AsLayer(output)
        for spec in outlyr.rootPrims:
            if spec.path.pathString.endswith('_txAttr'):
                identifier = spec.assetInfo.get('identifier')
                if identifier:
                    relpath  = spec.assetInfo['identifier'].path
                    primPath = spec.assetInfo['name']
                    utl.SetReference(spec, Sdf.Reference(relpath, primPath))
                    spec.assetInfo = {}
        outlyr.Save()
        del outlyr
