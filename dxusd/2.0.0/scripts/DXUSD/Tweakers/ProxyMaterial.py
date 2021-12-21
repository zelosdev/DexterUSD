#coding:utf-8
from __future__ import print_function
import os

from pxr import Sdf, Usd

from .Tweaker import Tweaker, ATweaker
import DXUSD.Arcs as arc
import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg


class AProxyMaterial(ATweaker):
    def __init__(self, **kwargs):
        '''
        [Arguments]
        mtlDir     (str) : proxy.mtl.usd dirpath (proxy version path). for standalone
        texAttrUsd (str) : tex.attr.usd fullpath.
        '''
        self.libFile= '/assetlib/3D/usd/material/preview/preview.usd'
        self.mtlDir = None
        self.texAttrUsd = None
        self.texData    = dict()
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
        if not self.mtlDir and not self.texAttrUsd:
            msg.errmsg('Treat@%s :' % self.__name__, 'No mtlDir or texAttrUsd')
            return var.FAILED

        self.modelVersion = None
        if self.texAttrUsd:
            self.D.SetDecode(utl.DirName(self.texAttrUsd))
            self.nslyr  = 'proxy'
            self.nsver  = utl.GetLastVersion(self.D.TASKN)
            self.mtlUsd = utl.SJoin(self.D.TASKNV, self.F.MTL)
        else:
            # work by standalone
            self.D.SetDecode(utl.DirName(self.mtlDir))
            self.mtlUsd = utl.SJoin(self.mtlDir, self.F.MTL)
            args = self.Switch(task=var.T.MODEL)
            self.modelVersion = utl.GetLastVersion(var.D.TASK.Encode(**args))

        if not self.texData:
            dirPath = utl.DirName(self.mtlUsd)
            msg.debug('[ Get Texture Information ] : %s' % dirPath)
            self.texData = self.getTexData(dirPath)

        return var.SUCCESS


    def getTexData(self, dirpath):
        result = dict()

        files = utl.GetFilesInDir(dirpath, ext='jpg')
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



class ProxyMaterial(Tweaker):
    ARGCLASS = AProxyMaterial
    def DoIt(self):
        msg.debug('%s.DoIt :' % self.__name__, self.arg.mtlUsd)
        self.outlyr = utl.AsLayer(self.arg.mtlUsd, create=True)
        self.outlyr = utl.CheckPipeLineLayerVersion(self.outlyr)

        utl.SetSublayer(self.outlyr, self.arg.libFile)
        for txlayer in self.arg.texData:
            self.createMaterial(txlayer)

        self.outlyr.Save()
        del self.outlyr

        self.composite()
        return var.SUCCESS

    def createMaterial(self, txlayer):
        attrs = self.arg.texData[txlayer]['attrs']
        targetMtl = '/preview/surface'
        if txlayer.endswith('_ZN'):
            targetMtl = '/preview/curve'

        spec = utl.GetPrimSpec(self.outlyr, '/' + txlayer, type='Material')
        utl.SetSpecialize(targetMtl, spec)

        modelver = self.arg.modelVersion
        if attrs.has_key(var.T.ATTR_MODELVER) and attrs[var.T.ATTR_MODELVER]:
            modelver = attrs[var.T.ATTR_MODELVER]
        if not modelver:
            return

        vsetSpec= utl.GetVariantSetSpec(spec, var.T.VAR_MODELVER)
        vspec   = utl.GetVariantSpec(vsetSpec, modelver)
        spec.variantSelections.update({var.T.VAR_MODELVER: modelver})

        primSpec = utl.GetPrimSpec(self.outlyr, vspec.primSpec.path.AppendPath('pbsSurface/diffC_Tex'), specifier='over')
        attrSpec = utl.GetAttributeSpec(primSpec, 'inputs:file', '', Sdf.ValueTypeNames.Asset)
        txname = txlayer + '_diffC'
        if attrs[var.T.ATTR_TXMULTIUV]:
            txname += '.<UDIM>'
        txname += '.jpg'
        attrSpec.default = './' + txname


    def composite(self):
        proxyUsd = utl.SJoin(self.arg.D.TASKN, self.arg.F.PROXY)
        outlyr = utl.AsLayer(proxyUsd, create=True)
        relpath= utl.GetRelPath(proxyUsd, self.arg.mtlUsd)
        utl.SetSublayer(outlyr, relpath)
        outlyr.Save()
        del outlyr
