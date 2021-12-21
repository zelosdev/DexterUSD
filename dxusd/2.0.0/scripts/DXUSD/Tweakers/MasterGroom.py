#coding:utf-8
from __future__ import print_function

import dxdict   # pylibs module

from pxr import Sdf, Usd, UsdGeom

from .Tweaker import Tweaker, ATweaker
from DXUSD.Structures import Arguments
import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg


class ACombineGroomLayers(ATweaker):
    def __init__(self, **kwargs):
        '''
        Create composited groom layers geom

        [Arguments]
        groom_outs (list)
        master     (str)
        customData (dict) : optional
        groom_reference   (dict) : optional. add subLayers. {'high': filename, 'low': filename}
        bodyMeshLayerData (dict) : optional
        bodyMeshAttrData  (dict) : optional
        groomAttrData     (dict) : optional
        '''
        # initialize
        ATweaker.__init__(self, **kwargs)

        self.outputs   = []     # *_geom.high.usd, *_geom.low.usd
        self.geomfiles = {'high': [], 'low': []}

    def Treat(self):
        if not self.groom_outs:
            msg.error('Treat@%s' % self.__name__, 'Not found groom_outs argument')
        if not self.master:
            msg.error('Treat@%s' % self.__name__, 'Not found master argument')

        master = self.master

        # if clip groom
        arg = Arguments()
        arg.D.SetDecode(utl.DirName(self.master))

        for out in self.groom_outs:
            for gtyp in self.geomfiles.keys():
                gfile = out + '.{}_geom.usd'.format(gtyp)
                if arg.task == 'clip':
                    gfile = gfile.replace('/base/', '/%s/' % arg.clip)
                self.geomfiles[gtyp].append(gfile)

        self.outputs.append(self.master.replace('.usd', '.high.usd'))
        self.outputs.append(self.master.replace('.usd', '.low.usd'))

        if self.has_attr('ovr_show'): self.show = self.ovr_show     # for MTK

        self.searchPath = self.GetSearchPath()
        return var.SUCCESS

class CombineGroomLayers(Tweaker):
    ARGCLASS = ACombineGroomLayers
    def __init__(self, arg, texData={}, meshFiles=[]):
        self.texData   = texData
        self.meshFiles = meshFiles
        Tweaker.__init__(self, arg)

    def DoIt(self):
        # HIGH
        self.CreateGeom(self.arg.outputs[0], 'high')
        # LOW
        self.CreateGeom(self.arg.outputs[1], 'low')

    def CreateGeom(self, output, gtyp):  # gtyp = high, low
        if self.arg.has_attr('customdir') and not self.arg.has_attr('show'):
            outlyr = utl.AsLayer(output, create=True)
        else:
            outlyr = utl.AsLayer(output, create=True, clear=True)
        if self.arg.has_attr('customData'):
            utl.UpdateLayerData(outlyr, self.arg.customData).doIt()
        utl.UpdateLayerData(outlyr, self.arg.geomfiles[gtyp][0]).doIt()

        if self.arg.has_attr('groom_reference') and self.arg.groom_reference:
            utl.SubLayersAppend(outlyr, utl.GetRelPath(output, self.arg.groom_reference[gtyp]))

        root = utl.GetPrimSpec(outlyr, '/Groom')
        root.SetInfo('kind', 'assembly')
        outlyr.defaultPrim = 'Groom'

        groomType = {}  # {ZN_Deform: Xform, ZN_Deform: BasisCurves}
        for fn in self.arg.geomfiles[gtyp]:
            name = utl.BaseName(fn).split('.')[0]   # groom layername
            type = self.GetRootType(fn)
            groomType[name] = type
            spec = utl.GetPrimSpec(outlyr, root.path.AppendChild(name), specifier='over')
            utl.ReferenceAppend(spec, utl.GetRelPath(output, fn))
            if not self.arg.has_attr('groom_reference') or self.arg.groom_reference == {}:
                if type != 'Xform':
                    self.curvesAttributes(spec)
                else:
                    self.meshFiles.append(fn)

        # attributes inherit
        if self.arg.has_attr('bodyMeshAttrData') and self.arg.has_attr('bodyMeshLayerData'):
            for shape, data in self.arg.bodyMeshAttrData.items():
                txClassPath = self.bodyMeshAttributeClass(outlyr, data)
                if txClassPath:
                    for node in self.arg.bodyMeshLayerData[shape]:
                        spec = outlyr.GetPrimAtPath(root.path.AppendChild(node))
                        if spec and groomType[node] != 'Xform':
                            utl.SetInherit(txClassPath, spec)
        else:
            msg.debug('# WARNING : not found argument bodyMeshAttrData')

        with utl.OpenStage(outlyr) as stage:
            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)

        outlyr.Save()
        del outlyr


    def curvesAttributes(self, spec):
        utl.GetAttributeSpec(spec, 'primvars:useHairNormal', 1,
            Sdf.ValueTypeNames.Float, info={'interpolation': 'constant'})

        if self.arg.has_attr('groomAttrData') and self.arg.groomAttrData.has_key(spec.name):
            for attr, data in self.arg.groomAttrData[spec.name].items():
                if attr.startswith('userProperties'):
                    utl.GetAttributeSpec(spec, attr, data['value'], data['type'], custom=True)
        else:
            utl.GetAttributeSpec(spec, var.T.ATTR_MATERIALSET, 'fur',
                Sdf.ValueTypeNames.String, custom=True)


    def bodyMeshAttributeClass(self, outlyr, data):
        if not (data.has_key(var.T.TXBASEPATH) and data.has_key(var.T.TXLAYERNAME)):
            return
        basePath  = data[var.T.TXBASEPATH]
        layerName = data[var.T.TXLAYERNAME]
        modelVer  = 'v001'
        if data.has_key(var.T.MODELVER):
            modelVer = data[var.T.MODELVER]

        texDir = utl.SearchInDirs(self.arg.searchPath, basePath)
        texDir = utl.SJoin(texDir, var.T.TEX)
        texVer = utl.GetLastVersion(texDir)

        arg = Arguments()
        arg.D.SetDecode(texDir)
        arg.name = layerName

        texUsd  = utl.SJoin(texDir, arg.F.MASTER)
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
        spec = outlyr.GetPrimAtPath(txClassPath)
        if not spec:
            spec = utl.GetPrimSpec(outlyr, txClassPath, specifier='class')
            relpath = utl.GetRelPath(outlyr.identifier, texUsd)
            spec.assetInfo = {'name': '/' + layerName, 'identifier': Sdf.AssetPath(relpath)}
            utl.SetReference(spec, Sdf.Reference(relpath, '/' + layerName))   # >>> doIt GroomLayerCompTex
            spec.variantSelections.update({var.T.VAR_MODELVER: modelVer})
            utl.GetAttributeSpec(spec, var.T.ATTR_MODELVER, modelVer,
                Sdf.ValueTypeNames.String, info={'interpolation': 'constant'})

        return txClassPath


    def GetRootType(self, filename):
        srclyr = utl.AsLayer(filename)
        spec   = srclyr.rootPrims[0]
        ntype  = spec.typeName
        return ntype




class AGroomLayerCompTex(ATweaker):
    def __init__(self, **kwargs):
        '''
        Composite texture tex.usd

        [Arguments]
        master (str)
        '''
        self.master = ''
        # initialize
        ATweaker.__init__(self, **kwargs)

        self.outputs = []

    def Treat(self):
        if not self.master:
            return var.IGNORE

        self.outputs.append(self.master.replace('.usd', '.high.usd'))
        self.outputs.append(self.master.replace('.usd', '.low.usd'))

        return var.SUCCESS

class GroomLayerCompTex(Tweaker):
    ARGCLASS = AGroomLayerCompTex
    def DoIt(self):
        for f in self.arg.outputs:
            self.Treat(f)

    def Treat(self, output):
        outlyr = utl.AsLayer(output)
        for spec in outlyr.rootPrims:
            if spec.path.pathString.endswith('_txAttr'):
                relpath  = spec.assetInfo['identifier'].path
                primPath = spec.assetInfo['name']
                utl.SetReference(spec, Sdf.Reference(relpath, primPath))
                spec.assetInfo = {}
        outlyr.Save()
        del outlyr


class AMasterGroomPack(ATweaker):
    def __init__(self, **kwargs):
        '''
        Create Groom Master

        [Arguments]
        master (str) : package output name
        groom_collection (str) : optional
        '''
        # initialize
        ATweaker.__init__(self, **kwargs)

        self.geomfiles = []

    def Treat(self):
        if not self.master:
            msg.errmsg('Treat@%s' % self.__name__, 'No master.')
            return var.FAILED

        arg = Arguments()
        arg.D.SetDecode(utl.DirName(self.master))

        self.geomfiles.append(self.master.replace('.usd', '.high.usd'))
        self.geomfiles.append(self.master.replace('.usd', '.low.usd'))

        return var.SUCCESS


class MasterGroomPack(Tweaker):
    ARGCLASS = AMasterGroomPack
    def DoIt(self):
        msg.debug('> Target Files :', self.arg.geomfiles)

        outlyr = utl.AsLayer(self.arg.master, create=True, clear=True)
        utl.UpdateLayerData(outlyr, self.arg.geomfiles[0]).doIt()

        default = self.arg.nslyr
        if self.arg.assetName:
            default = self.arg.assetName
        root = utl.GetPrimSpec(outlyr, '/' + default)
        outlyr.defaultPrim = default
        root.SetInfo('kind', 'assembly')
        root.assetInfo = {'name': default}

        # arc asset collection for shot
        if self.arg.has_attr('groom_collection') and self.arg.groom_collection:
            utl.ReferenceAppend(root, utl.GetRelPath(self.arg.master, self.arg.groom_collection))
            arg = Arguments()
            arg.D.SetDecode(utl.DirName(self.arg.groom_collection))
            if not arg.assetName:
                utl.AddCustomData(root, 'groupName', '')
            else:
                utl.AddCustomData(root, 'groupName', arg.assetName)

        groom = utl.GetPrimSpec(outlyr, root.path.AppendChild('Groom'))
        # render
        spec = utl.GetPrimSpec(outlyr, groom.path.AppendChild('Render'))
        utl.PayloadAppend(spec, utl.GetRelPath(self.arg.master, self.arg.geomfiles[0]))
        utl.SetPurpose(spec, 'render')
        # proxy
        spec = utl.GetPrimSpec(outlyr, groom.path.AppendChild('Proxy'))
        utl.PayloadAppend(spec, utl.GetRelPath(self.arg.master, self.arg.geomfiles[1]))
        utl.SetPurpose(spec, 'proxy')

        with utl.OpenStage(outlyr) as stage:
            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)

        outlyr.Save()
        del outlyr

        return var.SUCCESS
