#coding:utf-8
from __future__ import print_function
import os

from pxr import Usd, UsdGeom, Sdf, Gf, Vt

import maya.api.OpenMaya as OpenMaya
import maya.cmds as cmds

import DXUSD.Vars as var

from DXUSD.Tweakers.Tweaker import Tweaker, ATweaker

import DXUSD_MAYA.Message as msg
import DXUSD_MAYA.MUtils as mutl
import DXUSD_MAYA.Utils as utl

class AMashVelocities(ATweaker):
    def __init__(self, **kwargs):
        self.computeData = {}   # {primPath: MASH_Python, ...}

        # initialize
        ATweaker.__init__(self, **kwargs)

    def Treat(self):
        nsname, nodename = mutl.GetNamespace(self.node)
        for o in cmds.getAttr('%s.renderMeshes' % self.node):
            prefix   = nsname + ':' if nsname else ''
            fullPath = cmds.ls(prefix + o, l=True)
            for s in cmds.ls(prefix + o, dag=True, type='surfaceShape', l=True, ni=True):
                connected = cmds.listConnections(s, type='MASH_Python')
                if connected:
                    primPath = cmds.listRelatives(s, p=True, f=True)[0].replace('|%s' % prefix, '/')
                    for c in connected:
                        if cmds.attributeQuery('velocities', n=c, ex=True):
                            self.computeData[primPath] = c

        return var.SUCCESS


class MashVelocities(Tweaker):
    ARGCLASS = AMashVelocities
    def DoIt(self):
        if not self.arg.computeData:
            return var.SUCCESS

        print('#### Mash Velocities export ####')
        for f in self.arg.geomfiles:
            self.Treat(f)

        return var.SUCCESS


    def Treat(self, geomfile):
        outlyr = utl.AsLayer(geomfile)
        if not outlyr:
            return

        start = int(outlyr.startTimeCode)
        end   = int(outlyr.endTimeCode)
        step  = 1.0
        customData = outlyr.customLayerData
        if customData.has_key('step'):
            step = customData['step']

        for frame in range(start, end+1):
            for sample in mutl.GetFrameSample(step):
                frameSample = frame + sample
                cmds.currentTime(frameSample)

                for primPath, mashpyNode in self.arg.computeData.items():
                    spec = outlyr.GetPrimAtPath(primPath)
                    if spec:
                        attrSpec = utl.GetAttributeSpec(spec, 'velocities', None, Sdf.ValueTypeNames.Vector3fArray)

                        cmds.dgeval(mashpyNode)
                        value = cmds.getAttr('%s.velocities' % mashpyNode)
                        setval= list()
                        for v in value:
                            setval.append(Gf.Vec3f(*v))

                        outlyr.SetTimeSample(attrSpec.path, frameSample, Vt.Vec3fArray(setval))

        outlyr.Save()
        return var.SUCCESS
