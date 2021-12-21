#coding:utf-8
from __future__ import print_function
import os
import math
import random

from pxr import Sdf, Usd, UsdGeom, UsdSkel, Gf, Vt, Tf, Kind

import maya.api.OpenMaya as OpenMaya
import maya.api.OpenMayaAnim as OpenMayaAnim
import maya.cmds as cmds
import maya.mel as mel

from DXUSD.Structures import Arguments
import DXUSD.Vars as var

import DXUSD_MAYA.Message as msg
import DXUSD_MAYA.Exporters as exp
import DXUSD_MAYA.MUtils as mutl
import DXUSD_MAYA.Utils as utl

import DXRulebook.Interface as rb

# crowd plugin module
try:
    if not cmds.pluginInfo('glmCrowd', q=True, l=True):
        cmds.loadPlugin('glmCrowd')
    import glmCore
    print('#----------------------------')
    print('#')
    print('# load golaem api')
    print('#')
    print('#----------------------------')
except:
    pass

try:
    import McdGeneral
    import McdSimpleCmd
    import McdPlacementFunctions
    import McdRenderFBXFunctions
    import McdMeshDriveSetup
    print('#----------------------------')
    print('#')
    print('# load miarmy api')
    print('#')
    print('#----------------------------')
except:
    pass


#-------------------------------------------------------------------------------
#
#   EXPORT ASSET MAIN
#
#-------------------------------------------------------------------------------
def assetExport(node=None, show=None, shot=None, version=None, overwrite=False):
    # crowd plugin check
    #   Golaem - glmCrowd.so
    if cmds.pluginInfo('glmCrowd', q=True, l=True):
        assetExport_golaem(node, show, shot, version, overwrite)
    #   Miarmy - MiarmyProForMaya$MAYA_VER.so
    elif cmds.pluginInfo('MiarmyProForMaya%s' % cmds.about(v=True), q=True, l=True):
        assetExport_miarmy(node, show, shot, version, overwrite)
    else:
        assert False, '# ERROR : need crowd plugin.'


#-------------------------------------------------------------------------------
class GetJoints:
    def __init__(self, node):
        self.node = cmds.ls(node, l=True)[0]
        self.allJoints = cmds.ls(self.node, dag=True, type='joint', l=True)
        self.allJointsPath = list()
        self.allJointsName = list()

        allJointsPath = list()
        for j in self.allJoints:
            allJointsPath.append(self.getJointPath(j))

        splitStr = allJointsPath[0].split('_')
        prefix   = splitStr[0] + '_'
        suffix   = '_' + '_'.join(splitStr[2:])

        for j in allJointsPath:
            n = j.replace(prefix, '').replace(suffix, '')
            self.allJointsPath.append(n)
            self.allJointsName.append(n.split('/')[-1])

    def getJointPath(self, joint):
        jpath = joint.replace(self.node, '').replace('|', '/')[1:]
        return jpath

    def getOrientList(self):
        orients = list()
        for j in self.allJoints:
            jorient = cmds.getAttr('%s.jointOrient' % j)[0]
            quat = OpenMaya.MEulerRotation(math.radians(jorient[0]), math.radians(jorient[1]), math.radians(jorient[2]), 0).asQuaternion()
            orients.append(quat)
        return orients

    def getTransforms(self):
        bind = list(); rest = list()
        for j in self.allJoints:
            wsMtx = cmds.xform(j, q=True, ws=True, m=True)  # BindTransform
            bind.append(Gf.Matrix4d(*wsMtx))

            osMtx = cmds.xform(j, q=True, os=True, m=True)  # RestTransform
            rest.append(Gf.Matrix4d(*osMtx))
        return bind, rest


def GetClusterMap():
    result = dict()
    for c in cmds.ls(type='skinCluster'):
        geoms = cmds.skinCluster(c, q=True, g=True)
        if geoms:
            for g in geoms:
                result[cmds.ls(g, l=True)[0]] = c
    return result



#-------------------------------------------------------------------------------
#
#   Miarmy Asset
#
#-------------------------------------------------------------------------------
class MiarmyAssetExport(exp.MiarmyAssetExporter):
    def Exporting(self):
        # Member variable
        self.customData = {'sceneFile': self.arg.scene}

        self.geomnode = self.arg.node.replace('OriginalAgent_', 'Geometry_')

        # Custom User Attributes
        UsdAttr = utl.UsdUserAttributes(self.geomnode)
        UsdAttr.Set()

        opts = {'defaultMeshScheme': 'catmullClark'}
        utl.UsdExport(self.arg.geomfile, self.geomnode, **opts).doIt()

        UsdAttr.Clear()

        #-----------------------------------------------------------------------
        self.JOINT = GetJoints(self.arg.node)

        # create rig
        self.CreateRig()

        # Skel Setup
        self.SkelSetup()

        return var.SUCCESS


    def CreateRig(self):
        msg.debug('%s.CreateRig :' % self.__name__, self.arg.rigfile)
        outlyr = utl.AsLayer(self.arg.rigfile, create=True, clear=True)
        outlyr.defaultPrim = 'Rig'

        spec = utl.GetPrimSpec(outlyr, '/Rig', type='Scope')
        spec = utl.GetPrimSpec(outlyr, '/Rig/Skel', type='Skeleton')
        utl.SetPurpose(spec, 'guide')

        bind, rest = self.JOINT.getTransforms()
        utl.GetAttributeSpec(spec, 'bindTransforms', Vt.Matrix4dArray(bind), Sdf.ValueTypeNames.Matrix4dArray, Sdf.VariabilityUniform)
        utl.GetAttributeSpec(spec, 'restTransforms', Vt.Matrix4dArray(rest), Sdf.ValueTypeNames.Matrix4dArray, Sdf.VariabilityUniform)
        utl.GetAttributeSpec(spec, 'joints', self.JOINT.allJointsPath, Sdf.ValueTypeNames.TokenArray, Sdf.VariabilityUniform)
        utl.GetAttributeSpec(spec, 'jointNames', self.JOINT.allJointsName, Sdf.ValueTypeNames.TokenArray, Sdf.VariabilityUniform)

        with utl.OpenStage(outlyr) as stage:
            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
            prim = stage.GetPrimAtPath('/Rig/Skel')
            boundable = UsdGeom.Boundable(prim)
            extent    = UsdGeom.Boundable.ComputeExtentFromPlugins(boundable, Usd.TimeCode())
        utl.GetAttributeSpec(spec, 'extent', extent, Sdf.ValueTypeNames.Float3Array, Sdf.VariabilityVarying)

        # update customLayerData
        utl.UpdateLayerData(outlyr, self.customData).doIt()


        outlyr.Save()
        del outlyr


    def SkelSetup(self):
        msg.debug('%s.SkelSetup :' % self.__name__, self.arg.master)
        outlyr = utl.AsLayer(self.arg.master, create=True, clear=True)
        outlyr.defaultPrim = self.arg.nslyr

        root = utl.GetPrimSpec(outlyr, '/' + self.arg.nslyr)    # agent type

        skelRootPath = root.path.AppendChild('SkelRoot')
        skelRootSpec = utl.GetPrimSpec(outlyr, skelRootPath, type='SkelRoot')
        utl.CreateSkelBindingAPI(skelRootSpec)

        geomSpec = utl.GetPrimSpec(outlyr, skelRootPath.AppendChild('Geom'))
        utl.ReferenceAppend(geomSpec, './' + utl.BaseName(self.arg.geomfile))

        rigSpec  = utl.GetPrimSpec(outlyr, skelRootPath.AppendChild('Rig'), type='Scope')
        utl.ReferenceAppend(rigSpec, './' + utl.BaseName(self.arg.rigfile))

        # Add Skel Attributes
        self.SkelAttributes(outlyr, geomSpec)

        utl.CreateRelationshipSpec(skelRootSpec, 'skel:skeleton', Sdf.Path('Rig/Skel'), Sdf.VariabilityUniform)

        # Geometry Randomization
        self.GeomRandomizeSetup(root)

        with utl.OpenStage(outlyr) as stage:
            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)

        # update customLayerData
        utl.UpdateLayerData(outlyr, self.customData).doIt()

        outlyr.Save()
        del outlyr


    def SkelAttributes(self, outlyr, parent):   # parent spec
        clusterMap = GetClusterMap()

        for shape in cmds.ls(self.geomnode, dag=True, type='surfaceShape', ni=True, l=True):
            if not clusterMap.has_key(shape):
                continue

            cluster = clusterMap[shape]
            skinClusterFn    = OpenMayaAnim.MFnSkinCluster(mutl.GetMObject(cluster, False))
            influenceDagList = skinClusterFn.influenceObjects()
            influenceIndices = list()
            for j in influenceDagList:
                jpath = j.fullPathName()
                index = self.JOINT.allJoints.index(jpath)
                influenceIndices.append(index)

            shapeObj = mutl.GetMObject(shape)
            meshFn   = OpenMaya.MFnMesh(shapeObj)
            numVertices = meshFn.numVertices
            singleIdComp= OpenMaya.MFnSingleIndexedComponent()
            vertexComp  = singleIdComp.create(OpenMaya.MFn.kMeshVertComponent)

            weightData  = skinClusterFn.getWeights(shapeObj, vertexComp)
            weights     = weightData[0]
            numInfluences = int(weightData[1])
            maxInfluences = numInfluences

            JointIndices = [0]   * maxInfluences * numVertices
            JointWeights = [0.0] * maxInfluences * numVertices

            for vtx in range(numVertices):
                inputOffset = vtx * numInfluences
                outputOffset= vtx * maxInfluences
                for i in range(numInfluences):
                    weight = weights[inputOffset + i]
                    if not Gf.IsClose(weight, 0.0, 1e-8):
                        JointIndices[outputOffset] = influenceIndices[i]
                        JointWeights[outputOffset] = weight
                        outputOffset += 1

            trans = cmds.listRelatives(shape, p=True, f=True)[0]
            rpath = trans.replace('|%s|' % self.geomnode, '').replace('|', '/')
            # print('>', rpath)
            spec = utl.GetPrimSpec(outlyr, parent.path.AppendPath(rpath), specifier='over')
            utl.CreateSkelBindingAPI(spec)
            utl.GetAttributeSpec(spec, 'primvars:skel:geomBindTransform', Gf.Matrix4d(), Sdf.ValueTypeNames.Matrix4d)
            utl.GetAttributeSpec(spec, 'primvars:skel:jointIndices', Vt.IntArray(JointIndices), Sdf.ValueTypeNames.IntArray,
                info={'elementSize': numInfluences, 'interpolation': 'vertex'})
            utl.GetAttributeSpec(spec, 'primvars:skel:jointWeights', Vt.FloatArray(JointWeights), Sdf.ValueTypeNames.FloatArray,
                info={'elementSize': numInfluences, 'interpolation': 'vertex'})


    def GeomRandomizeSetup(self, parent):   # parent - defaultPrim spec
        # random root group
        randomroots = list()
        for child in cmds.listRelatives(self.geomnode, c=True):
            if not cmds.listRelatives(child, c=True, s=True):
                randomroots.append(child)

        if len(randomroots) > 1:
            for root in randomroots:
                name = 'random_' + root
                vsetSpec = utl.GetVariantSetSpec(parent, name)
                # choose child
                for c in cmds.listRelatives(root, c=True):
                    rpath = 'SkelRoot/Geom/' + root + '/' + c
                    vspec = Sdf.VariantSpec(vsetSpec, c)
                    spec  = utl.GetPrimSpec(parent.layer, vspec.primSpec.path.AppendPath(rpath), specifier='over')
                    spec.SetInfo('active', True)
                    parent.variantSelections.update({name: c})

    # DEBUG
    # def Tweaking(self):
    #     return var.SUCCESS
    #
    # def Compositing(self):
    #     return var.SUCCESS


def assetExport_miarmy(node=None, show=None, shot=None, version=None, overwrite=False):
    if not node:
        nodes = cmds.ls('OriginalAgent_*')
        if not nodes:
            return
        node = nodes[0]
    if not node:
        return

    # current scene filename
    sceneFile = cmds.file(q=True, sn=True)

    arg = exp.AMiarmyAssetExporter()
    arg.node  = node
    arg.scene = sceneFile
    arg.overwrite = overwrite

    # override
    if show:    arg.ovr_show = show
    if shot:    arg.ovr_shot = shot
    if version: arg.ovr_ver  = version

    # if arg.Treat():
    #     print(arg)

    MiarmyAssetExport(arg)


#-------------------------------------------------------------------------------
#
#   Miarmy Shot
#
#-------------------------------------------------------------------------------
class MiarmyShotExport(exp.MiarmyShotExporter):
    '''
    Only export skel animation per frame.
    '''
    def InitializeMiarmy(self):
        if not cmds.about(b=True):
            return

        mel.eval('McdInitMiarmy;')
        McdPlacementFunctions.placementAgent()

        globalNode  = McdGeneral.McdGetMcdGlobalNode()
        # enableCache = cmds.getAttr('%s.enableCache' % globalNode)
        # if not enableCache:
        #     assert False, 'Miarmy enableCache is off'

        brainNode = mel.eval('McdSimpleCommand -execute 3;')
        solverFrame = int(cmds.getAttr('%s.startTime' % brainNode))
        solverFrame-= 1
        for f in range(solverFrame, self.arg.exportRange[0]):
            cmds.currentTime(f)

        return True

    # get scene data
    @staticmethod
    def GetSceneData(scene=None):
        if not scene:
            scene = cmds.file(q=True, sn=True)

        data = dict()
        data['agents']  = cmds.ls(type='McdAgent')
        data['types']   = []
        data['files']   = []
        data['joints']  = []
        data['orients'] = []
        data['places']  = []
        for g in cmds.listRelatives('Miarmy_Contents', c=True, type='McdAgentGroup'):
            allChildren = cmds.listRelatives(g, c=True, p=False, path=True)
            for c in allChildren:
                if c.startswith('OriginalAgent_'):
                    data['types'].append(c)
                    jt = GetJoints(c)
                    data['joints'].append(jt.allJointsPath)
                    data['orients'].append(jt.getOrientList())
                    # agent file
                    arg = Arguments()
                    arg.D.SetDecode(scene, 'SHOW')
                    arg.N.agent.SetDecode(c, 'ASSET')
                    arg.N.agent.SetDecode(arg.nslyr, 'SETASSET')
                    data['files'].append(utl.SJoin(arg.D.TASKN, arg.F.NSLYR))
        for s in cmds.ls(type='McdPlace'):
            data['places'].append(cmds.listRelatives(s, p=True)[0])

        return data

    def MakeSkelAnimation(self, frame):
        output = utl.SJoin(self.arg.dstdir, 'crowd.skel.%04d.usd' % frame)
        outlyr = utl.AsLayer(output, create=True, clear=True)
        utl.UpdateLayerData(outlyr, self.customData).doIt()

        root = utl.GetPrimSpec(outlyr, '/Crowd')
        root.SetInfo('kind', 'assembly')
        outlyr.defaultPrim = 'Crowd'

        # agent types
        agentTypes = list()
        for ag in self.SD['types']:
            agentTypes.append(ag.replace('OriginalAgent_', ''))
        utl.GetAttributeSpec(root, 'userProperties:Crowd:agentTypes', agentTypes, Sdf.ValueTypeNames.StringArray,
                             variability=Sdf.VariabilityUniform, custom=True)

        # reference agents
        source = list()
        refer  = utl.GetPrimSpec(outlyr, '/_source_agents', specifier='class')
        for i in range(len(self.SD['types'])):
            name = self.SD['types'][i]
            spec = utl.GetPrimSpec(outlyr, refer.path.AppendChild(name))
            relpath = utl.GetRelPath(output, self.SD['files'][i])
            utl.ReferenceAppend(spec, relpath)
            # spec.assetInfo = {'name': name, 'identifier': Sdf.AssetPath(relpath)}
            spec.assetInfo = {'name': name}
            source.append(spec.path)

        # place xform
        for p in self.SD['places']:
            spec = utl.GetPrimSpec(outlyr, root.path.AppendChild(p))
            spec.SetInfo('kind', 'assembly')

        idx = 0
        for i in xrange(len(self.SD['agents'])):
            idx += 2
            node= self.SD['agents'][i]
            aid = cmds.getAttr('%s.agentId' % node)
            tid = cmds.getAttr('%s.tid' % node)
            pid = cmds.getAttr('%s.placeId' % node)     # placement id

            # agent spec
            agentSpec = utl.GetPrimSpec(outlyr, root.path.AppendPath('%s/Agent%s' % (self.SD['places'][pid], aid)))
            agentSpec.SetInfo('kind', 'component')
            agentSpec.assetInfo = {'name': self.SD['types'][tid].replace('OriginalAgent_', '')}
            utl.ReferenceAppend(agentSpec, '', path=source[tid])

            skelRootSpec = utl.GetPrimSpec(outlyr, agentSpec.path.AppendChild('SkelRoot'), specifier='over')
            skelAniSpec  = utl.GetPrimSpec(outlyr, skelRootSpec.path.AppendChild('SkelAnim'), type='SkelAnimation')

            T=list(); R=list(); MR=list(); S=list()
            # joint count iter
            for x in range(len(self.SD['joints'][tid])):
                trans = self.SD['data'][idx:idx+3]
                T.append(Gf.Vec3f(*trans))
                idx += 3

                rotate = self.SD['data'][idx:idx+3]
                orient = OpenMaya.MEulerRotation(math.radians(rotate[0]), math.radians(rotate[1]), math.radians(rotate[2]), 0).asQuaternion()
                orient*= self.SD['orients'][tid][x]
                MR.append(orient)
                R.append(Gf.Quath(orient.w, orient.x, orient.y, orient.z).Normalize())
                idx += 3

                scale = self.SD['data'][idx:idx+3]
                if x == 0:
                    S.append(Gf.Vec3f(*scale))
                else:
                    S.append(Gf.Vec3f(1))
                idx += 3

                num = self.SD['data'][idx] # extra data count
                idx += 1 + int(num)

            # agent transform
            xopTspec = utl.GetAttributeSpec(agentSpec, 'xformOp:translate', None, Sdf.ValueTypeNames.Double3)
            outlyr.SetTimeSample(xopTspec.path, frame, T[0])
            xopRspec = utl.GetAttributeSpec(agentSpec, 'xformOp:rotateXYZ', None, Sdf.ValueTypeNames.Float3)
            eur = MR[0].asEulerRotation()
            outlyr.SetTimeSample(xopRspec.path, frame, Gf.Vec3f(math.degrees(eur.x), math.degrees(eur.y), math.degrees(eur.z)))

            utl.GetAttributeSpec(agentSpec, 'xformOpOrder', ['xformOp:translate', 'xformOp:rotateXYZ'],
                                 Sdf.ValueTypeNames.TokenArray, variability=Sdf.VariabilityUniform)

            # init root transform
            T[0] = Gf.Vec3f(0, 0, 0)
            R[0] = Gf.Quath(1, 0, 0, 0)

            tspec = utl.GetAttributeSpec(skelAniSpec, 'translations', None, Sdf.ValueTypeNames.Float3Array)
            outlyr.SetTimeSample(tspec.path, frame, Vt.Vec3fArray(T))
            rspec = utl.GetAttributeSpec(skelAniSpec, 'rotations', None, Sdf.ValueTypeNames.QuatfArray)
            outlyr.SetTimeSample(rspec.path, frame, Vt.QuatfArray(R))
            sspec = utl.GetAttributeSpec(skelAniSpec, 'scales', None, Sdf.ValueTypeNames.Half3Array)
            outlyr.SetTimeSample(sspec.path, frame, Vt.Vec3fArray(S))

            # bind skel animation
            utl.GetAttributeSpec(skelAniSpec, 'joints', self.SD['joints'][tid], Sdf.ValueTypeNames.TokenArray, Sdf.VariabilityUniform)
            utl.CreateRelationshipSpec(skelRootSpec, 'skel:animationSource', skelAniSpec.path, Sdf.VariabilityUniform)

            # custom primvar
            utl.GetAttributeSpec(agentSpec, 'primvars:agentIndex', aid, Sdf.ValueTypeNames.Int, variability=Sdf.VariabilityUniform, info={'interpolation': 'constant'})
            utl.GetAttributeSpec(agentSpec, 'primvars:agentTypeIndex', tid, Sdf.ValueTypeNames.Int, variability=Sdf.VariabilityUniform, info={'interpolation': 'constant'})

        with utl.OpenStage(outlyr) as stage:
            # compute bound
            for i in xrange(len(self.SD['agents'])):
                node = self.SD['agents'][i]
                aid  = cmds.getAttr('%s.agentId' % node)
                pid  = cmds.getAttr('%s.placeId' % node)
                prim = stage.GetPrimAtPath(root.path.AppendPath('%s/Agent%s/SkelRoot' % (self.SD['places'][pid], aid)))
                boundable = UsdGeom.Boundable(prim)
                extent    = UsdGeom.Boundable.ComputeExtentFromPlugins(boundable, Usd.TimeCode(frame))
                spec = outlyr.GetPrimAtPath(prim.GetPath())
                specAttr = utl.GetAttributeSpec(spec, 'extent', None, Sdf.ValueTypeNames.Float3Array)
                outlyr.SetTimeSample(specAttr.path, frame, extent)

            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)

        outlyr.Save()
        del outlyr


    def Exporting(self):
        if self.arg.frameRange == [0, 0]:
            self.arg.frameRange = mutl.GetFrameRange()
        if self.arg.exportRange == [0, 0]:
            self.arg.exportRange = [self.arg.frameRange[0] - 1, self.arg.frameRange[1] + 1]
        self.fps = mutl.GetFPS()

        # Initialize Miarmy
        self.InitializeMiarmy()

        self.customData = {
            'sceneFile': self.arg.scene,
            'start': self.arg.frameRange[0],
            'end': self.arg.frameRange[1]
        }

        self.SD = MiarmyShotExport.GetSceneData()
        if self.arg.selAgents:
            self.SD['agents'] = cmds.ls(self.arg.selAgents, dag=True, type='McdAgent')

        for f in range(self.arg.exportRange[0], self.arg.exportRange[1] + 1):
            print('>', f)   # debug for progress.
            cmds.currentTime(f)
            self.SD['data'] = []
            if self.arg.selAgents:
                for n in self.SD['agents']:
                    cmds.select(n)
                    self.SD['data'].extend(mel.eval('McdAgentMatchCmd -mm 4'))
            else:
                self.SD['data'] = mel.eval('McdAgentMatchCmd -mm 3')

            self.MakeSkelAnimation(f)

        return var.SUCCESS

    def Tweaking(self):
        return var.SUCCESS
    def Compositing(self):
        return var.SUCCESS


class MiarmyShotComposit(exp.MiarmyShotExporter):
    '''
    Coalesce per frame skel files.
    Tweaking, Compositing
    '''
    def Coalesce(self):
        srcfile = utl.SJoin(self.arg.dstdir, 'crowd.skel.*.usd')
        frameFiles = utl.GetPerFrameFiles(srcfile, self.exportRange)
        utl.CoalesceFiles(frameFiles, self.exportRange, step=1.0, outFile=self.arg.master)


    def AgentPostProcess(self):
        with utl.OpenStage(self.outlyr) as stage:
            dprim = stage.GetDefaultPrim()
            for p in iter(Usd.PrimRange.AllPrims(dprim)):
                if p.GetName().startswith('Agent'):
                    attr = p.GetAttribute('primvars:agentIndex')
                    if not attr:
                        continue
                    aid = attr.Get()
                    random.seed(aid * 1000)
                    txid = random.randint(1, 9)
                    spec = utl.GetPrimSpec(self.outlyr, p.GetPath(), specifier='over')
                    utl.GetAttributeSpec(spec, 'primvars:txVarNum', txid, Sdf.ValueTypeNames.Int,
                                         variability=Sdf.VariabilityUniform, info={'interpolation': 'constant'})


    def Exporting(self):
        if self.arg.frameRange == [0, 0]:
            self.arg.frameRange = mutl.GetFrameRange()
        self.exportRange = [self.arg.frameRange[0] - 1, self.arg.frameRange[1] + 1]
        self.fps = mutl.GetFPS()

        self.customData = {
            'sceneFile': self.arg.scene,
            'start': self.arg.frameRange[0],
            'end': self.arg.frameRange[1]
        }

        self.Coalesce()

        self.outlyr = utl.AsLayer(self.arg.master)
        utl.UpdateLayerData(self.outlyr, self.customData).doIt()
        self.outlyr.startTimeCode = self.arg.frameRange[0]
        self.outlyr.endTimeCode   = self.arg.frameRange[1]
        self.outlyr.framesPerSecond    = self.fps
        self.outlyr.timeCodesPerSecond = self.fps

        self.AgentPostProcess()

        self.outlyr.Save()
        del self.outlyr

        return var.SUCCESS

    # def Tweaking(self):
    #     return var.SUCCESS

def shotExport_miarmy(overwrite=False, show=None, seq=None, shot=None, version=None,
                      fr=[0, 0], efr=[0, 0], user='anonymouse', process='geom'):
    # current scene filename
    sceneFile = cmds.file(q=True, sn=True)

    arg = exp.AMiarmyShotExporter()
    arg.scene = sceneFile
    arg.overwrite  = overwrite
    arg.user = user
    arg.frameRange = fr
    if efr != [0, 0]:
        arg.exportRange = efr

    # override
    if show: arg.ovr_show = show
    if seq:  arg.ovr_seq  = seq
    if shot: arg.ovr_shot = shot
    if version: arg.ver   = version

    if process == 'both':
        MiarmyShotExport(arg)
        exporter = MiarmyShotComposit(arg)
    else:
        if process == 'geom':
            exporter = MiarmyShotExport(arg)
        else:
            exporter = MiarmyShotComposit(arg)
    return exporter.arg.master


class GetGlmJoints:
    def __init__(self, bones):
        self.allJoints = list()
        for j in cmds.ls(bones, dag=True, type='joint', l=True):
            self.allJoints.append(j)

        prefix    = ''
        rootJoint = self.allJoints[0]
        if len(rootJoint.split('|')) > 2:
            prefix = rootJoint.replace(rootJoint.split('|')[-1], '')

        self.allJointsPath = list()
        self.allJointsName = list()
        for j in self.allJoints:
            path = j.replace(prefix, '').replace('|', '/')
            self.allJointsPath.append(path)
            self.allJointsName.append(j.split('|')[-1])

    def getTransforms(self):
        bind = list(); rest = list()
        for j in self.allJoints:
            wsMtx = cmds.xform(j, q=True, ws=True, m=True)  # BindTransform
            bind.append(Gf.Matrix4d(*wsMtx))

            osMtx = cmds.xform(j, q=True, os=True, m=True)  # RestTransform
            rest.append(Gf.Matrix4d(*osMtx))
        return bind, rest


#-------------------------------------------------------------------------------
#
#   Golaem Asset
#
#-------------------------------------------------------------------------------
class GolaemAssetExport(exp.GolaemAssetExporter):
    def Exporting(self):
        # Member variable
        self.customData = {'sceneFile': self.arg.scene,
                           'characterFile': self.arg.gcha}

        self.meshes = cmds.glmCharacterFileTool(characterFile=self.arg.gcha,
                                                getAttr='meshAssets')
        bones = cmds.glmCharacterFileTool(characterFile=self.arg.gcha,
                                          getAttr='bones')
        self.JOINT = GetGlmJoints(bones)

        if not os.path.exists(os.path.dirname(self.arg.gchafile)):
            os.makedirs(os.path.dirname(self.arg.gchafile))

        # golaem character
        cmds.glmCharacterMaker(script=True, file=self.arg.gcha,
                               outputFile=self.arg.gchafile)
        cmds.glmExportCharacterGeometry(characterFile=self.arg.gchafile,
                                        outputFileGCG=self.arg.gcgfile)
        cmds.glmCharacterFileTool(characterFile=self.arg.gchafile,
                                  setAttr='geoFilePaths',
                                  value=utl.GetRelPath(self.arg.gchafile, self.arg.gcgfile))

        # maya export
        cmds.select(self.arg.node)
        cmds.file(self.arg.gchafile.replace('.gcha', '.mb'), pr=True,
                  typ='mayaBinary', options='v=0;', es=True, f=True)

        # geom
        self.GeomExport(self.arg.geomfile)

        # rig
        self.CreateRig(self.arg.rigfile)

        # master
        self.SkelSetup(self.arg.master)

        return var.SUCCESS


    def GeomExport(self, filename):
        # remove subdiv attribute
        for shape in cmds.ls(self.meshes, dag=True, type='surfaceShape', ni=True):
            if cmds.attributeQuery('USD_ATTR_subdivisionScheme', n=shape, ex=True):
                cmds.deleteAttr('%s.USD_ATTR_subdivisionScheme' % shape)

        # Custom User Attributes
        UsdAttr = utl.UsdUserAttributes(self.arg.node)
        UsdAttr.Set()

        opts = {'defaultMeshScheme': 'catmullClark'}
        utl.UsdExport(filename, self.meshes, **opts).doIt()

        UsdAttr.Clear()

        # remove mesh extent and xformOp
        with utl.OpenStage(filename) as stage:
            for p in iter(Usd.PrimRange.AllPrims(stage.GetDefaultPrim())):
                # extent
                if p.GetTypeName() == 'Mesh':
                    p.RemoveProperty('extent')
                    Usd.ModelAPI(p).SetKind('component')
                # xform
                for attr in p.GetPropertiesInNamespace('xformOp'):
                    p.RemoveProperty(attr.GetName())
                if p.HasProperty('xformOpOrder'):
                    p.RemoveProperty('xformOpOrder')
            stage.GetRootLayer().Save()


    def CreateRig(self, filename):
        print('>> CreateRig')
        outlyr = utl.AsLayer(filename, create=True, clear=True)
        outlyr.defaultPrim = 'Rig'

        spec = utl.GetPrimSpec(outlyr, '/Rig', type='Scope')
        spec = utl.GetPrimSpec(outlyr, '/Rig/Skel', type='Skeleton')
        utl.SetPurpose(spec, 'guide')

        bind, rest = self.JOINT.getTransforms()
        utl.GetAttributeSpec(spec, 'bindTransforms', Vt.Matrix4dArray(bind), Sdf.ValueTypeNames.Matrix4dArray, Sdf.VariabilityUniform)
        utl.GetAttributeSpec(spec, 'restTransforms', Vt.Matrix4dArray(rest), Sdf.ValueTypeNames.Matrix4dArray, Sdf.VariabilityUniform)
        utl.GetAttributeSpec(spec, 'joints', self.JOINT.allJointsPath, Sdf.ValueTypeNames.TokenArray, Sdf.VariabilityUniform)
        utl.GetAttributeSpec(spec, 'jointNames', self.JOINT.allJointsName, Sdf.ValueTypeNames.TokenArray, Sdf.VariabilityUniform)

        with utl.OpenStage(outlyr) as stage:
            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
            # Extent
            prim = stage.GetPrimAtPath(spec.path)
            boundable = UsdGeom.Boundable(prim)
            extent    = UsdGeom.Boundable.ComputeExtentFromPlugins(boundable, Usd.TimeCode.Default())
            utl.GetAttributeSpec(spec, 'extent', extent, Sdf.ValueTypeNames.Float3Array)

        # update customLayerData
        utl.UpdateLayerData(outlyr, self.customData).doIt()

        outlyr.Save()
        del outlyr


    def SkelSetup(self, filename):
        # print('>> SkelSetup')
        outlyr = utl.AsLayer(filename, create=True, clear=True)
        outlyr.defaultPrim = self.arg.nslyr

        root = utl.GetPrimSpec(outlyr, '/' + self.arg.nslyr)
        root.assetInfo = {'name': self.arg.nslyr}
        root.SetInfo('kind', 'assembly')

        skelRootPath = root.path.AppendChild('SkelRoot')
        skelRootSpec = utl.GetPrimSpec(outlyr, skelRootPath, type='SkelRoot')
        utl.CreateSkelBindingAPI(skelRootSpec)

        geomSpec = utl.GetPrimSpec(outlyr, skelRootPath.AppendChild('Geom'))
        utl.ReferenceAppend(geomSpec, './%s.geom.usd' % self.arg.nslyr)

        rigSpec  = utl.GetPrimSpec(outlyr, skelRootPath.AppendChild('Rig'), type='Scope')
        utl.ReferenceAppend(rigSpec, './%s.rig.usd' % self.arg.nslyr)

        # Add Skel Attributes
        self.SkelAttributes(outlyr, geomSpec)

        utl.CreateRelationshipSpec(skelRootSpec, 'skel:skeleton', Sdf.Path('Rig/Skel'), Sdf.VariabilityUniform)

        with utl.OpenStage(outlyr) as stage:
            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
            # compute extent
            prim = stage.GetPrimAtPath(skelRootPath)
            boundable = UsdGeom.Boundable(prim)
            extent    = UsdGeom.Boundable.ComputeExtentFromPlugins(boundable, Usd.TimeCode.Default())
            utl.GetAttributeSpec(skelRootSpec, 'extent', extent, Sdf.ValueTypeNames.Float3Array)

        # update customLayerData
        utl.UpdateLayerData(outlyr, self.customData).doIt()

        outlyr.Save()
        del outlyr


    def SkelAttributes(self, outlyr, parent):
        for shape in cmds.ls(self.meshes, dag=True, type='surfaceShape', ni=True, l=True):
            history = cmds.listHistory(shape, groupLevels=True, pruneDagObjects=True)
            if not history:
                continue
            clusters = cmds.ls(history, type='skinCluster')
            if not clusters:
                continue

            trans = cmds.listRelatives(shape, p=True, f=True)[0]
            wmtx  = cmds.xform(trans, q=True, m=True, ws=True)

            rpath   = '/'.join(trans.split('|')[2:])
            cluster = clusters[0]
            skinClusterFn    = OpenMayaAnim.MFnSkinCluster(mutl.GetMObject(cluster, False))
            influenceDagList = skinClusterFn.influenceObjects()
            influenceIndices = list()
            for j in influenceDagList:
                jpath = j.fullPathName()
                index = self.JOINT.allJoints.index(jpath)
                influenceIndices.append(index)

            shapeObj = mutl.GetMObject(shape)
            meshFn   = OpenMaya.MFnMesh(shapeObj)
            numVertices  = meshFn.numVertices
            singleIdComp = OpenMaya.MFnSingleIndexedComponent()
            vertexComp   = singleIdComp.create(OpenMaya.MFn.kMeshVertComponent)

            weightData = skinClusterFn.getWeights(shapeObj, vertexComp)
            weights    = weightData[0]
            numInfluences = int(weightData[1])
            maxInfluences = numInfluences

            JointIndices = [0]   * maxInfluences * numVertices
            JointWeights = [0.0] * maxInfluences * numVertices

            for vtx in range(numVertices):
                inputOffset  = vtx * numInfluences
                outputOffset = vtx * maxInfluences
                for i in range(numInfluences):
                    weight = weights[inputOffset + i]
                    if not Gf.IsClose(weight, 0.0, 1e-8):
                        JointIndices[outputOffset] = influenceIndices[i]
                        JointWeights[outputOffset] = weight
                        outputOffset += 1

            spec = utl.GetPrimSpec(outlyr, parent.path.AppendPath(rpath), specifier='over')
            utl.CreateSkelBindingAPI(spec)
            utl.GetAttributeSpec(spec, 'primvars:skel:geomBindTransform', Gf.Matrix4d(*wmtx), Sdf.ValueTypeNames.Matrix4d)
            utl.GetAttributeSpec(spec, 'primvars:skel:jointIndices', Vt.IntArray(JointIndices), Sdf.ValueTypeNames.IntArray,
                info={'elementSize': numInfluences, 'interpolation': 'vertex'})
            utl.GetAttributeSpec(spec, 'primvars:skel:jointWeights', Vt.FloatArray(JointWeights), Sdf.ValueTypeNames.FloatArray,
                info={'elementSize': numInfluences, 'interpolation': 'vertex'})


    # def Tweaking(self):
    #     return var.SUCCESS
    #
    # def Compositing(self):
    #     return var.SUCCESS


#-------------------------------------------------------------------------------
#
#   Golaem Motion
#
#-------------------------------------------------------------------------------
class GolaemMotionExport:
    def __init__(self, args, fr=(None, None), step=0.0):
        self.args = args
        self.default    = ''
        self.jointNames = list()
        self.joints     = list()
        self.mayaJoints = list()

        coder = rb.Coder()
        assetDir = coder.D.TASKNVS.Encode(**self.args).replace('/motion', '')
        self.skelAsset = utl.SJoin(assetDir, self.args['nslyr'] + '.usd')
        self.motionName = self.args['motion']

        self.readAsset()
        self.fr = self.getFrameRange(fr)
        self.frameSamples = mutl.getFrameSamples(step)

        print('assetDir:', assetDir)
        print('self.skelAsset:', self.skelAsset)
        print('self.motionName:', self.motionName)
        print('self.fr:', self.fr)

    def readAsset(self):
        srclyr = utl.AsLayer(self.skelAsset)
        if not srclyr:
            print('# ERROR : not found skel asset!')
            return

        with utl.OpenStage(srclyr) as stage:
            dprim    = stage.GetDefaultPrim()
            self.default = dprim.GetName()
            skelroot = stage.GetPrimAtPath(dprim.GetPath().AppendChild('SkelRoot'))
            skeleton_path = skelroot.GetProperty('skel:skeleton').GetTargets()[0]

            prim = stage.GetPrimAtPath(skeleton_path)
            self.jointNames = prim.GetAttribute('jointNames').Get()
            self.joints     = prim.GetAttribute('joints').Get()


    def getFrameRange(self, fr):
        if fr[0] == None and fr[1] == None:
            return mutl.GetFrameRange()
        else:
            return fr

    def getJointDecomposeTransforms(self):
        xforms = list()
        for joint in self.mayaJoints:
            mtx = cmds.xform(joint, q=True, m=True, os=True)
            xforms.append(Gf.Matrix4d(*mtx))
        translations, rotations, scales = UsdSkel.DecomposeTransforms(Vt.Matrix4dArray(xforms))
        return translations, rotations, scales

    def doIt(self):
        '''
        SkelAsset composited filename.
            separated *.motion.usd file is only SkelAnimation data.
        '''
        if not self.joints:
            print('# ERROR : not found joints!')
            return

        # get maya joints
        for j in self.jointNames:
            cur = cmds.ls(j, r=True, type='joint')
            if cur:
                self.mayaJoints.append(cur[0])

        # motion file
        outputPath = os.path.dirname(self.skelAsset)
        master = os.path.join(outputPath, 'motion', self.motionName + '.usd')
        motionFile = master.replace('.usd', '.motion.usd')
        self.writeMotion(motionFile)
        print('> Write Motion\t:', motionFile)

        # skelAsset Composite
        self.composite(master, motionFile)
        print('> Composite Motion\t:', master)

        # save as scene
        scene = master.replace('.usd', '.mb')
        cmds.file(scene, pr=True, typ='mayaBinary', options='v=0;', ea=True,  f=True)
        print('> Save As maya scene\t:', scene)

    def setTimeCode(self, layer):
        layer.startTimeCode = self.fr[0]
        layer.endTimeCode   = self.fr[1]


    def writeMotion(self, out):
        outlyr = utl.AsLayer(out, create=True, clear=True, format='usda')
        outlyr.defaultPrim = 'SkelAnim'
        self.setTimeCode(outlyr)

        spec = utl.GetPrimSpec(outlyr, '/SkelAnim', type='SkelAnimation')
        utl.GetAttributeSpec(spec, 'joints', self.joints, Sdf.ValueTypeNames.TokenArray, Sdf.VariabilityUniform)

        attr_S = utl.GetAttributeSpec(spec, 'scales', None, Sdf.ValueTypeNames.Half3Array)
        attr_R = utl.GetAttributeSpec(spec, 'rotations', None, Sdf.ValueTypeNames.QuatfArray)
        attr_T = utl.GetAttributeSpec(spec, 'translations', None, Sdf.ValueTypeNames.Float3Array)

        for f in range(self.fr[0], self.fr[1] + 1):
            for s in self.frameSamples:
                frame = f + s
                cmds.currentTime(frame)

                translations, rotations, scales = self.getJointDecomposeTransforms()
                outlyr.SetTimeSample(attr_T.path, frame, translations)
                outlyr.SetTimeSample(attr_R.path, frame, rotations)
                outlyr.SetTimeSample(attr_S.path, frame, scales)

        outlyr.Save()
        del outlyr


    def composite(self, out, src):     # src is motion file
        outlyr = utl.AsLayer(out, create=True, clear=True)
        outlyr.defaultPrim = self.default
        self.setTimeCode(outlyr)

        root = utl.GetPrimSpec(outlyr, '/' + self.default)
        relpath = utl.GetRelPath(out, self.skelAsset)
        utl.ReferenceAppend(root, relpath)

        skelRootSpec = utl.GetPrimSpec(outlyr, root.path.AppendChild('SkelRoot'), specifier='over')

        skelAniSpec  = utl.GetPrimSpec(outlyr, skelRootSpec.path.AppendChild('SkelAnim'), specifier='over')
        utl.ReferenceAppend(skelAniSpec, './' + os.path.basename(src))

        # bind skel animation
        utl.CreateRelationshipSpec(skelRootSpec, 'skel:animationSource', skelAniSpec.path, Sdf.VariabilityUniform)

        # compute bound
        with utl.OpenStage(outlyr) as stage:
            for f in range(self.fr[0], self.fr[1] + 1):
                for s in self.frameSamples:
                    frame = f + s
                    cmds.currentTime(frame)

                    prim = stage.GetPrimAtPath(root.path.AppendChild('SkelRoot'))
                    boundable = UsdGeom.Boundable(prim)
                    extent    = UsdGeom.Boundable.ComputeExtentFromPlugins(boundable, Usd.TimeCode(frame))
                    spec = outlyr.GetPrimAtPath(prim.GetPath())
                    specAttr = utl.GetAttributeSpec(spec, 'extent', None, Sdf.ValueTypeNames.Float3Array)
                    outlyr.SetTimeSample(specAttr.path, frame, extent)
            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)

        outlyr.Save()
        del outlyr


#-------------------------------------------------------------------------------
#
#   Golaem Shot
#
#-------------------------------------------------------------------------------
class GolaemShotExport(exp.GolaemShotExporter):
    def initializeGolaem(self):
        self.gCaches = list()

        for glmCache in self.arg.glmCaches:
            cacheNode = glmCache.split(':')[0]
            gCache = glmCore.ReadSimCache(cacheNode, gscb=self.arg.gscb)
            if self.arg.exportRange == [0, 0]:
                self.arg.exportRange = gCache.cacheRange

            gCache.customData = {'sceneFile': self.arg.scene,
                               'gchaFiles': ''}

            # get USD agent asset
            for gcha in gCache.charFiles:
                if gCache.customData['gchaFiles']:
                    gCache.customData['gchaFiles'] += ', %s' % gcha
                else:
                    gCache.customData['gchaFiles'] = gcha

                fileName = os.path.basename(gcha).replace('gcha', 'usd')
                coder = rb.Coder()
                if '/works/' in gcha:
                    ret = coder.D.SHOW.Decode(gcha)
                    ret.update(coder.D.ASSET.Decode(gcha))
                    ret.pub = '_3d'
                    ret.task = 'agent'
                    ret.nslyr = fileName.split('.')[0]
                    if ret.asset == 'asset':
                        ret.asset = fileName.split('.')[0]
                    ret.nsver = utl.GetLastVersion(coder.D.Encode(**ret))
                    assetdir = os.path.join(coder.D.Encode(**ret), fileName)
                else:
                    ret = coder.D.AGENT.Decode(gcha)
                    ret.pop('subdir')
                    assetdir = os.path.join(coder.D.Encode(**ret), fileName)

                if os.path.exists(assetdir):
                    if not assetdir in gCache.assetFiles:
                        gCache.assetFiles.append(assetdir)
                        gCache.assetJoints.append(self.getSkelJointFromAsset(assetdir))
                else:
                    assert False, 'Error Agent path exists. %s' % assetdir

            msg.debug('cacheRange:', gCache.cacheRange)
            msg.debug('gchaFiles:', gCache.charFiles)
            msg.debug('assetFiles:', gCache.assetFiles)
            msg.debug('terrainFiles:', gCache.sTerrainFile, gCache.dTerrainFile)
            msg.debug('layoutFiles:', gCache.layoutFiles)
            msg.debug('killEntities:', len(gCache.killEntities))

            self.gCaches.append(gCache)


    def AddAgentSource(self, gCache, layer, assetPath):
        root = utl.GetPrimSpec(layer, '/_%s_agent_src' % gCache.cacheNode, specifier='class')
        name = os.path.basename(assetPath).split('.')[0]
        spec = utl.GetPrimSpec(layer, root.path.AppendChild(name))
        spec.assetInfo = {'name': name}
        spec.SetInfo('kind', 'component')
        relpath  = utl.GetRelPath(layer.identifier, assetPath)
        utl.ReferenceAppend(spec, relpath, clear=True)

        gCache.agentSrcs.append(spec)

    def getSkelJointFromAsset(self, assetFile):
        with utl.OpenStage(assetFile) as stage:
            dprim = stage.GetDefaultPrim()
            prim  = stage.GetPrimAtPath(dprim.GetPath().AppendPath('SkelRoot/Rig/Skel'))
            joints= prim.GetAttribute('joints').Get()
            return joints

    def toQuatf(self, orient):
        return Gf.Quatf(orient[3], orient[0], orient[1], orient[2])

    def computeEntityMatrix(self, gCache, index):
        boneCount, bonePositions, boneOrientations = gCache.getEntity(index)
        cid   = gCache.charIds[index]
        scale = Gf.Vec3h(gCache.entityScales[index])

        xforms = list()
        for i in range(boneCount):
            pos = Gf.Vec3f(*bonePositions[i])
            rot = self.toQuatf(boneOrientations[i])

            pid = gCache.charsParentBoneIds[cid][i]
            if pid == -1:
                mtx = UsdSkel.MakeTransform(pos, rot, scale)
                xforms.append(mtx)
            else:
                # me
                m_mtx = UsdSkel.MakeTransform(pos, rot, scale)
                # parent
                p_mtx = UsdSkel.MakeTransform(Gf.Vec3f(*bonePositions[pid]), self.toQuatf(boneOrientations[pid]), scale)
                mtx = m_mtx * p_mtx.GetInverse()
                xforms.append(mtx)

        return UsdSkel.DecomposeTransforms(Vt.Matrix4dArray(xforms))

    def setFrame(self, gCache, skelRootSpec, animSpec, index, frame):
        outlyr = skelRootSpec.layer

        result = gCache.getFrame(frame)
        if not result:
            return
        translations, rotations, scales = self.computeEntityMatrix(gCache, index)

        # Set SkelRoot translate
        trASpec = utl.GetAttributeSpec(skelRootSpec, 'xformOp:translate', None, Sdf.ValueTypeNames.Double3)
        outlyr.SetTimeSample(trASpec.path, frame, Gf.Vec3d(translations[0]))
        utl.GetAttributeSpec(skelRootSpec, 'xformOpOrder', ['xformOp:translate'], Sdf.ValueTypeNames.TokenArray, Sdf.VariabilityUniform)

        # Set SkelAnim
        translations[0] = Gf.Vec3f(0)
        posASpec = utl.GetAttributeSpec(animSpec, 'translations', None, Sdf.ValueTypeNames.Float3Array)
        outlyr.SetTimeSample(posASpec.path, frame, translations)

        rotASpec = utl.GetAttributeSpec(animSpec, 'rotations', None, Sdf.ValueTypeNames.QuatfArray)
        outlyr.SetTimeSample(rotASpec.path, frame, rotations)

        sclASpec = utl.GetAttributeSpec(animSpec, 'scales', None, Sdf.ValueTypeNames.Half3Array)
        outlyr.SetTimeSample(sclASpec.path, frame, scales)

    def makeSkelAnimation(self, frame):
        output = utl.SJoin(self.arg.dstdir, 'crowd.skel.%04d.usd' % frame)
        outlyr = utl.AsLayer(output, create=True, clear=True)

        outlyr.defaultPrim = 'Golaem'
        outlyr.startTimeCode = frame
        outlyr.endTimeCode   = frame

        root = utl.GetPrimSpec(outlyr, '/Golaem')
        root.SetInfo('kind', 'assembly')

        for gCache in self.gCaches:
            gCache.agentSrcs = list()
            agentTypes = list()

            # set agent specialize
            for asset in gCache.assetFiles:
                self.AddAgentSource(gCache, outlyr, asset)
                agentTypes.append(os.path.basename(asset).split('.')[0])

            # # group by fieldName
            for fieldName in gCache.fieldNames:

                groupSpec = utl.GetPrimSpec(outlyr, root.path.AppendChild(gCache.cacheNode))
                groupSpec.SetInfo('kind', 'assembly')
                utl.GetAttributeSpec(groupSpec, 'userProperties:Crowd:agentTypes', agentTypes, Sdf.ValueTypeNames.StringArray, variability=Sdf.VariabilityUniform, custom=True)

                # golaem simulation cache setup by fieldName
                gCache.doIt(fieldName)

                # iterate entity
                for i in range(gCache.entityCount):
                    cid = gCache.charIds[i]
                    entityId  = gCache.entityIds[i]
                    assetFile = gCache.assetFiles[cid]
                    agentSrc  = gCache.agentSrcs[cid]

                    if entityId in gCache.killEntities:
                        msg.debug('%s %s %s entity Killed!' % (gCache.cacheNode, fieldName, entityId))
                        continue

                    spec = utl.GetPrimSpec(outlyr, groupSpec.path.AppendChild('Agent_%s' % (i + 1)))
                    spec.SetInfo('kind', 'component')
                    utl.SetSpecialize(agentSrc, spec)

                    # extra attributes
                    utl.GetAttributeSpec(spec, 'primvars:agentIndex', entityId, Sdf.ValueTypeNames.Int, variability=Sdf.VariabilityUniform, info={'interpolation': 'constant'})
                    utl.GetAttributeSpec(spec, 'primvars:agentTypeIndex', cid, Sdf.ValueTypeNames.Int, variability=Sdf.VariabilityUniform, info={'interpolation': 'constant'})
                    random.seed(entityId * 1000)
                    txid = random.randint(1, 9)
                    utl.GetAttributeSpec(spec, 'primvars:txVarNum', txid, Sdf.ValueTypeNames.Int, variability=Sdf.VariabilityUniform, info={'interpolation': 'constant'})

                    skelRootSpec = utl.GetPrimSpec(outlyr, spec.path.AppendChild('SkelRoot'), specifier='over')
                    animSpec = utl.GetPrimSpec(outlyr, skelRootSpec.path.AppendChild('SkelAnim'), type='SkelAnimation')
                    # set joints
                    joints = gCache.assetJoints[cid]
                    utl.GetAttributeSpec(animSpec, 'joints', joints, Sdf.ValueTypeNames.TokenArray, Sdf.VariabilityUniform)

                    utl.CreateSkelBindingAPI(skelRootSpec)
                    utl.CreateRelationshipSpec(skelRootSpec, 'skel:animationSource', Sdf.Path('SkelAnim'), Sdf.VariabilityUniform)

                    # Frame
                    self.setFrame(gCache, skelRootSpec, animSpec, i, frame)


        with utl.OpenStage(outlyr) as stage:
            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
            for p in iter(Usd.PrimRange.AllPrims(stage.GetDefaultPrim())):
                if p.GetTypeName() == 'SkelRoot':
                    spec = outlyr.GetPrimAtPath(p.GetPath())
                    # Extent
                    boundable = UsdGeom.Boundable(p)
                    extent = UsdGeom.Boundable.ComputeExtentFromPlugins(boundable, Usd.TimeCode(frame))
                    if extent:
                        attrSpec = utl.GetAttributeSpec(spec, 'extent', None, Sdf.ValueTypeNames.Float3Array)
                        outlyr.SetTimeSample(attrSpec.path, frame, extent)

        # update customLayerData
        utl.UpdateLayerData(outlyr, gCache.customData).doIt()

        outlyr.Save()
        del outlyr
        return output

    def Exporting(self):
        self.initializeGolaem()

        if not os.path.exists(self.arg.dstdir):
            os.makedirs(self.arg.dstdir)

        # Frame
        for frame in range(self.arg.exportRange[0], self.arg.exportRange[1]+1):
            print('# export frame :', frame)
            self.makeSkelAnimation(frame)

    def Compositing(self):
        return var.SUCCESS


class GolaemShotComposit(exp.GolaemShotExporter):
    def Exporting(self):
        srcfile = utl.SJoin(self.arg.dstdir, 'crowd.skel.*.usd')
        frameFiles = utl.GetPerFrameFiles(srcfile, self.arg.exportRange)
        utl.CoalesceFiles(frameFiles, self.arg.exportRange, step=1.0, outFile=self.arg.skelfile)

        fps = mutl.GetFPS()
        customData = {
            'sceneFile': self.arg.scene,
            'start': self.arg.frameRange[0],
            'end': self.arg.frameRange[1]
        }

        outlyr = utl.AsLayer(self.arg.master, create=True, clear=True)
        utl.UpdateLayerData(outlyr, customData).doIt()
        outlyr.startTimeCode = self.arg.frameRange[0]
        outlyr.endTimeCode   = self.arg.frameRange[1]
        outlyr.timeCodesPerSecond = fps

        outlyr.defaultPrim = 'Crowd'
        root = utl.GetPrimSpec(outlyr, '/Crowd')
        root.SetInfo('kind', 'assembly')
        utl.ReferenceAppend(root, './' + os.path.basename(self.arg.skelfile))

        with utl.OpenStage(outlyr) as stage:
            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)

        outlyr.Save()
        del outlyr

        return var.SUCCESS


def assetExport_golaem(node=None, rootbone=None, show=None, version=None, overwrite=False):
    if not node:
        nodes = cmds.ls('glm_*')
        if not nodes:
            return
        node = nodes[0]
    if not node:
        print('> not found glm_groupNode!')
        return

    # current scene filename
    sceneFile = cmds.file(q=True, sn=True)

    arg = exp.AGolaemAssetExporter()
    arg.node  = node
    arg.scene = sceneFile
    arg.task = 'agent'
    arg.overwrite = overwrite
    arg.rootbone = rootbone

    cmLocator = cmds.ls(typ='CharacterMakerLocator')
    arg.gcha = cmds.getAttr(cmLocator[0] + '.currentFile')
    if not arg.rootbone:
        # arg.rootbone = cmds.ls(type='joint', dag=True)[0]
        jnts = cmds.listRelatives(arg.node, type='joint', ad=True)
        for i in jnts:
            pGrp = cmds.listRelatives(i, type='transform', p=True)
            if pGrp:
                if '_GRP' in pGrp[0]:
                    arg.rootbone = pGrp[0]

    # override
    if show:    arg.ovr_show = show
    if version: arg.ovr_ver = version

    GolaemAssetExport(arg)


def shotExport_golaem(overwrite=False, show=None, seq=None, shot=None, version=None,
                      fr=[0, 0], efr=[0, 0], gscb=None, glmCaches=None, user='anonymouse', process='geom'):
    # current scene filename
    sceneFile = cmds.file(q=True, sn=True)

    arg = exp.AGolaemShotExporter()
    arg.scene = sceneFile
    arg.overwrite  = overwrite
    arg.user = user

    if efr != [0, 0]:
        arg.exportRange = efr

    if fr != [0, 0]:
        arg.frameRange = fr
    else:
        arg.frameRange = mutl.GetFrameRange()

    if gscb: arg.gscb = gscb
    if glmCaches:
        arg.glmCaches = glmCaches.split(',')

    # override
    if show: arg.ovr_show = show
    if seq:  arg.ovr_seq  = seq
    if shot: arg.ovr_shot = shot
    if version: arg.ver   = version

    if process == 'both':
        GolaemShotExport(arg)
        GolaemShotComposit(arg)
    else:
        if process == 'geom':
            GolaemShotExport(arg)
        else:
            GolaemShotComposit(arg)
