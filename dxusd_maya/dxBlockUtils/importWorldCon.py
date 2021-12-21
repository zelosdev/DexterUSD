from pxr import Usd, UsdGeom, UsdUtils, Sdf, Vt, Gf, UsdMaya
import maya.cmds as cmds
import json
import common as cmn

import DXUSD.Utils as utl

EXP = '''
float $q[3];
$q[0] = {quat}.outputQuatX;
$q[1] = {quat}.outputQuatY;
$q[2] = {quat}.outputQuatZ;
float $w = {quat}.outputQuatW;
float $v = {ctr}.rotateWeight;

$w = acos($w) * $v;
normalize($q);
for($i=0; $i<3; $i++)
    $q[$i] *= sin($w);
$w = cos($w);

{output}.inputQuatX = $q[0];
{output}.inputQuatY = $q[1];
{output}.inputQuatZ = $q[2];
{output}.inputQuatW = $w;
'''


class importWorldCon:
    def __init__(self, top, inputfile):
        self.top = top
        self.inputfile = inputfile

        self.name = top.split('|')[-1]

        self.loadPlugins()

    def doIt(self):
        # get stage
        layer = utl.AsLayer(self.inputfile)

        stage = Usd.Stage.Open(layer)
        # get Op and timeSamples
        defPrim = stage.GetDefaultPrim()
        defPrim.GetVariantSet('WorldXform').SetVariantSelection('on')

        # get matrix node
        matrixNode = self.getMatrixNode(self.top)
        update = False
        if matrixNode:
            update = True
        else:
            matrixNode = cmds.createNode('fourByFourMatrix', name='%s_matrix'%self.name)
            cmds.addAttr(matrixNode, ln='initScale', keyable=True, dv=1)

        # set trasform attribute (xform, visibility)
        mayaAttrs = cmn.GetMayaTransformAttrs(defPrim)

        if mayaAttrs.transform != None:
            mayaAttrs.setAttr('transform', matrixNode)

        if mayaAttrs.scale != None:
            mayaAttrs.setAttr('scaleX', matrixNode, 'initScale')

        # if already top has worldXfrom, do not rig.
        if not update:
            # decompose node
            decomposeNode = cmds.createNode('decomposeMatrix', name='%s_decomposeMatrix'%self.name)
            cmds.connectAttr('%s.output'%matrixNode, '%s.inputMatrix'%decomposeNode)

            # create ctr
            ctr = self.createCtr('world', '%s_worldXform_CON'%self.name)
            ctrFg = cmds.group(ctr, name='%s_worldXform_NUL'%self.name)
            ctr = ctrFg + "|" + ctr

            cmds.addAttr(ctr, ln='txWeight', keyable=True, min=0, dv=0)
            cmds.addAttr(ctr, ln='tyWeight', keyable=True, min=0, dv=0)
            cmds.addAttr(ctr, ln='tzWeight', keyable=True, min=0, dv=0)
            cmds.addAttr(ctr, ln='rotateWeight', keyable=True, min=0, dv=0)
            cmds.addAttr(ctr, ln='useWorldConScale', keyable=True, at='bool', dv=0)
            cmds.addAttr(ctr, ln='scaleWeight', keyable=True, min=0, dv=1)

            # rig ctr (translate)
            tMult = cmds.createNode('multiplyDivide', name='%s_translateMult_MD'%self.name)

            cmds.connectAttr('%s.txWeight'%ctr, '%s.input1X'%tMult)
            cmds.connectAttr('%s.tyWeight'%ctr, '%s.input1Y'%tMult)
            cmds.connectAttr('%s.tzWeight'%ctr, '%s.input1Z'%tMult)

            cmds.connectAttr('%s.outputTranslate'%decomposeNode, '%s.input2'%tMult)
            cmds.connectAttr('%s.output'%tMult, '%s.translate'%ctrFg)

            # rig ctr (rotate)
            inAxisAngleNode = cmds.createNode('quatToAxisAngle', name='%s_inAxisAngle_QAA'%self.name)
            weightedAngleNode = cmds.createNode('multiplyDivide', name='%s_weightedAngle_MD'%self.name)
            outQuatNode = cmds.createNode('axisAngleToQuat', name='%s_outAxisAngle_QAA'%self.name)
            eulerNode = cmds.createNode('quatToEuler', name='%s_outRotate_QTE'%self.name)

            # inQuatNode > inAxisAngleNode
            cmds.connectAttr('%s.outputQuat'%decomposeNode, '%s.inputQuat'%inAxisAngleNode)
            # inAxisAngleNode > weightedAngleNode, ctr (weight) > weightedAngleNode
            cmds.connectAttr('%s.outputAngle'%inAxisAngleNode, '%s.input1X'%weightedAngleNode)
            cmds.connectAttr('%s.rotateWeight'%ctr, '%s.input2X'%weightedAngleNode)
            # inAxisAngleNode(axis) > outAxisAngleNode, weightedAngleNode > outQuatNode
            cmds.connectAttr('%s.outputX'%weightedAngleNode, '%s.inputAngle'%outQuatNode)
            cmds.connectAttr('%s.outputAxis'%inAxisAngleNode, '%s.inputAxis'%outQuatNode)
            # outQuatNode > eulerNode
            cmds.connectAttr('%s.outputQuat'%outQuatNode, '%s.inputQuat'%eulerNode)

            # eulerNode to ctrFg
            cmds.connectAttr('%s.outputRotate'%eulerNode, '%s.rotate'%ctrFg)

            # rig ctr (scale)
            scaleCdtNode = cmds.createNode('condition', name='%s_scaleUse_CDT'%self.name)
            scaleWeightNode = cmds.createNode('multiplyDivide', name='%s_scaleWeight_MD'%self.name)

            cmds.setAttr('%s.operation'%scaleCdtNode, 1)

            cmds.connectAttr('%s.initScale'%matrixNode, '%s.colorIfTrueR'%scaleCdtNode)
            cmds.connectAttr('%s.useWorldConScale'%ctr, '%s.firstTerm'%scaleCdtNode)
            cmds.connectAttr('%s.outColorR'%scaleCdtNode, '%s.input1X'%scaleWeightNode)
            cmds.connectAttr('%s.scaleWeight'%ctr, '%s.input2X'%scaleWeightNode)
            cmds.connectAttr('%s.outputX'%scaleWeightNode, '%s.scaleX'%ctrFg)
            cmds.connectAttr('%s.outputX'%scaleWeightNode, '%s.scaleY'%ctrFg)
            cmds.connectAttr('%s.outputX'%scaleWeightNode, '%s.scaleZ'%ctrFg)


        # ----------------------------------------------------------------------
        # root_con
        # ----------------------------------------------------------------------

        # find root_con usd file
        rcPath = None
        for sdfStack in defPrim.GetPrimStack():
            path   = sdfStack.layer.realPath
            if '.xform.' in path:
                rcPath = path.replace('.xform.', '.root_con.')
                break

        rcLayer = Sdf.Layer.FindOrOpen(rcPath)
        rcStage = None

        if rcLayer:
            rcStage = Usd.Stage.Open(rcPath)
        else:
            # if no root_con, rig constraint mastering
            if not update:
                self.xformMastering(ctr, ctrFg, ctr)
            return

        # get Op and timeSamples
        rcdprim = rcStage.GetDefaultPrim()

        # get matrix node
        rcMatrixNode = self.getRootConMatrixNode(matrixNode)
        update = False

        if rcMatrixNode:
            update = True
        else:
            rcMatrixNode = cmds.createNode('fourByFourMatrix', name='%s_rootCon_matrix'%self.name)
            cmds.connectAttr('%s.message'%rcMatrixNode, '%s.rootConMatrix'%matrixNode)


        # set trasform attribute (xform, visibility)
        rcMayaAttrs = cmn.GetMayaTransformAttrs(rcdprim)

        if rcMayaAttrs.transform != None:
            rcMayaAttrs.setAttr('transform', rcMatrixNode)

        if not update:
            # create ctr
            rcCtr = self.createCtr('rootCon', '%s_rootConXform_CON'%self.name, (1, 1, 0))
            rcCtrFg = cmds.group(rcCtr, name='%s_rootConXform_NUL'%self.name)
            rcCtr = ctr + "|" + rcCtrFg + "|" + rcCtr

            cmds.parent(rcCtrFg, ctr)

            cmds.addAttr(rcCtr, ln='txWeight', keyable=True, min=0, dv=1)
            cmds.addAttr(rcCtr, ln='tyWeight', keyable=True, min=0, dv=1)
            cmds.addAttr(rcCtr, ln='tzWeight', keyable=True, min=0, dv=1)
            cmds.addAttr(rcCtr, ln='rotateWeight', keyable=True, min=0, dv=1)

            # create invert transform locator
            invertLoc = cmds.spaceLocator(name='%s_rootCon_inverseMatrix_loc'%self.name)[0]
            cmds.parent(invertLoc, rcCtr)

            invertLoc = rcCtr + "|" + invertLoc

            cmds.setAttr('%s.v'%invertLoc, False)

            # fix init scale
            initScaleMatrix = cmds.createNode('composeMatrix', name='%s_initScale_composeMatrix'%self.name)
            initScaledMul   = cmds.createNode('multMatrix', name='%s_initScaled_mulMatrix'%self.name)

            cmds.connectAttr('%s.initScale'%matrixNode, '%s.inputScaleX'%initScaleMatrix)
            cmds.connectAttr('%s.initScale'%matrixNode, '%s.inputScaleY'%initScaleMatrix)
            cmds.connectAttr('%s.initScale'%matrixNode, '%s.inputScaleZ'%initScaleMatrix)

            cmds.connectAttr('%s.outputMatrix'%initScaleMatrix, '%s.matrixIn[0]'%initScaledMul)
            cmds.connectAttr('%s.output'%matrixNode, '%s.matrixIn[1]'%initScaledMul)

            # set world_rootCon matrix into worldXform matrix
            iMatrix = cmds.createNode('inverseMatrix', name='%s_worldInverse_inverseMatrix'%self.name)
            rcLocalMatrix = cmds.createNode('multMatrix', name='%s_rootCon_localMatrix_multMatrix'%self.name)

            cmds.connectAttr('%s.matrixSum'%initScaledMul, '%s.inputMatrix'%iMatrix)

            cmds.connectAttr('%s.output'%rcMatrixNode, '%s.matrixIn[0]'%rcLocalMatrix)
            cmds.connectAttr('%s.outputMatrix'%iMatrix, '%s.matrixIn[1]'%rcLocalMatrix)

            # invertLoc rigging
            rcInvertMatrix = cmds.createNode('inverseMatrix', name='%s_rootCon_localInverseMatrix_multMatrix'%self.name)
            rcInvertDecomp = cmds.createNode('decomposeMatrix', name='%s_rootCon_localInverse_decomposeMatrix'%self.name)

            cmds.connectAttr('%s.matrixSum'%rcLocalMatrix, '%s.inputMatrix'%rcInvertMatrix)
            cmds.connectAttr('%s.outputMatrix'%rcInvertMatrix, '%s.inputMatrix'%rcInvertDecomp)

            cmds.connectAttr('%s.outputTranslate'%rcInvertDecomp, '%s.translate'%invertLoc)
            cmds.connectAttr('%s.outputRotate'%rcInvertDecomp, '%s.rotate'%invertLoc)
            cmds.connectAttr('%s.outputScale'%rcInvertDecomp, '%s.scale'%invertLoc)


            # decompose node
            decomposeNode = cmds.createNode('decomposeMatrix', name='%s_rootCon_decomposeMatrix'%self.name)
            cmds.connectAttr('%s.matrixSum'%rcLocalMatrix, '%s.inputMatrix'%decomposeNode)


            # rig ctr (translate)
            tMult = cmds.createNode('multiplyDivide', name='%s_rootCon_translateMult_MD'%self.name)

            cmds.connectAttr('%s.txWeight'%rcCtr, '%s.input1X'%tMult)
            cmds.connectAttr('%s.tyWeight'%rcCtr, '%s.input1Y'%tMult)
            cmds.connectAttr('%s.tzWeight'%rcCtr, '%s.input1Z'%tMult)

            cmds.connectAttr('%s.outputTranslate'%decomposeNode, '%s.input2'%tMult)
            cmds.connectAttr('%s.output'%tMult, '%s.translate'%rcCtrFg)

            # rig ctr (rotate)
            inAxisAngleNode = cmds.createNode('quatToAxisAngle', name='%s_rootCon_inAxisAngle_QAA'%self.name)
            weightedAngleNode = cmds.createNode('multiplyDivide', name='%s_weightedAngle_MD'%self.name)
            outQuatNode = cmds.createNode('axisAngleToQuat', name='%s_rootCon_outAxisAngle_QAA'%self.name)
            eulerNode = cmds.createNode('quatToEuler', name='%s_rootCon_outRotate_QTE'%self.name)

            # inQuatNode > inAxisAngleNode
            cmds.connectAttr('%s.outputQuat'%decomposeNode, '%s.inputQuat'%inAxisAngleNode)
            # inAxisAngleNode > weightedAngleNode, ctr (weight) > weightedAngleNode
            cmds.connectAttr('%s.outputAngle'%inAxisAngleNode, '%s.input1X'%weightedAngleNode)
            cmds.connectAttr('%s.rotateWeight'%rcCtr, '%s.input2X'%weightedAngleNode)
            # inAxisAngleNode(axis) > outAxisAngleNode, weightedAngleNode > outQuatNode
            cmds.connectAttr('%s.outputX'%weightedAngleNode, '%s.inputAngle'%outQuatNode)
            cmds.connectAttr('%s.outputAxis'%inAxisAngleNode, '%s.inputAxis'%outQuatNode)
            # outQuatNode > eulerNode
            cmds.connectAttr('%s.outputQuat'%outQuatNode, '%s.inputQuat'%eulerNode)

            # eulerNode to ctrFg
            cmds.connectAttr('%s.outputRotate'%eulerNode, '%s.rotate'%rcCtrFg)

            # connect scale
            cmds.connectAttr('%s.outputScale'%decomposeNode, '%s.scale'%rcCtrFg)

            # if root_con, rig constraint mastering to rootCon
            self.xformMastering(invertLoc, ctrFg, ctr)

        self.setRootConInitPosition()
        

    def xformMastering(self, ctr, ctrFg, masterCtr):
        # constraint top to ctr
        pCon = cmds.parentConstraint(ctr, self.top, mo=False)[0]
        sCon = cmds.scaleConstraint(ctr, self.top, mo=False)[0]

        # add worldXformMaster attribute for cache exporting
        try:
            cmds.addAttr(masterCtr, ln='worldXformMaster', at='bool', dv=1)
        except:
            pass

        pConW = cmds.parentConstraint(pCon, q=True, wal=True)[0]
        sConW = cmds.scaleConstraint(sCon, q=True, wal=True)[0]
        cmds.connectAttr('%s.worldXformMaster'%masterCtr, '%s.%s'%(pCon, pConW))
        cmds.connectAttr('%s.worldXformMaster'%masterCtr, '%s.%s'%(sCon, sConW))

        # group
        topParent = cmds.listRelatives(self.top, p=True, f=True)
        if topParent:
            cmds.parent(ctrFg, topParent[0])


    def getMatrixNode(self, obj):
        constraint = cmds.parentConstraint(obj, q=True)
        matrixNode = None
        if constraint:
            targets = cmds.parentConstraint(constraint, q=True, tl=True)
            if targets:
                worldXform = cmds.listRelatives(targets[0], p=True, f=True)[0]

                for node in cmds.listHistory(worldXform, ac=True):
                    if cmds.objectType(node) == 'fourByFourMatrix':
                        matrixNode = node
                        break
        return matrixNode

    def getRootConMatrixNode(self, wmNode):
        if cmds.attributeQuery('rootConMatrix', node=wmNode, exists=True):
            inputs = cmds.listConnections('%s.rootConMatrix'%wmNode, s=True, d=False, type='fourByFourMatrix')
            if inputs:
                return inputs[0]
        else:
            cmds.addAttr(wmNode, ln='rootConMatrix', at='message')

        return None




    def loadPlugins(self):
        plugins = ['matrixNodes.so', 'quatNodes.so']
        for p in plugins:
            if not cmds.pluginInfo(p, q=True, l=True):
                cmds.loadPlugin(p)


    def createCtr(self, type, name, color=(1, 0, 0)):
        jsonpath = __file__.split('/')
        jsonpath[-1] = 'ctrs.json'
        jsonpath = '/'.join(jsonpath)
        with open(jsonpath, 'r') as f:
            ctrs = json.load(f)

        if not type in ctrs.keys():
            cmds.error('creaetCtr --> Given type does not exist(%s)'%type)

        ctr = cmds.curve(
            name=name,
            degree=ctrs[type]['degree'],
            knot=ctrs[type]['knot'],
            point=ctrs[type]['point']
        )

        cmds.setAttr('%s.overrideEnabled'%ctr, True)
        #cmds.setAttr('%s.setObjectColorType'%ctr, 'RGBColor', type='string')
        cmds.setAttr('%s.overrideRGBColors'%ctr, 1)
        cmds.setAttr('%s.overrideColorRGB'%ctr, *color, type='float3')

        return ctr

    def setRootConInitPosition(self):
        startTime = cmds.playbackOptions(q=True, ast=True)

        if len(cmds.ls('%s_rootCon_multMatrixInit'%self.name)) < 1:
            rootConMultMatrixInit = cmds.shadingNode('multMatrix', asUtility=True, n='%s_rootCon_multMatrixInit'%self.name)
        cmds.connectAttr('%s.matrixSum'%rootConMultMatrixInit, '%s_rootCon_decomposeMatrix.inputMatrix'%self.name, force=True)
        cmds.connectAttr('%s_rootCon_matrix.output'%self.name, '%s.matrixIn[0]'%rootConMultMatrixInit, force=True)
        if len(cmds.ls('%s_rootCon_matrixInit'%self.name)) < 1:
            rootConMatrixInit = cmds.shadingNode('fourByFourMatrix', asUtility=True, n='%s_rootCon_matrixInit'%self.name)
        if len(cmds.ls('%s_rootCon_inverseMatrixInit'%self.name)) < 1:
            rootConInverseMatrixInit = cmds.shadingNode('inverseMatrix', asUtility=True, n='%s_rootCon_inverseMatrixInit'%self.name)
        cmds.connectAttr('%s.output'%rootConMatrixInit, '%s.inputMatrix'%rootConInverseMatrixInit, force=True)
        cmds.connectAttr('%s.outputMatrix'%rootConInverseMatrixInit, '%s.matrixIn[1]'%rootConMultMatrixInit, force=True)

        cmds.setAttr('%s.in00'%rootConMatrixInit, cmds.getAttr('%s_rootCon_matrix.in00'%self.name, t=startTime))
        cmds.setAttr('%s.in01'%rootConMatrixInit, cmds.getAttr('%s_rootCon_matrix.in01'%self.name, t=startTime))
        cmds.setAttr('%s.in02'%rootConMatrixInit, cmds.getAttr('%s_rootCon_matrix.in02'%self.name, t=startTime))
        cmds.setAttr('%s.in03'%rootConMatrixInit, cmds.getAttr('%s_rootCon_matrix.in03'%self.name, t=startTime))
        cmds.setAttr('%s.in10'%rootConMatrixInit, cmds.getAttr('%s_rootCon_matrix.in10'%self.name, t=startTime))
        cmds.setAttr('%s.in11'%rootConMatrixInit, cmds.getAttr('%s_rootCon_matrix.in11'%self.name, t=startTime))
        cmds.setAttr('%s.in12'%rootConMatrixInit, cmds.getAttr('%s_rootCon_matrix.in12'%self.name, t=startTime))
        cmds.setAttr('%s.in13'%rootConMatrixInit, cmds.getAttr('%s_rootCon_matrix.in13'%self.name, t=startTime))
        cmds.setAttr('%s.in20'%rootConMatrixInit, cmds.getAttr('%s_rootCon_matrix.in20'%self.name, t=startTime))
        cmds.setAttr('%s.in21'%rootConMatrixInit, cmds.getAttr('%s_rootCon_matrix.in21'%self.name, t=startTime))
        cmds.setAttr('%s.in22'%rootConMatrixInit, cmds.getAttr('%s_rootCon_matrix.in22'%self.name, t=startTime))
        cmds.setAttr('%s.in23'%rootConMatrixInit, cmds.getAttr('%s_rootCon_matrix.in23'%self.name, t=startTime))
        cmds.setAttr('%s.in30'%rootConMatrixInit, cmds.getAttr('%s_rootCon_matrix.in30'%self.name, t=startTime))
        cmds.setAttr('%s.in31'%rootConMatrixInit, cmds.getAttr('%s_rootCon_matrix.in31'%self.name, t=startTime))
        cmds.setAttr('%s.in32'%rootConMatrixInit, cmds.getAttr('%s_rootCon_matrix.in32'%self.name, t=startTime))
        cmds.setAttr('%s.in33'%rootConMatrixInit, cmds.getAttr('%s_rootCon_matrix.in33'%self.name, t=startTime))

        if len(cmds.ls('%s_rootCon_decomposeMatrixInit'%self.name)) < 1:
            rootConDecomposeMatrixInit = cmds.shadingNode('decomposeMatrix', asUtility=True, n='%s_rootCon_decomposeMatrixInit'%self.name)
        cmds.connectAttr('%s_rootCon_localMatrix_multMatrix.matrixSum'%self.name, '%s.inputMatrix'%rootConDecomposeMatrixInit, force=True)

        cmds.select('%s_rootConXform_NUL'%self.name, r=True)
        cmds.group(n='%s_rootConInitPos_NUL'%self.name)
        cmds.xform('%s_rootConInitPos_NUL'%self.name, os=True, piv=(0,0,0))
        cmds.setAttr('%s_rootConInitPos_NUL.tx'%self.name, cmds.getAttr('%s.otx'%rootConDecomposeMatrixInit, t=startTime))
        cmds.setAttr('%s_rootConInitPos_NUL.ty'%self.name, cmds.getAttr('%s.oty'%rootConDecomposeMatrixInit, t=startTime))
        cmds.setAttr('%s_rootConInitPos_NUL.tz'%self.name, cmds.getAttr('%s.otz'%rootConDecomposeMatrixInit, t=startTime))
        cmds.setAttr('%s_rootConInitPos_NUL.rx'%self.name, cmds.getAttr('%s.orx'%rootConDecomposeMatrixInit, t=startTime))
        cmds.setAttr('%s_rootConInitPos_NUL.ry'%self.name, cmds.getAttr('%s.ory'%rootConDecomposeMatrixInit, t=startTime))
        cmds.setAttr('%s_rootConInitPos_NUL.rz'%self.name, cmds.getAttr('%s.orz'%rootConDecomposeMatrixInit, t=startTime))
        cmds.setAttr('%s_rootConInitPos_NUL.sx'%self.name, cmds.getAttr('%s.osx'%rootConDecomposeMatrixInit, t=startTime))
        cmds.setAttr('%s_rootConInitPos_NUL.sy'%self.name, cmds.getAttr('%s.osy'%rootConDecomposeMatrixInit, t=startTime))
        cmds.setAttr('%s_rootConInitPos_NUL.sz'%self.name, cmds.getAttr('%s.osz'%rootConDecomposeMatrixInit, t=startTime))

        cmds.delete('%s'%rootConDecomposeMatrixInit)
