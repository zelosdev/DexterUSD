# coding:utf-8
from __future__ import print_function
import pprint
import os

from pxr import Usd, UsdGeom, Sdf, Gf, Vt

import maya.api.OpenMaya as OpenMaya
import maya.cmds as cmds

import DXUSD.Vars as var

from DXUSD.Tweakers.Tweaker import Tweaker, ATweaker

import DXUSD.Utils as utl
import DXUSD_MAYA.Message as msg
import DXUSD_MAYA.MUtils as mutl
import math
'''
refData = {
    refName(Sdf.Path): {
        'filePath': reference file path,
        'nodes': [transform node, ...],
        'offset': dxTimeOffset node offset value,
        'primPath': get node attr,
        'excludePrimPaths': get node attr
    }
}
'''


class AInvisibleIds(ATweaker):
    def __init__(self, **kwargs):
        '''
        [Arguments]
        invNodes (list): compute nodes.
        geomfile  (str) : output geomfile
        '''
        self.invNodes = []

        # initialize
        ATweaker.__init__(self, **kwargs)

    def Treat(self):
        if not self.geomfiles:
            msg.errmsg('Treat@%s' % self.__name__, 'no dstdir argument.')
        if not self.invNodes:
            return var.IGNORE
        return var.SUCCESS


class InvisibleIds(Tweaker):
    ARGCLASS = AInvisibleIds

    def DoIt(self):
        print('self.arg.invNodes:',self.arg.invNodes)
        ofile = self.arg.geomfiles[0]
        print('ofile:', self.arg.geomfiles[0])
        dstlyr = utl.AsLayer(ofile)
        if not dstlyr:
            return

        for node in self.arg.nodes:
            self.SetInvisibleIds(node, ofile, dstlyr)

        dstlyr.Save()
        del dstlyr

        return var.SUCCESS


    def SetInvisibleIds(self, node, ofile, dstlyr):
        usdData = self.getUsdData(node, ofile)
        root = dstlyr.rootPrims[0]
        name = usdData[node]['name']

        if usdData[node].has_key('ids'):
            ids = []
            for sp in self.getSphere(node):
                scale = cmds.getAttr('%s.scale' % sp)[0]
                radius = max(list(scale))
                sPos = cmds.getAttr('%s.translate' % sp)[0]
                for index, pos in enumerate(usdData[node]['positions']):
                    if radius > self.getDistance(sPos, pos):
                        id = usdData[node]['ids'][index]
                        ids.append(id)

            if cmds.nodeType(node) == 'dxBlock':
                geomspec = utl.GetPrimSpec(dstlyr, root.path.AppendChild('Geom'), specifier='over')
                p = utl.GetPrimSpec(dstlyr, geomspec.path.AppendChild(name), specifier='over')
                s = utl.GetPrimSpec(dstlyr, p.path.AppendChild('scatter'), specifier='over')
                pspec = utl.GetPrimSpec(dstlyr, s.path.AppendChild(name), specifier='over')
                sspec = utl.GetPrimSpec(dstlyr, pspec.path.AppendChild('scatter'), specifier='over')

                if ids:
                    utl.GetAttributeSpec(sspec, 'invisibleIds', ids,
                                         Sdf.ValueTypeNames.Int64Array)

            else:
                spec = utl.GetPrimSpec(dstlyr, root.path.AppendChild(node), specifier='over')
                geomspec = utl.GetPrimSpec(dstlyr, spec.path.AppendChild('Geom'), specifier='over')
                pspec = utl.GetPrimSpec(dstlyr, geomspec.path.AppendChild(name), specifier='over')
                sspec = utl.GetPrimSpec(dstlyr, pspec.path.AppendChild('scatter'), specifier='over')
                if ids:
                    utl.GetAttributeSpec(sspec, 'invisibleIds', ids,
                                         Sdf.ValueTypeNames.Int64Array)

    def getUsdData(self,node, ofile):
        '''
        {node: {'name':      '',
                'positions': '',
                'ids':       '' }
        }
        '''
        stage = Usd.Stage.Open(ofile)
        dPrim = stage.GetDefaultPrim()
        treeIter = iter(Usd.PrimRange.AllPrims(dPrim))
        data = {}

        if cmds.nodeType(node) == 'dxBlock':
            primName = dPrim.GetName()
            data = {}
            data[primName] = {}
            for g in dPrim.GetChildren():
                for n in g.GetChildren():
                    for p in n.GetChildren():
                        if p.GetName() == 'scatter':
                            for pprim in p.GetChildren():
                                for pp in pprim.GetChildren():
                                    if p.GetName() == 'scatter':
                                        data[node]['name'] = pprim.GetName()
                                        pt = UsdGeom.PointInstancer(pp)
                                        data[node]['positions'] = pt.GetPositionsAttr().Get()
                                        data[node]['ids'] = pt.GetIdsAttr().Get()
        else:
            for i in treeIter:
                if i.GetName() == node:
                    data[node] = {}
                    for g in i.GetChildren():
                        for n in g.GetChildren():
                            for p in n.GetChildren():
                                if p.GetName() == 'scatter':
                                    data[node]['name'] = n.GetName()
                                    pt = UsdGeom.PointInstancer(p)
                                    data[node]['positions'] = pt.GetPositionsAttr().Get()
                                    data[node]['ids'] = pt.GetIdsAttr().Get()
        return data


    def getSphere(self,node):
        Modifiers = []
        for n in self.arg.nodes:
            getsphere = cmds.listRelatives(n, ad=True, c=True, type='nurbsSurface')
            if getsphere:
                for i in getsphere:
                    trans = cmds.listRelatives(i, p=True)[0]
                    if not trans in Modifiers:
                        if mutl.GetmeshViz(trans):
                            Modifiers.append(trans)
        if Modifiers:
            for i in Modifiers:
                cmds.parent(i, w=1)
                cmds.parent(i, node)

        return Modifiers


    def getDistance(self,pos1, pos2):
        x1, y1, z1 = pos1
        x2, y2, z2 = pos2
        distance = math.sqrt(math.pow(x2 - x1, 2) + math.pow(y2 - y1, 2) + math.pow(z2 - z1, 2))
        return distance