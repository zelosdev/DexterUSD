#coding:utf-8
from __future__ import print_function

from pxr import Sdf

import DXUSD.Utils as utl
import DXUSD_HOU.Message as msg
from DXUSD.Exporters.Export import AExport as DXUSD_AExport
from DXUSD.Exporters.Export import Export as DXUSD_Export

import DXUSD_HOU.Structures as srt
import DXUSD_HOU.Vars as var
import DXUSD_HOU.Tweakers as twk
import DXUSD_HOU.PostJobs as post


class AExport(DXUSD_AExport):
    def __init__(self, **kwargs):
        '''
        [Attributes from houdini]
        lyrtype (var.LYRTYPE): layer type (geom, inst, groom, feather, crwod...)
        prctype (var.PRCTYPE): post process type (none, clip, sim, fx)

        task (var.T.TASKS): task name
        taskCode (str)    : package task code (eg. 'TASKN') for rulebook

        srclyr (str)      : input usd layer
        cliprate (str)    : clip rate (eg. '0.8 1.0 1.2')
        dependency (dict) : depend usd path and variants
          {
            'asset/branch/shot': {
                (task): { __USDPATH__:'/show/pipe/...',
                          __ORDER__:['vset1', 'vset2', ...],
                          'vset1':'on',
                          'vset2':'off' }, ...
            }
          }

        [Attributes]
        sequenced (bool)  : if True, it's sequenced usd layer
        taskProduct (str) : task product name for rulebook

        dstlyr (str)     : master usd path
        customData (dict): custom layer data

        '''
        self.lyrtype = None
        self.prctype = var.PRCNONE
        self.simprc = False
        self.sequenced = False

        self.task = None
        self.taskCode = None
        self.taskProduct = 'GEOM'

        self.timeLayers = None
        self.loopRange = None
        self.dependency = None
        self.customData = dict()

        self.srclyr = None
        self.dstlyr = None
        self.flattenlyrs = list()

        self.LODs = list()

        DXUSD_AExport.__init__(self, **kwargs)

    def CheckSourceLayer(self, taskProduct, taskCode=None):
        if not taskCode:
            try:
                taskCode = self.taskCode
            except:
                msg.errmsg('Set taskCode argument.')
                return var.FAILED

        res = self.CheckArguments(taskCode)

        if res != var.SUCCESS:
            try:
                self.D.SetDecode(utl.DirName(self.srclyr),  taskCode)
                self.F.SetDecode(utl.BaseName(self.srclyr), taskProduct)
            except Exception as e:
                msg.errmsg(e)
                msg.errmsg('Cannot decode srclyr(%s)'%self.srclyr)
                return var.FAILED

        if not self.srclyr:
            try:
                self.srclyr = utl.SJoin(self.D[taskCode], self.F[taskProduct])
            except Exception as e:
                msg.errmsg(e)
                emsg = 'Cannot encode srclyr(%s, %s)'%(taskCode, taskProduct)
                msg.errmsg(emsg)
                msg.errmsg(self)
                return var.FAILED

        # set metadata
        self.srclyr = utl.AsLayer(self.srclyr)
        self.meta.Get(self.srclyr)

        self.LODs = self.FindLODs()

        return var.SUCCESS

    def FindLODs(self, maxDepth=5):
        lodnames = {
            var.T.HIGH:['Render', 'high'],
            var.T.MID:['mid'],
            var.T.LOW:['Proxy', 'low']
        }

        def WalkGragh(prim, res, maxDepth, curDepth=0):
            for child in prim.nameChildren.keys():
                for k, v in lodnames.items():
                    if child in v:
                        if k not in res:
                            res.append(k)
                        break
                else:
                    curDepth += 1
                    if curDepth < maxDepth:
                        child = prim.GetPrimAtPath(child)
                        WalkGragh(child, res, maxDepth, curDepth)

        if self.lyrtype == var.LYRFEATHER:
            res = [var.T.HIGH, var.T.LOW]
        else:
            res = []
            dprim = utl.GetDefaultPrim(self.srclyr)
            WalkGragh(dprim, res, maxDepth)

        return res


    def SetDestinationLayer(self, taskProduct, taskCode=None):
        if not taskCode:
            try:
                taskCode = self.taskCode
            except:
                msg.errmsg('Set taskCode argument.')
                return var.FAILED

        try:
            if self.get(var.T.TASK) == var.T.CLIP:
                taskCode = taskCode[:-1]

            self.dstlyr  = utl.SJoin(self.D[taskCode], self.F[taskProduct])
        except Exception as e:
            msg.errmsg(e)
            emsg = 'Cannot encode dstlyr(%s, %s)'%(taskCode, taskProduct)
            msg.errmsg(emsg)
            msg.errmsg(self)
            return var.FAILED
        return var.SUCCESS

    def SetSequenced(self):
        try:
            if self.IsShot() or self.prctype == var.PRCCLIP or self.simprc:
                self.sequenced = True
        except Exception as e:
            msg.errmsg(e)
            emsg = 'Cannot figure out sequenced or not'
            msg.errmsg(emsg)
            msg.errmsg(self)
            return var.FAILED
        return var.SUCCESS

    def FindRigFile(self):
        res        = srt.DependentFile()
        customData = utl.AsLayer(self.srclyr).customLayerData

        if customData.has_key(var.T.CUS_RIGFILE):
            res.SetFile(customData[var.T.CUS_RIGFILE])

        if not res:
            adata = {}
            if self.dependency.HasBranch():
                adata = self.dependency[var.T.BRANCH]
            elif self.dependency.HasAsset():
                adata = self.dependency[var.T.ASSET]
            elif self.dependency.HasShot():
                adata = self.dependency[var.T.SHOT]

            if adata.get(var.T.TASK) == var.T.RIG:
                res.SetFile(adata[var.USDPATH])
            elif adata.get(var.T.TASK) == var.T.MODEL:
                res.SetFile(adata[var.USDPATH])
            elif adata.get(var.SRCPATH):
                res.SetFile(adata[var.SRCPATH])

        if not res:
            msg.errmsg('Cannot find rig file')

        return res

    def FindGroomFile(self):
        from DXUSD.Structures import Arguments

        res        = srt.DependentFile()
        customData = utl.AsLayer(self.srclyr).customLayerData

        cusname = var.NULL
        if self.lyrtype == var.LYRGROOM:
            cusname = var.T.CUS_GROOMFILE

        elif self.lyrtype == var.LYRFEATHER:
            cusname = var.T.CUS_FEATHERFILE

        if customData.has_key(cusname):
            if self.lyrtype == var.LYRGROOM:
                arg = Arguments()
                gfile = customData[cusname]
                arg.D.SetDecode(gfile)
                arg.task = 'groom'
                arg.nslyr = utl.BaseName(utl.BaseName(gfile).split('.')[0])
                master = utl.SJoin(arg.D['TASKN'], arg.F.MASTER)
                res.SetFile(master)

            elif self.lyrtype == var.LYRFEATHER:
                res.SetFile(customData[cusname])

        if not res:
            for kind in [var.T.BRANCH, var.T.ASSET, var.T.SHOT]:
                if self.dependency[kind].get(var.LYRTASK) == var.T.GROOM:
                    if kind == var.T.SHOT:
                        res.SetFile(self.dependency[kind][var.SRCPATH])
                    else:
                        res.SetFile(self.dependency[kind][var.USDPATH])
                    break

        if not res:
            msg.errmsg('Cannot find %s file'%self.lyrtype)

        return res


    def FindInputCacheFile(self):
        res        = srt.DependentFile()
        customData = utl.AsLayer(self.srclyr).customLayerData

        if customData.has_key(var.T.CUS_INPUTCACHE):
            res.SetFile(customData[var.T.CUS_INPUTCACHE])

        if not res and self.dependency.HasShot():
            res.SetFile(self.dependency[var.T.SHOT][var.USDPATH])

        if not res:
            msg.errmsg('Cannot find input cache file')

        return res


class Export(DXUSD_Export):
    ARGCLASS = AExport
    POSTJOB  = None

    def Exporting(self):
        return var.SUCCESS

    def Completing(self):
        if isinstance(self.POSTJOB, post.PostJob):
            job = self.POSTJOB(self.arg)
            res = utl.CheckRes('', job.Treat, 'Treat', 1)
            if res == var.SUCCESS:
                res = utl.CheckRes('', job.DoIt, 'DoIt', 1)

            if res != var.SUCCESS:
                return res
        return DXUSD_Export.Completing(self)


    def AddClipPack(self, twks):
        if self.arg.task != var.T.CLIP:
            return

        def ChangeDirName(arg, path, clip):
            if isinstance(path, Sdf.Layer):
                path = path.realPath

            flags = var.D.Decode(utl.DirName(path))
            flags.clip = arg.clip
            filename = utl.BaseName(path)
            return utl.SJoin(var.D.Encode(**flags), filename)

        # ----------------------------------------------------------------------
        # create clip tweakers
        cliptwks = twk.Tweak()
        clips = ['base'] + self.arg.timeLayers
        for clip in clips:
            clip = clip.replace('.', '_')
            # duplicate tweakers for each loop
            if clip != 'base':
                for q in twks.queue:
                    t = q.copy()
                    t.arg.clip = clip

                    for i in range(len(t.arg.inputs)):
                        t.arg.inputs[i] = ChangeDirName(t.arg,
                                                        t.arg.inputs[i], clip)

                    for i in range(len(t.arg.outputs)):
                        t.arg.outputs[i]= ChangeDirName(t.arg,
                                                        t.arg.outputs[i], clip)

                    if t.arg.get('master'):
                        filename = utl.BaseName(t.arg.master)
                        t.arg.master = utl.SJoin(t.arg.D.TASKNVC, filename)

                    cliptwks << t

            # add ClipGeomPack
            cgArg = twk.AClipGeomPack()
            self.arg.clip = clip
            cgArg.output = utl.SJoin(self.arg.D.TASKNVC, self.arg.F.CLIP)
            cliptwks << twk.ClipGeomPack(cgArg)

        # turn clip back to base
        self.arg.clip = 'base'

        # ----------------------------------------------------------------------
        # add loopClip to the first
        arg = twk.ALoopClip(**self.arg)

        # set args
        arg.clip = 'base'
        arg.dstdir = arg.D.TASKNV
        arg.master = utl.SJoin(arg.dstdir, arg.F.MASTER)

        if not self.arg.flattenlyrs:
            msg.errmsg('@%s :'%self.__name__, 'Need flattenlyrs for clip')
            return var.FAILED

        arg.geomfiles = self.arg.flattenlyrs

        if utl.PathExists(arg.master):
            srclyr = utl.AsLayer(arg.master)
            start  = int(srclyr.startTimeCode)
            end    = int(srclyr.endTimeCode)
            arg.loopRange = (start, end)
        elif not arg.get('looprange'):
            arg.loopRange = [1001, 2000]

        # add tweakers
        twks.Add(twk.LoopClip(arg), 0)

        # ----------------------------------------------------------------------
        # add clip tweakers
        twks << cliptwks
        twks << twk.MasterClipPack(arg)

        return var.SUCCESS
