#coding:utf-8
from __future__ import print_function
import os
import alembic, imath

from pxr import Sdf, Usd, UsdGeom

from .Tweaker import Tweaker, ATweaker

import DXUSD.Arcs as arc
import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg


class AConvertAlembic(ATweaker):
    def __init__(self, **kwargs):
        ATweaker.__init__(self, **kwargs)

    def Treat(self):
        return var.SUCCESS

class ConvertAlembic(Tweaker):
    ARGCLASS = AConvertAlembic

    def DoIt(self):
        # currntly only cameras, the rest of geom later
        for geom in self.arg.geomfiles:
            self.CameraToAlembic(geom)

        return var.SUCCESS

    def CameraToAlembic(self, USDcam):
        stage = Usd.Stage.Open(USDcam)
        rootPrim = stage.GetPrimAtPath('/')
        dPrim = stage.GetDefaultPrim()
        fps = stage.GetFramesPerSecond()
        attrs = dPrim.GetAttributes()

        camInfo = {}
        for attr in attrs:
            frames = attr.GetTimeSamples()
            data = attr.Get()
            if frames:
                camInfo['frames'] = []
                data = []

            for f in frames:
                camInfo['frames'].append(f / fps)
                if 'Aperture' in attr.GetName():
                    data.append(attr.Get(Usd.TimeCode(f)) * 0.1)
                else:
                    data.append(attr.Get(Usd.TimeCode(f)))
            if data:
                camInfo[attr.GetName()] = data

        abcCamName = dPrim.GetName()
        outfile = USDcam.replace('.usd', '.abc')
        archive = alembic.Abc.OArchive(str(outfile))

        tVec = alembic.AbcCoreAbstract.TimeVector()
        tVec[:] = camInfo['frames'][0]
        timePerCycle = 1.0 / fps
        numSamplePerCycle = 1
        numSamps = len(camInfo['frames'])

        tst = alembic.AbcCoreAbstract.TimeSamplingType(numSamplePerCycle, timePerCycle)
        timeSample = alembic.AbcCoreAbstract.TimeSampling(tst, tVec)
        tsIdx = archive.addTimeSampling(timeSample)

        stepSize = float(tst.getTimePerCycle())
        start = timeSample.getSampleTime(0) / stepSize
        end = timeSample.getSampleTime(numSamps-1) / stepSize

        xform = alembic.AbcGeom.OXform(archive.getTop(), abcCamName, tsIdx)
        xfSample = alembic.AbcGeom.XformSample()
        xfOp = alembic.AbcGeom.XformOp()

        cam = alembic.AbcGeom.OCamera(xform, '%sShape' % abcCamName, tsIdx)
        camSample = alembic.AbcGeom.CameraSample()

        for cnt, info in enumerate(camInfo['xformOp:translate']):
            trans = imath.V3d(*info)
            rot = imath.V3d(*camInfo['xformOp:rotateZXY'][cnt])
            xfSample.setTranslation(trans)
            xfSample.setYRotation(rot[1])
            xfSample.setXRotation(rot[0])
            xfSample.setZRotation(rot[2])
            xform.getSchema().set(xfSample)

            camSample.setHorizontalAperture(camInfo['horizontalAperture'][cnt])
            camSample.setVerticalAperture(camInfo['verticalAperture'][cnt])
            if camInfo.has_key('horizontalApertureOffset'):
                camSample.setHorizontalFilmOffset(camInfo['horizontalApertureOffset'][cnt])
            if camInfo.has_key('verticalApertureOffset'):
                camSample.setVerticalFilmOffset(camInfo['verticalApertureOffset'][cnt])
            camSample.setFocalLength(camInfo['focalLength'][cnt])
            camSample.setFocusDistance(camInfo['focusDistance'][cnt])
            camSample.setFStop(camInfo['fStop'][cnt])
            camSample.setNearClippingPlane(camInfo['clippingRange'][cnt][0])
            camSample.setFarClippingPlane(camInfo['clippingRange'][cnt][1])
            cam.getSchema().set(camSample)
        return var.SUCCESS
