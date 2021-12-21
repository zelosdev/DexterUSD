#coding:utf-8

##########################################
__author__  = '''
    daeseok.chae in Dexter CGSupervisor
    '''
__date__ = '2020.07.09'
__comment__ = 'export asset for usd-2.0'
__windowName__ = "dxsUsdAssetExport"
##########################################

import maya.OpenMayaUI as mui
import shiboken2 as shiboken
import maya.cmds as cmds
import maya.OpenMaya as om
import os

from .AssetExportUI import Ui_Form
from .AssetItem import AssetNameItem, AssetAgentItem, AssetAgentMotionItem, AssetBranchItem, AssetClipItem
import Define

from PySide2 import QtWidgets
from PySide2 import QtCore
from PySide2 import QtGui

import DXRulebook.Interface as rb

import DXUSD_MAYA.Message as dxmsg
import DXUSD_MAYA.Rig as Rig

def GetModelList():
    result = list()
    for s in cmds.ls(['*_model_*GRP', '*_lidar_*GRP'], sl=True, r=True):
        result.append(s)

    # sorting model file.
    high = []
    mid = []
    low = []
    for node in result:
        if "model_low" in node:
            low.append(node)
        elif "model_mid" in node:
            mid.append(node)
        else:
            high.append(node)

    result = high + mid + low
    return result


def GetZennList():
    zennRoot = list()
    if not cmds.pluginInfo('ZENNForMaya', q=True, l=True):
        return zennRoot
    if not cmds.objExists('ZN_ExportSet'):
        return zennRoot
    for n in cmds.ls(sl=True, dag=True, type='dxBlock', l=True):
        rootNode = n.split('|')[1]
        if '_ZN_' in rootNode and not rootNode in zennRoot:
            zennRoot.append(rootNode)
    return zennRoot


def GetCrowdAssetList():
    result = list()
    for node in cmds.ls("glm_*", sl = True):
        if not cmds.pluginInfo('glmCrowd', q=True, l=True):
            return result
        if cmds.objExists('geometry_GRP'):
            result.append(node)

    for node in cmds.ls("OriginalAgent_*", sl = True):
        if not cmds.pluginInfo('MiarmyProForMaya%s' % cmds.about(v=True), q=True, l=True):
            return result
        geometryNode = node.replace("OriginalAgent", "Geometry")
        if cmds.objExists(geometryNode):
            result.append(node)

    return result
#
#
# def GetLightAssetList():
#     result = list()
#     for node in cmds.ls("*_lgt*", sl = True, type = "dxBlock"):
#         if cmds.getAttr("%s.type" % node) == 5 and cmds.getAttr("%s.action" % node) == 1:
#             result.append(node)
#
#     return result


def getMayaWindow():
    '''
    get Maya Window Process
    :return: Maya window Process
    '''
    try:
        ptr = mui.MQtUtil.mainWindow()
        return shiboken.wrapInstance(long(ptr), QtWidgets.QMainWindow)
    except:
        return None


class AssetExportTool(QtWidgets.QWidget):
    def __init__(self, parent = getMayaWindow()):

        # Load dependency plugin
        plugins = ['backstageMenu', 'pxrUsd', 'DXUSD_Maya']
        for p in plugins:
            if not cmds.pluginInfo(p, q=True, l=True):
                cmds.loadPlugin(p)

        QtWidgets.QWidget.__init__(self, parent)

        self.setWindowFlags(QtCore.Qt.Window)

        self.ui = Ui_Form()
        self.ui.setupUi(self)

        self.move(parent.frameGeometry().center() - self.frameGeometry().center())

        self.modelVariantColor = QtGui.QBrush(QtGui.QColor(9, 212, 255))
        self.assetNameColor = QtGui.QBrush(QtGui.QColor(9, 255, 212))

        self.isExport = False

        self.itemFont = QtGui.QFont()
        self.itemFont.setPointSize(13)
        self.itemFont.setBold(True)

        # project auto setup
        scenePath = cmds.file(q=True, sn=True)
        if scenePath == "":
            scenePath = cmds.workspace(q = True, rd=True)

        # TODO: working auto show name
        coder = rb.Coder()
        ret = coder.D.SHOW.Decode(scenePath)
        dxmsg.debug('scenePath-Decode', scenePath, ret)
        self.showName = ret.show
        self.ui.showEdit.setText(self.showName)

        # make completer of show
        customNeedCompleter = []
        customNeedCompleter.append("/assetlib/_3d")

        showCompleter = QtWidgets.QCompleter(customNeedCompleter)
        showCompleter.popup().setFont(self.itemFont)
        self.ui.showEdit.setCompleter(showCompleter)

        self.outlineSelectionChanged()

        # Signal connect
        self.ui.showEdit.textChanged.connect(lambda : self.makeTreeWidgetFromNodes())
        self.ui.shotEdit.textChanged.connect(lambda : self.makeTreeWidgetFromNodes())
        self.ui.clipCheckBox.stateChanged.connect(lambda : self.outlineSelectionChanged())
        self.ui.glmMotionCheckBox.stateChanged.connect(lambda : self.outlineSelectionChanged())
        self.ui.overWriteCheckBox.stateChanged.connect(lambda : self.outlineVersionChanged())
        self.ui.assetExportBtn.clicked.connect(self.exportAsset)

        # Maya selection event callback
        self.callback = om.MEventMessage.addEventCallback("SelectionChanged", self.outlineSelectionChanged)

    def closeEvent(self, event):
        # clean up callback
        try:
            om.MMessage.removeCallback(self.callback)
        except:
            pass

    def outlineSelectionChanged(self, *args, **kwargs):
        if self.isExport:
            return

        # model
        modelList = GetModelList()

        # rig
        rigList = cmds.ls(sl=True, type='dxRig')

        # zenn
        groomList = GetZennList()

        # crowd
        crowdList = GetCrowdAssetList()

        # light
        # lgtList = GetLightAssetList()

        # camera
        camList = cmds.ls(sl=True, type='dxCamera')

        self.selectNode = modelList + rigList + groomList + crowdList + camList # + lgtList

        #  ui changed for export asset type
        # ui visibility
        self.ui.clipCheckBox.setVisible(False)
        self.ui.glmMotionCheckBox.setVisible(False)
        self.ui.stepEdit.setVisible(False)
        self.ui.stepLabel.setVisible(False)
        self.ui.loopRangeLabel.setVisible(False)
        self.ui.loopStartEdit.setVisible(False)
        self.ui.loopEndEdit.setVisible(False)
        self.ui.loopScaleLabel.setVisible(False)
        self.ui.loopScaleEdit.setVisible(False)

        if self.selectNode:
            if modelList:
                self.ui.clipCheckBox.setVisible(True)
                if self.ui.clipCheckBox.isChecked():
                    self.clipVisibilityByUI()
                else:
                    self.clipVisibilityByUI()
            if rigList:
                self.ui.clipCheckBox.setVisible(True)
                self.ui.glmMotionCheckBox.setVisible(True)
                if self.ui.glmMotionCheckBox.isChecked():
                    self.ui.clipCheckBox.setVisible(False)
                    pass
                elif self.ui.clipCheckBox.isChecked():
                    self.ui.glmMotionCheckBox.setVisible(False)
                    self.clipVisibilityByUI()
            if groomList:
                self.ui.clipCheckBox.setVisible(True)
                # self.clipVisibilityByUI()

            self.makeTreeWidgetFromNodes()
        else:
            self.cleanupTreeWidget()
            return

    def clipVisibilityByUI(self):
        if not self.ui.clipCheckBox.isChecked():
            self.ui.stepEdit.setVisible(False)
            self.ui.stepLabel.setVisible(False)
            # self.ui.loopCheckBox.setVisible(False)
            self.ui.loopScaleLabel.setVisible(False)
            self.ui.loopScaleEdit.setVisible(False)
        else:
            # self.ui.loopCheckBox.setVisible(True)
            self.ui.stepLabel.setVisible(True)
            self.ui.stepEdit.setVisible(True)
            # it is loop animation
            self.ui.loopScaleLabel.setVisible(True)
            self.ui.loopScaleEdit.setVisible(True)
            self.ui.loopRangeLabel.setVisible(True)
            self.ui.loopStartEdit.setVisible(True)
            self.ui.loopEndEdit.setVisible(True)

    def cleanupTreeWidget(self):
        while self.ui.treeWidget.topLevelItemCount() > 0:
            self.ui.treeWidget.takeTopLevelItem(0)
            treeitem = self.ui.treeWidget.topLevelItem(0)
            if treeitem:
                if treeitem.childCount() > 0:
                    treeitem.takeChildren()

    def getAssetName(self, nodeName):
        nodeType = cmds.nodeType(nodeName)
        if nodeType == 'dxRig' and self.ui.clipCheckBox.isChecked():
            coder = rb.Coder('N', 'USD')
            ret = coder.ani.ASSET.Decode(nodeName)
            dxmsg.debug('getAssetName', 'clip', ret.asset, ret.task, ret)
            return cmds.getAttr('%s.assetName' % nodeName), Define.CLIP_TYPE, ret
        if nodeType == 'dxRig' and self.ui.glmMotionCheckBox.isChecked():
            coder = rb.Coder('N', 'USD')
            ret = coder.ani.ASSET.Decode(nodeName)
            dxmsg.debug('getAssetName', 'motion', ret.asset, ret.task, ret)
            return cmds.getAttr('%s.assetName' % nodeName), Define.AGENT_TYPE, ret
        else:
            try:
                coder = rb.Coder('N', 'MAYA', 'TOP')
                ret = coder.Decode(nodeName)
                if ret.has_key('task'):
                    dxmsg.debug('getAssetName', ret.asset, ret.task, ret)
                    if ret.has_key('set'):
                        dxmsg.debug('set type')
                        return ret.asset, Define.SET_TYPE, ret
                    elif ret.task == 'groom' and self.ui.clipCheckBox.isChecked():
                        return ret.asset, Define.CLIP_TYPE, ret
                    return ret.asset, ret.task, ret
            except Exception as e:
                print e.message
            else:
                if 'glm_' in nodeName:
                    return nodeName.replace('glm_', '').split("_")[0], Define.AGENT_TYPE, ret
                elif "OriginalAgent_" in nodeName:
                    return nodeName.replace("OriginalAgent_", "").split("_")[0], Define.AGENT_TYPE, ret
                else:
                    dxmsg.Warning("Not Found Task")

    def makeTreeWidgetFromNodes(self):
        self.cleanupTreeWidget()

        treeItemDic = {}

        for node in self.selectNode:
            try:
                assetName, assetType, rbRet = self.getAssetName(node)
            except Exception as e:
                dxmsg.debug(e.message)
                continue

            # first, has same asset
            if not treeItemDic.has_key(assetName):
                treeItemDic[assetName] = AssetNameItem(self.ui.treeWidget, self.ui.showEdit.text(), assetName, self.ui.overWriteCheckBox.isChecked(), shotName=self.ui.shotEdit.text())
                treeItemDic[assetName].setFont(0, self.itemFont)
                treeItemDic[assetName].setForeground(0, self.assetNameColor)

            assetTypeItem = treeItemDic[assetName].getAssetType(assetType)
            if not assetTypeItem:
                assetTypeItem = treeItemDic[assetName].addAssetType(assetType,
                                                                    rbRet.IsBranch(),
                                                                    rbRet.get('branch'))
            print 'assetTypeItem.nodes:', assetTypeItem.nodes
            assetTypeItem.nodes[assetType].append(node)

            if assetType == Define.MODEL_TYPE or assetType == Define.LIDAR_TYPE:
                # normal
                if rbRet.IsBranch():
                    branchName = rbRet.branch
                    if not assetTypeItem.branchNodeDict.has_key(branchName):
                        assetTypeItem.branchNodeDict[branchName] = []
                    assetTypeItem.branchNodeDict[branchName].append(node)

                    if not assetTypeItem.nodeDict.has_key(branchName):
                        assetTypeItem.nodeDict[branchName] = {}
                        assetTypeItem.nodeDict[branchName]['item'] = AssetBranchItem(assetTypeItem,
                                                                                     self.ui.showEdit.text(),
                                                                                     assetName, branchName,
                                                                                     node,
                                                                                     self.ui.overWriteCheckBox.isChecked())
                        assetTypeItem.nodeDict[branchName]['item'].setFont(0, self.itemFont)
                        assetTypeItem.nodeDict[branchName]['item'].setForeground(0, self.modelVariantColor)
                    item = assetTypeItem.nodeDict[branchName]['item']
                    QtWidgets.QTreeWidgetItem(item, [node]).setFont(0, self.itemFont)
                else:
                    QtWidgets.QTreeWidgetItem(assetTypeItem, [node]).setFont(0, self.itemFont)
            elif assetType == Define.RIG_TYPE:
                # normal
                if rbRet.IsBranch():
                    branchName = rbRet.branch
                    if not assetTypeItem.branchNodeDict.has_key(branchName):
                        assetTypeItem.branchNodeDict[branchName] = []
                    assetTypeItem.branchNodeDict[branchName].append(node)

                    if not assetTypeItem.nodeDict.has_key(branchName):
                        assetTypeItem.nodeDict[branchName] = {}
                        assetTypeItem.nodeDict[branchName]['item'] = AssetBranchItem(assetTypeItem,
                                                                                     self.ui.showEdit.text(),
                                                                                     assetName, branchName,
                                                                                     node,
                                                                                     self.ui.overWriteCheckBox.isChecked())
                        assetTypeItem.nodeDict[branchName]['item'].setFont(0, self.itemFont)
                        assetTypeItem.nodeDict[branchName]['item'].setForeground(0, self.modelVariantColor)
                    item = assetTypeItem.nodeDict[branchName]['item']
                    QtWidgets.QTreeWidgetItem(item, [node]).setFont(0, self.itemFont)
                else:
                    variantData = Rig.GetRigVariant(node)
                    if variantData:
                        QtWidgets.QTreeWidgetItem(assetTypeItem, [node]).setFont(0, self.itemFont)

                        for ctrln, variants in variantData.items():
                            for n, i in variants:
                                branchName = n
                                if branchName == assetName:
                                    continue

                                if not assetTypeItem.branchNodeDict.has_key(branchName):
                                    assetTypeItem.branchNodeDict[branchName] = []
                                assetTypeItem.branchNodeDict[branchName].append(node)

                                if not assetTypeItem.nodeDict.has_key(branchName):
                                    assetTypeItem.nodeDict[branchName] = {}
                                    assetTypeItem.nodeDict[branchName]['item'] = AssetBranchItem(assetTypeItem,
                                                                                                 self.ui.showEdit.text(),
                                                                                                 assetName, branchName,
                                                                                                 node,
                                                                                                 self.ui.overWriteCheckBox.isChecked())
                                    assetTypeItem.nodeDict[branchName]['item'].setFont(0, self.itemFont)
                                    assetTypeItem.nodeDict[branchName]['item'].setForeground(0, self.modelVariantColor)
                                item = assetTypeItem.nodeDict[branchName]['item']
                                QtWidgets.QTreeWidgetItem(item, [node]).setFont(0, self.itemFont)
                    else:
                        QtWidgets.QTreeWidgetItem(assetTypeItem, [node]).setFont(0, self.itemFont)
            elif assetType == Define.GROOM_TYPE:
                # normal
                if rbRet.IsBranch():
                    branchName = rbRet.branch
                    if not assetTypeItem.branchNodeDict.has_key(branchName):
                        assetTypeItem.branchNodeDict[branchName] = []
                    assetTypeItem.branchNodeDict[branchName].append(node)

                    if not assetTypeItem.nodeDict.has_key(branchName):
                        assetTypeItem.nodeDict[branchName] = {}
                        assetTypeItem.nodeDict[branchName]['item'] = AssetBranchItem(assetTypeItem,
                                                                                     self.ui.showEdit.text(),
                                                                                     assetName, branchName,
                                                                                     node,
                                                                                     self.ui.overWriteCheckBox.isChecked())
                        assetTypeItem.nodeDict[branchName]['item'].setFont(0, self.itemFont)
                        assetTypeItem.nodeDict[branchName]['item'].setForeground(0, self.modelVariantColor)
                    item = assetTypeItem.nodeDict[branchName]['item']
                    # QtWidgets.QTreeWidgetItem(item, [node]).setFont(0, self.itemFont)
                    for c in cmds.sets('ZN_ExportSet', q=True):
                        QtWidgets.QTreeWidgetItem(item, [c]).setFont(0, self.itemFont)
                else:
                    # QtWidgets.QTreeWidgetItem(assetTypeItem, [node]).setFont(0, self.itemFont)
                    for c in cmds.sets('ZN_ExportSet', q=True):
                        QtWidgets.QTreeWidgetItem(assetTypeItem, [c]).setFont(0, self.itemFont)

            elif assetType == Define.AGENT_TYPE:
                if not self.ui.glmMotionCheckBox.isChecked():
                    agentType = node.replace("OriginalAgent_", "").replace("glm_", "")
                    AssetAgentItem(assetTypeItem, self.ui.showEdit.text(), assetName, agentType, node, self.ui.overWriteCheckBox.isChecked())
                else:
                    agentType = os.path.basename(cmds.file(q=True, sn=True)).split('.')[0]
                    AssetAgentMotionItem(assetTypeItem, self.ui.showEdit.text(), assetName, agentType, rbRet, self.ui.overWriteCheckBox.isChecked())

            elif assetType == Define.CLIP_TYPE:
                # has purpose, not lod
                if rbRet.task == 'groom':
                    nslyr = cmds.getAttr('%s.nsLayer' % node)
                    AssetClipItem(assetTypeItem, self.ui.showEdit.text(), assetName, nslyr,
                                  node, self.ui.overWriteCheckBox.isChecked(), rbRet.task).setFont(0, self.itemFont)
                else:
                    AssetClipItem(assetTypeItem, self.ui.showEdit.text(), assetName, rbRet.nslyr,
                                  node, self.ui.overWriteCheckBox.isChecked(), rbRet.task).setFont(0, self.itemFont)

            elif assetType == Define.CAM_TYPE:
                # cameras = dxsUsd.GetCameraNodes(node)
                cameras = []
                assetTypeItem.nodes[assetType] = cameras
                for cam in cameras:
                    name = cam.split('|')[-1].split(':')[-1]
                    QtWidgets.QTreeWidgetItem(assetTypeItem, [name]).setFont(0, self.itemFont)

            elif assetType == Define.LGT_TYPE:
                name = node.split("_lgt_")[1]
                QtWidgets.QTreeWidgetItem(assetTypeItem, [name]).setFont(0, self.itemFont)

            else:
                QtWidgets.QTreeWidgetItem(assetTypeItem, [node]).setFont(0, self.itemFont)

        self.ui.treeWidget.expandAll()


    def outlineVersionChanged(self):
        overWrite = self.ui.overWriteCheckBox.isChecked()
        for topLevelIndex in range(self.ui.treeWidget.topLevelItemCount()):
            assetItem = self.ui.treeWidget.topLevelItem(topLevelIndex)
            assetName = assetItem.text(0)
            for childIndex in range(assetItem.childCount()):
                typeItem = assetItem.child(childIndex)
                if not typeItem.versionEdit:
                    typeItem.child(childIndex).overWrite = overWrite
                    typeItem.child(childIndex).updateLastVersion()
                else:
                    typeItem.overWrite = overWrite
                    typeItem.updateLastVersion()


    def mConfirmDialog(self, assetName, version, isOverwrite):
        if isOverwrite:
            msg = cmds.confirmDialog(
                title='Overwrite?', message='%s of %s overwrite?' % (version, assetName),
                icon='warning', button=['OK', 'CANCEL']
            )
            assert msg != 'CANCEL', '# msg : stopped process!'

    def exportAsset(self):
        # exception
        if not self.selectNode:
            cmds.confirmDialog(title="Error",
                               message="not found publish nodes\ncheck please",
                               icon="warning",
                               button=["OK"])
            return

        self.isExport = True
        self.showName  = str(self.ui.showEdit.text())
        self.shotName = str(self.ui.shotEdit.text())
        cmds.waitCursor(state=True)
        # try:
        for topLevelIndex in range(self.ui.treeWidget.topLevelItemCount()):
            assetItem = self.ui.treeWidget.topLevelItem(topLevelIndex)
            for childIndex in range(assetItem.childCount()):
                typeItem = assetItem.child(childIndex)
                if typeItem.text(0) == Define.MODEL_TYPE:
                    self.exportModelExec(assetItem, typeItem)
                elif typeItem.text(0) == Define.LIDAR_TYPE:
                    self.exportLidarExec(assetItem, typeItem)
                elif typeItem.text(0) == Define.RIG_TYPE:
                    self.exportRigExec(assetItem, typeItem)
                elif typeItem.text(0) == Define.GROOM_TYPE:
                    self.exportGroomAssetExec(assetItem, typeItem)
                elif typeItem.text(0) == Define.AGENT_TYPE:
                    self.exportAgentAssetExec(assetItem, typeItem)
                elif typeItem.text(0) == Define.CAM_TYPE:
                    self.exportCameraAssetExec(assetItem, typeItem)
                elif typeItem.text(0) == Define.CLIP_TYPE:
                    self.exportClipExec(assetItem, typeItem)
                elif typeItem.text(0) == Define.LGT_TYPE:
                    self.exportLgtExec(assetItem, typeItem)
                else:
                    cmds.confirmDialog(title="error!",
                                       message="type not found",
                                       icon="warning",
                                       button=["OK"])
                    continue
        # except Exception as e:
        #     cmds.confirmDialog(title="Fail!!!",
        #                        message="Export Fail\n%s" % e.message,
        #                        icon="warning",
        #                        button=["OK"])
        #     return
        cmds.waitCursor(state=False)
        cmds.select(cl=True)
        cmds.confirmDialog(title="Success!",
                           message="Export Success",
                           icon="information",
                           button=["OK"])

        self.isExport = False
        self.outlineSelectionChanged()

    def exportModelExec(self, assetItem, typeItem):
        import DXUSD_MAYA.Model as Model

        if typeItem.isBranch:
            for branchIndex in range(typeItem.childCount()):
                branchItem = typeItem.child(branchIndex)
                branchName = branchItem.branchName
                nodes = typeItem.branchNodeDict[branchName]
                version = branchItem.versionEdit.text()
                # export
                Model.assetExport(nodes=nodes, show=self.showName, shot=self.shotName, version=version)
        else:
            nodes = typeItem.nodes[Define.MODEL_TYPE]
            version = typeItem.versionEdit.text()
            # export
            Model.assetExport(nodes=nodes, show=self.showName, shot=self.shotName, version=version)
        return

    def exportLidarExec(self, assetItem, typeItem):
        import DXUSD_MAYA.Model as Model

        nodes = typeItem.nodes[Define.LIDAR_TYPE]
        version = typeItem.versionEdit.text()
        # export
        print('nodes:', nodes)
        print('showName:', self.showName)
        print('version:', version)

        Model.lidarExport(nodes=nodes, show=self.showName, version=version)
        return

    def exportRigExec(self, assetItem, typeItem, shotName = ""):
        showName = self.showName
        nodes = typeItem.nodes[Define.RIG_TYPE]
        # export
        Rig.assetExport(node=nodes[0], show=self.showName, shot=self.shotName)
        return

    def exportLgtExec(self, assetItem, typeItem):
        # assetName = assetItem.text(0)
        # version = typeItem.versionEdit.text()
        # # if shotName:
        # #     seq = shotName.split("_")[0]
        # #     assetDir = "{SHOWDIR}/shot/{SEQ}/{SHOT}/lighting/{ASSETNAME}".format(SHOWDIR=self.showName,
        # #                                                                     SEQ=seq,
        # #                                                                     SHOT=shotName,
        # #                                                                     ASSETNAME=assetName)
        # self.mConfirmDialog(assetName, version, typeItem.overwriteVersion)
        # outDirs = []
        # for node in typeItem.nodes[Define.LGT_TYPE]:
        #     # if shotName:
        #     #     mdExp = dxsUsd.RigAssetExport(node=node, assetDir=assetDir)
        #     #     mdExp.doIt()
        #     # else:
        #     mdExp = dxsUsd.LightInstanceExport(node=node, showName=self.showName, asset=assetName, version=version)
        #     mdExp.doIt()
        #     if not mdExp.outDir in outDirs:
        #         outDirs.append(mdExp.outDir)
        #         version = os.path.basename(mdExp.outDir)
        #
        # dxsUsd.DBQuery.assetInsertDB(self.showName, assetName, version, "lighting", outDirs)
        return

    def exportClipExec(self, assetItem, typeItem, shotName = ""):
        import DXUSD_MAYA.Clip as Clip

        # current scene
        sceneFileName = cmds.file(q=True, sn=True)
        # Check Clip Task
        nsLayerItem = typeItem.child(0)

        if nsLayerItem.clipTask == "groom":
            node = nsLayerItem.node
            # export
            Clip.groomExport(node=node)

        else:
            # isLoop = self.ui.loopCheckBox.isChecked()
            # default
            step = 1.0
            loopScales = [0.8, 1.0, 1.5]
            loopRange  = (1001, 5000)

            stepText = str(self.ui.stepEdit.text())
            if stepText:
                step = float(stepText)
            loopScalesText = str(self.ui.loopScaleEdit.text())
            if loopScalesText:
                loopScales = list()
                for i in loopScalesText.split(','):
                    loopScales.append(float(i))
            loopStartText = str(self.ui.loopStartEdit.text())
            loopEndText = str(self.ui.loopEndEdit.text())
            if loopStartText and loopEndText:
                loopRange = (int(loopStartText), int(loopEndText))

            for index in range(typeItem.childCount()):
                childItem = typeItem.child(index)
                # export
                Clip.rigExport(node=childItem.node, show=self.showName, shot=self.shotName,
                               version=childItem.versionEdit.text(),
                               timeScales=loopScales, loopRange=loopRange, step=step)

        return

    def exportGroomAssetExec(self, assetItem, typeItem, shotName = ""):
        import DXUSD_MAYA.Groom as Groom

        node = typeItem.nodes[Define.GROOM_TYPE][0]
        # export
        Groom.assetExport(node=node, show=self.showName, shot=self.shotName)
        return

    def exportCameraAssetExec(self, assetItem, typeItem):
        # assetName = assetItem.text(0)
        # version = typeItem.versionEdit.text()
        # if shotName:
        #     seq = shotName.split("_")[0]
        #     assetDir = "{SHOWDIR}/shot/{SEQ}/{SHOT}/asset/{ASSETNAME}".format(SHOWDIR=self.showName,
        #                                                                     SEQ=seq,
        #                                                                     SHOT=shotName,
        #                                                                     ASSETNAME=assetName)
        # self.mConfirmDialog(assetName, version, typeItem.overwriteVersion)
        # for node in typeItem.nodes[Define.CAM_TYPE]:
        #     if shotName:
        #         dxsUsd.CameraAssetExport(node=node, assetDir=assetDir, version=version).doIt()
        #     else:
        #         dxsUsd.CameraAssetExport(node=node, showName=self.showName, asset=assetName, version=version).doIt()
        return

    def exportAgentAssetExec(self, assetItem, typeItem):
        import DXUSD_MAYA.Crowd as Crowd

        version  = typeItem.child(0).versionEdit.text()
        node     = typeItem.nodes[Define.AGENT_TYPE][0]

        if not self.ui.glmMotionCheckBox.isChecked():
            Crowd.assetExport(node=node, show=self.showName, shot=self.shotName, version=version)
        else:
            motion = Crowd.GolaemMotionExport(typeItem.child(0).kwargs)
            motion.doIt()
        return


def main():
    if cmds.window(__windowName__, exists = True):
        cmds.deleteUI(__windowName__)

    window = AssetExportTool()
    window.setObjectName(__windowName__)
    window.show()
