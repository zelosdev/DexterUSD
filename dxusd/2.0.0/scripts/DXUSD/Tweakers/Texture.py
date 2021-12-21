#coding:utf-8
from __future__ import print_function

from pxr import Sdf, Usd
import shutil, os

from DXUSD.Structures import Arguments
from .Tweaker import Tweaker, ATweaker
import DXUSD.Arcs as arc
import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg


class ATexture(ATweaker):
    def __init__(self, **kwargs):
        '''
        [Arguments]
        texAttrDir (str)  : tex.attr.usd dirpath (texture version path). for standalone
        texAttrUsd (str)  : tex.attr.usd fullpath
        texData (dict)    : texture data information
        '''

        self.texAttrDir = None
        self.texAttrUsd = None
        self.texData    = dict()
        self.modelVersion = None
        # {$txLayerName:
        #     {'attrs':
        #         {var.T.ATTR_MODELVER: 'v001', # if task is model, it's none
        #          var.T.ATTR_TXMULTIUV: 0
        #         },
        #      'channels': ['diffC', ...]
        #     }
        # }

        # initialize
        ATweaker.__init__(self, **kwargs)

    def Treat(self):
        if not self.texAttrDir and not self.texAttrUsd:
            msg.errmsg('Treat@%s :' % self.__name__, 'No texAttrDir or texAttrUsd')
            return var.FAILED

        if self.texAttrDir:
            msg.debug(self.texAttrDir)
            # work by standalone
            dirPath = self.texAttrDir
            self.D.SetDecode(dirPath)
            self.texAttrUsd = utl.SJoin(dirPath, self.F.ATTR)
            args = self.Switch(task=var.T.MODEL)
            if self.modelVersion is None:
                self.modelVersion = utl.GetLastVersion(var.D.TASK.Encode(**args))
        else:
            msg.debug(self.texAttrUsd)
            dirPath = utl.DirName(self.texAttrUsd)
            self.D.SetDecode(dirPath)

        msg.debug(self.assetRoot)
        self.basePath = self.D.TASK.split(self.assetRoot + '/')[-1]
        self.version  = self.nsver

        if not self.texData:
            msg.debug('[ Get Texture Information ] : %s' % dirPath)
            self.texData = self.getTexData(dirPath)

        return var.SUCCESS


    def getTexData(self, dirpath):
        result = dict()

        files = utl.GetFilesInDir(dirpath, ext='tex')
        for n in files:
            try:
                dc = var.F.MAP.MASTER.Decode(n)
            except:
                msg.errmsg('can not decode filename : %s' % n)
                continue

            if not dc.name:
                src = dc.unknown.split('_')
                dc.channel = src[-1]
                dc.name    = '_'.join(src[:-1])
            txlayer = dc.name

            if result.has_key(txlayer):
                data = result[txlayer]
            else:
                result[txlayer] = {
                    'attrs': {var.T.ATTR_TXMULTIUV: 0},
                    'channels': []
                }
                data = result[txlayer]

            if dc.udimnum:
                data['attrs'][var.T.ATTR_TXMULTIUV] = 1
            data['channels'].append(dc.channel)
        return result



class Texture(Tweaker):
    ARGCLASS = ATexture
    def DoIt(self):
        msg.debug('%s.DoIt :' % self.__name__, self.arg.texAttrUsd)
        outlyr = utl.AsLayer(self.arg.texAttrUsd, create=True)
        outlyr = utl.CheckPipeLineLayerVersion(outlyr)
        for txlayer in self.arg.texData:
            spec = utl.GetPrimSpec(outlyr, '/' + txlayer, specifier='class')
            attrs= self.arg.texData[txlayer]['attrs']
            self.createGeom(spec, txlayer, attrs)
            self.modelVersionVariant(spec, attrs)
        outlyr.Save()
        del outlyr

        # composite
        self.composite()

        return var.SUCCESS


    def createGeom(self, spec, txlayer, attrs):
        # txBasePath
        utl.GetAttributeSpec(spec, var.T.ATTR_TXBASEPATH, self.arg.basePath, Sdf.ValueTypeNames.String, info={'interpolation': 'constant'})
        # txLayerName
        utl.GetAttributeSpec(spec, var.T.ATTR_TXLAYERNAME, txlayer, Sdf.ValueTypeNames.String, info={'interpolation': 'constant'})
        # udim
        udim = attrs[var.T.ATTR_TXMULTIUV]
        if udim:
            utl.GetAttributeSpec(spec, var.T.ATTR_TXMULTIUV, udim, Sdf.ValueTypeNames.Int, info={'interpolation': 'constant'})
        else:
            utl.DelAttributeSpec(spec, var.T.ATTR_TXMULTIUV)

        # channels
        if self.arg.texData[txlayer].has_key('channels'):
            for ch in self.arg.texData[txlayer]['channels']:
                if ch:
                    utl.GetAttributeSpec(spec, 'userProperties:Texture:channels:' + ch, 1, Sdf.ValueTypeNames.Int, custom=True)
                    if 'dis' in ch:
                        utl.GetAttributeSpec(spec, var.T.ATTR_DISBOUND, 0.1, Sdf.ValueTypeNames.Float)

    def modelVersionVariant(self, spec, attrs):
        modelver = self.arg.modelVersion
        if attrs.has_key(var.T.ATTR_MODELVER) and attrs[var.T.ATTR_MODELVER]:
            modelver = attrs[var.T.ATTR_MODELVER]
        if not modelver:
            return

        vsetSpec = utl.GetVariantSetSpec(spec, var.T.VAR_MODELVER)
        if modelver in spec.GetVariantNames(var.T.VAR_MODELVER):
            vpath = spec.path.AppendVariantSelection(var.T.VAR_MODELVER, modelver)
            vspec = spec.layer.GetPrimAtPath(vpath)
        else:
            vspec = Sdf.VariantSpec(vsetSpec, modelver).primSpec
        spec.variantSelections.update({var.T.VAR_MODELVER: modelver})
        utl.GetAttributeSpec(vspec, var.T.ATTR_TXVERSION, self.arg.version, Sdf.ValueTypeNames.String)


    def composite(self):
        texUsd = utl.SJoin(self.arg.D.TASKN, self.arg.F.TEX)
        outlyr = utl.AsLayer(texUsd, create=True)
        relpath= utl.GetRelPath(texUsd, self.arg.texAttrUsd)
        utl.SetSublayer(outlyr, relpath)
        outlyr.Save()
        del outlyr
