#coding:utf-8
from __future__ import print_function
import os

from pxr import Sdf, Usd, UsdGeom
import maya.cmds as cmds

from DXUSD.Tweakers import Tweaker, ATweaker
import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD_MAYA.Message as msg

class APurposeAttrSetup(ATweaker):
    def __init__(self, **kwargs):
        '''
        '''

        # initialize
        ATweaker.__init__(self, **kwargs)

    def Treat(self):
        if not self.node or not self.geomfiles:
            msg.errmsg('Treat@%s' % self.__name__, 'No inputs.')
            return var.FAILED
        return var.SUCCESS


class PurposeAttrSetup(Tweaker):
    ARGCLASS = APurposeAttrSetup
    def DoIt(self):
        for fn in self.arg.geomfiles:
            filePath = fn.replace('.usd', '.topology.usd')
            if os.path.exists(filePath):
                fn = filePath
            msg.debug('\t >>', fn)

            dstLayer = utl.AsLayer(fn)

            for n in cmds.ls(self.arg.node, dag=True, type='transform', l=True):
                if cmds.attributeQuery('USD_ATTR_purpose', n=n, ex=True):
                    val = cmds.getAttr('%s.USD_ATTR_purpose' % n)
                    if val == 'default':
                        if self.arg.nsLayer:
                            primPath = n.replace('|' + self.arg.nsLayer + ':', '/')
                        else:
                            primPath = n.replace('|', '/')
                        prim = dstLayer.GetPrimAtPath(primPath)
                        if prim:
                            UsdGeom.Scope(prim).CreatePurposeAttr(UsdGeom.Tokens.default_)

            tmpfile = fn.replace('.usd', '_tmp.usd')
            dstLayer.Export(tmpfile, args={'format': 'usdc'})
            os.remove(fn)
            os.rename(tmpfile, fn)
        return var.SUCCESS

    def initPrim(self, lyr, dst):
        prefixes = Sdf.Path(dst).GetPrefixes()
        for i in range(len(prefixes) - 1):
            prim = lyr.GetPrimAtPath(prefixes[i])
            if not prim:
                utl.GetPrimSpec(lyr, prefixes[i])


    def xformCopy(self, lyr, src, dst):
        dstPath = Sdf.Path(dst)
        prefixes = Sdf.Path(src).GetPrefixes()
        prefixes.reverse()
        for sp in prefixes[1:-1]:
            prim = lyr.GetPrimAtPath(sp)
            dstPath = dstPath.GetParentPath()
            if sp != dstPath:
                xformOpAttrs = prim.GetAuthoredPropertiesInNamespace('xformOp')
                if xformOpAttrs:
                    for attr in xformOpAttrs:
                        attrPath = attr.GetPath()
                        attrName = attr.GetName()
                        Sdf.CopySpec(lyr, attrPath, lyr, Sdf.Path(dstPath.pathString + '.' + attrName))
                    Sdf.CopySpec(lyr, Sdf.Path(sp.pathString + '.xformOpOrder'), lyr, Sdf.Path(dstPath.pathString +'.xformOpOrder'))
                else:
                    dstPrim = lyr.GetPrimAtPath(dstPath)
                    UsdGeom.Xform(dstPrim).CreateXformOpOrderAttr().Block()
