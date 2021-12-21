#coding:utf-8
from __future__ import print_function
import os, glob

from pxr import Sdf, Usd, UsdGeom, Vt, Gf

from .Tweaker import Tweaker, ATweaker
from DXUSD.Structures import Arguments
import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg

class ALoopClip(ATweaker):
    def __init__(self, **kwargs):
        '''
        [Arguments]
        geomfiles (list) : input geom files
            geomfile must have - customLayerData start, end
        '''

        self.timeScales= [0.8, 1.0, 1.2]
        self.loopRange = (1001, 1200)
        self.frameSample = [0.0]

        self.clipRange = ()                 # for update or modify source clipRange

        # initialize
        ATweaker.__init__(self, **kwargs)

    def Treat(self):
        if not self.has_attr('geomfiles'):
            msg.errmsg('Treat@%s' % self.__name__, 'No geomfiles.')
            return var.FAILED
        return var.SUCCESS


class LoopClip(Tweaker):
    ARGCLASS = ALoopClip
    def DoIt(self):
        # print('>', self.arg)
        for gf in self.arg.geomfiles:
            if '/base/' in gf:
                for ts in self.arg.timeScales:
                    self.Treat(gf, ts)
        return var.SUCCESS


    def Treat(self, srcfile, timeScale):
        # Loop Clip Name
        # name = 'loop_%s' % str(timeScale).replace('.', '_')
        name = str(timeScale).replace('.', '_')

        outfile = srcfile.replace('/base/', '/%s/' % name)
        msg.debug('Treat@%s' % self.__name__, outfile)

        srclyr = utl.AsLayer(srcfile)
        dname  = srclyr.defaultPrim

        dstlyr = utl.AsLayer(outfile, create=True, clear=True)
        dstlyr.defaultPrim = dname
        spec = utl.GetPrimSpec(dstlyr, '/' + dname, specifier='over')

        relpath = utl.GetRelPath(outfile, srcfile)
        utl.SubLayersAppend(dstlyr, relpath)
        utl.UpdateLayerData(dstlyr, srclyr).doIt()

        customLayerData = dstlyr.customLayerData

        # valueclip for loop
        if customLayerData.has_key('start') and customLayerData.has_key('end'):
            clipRange = (customLayerData['start'], customLayerData['end'])
        else:
            clipRange = (int(dstlyr.startTimeCode) + 1, int(dstlyr.endTimeCode) - 1)

        if self.arg.clipRange: clipRange = self.arg.clipRange

        times= self.new_computeLoopTimes(clipRange, timeScale)
        data = {
            'active': Vt.Vec2dArray([Gf.Vec2d(0, 0)]),
            'assetPaths': Sdf.AssetPathArray([Sdf.AssetPath(relpath)]),
            'primPath': '/' + dname,
            'times': Vt.Vec2dArray(times)
        }
        spec.SetInfo('clips', {'default': data})

        start = int(times[0][0]); end = int(times[-1][0])
        customLayerData['start'] = start
        customLayerData['end']   = end
        dstlyr.customLayerData   = customLayerData
        dstlyr.startTimeCode = start
        dstlyr.endTimeCode   = end

        with utl.OpenStage(dstlyr) as stage:
            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)

        dstlyr.Save()

        del dstlyr
        del srclyr
        return var.SUCCESS


    def computeLoopTimes(self, clipRange, timeScale):
        times = list()

        step  = int(round(clipRange[1] - clipRange[0] + 1) * (1.0 / timeScale))

        for i in range((self.arg.loopRange[1] - self.arg.loopRange[0]) / step):
            c_start = self.arg.loopRange[0] + step * i
            c_end   = c_start + step - 1
            if len(self.arg.frameSample) > 1:
                # start
                for t in self.arg.frameSample:
                    timeSet = (c_start + t, clipRange[0] + t)
                    if not timeSet in times:
                        times.append(timeSet)
                # end
                for t in self.arg.frameSample:
                    timeSet = (c_end + t, clipRange[1] + t)
                    if not timeSet in times:
                        times.append(timeSet)
            else:
                times.append((c_start, clipRange[0]))
                times.append((c_end, clipRange[1]))
                times.append((c_end + 0.5, clipRange[1] + 0.5))

        return times


    def new_computeLoopTimes(self, clipRange, timeScale):
        times = list()

        # clip duration
        duration = clipRange[1] - clipRange[0] + 1

        # stage time step
        step = int(duration / timeScale)
        # print('> step :', step, '/', 'timeScale :', timeScale)

        stage_start = self.arg.loopRange[0]
        clip_start  = clipRange[0]
        for i in range((self.arg.loopRange[1] - self.arg.loopRange[0]) / step):
            stage_end = stage_start + step

            # clip time
            clip_end = clip_start + (step * timeScale)
            clip_end = round(clip_end, 2)
            if int(clip_end) > clipRange[1]:
                clip_end -= timeScale
                stage_end-= 1

            # update times
            update_times = [(stage_start, clip_start), (stage_end, clip_end)]

            # for motionblur
            for s in range(1, 100):
                vs  = s * 0.01
                tmp = clip_end + (vs * timeScale)
                if int(tmp) > clipRange[1]:
                    break
                subframe = vs
                mb_end   = tmp

            update_times.append((stage_end + subframe, round(mb_end, 2)))
            if subframe != 0.99:
                subframe += 0.01
                mb_end    = clip_end + (subframe * timeScale) - duration
                update_times.append((stage_end + subframe, round(mb_end, 2)))

            # update times
            times += update_times

            # update clip start
            clip_start = clip_end + timeScale - duration
            clip_start = round(clip_start, 2)

            # update stage start
            stage_start = stage_end + 1

        return times
