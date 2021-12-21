# coding:utf-8
from __future__ import print_function

import os
import string
import math

from pxr import Gf, Sdf, Usd, Vt, UsdGeom

import maya.api.OpenMaya as OpenMaya
import maya.cmds as cmds

import DXUSD.Vars as var

import DXUSD_MAYA.Message as msg
import DXUSD_MAYA.Exporters as exp
import DXUSD_MAYA.MUtils as mutl
import DXUSD_MAYA.Utils as utl


class LayoutGeomExport(exp.LayoutExporter):
    def Exporting(self):
        self.arg.customData = {
            'sceneFile': self.arg.scene,
            'start': self.arg.frameRange[0],
            'end': self.arg.frameRange[1]
        }
        extnodes = []
        for node in self.arg.nodes:
            if cmds.listRelatives(node, ad=True, c=True, type='nurbsSurface'):
                self.arg.invNodes.append(node)
            if cmds.nodeType(node) == 'dxBlock':
                action = cmds.getAttr('%s.action' % node)
                btype  = cmds.getAttr('%s.type' % node)
                if action == 1:
                    if btype == 2:      # PointInstancer
                        self.arg.ptNodes.append(node)
                    elif btype == 1:    # Model
                        self.arg.N.layout.SetDecode(node)
                        geomfile = utl.SJoin(self.arg.dstdir, self.arg.F.GEOM)
                        self.arg.geomfiles.append(geomfile)

                        customData = self.arg.customData.copy()
                        importFile = cmds.getAttr('%s.importFile' % node)
                        if importFile:
                            customData['importFile'] = importFile

                        utl.UsdExport(geomfile, node, fr=self.arg.frameRange, fs=self.arg.frameSample,
                                      customLayerData=customData).doIt()
            else:
                if not cmds.nodeType(node) == 'dxAssembly':
                    extnodes.append(node)

        if extnodes:
            node = cmds.group(extnodes, n=self.arg.nslyr)
            self.arg.N.layout.SetDecode(node)
            geomfile = utl.SJoin(self.arg.dstdir, self.arg.F.GEOM)
            self.arg.geomfiles.append(geomfile)
            utl.UsdExport(geomfile, node, fr=self.arg.frameRange, fs=self.arg.frameSample,
                          customLayerData=self.arg.customData).doIt()

        return var.SUCCESS

    def Compositing(self):
        return var.SUCCESS


class LayoutCompositor(exp.LayoutExporter):
    def Exporting(self):
        return var.SUCCESS

    def Tweaking(self):
        return var.SUCCESS


def shotExport(nodes=None, overwrite=False, show=None, seq=None, shot=None,
               version=None, user='anonymous', fr=[0, 0], step=1.0, process='geom'):
    if not nodes:
        return
    # current scene filename
    sceneFile = cmds.file(q=True, sn=True)

    expnodes = list()
    # visible check
    for n in nodes:
        if mutl.GetViz(cmds.ls(n, l=True)[0]):
            expnodes.append(n)
    if not expnodes:
        return '# message : not found export nodes.'

    arg = exp.ALayoutExporter()
    arg.scene = sceneFile
    arg.nodes = expnodes
    arg.overwrite = overwrite
    arg.step = step
    arg.frameRange  = mutl.GetFrameRange()
    arg.frameSample = mutl.GetFrameSample(step)

    # override
    if show: arg.ovr_show = show
    if seq:  arg.ovr_seq  = seq
    if shot: arg.ovr_shot = shot
    if version: arg.ovr_ver = version
    if fr != [0, 0]:
        arg.frameRange = fr

    if process == 'both':
        LayoutGeomExport(arg)
        arg.overwrite = True
        exporter = LayoutCompositor(arg)
    else:
        if process == 'geom':
            exporter = LayoutGeomExport(arg)
        else:
            exporter = LayoutCompositor(arg)
    return exporter.arg.master
