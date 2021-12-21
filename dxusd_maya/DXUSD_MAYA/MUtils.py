#coding:utf-8

import maya.api.OpenMaya as OpenMaya
import maya.api.OpenMayaAnim as OpenMayaAnim
import maya.cmds as cmds
import os
import re
import string

import DXUSD_MAYA.Message as msg
from pxr import Gf

def GetNamespace(node):
    src = node.split('|')[-1].split(':')
    if len(src) > 1:
        ns = ':'.join(src[:-1])
    else:
        ns = None
    return ns, src[-1]

def JoinNsNameAndNode(ns, node):
    return node if not ns else '%s:%s' % (ns, node)

def GetReferenceFile(node):
    if cmds.referenceQuery(node, isNodeReferenced=True):
        filename = cmds.referenceQuery(node, filename=True, withoutCopyNumber=True)
        return filename
    else:
        return ''

def GetFrameRange():
    start = int(cmds.playbackOptions(q=True, min=True))
    end   = int(cmds.playbackOptions(q=True, max=True))
    return start, end

def GetFrameSample(step):
    samples = list()
    if step == 0:
        samples.append(0.0)
    else:
        for i in range(0, 100, int(step * 100)):
            samples.append(round(i * 0.01, 2))
    return samples

def GetIterFrames(fr, step=5):
    duration = fr[1] - fr[0] + 1
    if duration <= step:
        return [(fr[0], fr[1])]

    result = list()
    for frame in range(fr[0], fr[1], step):
        result.append((frame, frame + step - 1))
    if result[-1][-1] != fr[1]:
        result[-1] = (result[-1][0], fr[1])
    return result

_TIMEUNIT_MAP = {
    'game': 15, 'film': 24, 'pal': 25, 'ntsc': 30, 'show': 48, 'palf': 50, 'ntscf': 60,
    '2fps': 2, '3fps': 3, '4fps': 4, '5fps': 5, '6fps': 6, '8fps': 8, '10fps': 10, '12fps': 12, '16fps': 16,
    '20fps': 20, '23.976fps': 23.976, '29.97fps': 29.97, '29.97df': 29.97,
    '40fps': 40, '47.952fps': 47.952, '59.94fps': 59.94, '75fps': 75, '80fps': 80,
    '100fps': 100, '120fps': 120, '125fps': 125, '150fps': 150,
    '200fps': 200, '240fps': 240, '250fps': 250, '300fps': 300, '375fps': 375,
    '400fps': 400, '500fps': 500, '600fps': 600, '750fps': 750, '1200fps': 1200,
    '1500fps': 1500, '2000fps': 2000, '3000fps': 3000, '6000fps': 6000, '44100fps': 41000, '48000fps': 48000
}
_FPS_MAP = {}
for timeunit, fps in _TIMEUNIT_MAP.items():
    _FPS_MAP[fps] = timeunit

def GetFPS():
    timeUnit = cmds.currentUnit(q=True, t=True)
    return _TIMEUNIT_MAP[timeUnit]

def SetFPS(fps):
    cmds.currentUnit(t=_FPS_MAP[fps])

def GetMObject(name, dag=True):
    sels = OpenMaya.MGlobal.getSelectionListByName(name)
    if dag:
        return sels.getDagPath(0)
    else:
        return sels.getDependNode(0)

def GetViz(node):
    viz = True
    source = node.split('|')
    for i in range(1, len(source)):
        path = string.join(source[:i + 1], '|')
        if cmds.listConnections('%s.visibility' % path):
            vals = cmds.keyframe(path, at='visibility', q=True, vc=True)
            if not 1.0 in vals:
                return False
        else:
            viz = cmds.getAttr('%s.visibility' % path)
            if not viz:
                return viz
        connects = cmds.listConnections('%s.drawOverride' % path, type='displayLayer')
        if connects:
            for c in connects:
                viz = cmds.getAttr('%s.visibility' % c)
                if not viz:
                    return viz
    return viz

def GetmeshViz(node):
    viz = True
    if cmds.listConnections('%s.visibility' % node):
        vals = cmds.keyframe(node, at='visibility', q=True, vc=True)
        if not 1.0 in vals:
            return False
    else:
        viz = cmds.getAttr('%s.visibility' % node)
        if not viz:
            return viz
    connects = cmds.listConnections('%s.drawOverride' % node, type='displayLayer')
    if connects:
        for c in connects:
            viz = cmds.getAttr('%s.visibility' % c)
            if not viz:
                return viz
    return viz

class GetGfXform:
    def __init__(self, matrix=None, transform=None):
        if matrix:
            self.asMatrix(matrix)
        elif transform:
            self.asTransform(transform)

    def asTransform(self, transform):
        self.translate = transform[0]
        self.scale = transform[1]
        self.rotate = OpenMaya.MEulerRotation(transform[2], transform[3]).asQuaternion()

    def asMatrix(self, matrix):
        tmx = OpenMaya.MTransformationMatrix(OpenMaya.MMatrix(matrix))

        self.translate = tmx.translation(OpenMaya.MSpace.kWorld)
        self.scale = tmx.scale(OpenMaya.MSpace.kWorld)
        self.rotate = tmx.rotation(asQuaternion=True)

    def Get(self, scheme='PointInstancer'):
        if scheme == 'PointInstancer':
            pos = Gf.Vec3f(*self.translate)
            scl = Gf.Vec3f(*self.scale)
            ort = Gf.Quath(self.rotate.w, self.rotate.x, self.rotate.y, self.rotate.z)
            return pos, scl, ort
        if scheme == 'Points':
            pos = Gf.Vec3f(*self.translate)
            scl = Gf.Vec3f(*self.scale)
            ort = Gf.Vec4f(self.rotate.x, self.rotate.y, self.rotate.z, self.rotate.w)
            return pos, scl, ort


def GetXformMatrix(node, start, end, step=1.0):
    '''
    Returns:
        matrix (list)       : [[4x4 matrix], [...], [...]]
        frameSampling (list): [1.0, 1.25, 1.5, ...]
    :param node:
    :param start:
    :param end:
    :param step:
    :return:
    '''

    mtxList = list()
    frmList = list()
    currentFrame = cmds.currentTime(q=True)

    for frame in range(start, end + 1):
        for sample in GetFrameSample(step):
            frameSample = frame + sample
            cmds.currentTime(frameSample)
            mtxValue = cmds.xform(node, q=True, ws=True, m=True, eu=True)

            mtxList.append(list(mtxValue))
            frmList.append(frameSample)

    cmds.currentTime(currentFrame)
    return mtxList, frmList

def GetGfTransform(node, start, end, step=1.0):
    tmpCam = cmds.spaceLocator()
    cmds.setAttr(tmpCam[0] + '.rotateOrder', 2)
    cmds.parentConstraint(node, tmpCam)
    cmds.bakeResults(tmpCam, t=(cmds.playbackOptions(q=True, ast=True),
                     cmds.playbackOptions(q=True, aet=True)), pok=True,
                     at=["tx", "ty", "tz", "rx", "ry", "rz"])

    if cmds.listAttr(tmpCam[0], k=True):
        for ln in cmds.listAttr(tmpCam[0], k=True):
            typeln = cmds.getAttr('%s.%s' % (tmpCam[0], ln), type=True)
            if re.findall(r'\d+', typeln):
                continue

            plug = '%s.%s' % (tmpCam[0], ln)
            frames = cmds.keyframe(plug, q=True, a=True)
            if not frames:
                continue
            tangents = cmds.keyTangent(plug, q=True, ia=True, oa=True)
            tangents = list(set(tangents))
            if len(tangents) == 1:
                continue

            # Start Frame
            refValue = cmds.getAttr(plug, t=frames[2]-1)
            startValue = cmds.getAttr(plug, t=frames[1]-1)
            setValue = cmds.getAttr(plug, t=frames[0]-1)
            if startValue == setValue:
                msg.debug('start offset value', plug, setValue, startValue)
                offsetValue = refValue - startValue
                setValue = startValue - offsetValue
                cmds.setKeyframe(plug, itt='spline', ott='spline', t=frames[0]-1, v=setValue)

            # End Frame
            refValue = cmds.getAttr(plug, t=frames[-3]+1)
            endValue = cmds.getAttr(plug, t=frames[-2]+1)
            setValue = cmds.getAttr(plug, t=frames[-1]+1)
            if endValue == setValue:
                msg.debug('end offset value', plug, endValue, setValue)
                offsetValue = endValue - refValue
                setValue = endValue + offsetValue
                cmds.setKeyframe(plug, itt='spline', ott='spline', t=frames[-1]+1, v=setValue)

            cmds.filterCurve(plug)

    tranList = list()
    rotList = list()
    frmList = list()
    currentFrame = cmds.currentTime(q=True)

    for frame in range(start, end + 1):
        for sample in GetFrameSample(step):
            frameSample = frame + sample
            cmds.currentTime(frameSample)

            tran = Gf.Vec3f(cmds.getAttr(tmpCam[0] + '.tx'),
                             cmds.getAttr(tmpCam[0] + '.ty'),
                             cmds.getAttr(tmpCam[0] + '.tz'))
            rot = Gf.Vec3f(cmds.getAttr(tmpCam[0] + '.rx'),
                            cmds.getAttr(tmpCam[0] + '.ry'),
                            cmds.getAttr(tmpCam[0] + '.rz'))

            tranList.append(tran)
            rotList.append(rot)
            frmList.append(frameSample)

    cmds.currentTime(currentFrame)
    cmds.delete(tmpCam)
    return tranList, rotList, frmList

def GetMatrixByGf(position, orient, scale):
    tmtx = OpenMaya.MTransformationMatrix()
    tmtx.setScale([scale[0], scale[1], scale[2]], OpenMaya.MSpace.kWorld)

    img = orient.imaginary
    quat= OpenMaya.MQuaternion([img[0], img[1], img[2], orient.real])
    tmtx.setRotation(quat.asEulerRotation())

    tmtx.setTranslation(OpenMaya.MVector(*position), OpenMaya.MSpace.kWorld)
    return tmtx.asMatrix()

def getGfXform(node):
    mtx = cmds.xform(node, q=True, m=True, ws=True, eu=True)
    mtx = OpenMaya.MTransformationMatrix(OpenMaya.MMatrix(mtx))
    scale  = mtx.scale(OpenMaya.MSpace.kWorld)
    orient = mtx.rotation(asQuaternion=True)
    trans  = mtx.translation(OpenMaya.MSpace.kWorld)

    S = Gf.Vec3f(*scale)
    O = Gf.Quath(orient.w, orient.x, orient.y, orient.z)
    T = Gf.Vec3f(*trans)
    return S, O, T

#-------------------------------------------------------------------------------
#
#   FOR RIG ANIMATION
#
#-------------------------------------------------------------------------------
def GetRigConData(node):
    worldConDict = {
        'dexter': {
            'nodes': ['place_CON', 'place_NUL', 'direction_NUL', 'direction_CON', 'move_NUL', 'move_CON'],
            'attrs': ['tx', 'ty', 'tz', 'rx', 'ry', 'rz']
        }
    }

    attrList = worldConDict['dexter']['attrs']
    conList  = worldConDict['dexter']['nodes']
    nsName, nodeName = GetNamespace(node)

    rigConList = list()
    for con in conList:
        name = JoinNsNameAndNode(nsName, con)
        if cmds.objExists(name):
            rigConList.append(name)
    if len(conList) != len(rigConList):
        rigConList = None
    return rigConList, attrList


InitScaleAttributes = ['initScale']
class MuteCtrl:
    '''
    Attribute mute control
    '''
    def __init__(self, nodes, attrs):
        self.nodes = nodes
        self.attrs = attrs
        self.data = dict()
        self.initScaleAttr = None

    def getValue(self):
        for node in self.nodes:
            self.data[node] = dict()
            for ln in self.attrs:
                if not cmds.getAttr('%s.%s' % (node, ln), l=True):
                    self.data[node][ln] = cmds.getAttr('%s.%s' % (node, ln))
            # initScale
            for at in InitScaleAttributes:
                if cmds.attributeQuery(at, n=node, ex=True):
                    self.initScaleAttr = at
                    self.data[node][at] = cmds.getAttr('%s.%s' % (node, at))

    # Controller is Set Mute
    def setMute(self):
        if not self.data:
            return
        # scale attribute
        scaleAttrs = ['sx', 'sy', 'sz']
        if self.initScaleAttr:
            scaleAttrs.append(self.initScaleAttr)
        for node in self.data:
            for ln in self.data[node]:
                if ln in scaleAttrs:
                    try:
                        cmds.setAttr('%s.%s' % (node, ln), 1)
                    except Exception as e:
                        msg.warning(e.message)
                else:
                    try:
                        cmds.setAttr('%s.%s' % (node, ln), 0)
                    except Exception as e:
                        msg.warning(e.message)
                cmds.mute('%s.%s' % (node, ln), d=False, f=True)

    def setUnMute(self):
        if not self.data:
            return
        for node in self.data:
            for ln in self.data[node]:
                try:
                    cmds.setAttr('%s.%s' % (node, ln), self.data[node][ln])
                except Exception as e:
                    msg.warning(e.message)
                cmds.mute('%s.%s' % (node, ln), d=True, f=True)

def GetZennAssetInfo(showDir):
    infoRule = '{DIR}/_config/AssetInfo.json'
    infoFile = infoRule.format(DIR=showDir)
    if not os.path.exists(infoFile):
        pathRuleFile = '{DIR}/_config/pathRule.json'.format(DIR=showDir)
        if os.path.exists(pathRuleFile):
            with open(pathRuleFile, 'r') as f:
                ruleData = eval(f.read())
                if ruleData.has_key('refShow') and ruleData['refShow']:
                    for sdir in ruleData['refShow']:
                        infoFile = infoRule.format(DIR=sdir)
                        if os.path.exists(infoFile):
                            break
    if not os.path.exists(infoFile):
        msg.error('Not found "%s" file' % infoFile)
        return None

    with open(infoFile, 'r') as f:
        data = eval(f.read())
        if data.has_key('zenn'):
            return data['zenn']
        else:
            msg.error("Not found 'zenn' in '%s' file." % infoFile)

def AbcExport(filename, nodes, fr=[None, None], step=0.0):
    currentFrame = cmds.currentTime(q=True)
    if fr[0] == None and fr[1] == None:
        fr = (currentFrame, currentFrame)
    if step == 0.0:
        step = 1.0

    opts  = '-uv -wv -wuvs -ef -df ogawa -ws'
    opts += ' -a MaterialSet'
    opts += ' -atp rman'
    opts += ' -fr %s %s' % (fr[0], fr[1])
    opts += ' -step %s' % step
    for n in nodes:
        opts += ' -rt %s' % n
    opts += ' -file %s' % filename
    cmds.AbcExport(j=opts, v=True)
    msg.debug('> Export alembic\t:', filename)
    return filename

def InitPlugins(plugins):
    unplugins = [
        'bifrostvisplugin', 'bifrostshellnode', 'ZArachneForMaya',
        'xgenToolkit', 'xgSplineDataToXpd',
        # 'pxrUsd', 'pxrUsdTranslators'     # if maya auto load this plugin, error occurred. so remove this
    ]
    for p in unplugins:
        if cmds.pluginInfo(p, q=True, l=True):
            cmds.unloadPlugin(p)
            msg.debug('info', 'unload plugin -> %s' % p)
    for p in plugins:
        if not cmds.pluginInfo(p, q=True, l=True):
            cmds.loadPlugin(p)
        msg.debug('info', 'plugin -> %s %s' % (p, cmds.pluginInfo(p, q=True, l=True)))
