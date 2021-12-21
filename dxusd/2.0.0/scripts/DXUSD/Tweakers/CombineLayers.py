#coding:utf-8
from __future__ import print_function

import re

import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg
import DXUSD.Structures as srt
from DXUSD.Structures import Arguments
from .Tweaker import Tweaker, ATweaker

from pxr import Sdf, Usd
import dxdict   # pylibs module

class ACombineLayers(ATweaker):
    def __init__(self, **kwargs):
        '''
        inputs에 있는 모든 레이어에서, rules에 맞는 프림을 찾아 outputs 레이어의
        정해진 프림경로로 레퍼런스 한다. 모든 프림은 over 로 작성한다.

        [Attributes]
        inputs (layers or paths) : find prims in all input layers
        outputs (layer) : output layer

        rules (list) : rules of source and destination prim
            [ (source rule, destination rule [, srclyr index]), ... ]
            - source rule : None - use default prim
                            'regular expression' - match prim name with exp
                            'name=newname' - fine named prim and rename
                            '@radius=1' - find attr, and check the value (todo)
                            '$component' - find component kind (todo)
            - destination rule : None - use same prim path
                                 'prim path' - move prim under the given path
            - srclyr index : if multi sources, specify the index. (default = 0)
            eg. [
                [None, '/World'],
                    - ref default prim to under /World
                [None, '/World', 1]
                    - ref second source layer's default prim to /World
                ['.*_PLY', None]
                    - only prims that end with _PLY move to the
                    - same prim path
                ['Proxy=Laminations', None]
                    - prims named 'Proxy' move to the
                    - same prim path renaming to 'Laminations'
            ]
        '''
        self.rules = list()
        self.dprim = None
        ATweaker.__init__(self, **kwargs)


    def Treat(self):
        if not (self.inputs and self.outputs):
            msg.errmsg('Set inputs and outputs')
            return var.FAILED

        if not self.rules:
            return var.IGNORE

        return var.SUCCESS


class CombineLayers(Tweaker):
    ARGCLASS = ACombineLayers

    def DoIt(self):
        combines = []
        rules    = self.ResolveRules()
        dstlyr   = utl.AsLayer(self.arg.outputs[0], create=True)

        listCombines = []
        for i, srclyr in enumerate(self.arg.inputs):
            combines = self.GetCombines(utl.AsLayer(srclyr), dstlyr, rules[i])
            listCombines.append(combines)

        # copy layer metadata
        # utl.UpdateLayerData(dstlyr, self.arg.inputs[0]).doIt(up=True)

        # build scenegraph
        for i, combines in enumerate(listCombines):
            for j, combine in enumerate(combines):
                spec = utl.GetPrimSpec(dstlyr, combine[1], 'over')
                prefixes = spec.path.GetPrefixes()

                if len(prefixes) > 1:
                    leaf = dstlyr.GetPrimAtPath(prefixes.pop(-1))

                    # TODO: 레퍼런스가 등록되는 프림 상위의 대한 처리가 def Xform 으로
                    # 고정되어 있는데, 추후 다른 것이 필요하면, 업데이트가 필요하다.
                    for k, p in enumerate(prefixes):
                        p = dstlyr.GetPrimAtPath(p)
                        if p.specifier == var.OVER:
                            p.specifier = var.DEF
                            p.typeName = 'Xform'
                            if k == 0: # when root
                                p.kind = var.KIND.ASB
                spec.ClearReferenceList()
                spec.referenceList.prependedItems.append(combine[0])

        if self.arg.dprim:
            dstlyr.defaultPrim = utl.AsSdfDPrim(self.arg.dprim)
        elif dstlyr.rootPrims:
            dstlyr.defaultPrim = dstlyr.rootPrims[0].name

        # save layer
        self.arg.meta.Set(dstlyr)
        return var.SUCCESS


    def GetCombines(self, srclyr, dstlyr, rules):
        res = []
        srcrelpath = utl.GetRelPath(dstlyr.realPath, srclyr.realPath)
        with utl.OpenStage(srclyr) as stg:
            dprim = stg.GetDefaultPrim().GetPath()
            if rules.dprim:
                for rule in rules.dprim:
                    res.append(self.GetRefSpec(relpath, rule[1]))
            else:
                for prim in stg.TraverseAll():
                    if self.MatchName(prim, rules.name, srcrelpath, res):
                        continue
                    if self.MatchPath(prim, rules.path, srcrelpath, res):
                        continue
                    if self.MatchAttr(prim, rules.attr, srcrelpath, res):
                        continue
                    if self.MatchKind(prim, rules.kind, srcrelpath, res):
                        continue

        return res


    def MatchName(self, prim, rules, relpath, res):
        name = prim.GetName()
        for rule in rules:
            elms = rule[0].split('=')
            match = re.match(elms[0], name)
            if match and match.group() == name:
                if rule[1]:
                    if rule == '/':
                        dst = '/' + elms[len(elms) > 1]
                    else:
                        dst = rule[1].AppendChild(elms[len(elms) > 1])
                else:
                    dst = prim.GetPath()
                    if len(elms) > 1:
                        dst = dst.GetParentPath().AppendChild(elms[1])

                res.append(self.GetRefSpec(relpath, dst, prim.GetPath()))
                return True
        return False


    def MatchPath(self, prim, rules, relpath, res):
        path = str(prim.GetPath())
        for rule in rules:
            elms = rule[0].split('=')
            match = re.match(elms[0], path)
            if match and match.group() == path:
                if rule[1]:
                    _n = prim.GetName() if len(elms) == 1 else elms[1]
                    if rule[1] == '/':
                        dst = '/' + _n
                    else:
                        dst = rule[1].AppendChild(_n)
                else:
                    dst = prim.GetPath()
                    if len(elms) > 1:
                        dst = dst.GetParentPath().AppendChild(elms[1])
                res.append(self.GetRefSpec(relpath, dst, prim.GetPath()))
                return True
        return False

    def MatchAttr(self, prim, rules, relpath, res):
        # TODO: match attr
        return False


    def MatchKind(self, prim, rules, relpath, res):
        # TODO: match kind
        return False


    def GetRefSpec(self, relpath, dst, src=Sdf.Path.emptyPath):
        ref = Sdf.Reference(relpath, str(src))
        return (ref, dst)


    def ResolveRules(self):
        res = []
        for i in range(len(self.arg.inputs)):
            r = srt.Layers()
            r.AddLayer('dprim', [])
            r.AddLayer('path',  [])
            r.AddLayer('name',  [])
            r.AddLayer('attr',  [])
            r.AddLayer('kind',  [])
            res.append(r)
        for rule in self.arg.rules:
            idx = rule[2] if len(rule) > 2 else 0
            if rule[1]:
                if rule[1] != '/':
                    rule[1] = Sdf.Path(rule[1])
            if rule[0] == None:
                res[idx].dprim.append(rule)
            elif rule[0].startswith('@'):
                res[idx].attr.append([rule[0][1:], rule[1]])
            elif rule[0].startswith('$'):
                res[idx].kind.append([rule[0][1:], rule[1]])
            elif rule[0].startswith('/'):
                res[int(idx)].path.append([rule[0], rule[1]])
            else:
                res[idx].name.append(rule)
        return res


class HCombineGroomLayers(Tweaker):
    ARGCLASS = ACombineLayers
    def __init__(self, arg, texData={}):
        self.texData   = texData
        self.bodyMeshLayerData = {}
        Tweaker.__init__(self, arg)

    def DoIt(self):
        dstlyr = utl.AsLayer(self.arg.outputs[0])
        for spec in dstlyr.rootPrims[0].nameChildren:
            with utl.OpenStage(dstlyr) as stage:
                treeIter = iter(Usd.PrimRange.AllPrims(stage.GetPseudoRoot()))
                treeIter.next()
                for p in treeIter:
                    if p.GetName() == spec.name:
                        txClassPath= self.bodyMeshAttributeClass(dstlyr, p)
                        utl.SetInherit(txClassPath, spec)
                        self.curvesAttributes(p, spec)
        dstlyr.Save()
        del dstlyr

    def curvesAttributes(self, prim, spec):
        utl.GetAttributeSpec(spec, 'primvars:useHairNormal', 1,
            Sdf.ValueTypeNames.Float, info={'interpolation': 'constant'})

        materialset = prim.GetAttribute('userProperties:MaterialSet').Get(0)
        utl.GetAttributeSpec(spec, var.T.ATTR_MATERIALSET, materialset,
                             Sdf.ValueTypeNames.String, custom=True)

    def bodyMeshAttributeClass(self, dstlyr, prim):
        basePath = prim.GetAttribute('primvars:txBasePath').Get(0)
        layerName = prim.GetAttribute('primvars:txLayerName').Get(0)
        modelVer = prim.GetAttribute('primvars:modelVersion').Get(0)

        texDir = utl.SearchInDirs(self.arg.D.PUB, basePath)
        texDir = utl.SJoin(texDir, var.T.TEX)
        texVer = utl.GetLastVersion(texDir)

        arg = Arguments()
        arg.D.SetDecode(texDir)
        arg.name = layerName

        texUsd = utl.SJoin(texDir, arg.F.MASTER)
        texAttr = utl.SJoin(texDir, texVer, arg.F.ATTR)
        txClassPath = arg.N.PRIM_TXATTR

        primData = {
            texAttr: {layerName: {'attrs': {var.T.ATTR_MODELVER: modelVer,
                                            var.T.ATTR_TXMULTIUV: 0},
                                  'classPath': txClassPath}}
        }

        # update texData
        dxdict.deepupdate(self.texData, primData)

        # create attribute classprim
        spec = dstlyr.GetPrimAtPath(txClassPath)
        if not spec:
            spec = utl.GetPrimSpec(dstlyr, txClassPath, specifier='class')
            relpath = utl.GetRelPath(dstlyr.identifier, texUsd)
            utl.SetReference(spec, Sdf.Reference(relpath, '/' + layerName))
            spec.variantSelections.update({var.T.VAR_MODELVER: modelVer})
            utl.GetAttributeSpec(spec, var.T.ATTR_MODELVER, modelVer,
                                 Sdf.ValueTypeNames.String, info={'interpolation': 'constant'})

        return txClassPath
