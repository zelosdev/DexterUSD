import os, sys, re, shutil

import DXUSD.Tweakers as twk

import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg

from pxr import Usd

def getGeomFiles(walkDir):
    result = list()
    for root, dirs, names in os.walk(walkDir):
        for name in names:
            if name.endswith('_geom.usd'):
                result.append(os.path.join(root, name))
    return result


def doIt(rootDir, timeScales, loopRange=None):
    arg = twk.ALoopClip()
    #arg.timeScales = [0.1, 2.0]
    arg.timeScales = timeScales
    arg.loopRange  = None
    arg.clipRange  = None
    arg.geomfiles  = getGeomFiles(rootDir)

    baseStage = Usd.Stage.Open('%s/base.usd' % rootDir)
    baseClipStart = baseStage.GetMetadata('startTimeCode')
    baseClipEnd = baseStage.GetMetadata('endTimeCode')
    arg.clipRange = (int(baseClipStart), int(baseClipEnd))

    if arg.clipRange == None:
        print 'base timecode error'
        return

    verDir = os.path.dirname(rootDir)

    loopRefDir = ''
    loopRefUsd = ''
    refTimeScales = [0.5, 0.8, 1.2, 1.5, 1.0]
    for rts in refTimeScales:
        rtsn = str(rts).replace('.', '_')
        loopRefDir = '%s/%s' % (verDir, rtsn)
        loopRefUsd = '%s/%s.usd' % (loopRefDir, rtsn)
        if os.path.isfile(loopRefUsd):
            print 'Loop range reference file:', loopRefUsd
            origStage = Usd.Stage.Open(loopRefUsd)
            origLoopStart = origStage.GetMetadata('startTimeCode')
            origLoopEnd = origStage.GetMetadata('endTimeCode')
            arg.loopRange = (int(origLoopStart), int(origLoopEnd))
            break
        loopRefUsd = '' 

    if loopRange != None:
        arg.loopRange = loopRange

    if arg.loopRange == None:
        arg.loopRange = (1001, 5000)
    print 'arg.loopRange', arg.loopRange
    if arg.Treat() == var.SUCCESS:
        print(arg)
        cliptwk = twk.LoopClip(arg)
        cliptwk.DoIt()

    if os.path.isfile(loopRefUsd):
        for ts in arg.timeScales:
            tn = str(ts).replace('.', '_')
            newTsDir = '%s/%s' % (verDir, tn)
            newTsUsd = '%s/%s.usd' % (newTsDir, tn)
            shutil.copy(loopRefUsd, newTsUsd)
            print 'open usd', newTsUsd
            newTsStage = Usd.Stage.Open(newTsUsd)
            newTsStage.SetMetadata('startTimeCode', arg.loopRange[0])
            newTsStage.SetMetadata('endTimeCode', arg.loopRange[1])
            newTsStage.Save()
                
            try: lsd = os.listdir(loopRefDir)
            except: continue
                         
            for fn in lsd:
                if fn.endswith('_rig.usd'):
                    newRigUsd = '%s/%s' % (newTsDir, fn)
                    shutil.copy('%s/%s' % (loopRefDir, fn), newRigUsd)
                    print 'open usd', newRigUsd
                    newRigStage = Usd.Stage.Open(newRigUsd)
                    newRigStage.SetMetadata('startTimeCode', arg.loopRange[0])
                    newRigStage.SetMetadata('endTimeCode', arg.loopRange[1])
                    newRigStage.Save()

if __name__ == '__main__':
    from UpdateLoopClipGeomDialog import UpdateLoopClipGeomDialog

    if len(sys.argv) != 2:
        UpdateLoopClipGeomDialog('Arg Error')
        exit(1)

    dialog = UpdateLoopClipGeomDialog(sys.argv[1])
    if not dialog.result or dialog.error:
        exit(1)

    # print dialog.clipBaseDir.text()

    timeScaleArgs = dialog.timeScales.text().split(',')
    timeScaleFloatArgs = []
    for tsa in timeScaleArgs:
        if not re.match(r'[0-9]{1,2}\.[0-9]{1,3}$', tsa) and not re.match(r'[0-9]{1,2}$', tsa):
            UpdateLoopClipGeomDialog('Timescale Error')
            exit(1)

        timeScaleFloatArgs.append(float(tsa))

    loopRange = None
    loopRangeText = dialog.loopRange.text()
    if re.match(r'[0-9]{1,4}\,[0-9]{1,4}$', loopRangeText):
        loopStart, loopEnd = loopRangeText.split(',')
        if loopStart < loopEnd:
            loopRange = (int(loopStart), int(loopEnd))

    doIt(dialog.clipBaseDir.text(), timeScaleFloatArgs, loopRange)
