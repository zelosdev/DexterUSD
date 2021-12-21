#coding:utf-8
from __future__ import print_function
import os

from pxr import Usd, Sdf

import DXUSD.Vars as var

import DXUSD_MAYA.Exporters as exp
import DXUSD_MAYA.MUtils as mutl
import DXUSD_MAYA.Utils as utl
import DXUSD_MAYA.Message as msg

import maya.cmds as cmds


class ModelExport(exp.ModelExporter):
    def Exporting(self):
        # TEST
        print('#### ModelExport ####')

        # Custom User Attributes
        UsdAttr = utl.UsdUserAttributes(self.arg.nodes)
        UsdAttr.exclude = ['txVersion']
        UsdAttr.Set()

        for i in range(len(self.arg.nodes)):
            node = self.arg.nodes[i]
            ofile= self.arg.geomfiles[i]

            if cmds.nodeType(node) == 'dxBlock' or cmds.nodeType(node) == 'TN_TaneTransform':
                self.arg.ptNodes += cmds.ls(node, l=True)
            else:
                utl.UsdExport(ofile, node).doIt()

                # get dxBlock,Tane nodes
                try:
                    xnodes = cmds.listRelatives(node, c=True, f=True, type=['dxBlock','TN_TaneTransform'])
                except:
                    xnodes = cmds.listRelatives(node, c=True, f=True, type=['dxBlock'])

                if xnodes:
                    self.arg.ptNodes += xnodes
                    self.removePrims(ofile, xnodes)

        # Custom User Attributes Clear
        UsdAttr.Clear()

    def removePrims(self, filename, nodes): # fullpath node list
        outlyr = utl.AsLayer(filename)
        editor = Sdf.BatchNamespaceEdit()
        for n in nodes:
            editor.Add(n.replace('|', '/'), Sdf.Path.emptyPath)
        outlyr.Apply(editor)
        outlyr.Save()
        del outlyr


    # def Tweaking(self):
    #     return var.SUCCESS
    # def Compositing(self):
    #     return var.SUCCESS


class LidarExport(exp.LidarExporter):
    def Exporting(self):
        print('#### LidarExport ####')

        for i in range(len(self.arg.nodes)):
            node = self.arg.nodes[i]
            ofile= self.arg.geomfiles[i]

            utl.UsdExport(ofile, node).doIt()

            for idx, mesh in enumerate(sorted(cmds.listRelatives(node, f=True))):
                if '_low' in mesh:   lod = 'low'
                else:                lod = 'high'

                if '_bg' in mesh:   num = 'bg'
                else:               num = str(idx+1).zfill(2)

                abcFile = '%s_lidar_%s.%s_geom.obj' % (self.arg.asset, num, lod)
                exportPath = os.path.join(self.arg.dstdir, abcFile)

                if not cmds.pluginInfo('objExport', q=True, l=True):
                    cmds.loadPlugin('objExport')

                cmds.select(mesh)
                cmds.file(exportPath, pr=1, typ='OBJexport', es=1,
                          op='groups=0;ptgroups=0;materials=0;smoothing=0;normals=0')
                msg.debug('> Export OBJ\t:', exportPath)
                # mutl.AbcExport(exportPath, [mesh])


def assetExport(nodes=[], show=None, shot=None, version=None):
    if not nodes:
        return '# message : not found nodes.'
    # current scene filename
    sceneFile = cmds.file(q=True, sn=True)

    expnodes = list()
    # visible check
    for n in nodes:
        if mutl.GetViz(cmds.ls(n, l=True)[0]):
            expnodes.append(n)
    if not expnodes:
        return '# message : not found export nodes.'

    arg = exp.AModelExporter()
    arg.scene = sceneFile
    arg.nodes = expnodes
    # override
    if show: arg.ovr_show = show
    if shot: arg.ovr_shot = shot
    if version: arg.ovr_ver  = version
    ModelExport(arg)


def mtkExport(nodes=[], customdir=''):
    if not nodes:
        return '# message : not found nodes. skip model export.'
    # current scene filename
    sceneFile = cmds.file(q=True, sn=True)

    expnodes = list()
    # visible check
    for n in nodes:
        if mutl.GetViz(cmds.ls(n, l=True)[0]):
            expnodes.append(n)
    if not expnodes:
        return '# message : not found export nodes. skip model export.'

    arg = exp.AModelExporter()
    arg.scene = sceneFile
    arg.nodes = expnodes
    arg.customdir = customdir
    ModelExport(arg)


def lidarExport(nodes=[], show=None, version=None):
    if not nodes:
        return '# message : not found nodes.'
    # current scene filename
    sceneFile = cmds.file(q=True, sn=True)

    arg = exp.ALidarExporter()
    arg.scene = sceneFile
    arg.nodes = nodes

    # override
    if show: arg.ovr_show = show
    if version: arg.ovr_ver  = version

    LidarExport(arg)
