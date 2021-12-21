#coding:utf-8
from __future__ import print_function

import soho
import os

import DXUSD_HOU.Message as msg

import DXUSD_HOU.Vars as var
import DXUSD_HOU.Utils as utl
import DXUSD_HOU.Structures as srt
import DXUSD_HOU.HouExport as exp


parameterDefines = {
    'now'       : soho.SohoParm('state:time', 'real', [0], False, key='now'),
    'fps'       : soho.SohoParm('state:fps', 'real', [0], False, key='fps'),
    'trange'    : soho.SohoParm('trange', 'int', [0], False),
    'f'         : soho.SohoParm('f', 'real', [1, 1, 1], False),
    'respath'   : soho.SohoParm('resultpath', 'string', [''], False),
    'numtasks'  : soho.SohoParm('tasks', 'int', [0], False)
}

params = soho.evaluate(parameterDefines)

now    = params['now'].Value[0]
fps    = params['fps'].Value[0]
startframe = endframe = int(now * params['fps'].Value[0] + 1)

if params['trange'].Value[0] > 0:
    startframe = int(params['f'].Value[0])
    endframe   = int(params['f'].Value[1])


meta   = utl.StageMetadata()
meta.sf = startframe
meta.ef = endframe
meta.fps = fps

arg   = srt.Arguments()
arg.D.SetDecode(params['resultpath'].Value[0])
tasks = srt.Tasks(arg)

# ------------------------------------------------------------------------------
# resolve tasks
for i in range(1, params['tasks'].Value[0]+1):
    tparmDefines = {
        'taskenable' : soho.SohoParm('taskenable%d'%i, 'int', [0], False),
        'taskname'   : soho.SohoParm('taskname%d'%i, 'string', [''], False),
        'taskcode'   : soho.SohoParm('taskcode%d'%i, 'string', [''], False),
        'taskver'    : soho.SohoParm('taskver%d'%i, 'string', [''], False),
        'numnslyrs'  : soho.SohoParm('nslyrs%d'%i, 'int', [0], False)
    }
    tparms = soho.evaluate(tparmDefines)
    if not tparms['taskenable%d'%i].Value[0]:
        continue

    task = tasks.Add(tparms['taskname%d'%i].Value[0],
                     tparms['taskcode%d'%i].Value[0])
    vers = tparms['taskver%d'%i].Value[0]
    if vers:
        task.arg.ver = task.vers = vers

    # --------------------------------------------------------------------------
    # resolve nslyrs
    for j in range(1, tparms['nslyrs%d'%i].Value[0]+1):
        _j = (i, j)
        nparmDefines = {
            'nslyrenable' : soho.SohoParm('nslyrenable%d_%d'%_j, 'int',    [0],  False),
            'nslyrname'   : soho.SohoParm('nslyrname%d_%d'%_j,   'string', [''], False),
            'nslyrver'    : soho.SohoParm('nslyrver%d_%d'%_j,    'string', [''], False),
            'nullnslyr'   : soho.SohoParm('nullnslyr%d_%d'%_j,   'int',    [0],  False),
            'numsublyr'   : soho.SohoParm('sublyrs%d_%d'%_j,     'int',    [0],  False)
        }
        nparms = soho.evaluate(nparmDefines)
        if not nparms['nslyrenable%d_%d'%_j].Value[0]:
            continue

        if nparms['nullnslyr%d_%d'%_j].Value[0]:
            nslyr = task.Add(var.NULL)
        else:
            nslyr = task.Add(nparms['nslyrname%d_%d'%_j].Value[0])
            nslyr.arg = srt.Arguments(**nslyr.arg)
            nslyr.arg.nslyr = nslyr.name

            vers = nparms['nslyrver%d_%d'%_j].Value[0]
            if vers:
                nslyr.arg.nsver = nslyr.vers = vers

        # ----------------------------------------------------------------------
        # sublay
        for k in range(1, nparms['sublyrs%d_%d'%_j].Value[0]+1):
            _k = (i, j, k)
            sparmDefines = {
                'sublyrenable' : soho.SohoParm('sublyrenable%d_%d_%d'%_k, 'int',    [0],  False),
                'sublyrname'   : soho.SohoParm('sublyrname%d_%d_%d'%_k,   'string', [''], False),
                'sublyrver'    : soho.SohoParm('sublyrver%d_%d_%d'%_k,    'string', [''], False),
                'nullsublyr'   : soho.SohoParm('nullsublyr%d_%d_%d'%_k,   'int',    [0],  False),
                'numlayers'    : soho.SohoParm('layers%d_%d_%d'%_k,       'int',    [0],  False)
            }
            sparms = soho.evaluate(sparmDefines)
            if not sparms['sublyrenable%d_%d_%d'%_k].Value[0]:
                continue

            if sparms['nullsublyr%d_%d_%d'%_k].Value[0]:
                sublyr = nslyr.Add(var.NULL)
            else:
                sublyr = nslyr.Add(sparms['sublyrname%d_%d_%d'%_k].Value[0])
                sublyr.arg = srt.Arguments(**sublyr.arg)
                sublyr.arg.subdir = sublyr.name

                vers = sparms['sublyrver%d_%d_%d'%_k].Value[0]
                if vers:
                    sublyr.arg.subver = sublyr.subver = vers

            # ------------------------------------------------------------------
            # resolve layers
            for l in range(1, sparms['layers%d_%d_%d'%_k].Value[0]+1):
                _l = (i, j, k, l)
                lparmDefines = {
                    'layerenable'     : soho.SohoParm('layerenable%d_%d_%d_%d'%_l,     'int',    [0],    False),
                    'layeroutputfile' : soho.SohoParm('layeroutputfile%d_%d_%d_%d'%_l, 'string', [''],   False),
                    'inputroptype'    : soho.SohoParm('inputroptype%d_%d_%d_%d'%_l,    'string', [''],   False),
                    'layerdata'       : soho.SohoParm('layerdata%d_%d_%d_%d'%_l,       'string', ['{}'], False)
                }
                lparms = soho.evaluate(lparmDefines)
                if not lparms['layerenable%d_%d_%d_%d'%_l].Value[0]:
                    continue

                outputfile = lparms['layeroutputfile%d_%d_%d_%d'%_l].Value[0]
                lyrdata = eval(lparms['layerdata%d_%d_%d_%d'%_l].Value[0])

                output = utl.SJoin(lyrdata['outpath'], outputfile)
                if os.path.exists(output):
                    lyr = sublyr.Add(utl.BaseName(output))
                    lyr.arg.D.SetDecode(utl.DirName(output), task.code)

                    lyr.lyrtype = lyrdata['lyrtype']
                    lyr.prctype = lyrdata['prctype']
                    lyr.simprc  = lyrdata['simprc']
                    lyr.sequenced = eval(lyrdata['sequenced'])
                    lyr.outpath = output

                    if lyrdata.has_key('cliprate'):
                        lyr.cliprate = lyrdata['cliprate'].split(' ')
                        lyr.looprange = []
                        for r in lyrdata['looprange'].split(' '):
                            lyr.looprange.append(int(r))

                    if lyrdata.has_key('dependpath'):
                        lyr.dependpath = lyrdata['dependpath']

                    if lyrdata.has_key('extra'):
                        lyr.extra = eval(lyrdata['extra'])
                        lyr.arg.update(lyr.extra)

                    lyr.dependency = utl.DependInfoToDict(lyrdata)
                else:
                    msg.warning('Cannot find source layer (%s)'%output)

# ------------------------------------------------------------------------------
# Run Export !!!
exp.HouExport(tasks, meta)
