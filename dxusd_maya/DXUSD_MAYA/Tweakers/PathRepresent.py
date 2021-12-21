#coding:utf-8
from __future__ import print_function
import os

from pxr import Sdf, Usd, UsdGeom, Vt
import maya.cmds as cmds

from DXUSD.Tweakers import Tweaker, ATweaker
import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD_MAYA.Message as msg

class APathRepresent(ATweaker):
    def __init__(self, **kwargs):
        '''
        '''

        # initialize
        ATweaker.__init__(self, **kwargs)

    def Treat(self):
        if not self.node or not self.geomfiles:
            msg.errmsg('Treat@%s' % self.__name__, 'No inputs.')
            return var.FAILED
        self.rootPath = cmds.getAttr('%s.rootPrimPath' % self.refNode)
        return var.SUCCESS


class PathRepresent(Tweaker):
    ARGCLASS = APathRepresent
    def DoIt(self):
        for fn in self.arg.geomfiles:
            dstLayer = utl.AsLayer(fn)
            dprim = dstLayer.rootPrims[0]

            msg.debug(dprim)

            editor = Sdf.BatchNamespaceEdit()
            for shape in cmds.ls(self.arg.node, dag=True, s=True, ni=True):
                trNode = cmds.listRelatives(shape, p=True, f=True)[0]
                srcPath = trNode.replace(':', '_').replace('|', '/')
                dstPath = cmds.getAttr('%s.primPath' % trNode)
                # msg.debug(srcPath, '->', dstPath)
                if srcPath != dstPath:
                    self.initPrim(dstLayer, dstPath)
                    editor.Add(srcPath, dstPath)
                    # Copy Xform Attribute
                    self.xformCopy(dstLayer, srcPath, dstPath)
            dstLayer.Apply(editor)

            dprimPath = cmds.ls(self.arg.node, l=True)[0].replace(':', '_').replace('|', '/')
            if dprimPath != self.arg.rootPath:
                edit = Sdf.BatchNamespaceEdit()
                edit.Add('/' + dprimPath.split('/')[1], Sdf.Path.emptyPath)
                dstLayer.Apply(edit)

            dprim = dstLayer.rootPrims[0]
            dstLayer.defaultPrim = dprim.name

            if dprim.properties.get('xformOpOrder') and isinstance(dprim.properties.get('xformOpOrder').default, Vt.TokenArray):
                msg.debug(dprim.properties.get('xformOpOrder').default)
                for attr in dprim.properties.get('xformOpOrder').default:
                    attrSpec = dprim.properties.get(attr)
                    if attrSpec:
                        dprim.RemoveProperty(attrSpec)
                dprim.RemoveProperty(dprim.properties.get('xformOpOrder'))

            # # Remove Geom & Looks
            # with utl.OpenStage(dstLayer) as stage:
            #     defaultPrim = stage.GetDefaultPrim()
            #     removeEdit = Sdf.BatchNamespaceEdit()
            #     for prefixPrim in defaultPrim.GetChildren():
            #         removeEdit.Add(prefixPrim.GetPath().pathString, Sdf.Path.emptyPath)
            #         msg.debug(prefixPrim.GetPath().pathString, '->', Sdf.Path.emptyPath)
            #
            #         for childPrim in prefixPrim.GetChildren():
            #             msg.debug(prefixPrim.GetPath().pathString, prefixPrim.GetName())
            #             msg.debug(childPrim.GetPath().pathString, childPrim.GetName())
            #             msg.debug(childPrim.GetPath().pathString, '->', childPrim.GetPath().pathString.replace('/%s' % prefixPrim.GetName(), ''))
            #
            #
            #     removeEdit.Add(dprimPath + '/Geom/noneTransform_GRP', dprimPath + '/noneTransform_GRP')
            #     removeEdit.Add(dprimPath + '/Geom', Sdf.Path.emptyPath)
            #     dstLayer.Apply(removeEdit)

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
                xformOpAttrs = prim.properties.get('xformOpOrder')
                if xformOpAttrs:
                    if isinstance(xformOpAttrs.default, Vt.TokenArray):
                        for attr in xformOpAttrs.default:
                            attrPath = attr.path
                            attrName = attr.name
                            Sdf.CopySpec(lyr, attrPath, lyr, Sdf.Path(dstPath.pathString + '.' + attrName))
                        Sdf.CopySpec(lyr, Sdf.Path(sp.pathString + '.xformOpOrder'), lyr, Sdf.Path(dstPath.pathString +'.xformOpOrder'))
                    else:
                        dstPrim = lyr.GetPrimAtPath(dstPath)
                        UsdGeom.Xform(dstPrim).CreateXformOpOrderAttr().Block()
