#coding:utf-8

##########################################
__author__  = '''
    daeseok.chae in Dexter CGsupervisor
'''
__date__ = '2020.07.09'
##########################################

from PySide2 import QtWidgets
from PySide2 import QtGui
from PySide2 import QtCore
import maya.cmds as cmds

import os

import Define
import DXUSD.Utils as utls
import DXUSD_MAYA.Message as msg
import DXRulebook.Interface as rb


def labelColorSet(label, qcolor):
    palette = label.palette()
    palette.setColor(label.foregroundRole(), qcolor)
    label.setPalette(palette)

class AssetNameItem(QtWidgets.QTreeWidgetItem):
    def __init__(self, parent, showName, assetName, overWrite, shotName=''):
        QtWidgets.QTreeWidgetItem.__init__(self, parent)

        self.showName   = showName
        self.shotName = shotName
        self.assetName = assetName.split(' ')[-1]
        self.setText(0, assetName)
        self.overWrite = overWrite

        self.availableColor = QtGui.QColor(QtCore.Qt.green)
        self.unavailableColor = QtGui.QColor(QtCore.Qt.red)

        self.hasTypeDict = {}

    def getAssetType(self, assetType):
        if self.hasTypeDict.has_key(assetType):
            return self.hasTypeDict[assetType]
        else:
            return None

    def addAssetType(self, assetType, isBranch=False, branchName=""):
        self.hasTypeDict[assetType] = AssetTypeItem(self, self.showName, self.assetName, assetType, isBranch, branchName, self.overWrite, shotName=self.shotName)

        return self.hasTypeDict[assetType]

class AssetTypeItem(QtWidgets.QTreeWidgetItem):
    def __init__(self, parent, showName, assetName, task, isBranch=False, branchName="", overWrite=False, shotName=''):
        '''
        :param parent:
        :param showName: showName is /show/???
        :param assetName: assetName
        :param task: model, rig, clip, etc...
        :param isBranch:
        :param branchName:
        :param overWrite:
        '''
        QtWidgets.QTreeWidgetItem.__init__(self, parent)
        itemFont = QtGui.QFont()
        itemFont.setPointSize(13)
        itemFont.setBold(True)

        self.overWrite = overWrite
        self.assetType = task
        self.setText(0, task)

        self.availableColor = QtGui.QColor(QtCore.Qt.green)
        self.unavailableColor = QtGui.QColor(QtCore.Qt.red)

        self.typeColor = QtGui.QBrush(QtGui.QColor(228, 133, 36))
        self.setFont(0, itemFont)
        self.setForeground(0, self.typeColor)

        # path setting
        coder = rb.Coder()
        self.kwargs = {'asset':assetName, 'task':task}

        if task == Define.SET_TYPE:
            self.kwargs['task'] = Define.MODEL_TYPE

        if showName == '/assetlib/_3d':
            self.kwargs['customdir'] = showName
        else:
            self.kwargs['show'] = showName
            self.kwargs['pub'] = '_3d'

        print shotName
        if shotName:
            if '_' in shotName:
                splitShotName = shotName.split('_')
                self.kwargs['seq'] = splitShotName[0]
                self.kwargs['shot'] = splitShotName[1]
            else:
                self.kwargs['seq'] = shotName

        self.isBranch = isBranch
        if isBranch:
            self.kwargs['branch'] = branchName

        self.assetDir = coder.D.Encode(**self.kwargs)
        msg.debug('TASK[{TASK}] : {ASSETDIR}'.format(TASK=task, ASSETDIR=self.assetDir))
        # TASK MODEL : /show/pipe/_3d/asset/$ASSETNAME/model

        # Node Setup
        self.nodeDict = {}
        self.nodes = {Define.MODEL_TYPE:[],
                      Define.LIDAR_TYPE:[],
                      Define.CLIP_TYPE:[],
                      Define.SET_TYPE:[],
                      Define.RIG_TYPE:[],
                      Define.CAM_TYPE:[],
                      Define.GROOM_TYPE: [],
                      Define.ANI_TYPE:[],
                      Define.AGENT_TYPE:[],
                      Define.LGT_TYPE: []}

        self.versionEdit = None
        if task != Define.CLIP_TYPE and task != Define.AGENT_TYPE and not isBranch:
            self.versionEdit = QtWidgets.QLineEdit()
            self.versionEdit.setFont(itemFont)
            if type(parent) == QtWidgets.QTreeWidget:
                parent.setItemWidget(self, 1, self.versionEdit)
            else:
                parent.treeWidget().setItemWidget(self, 1, self.versionEdit)

            self.versionEdit.textChanged.connect(lambda: self.overwriteVersionCheck())
            # Version Setup
            self.updateLastVersion()

        self.branchNodeDict = {}
        self.isVariant = False
        self.isLod = False
        self.isPurpose = False

    def updateLastVersion(self):
        if isinstance(self.versionEdit, QtWidgets.QLineEdit):
            if self.kwargs['task'] == Define.RIG_TYPE or self.kwargs['task'] == Define.GROOM_TYPE:
                sceneName = cmds.file(q=True, sn=True)
                if sceneName:
                    sceneName = os.path.splitext(os.path.basename(sceneName))[0]
                else:
                    sceneName = 'xxx'
                self.versionEdit.setText(sceneName)
            else:
                if self.overWrite:
                    self.versionEdit.setText(utls.GetLastVersion(self.assetDir))
                else:
                    self.versionEdit.setText(utls.GetNextVersion(self.assetDir))

    def overwriteVersionCheck(self):
        if self.kwargs['task'] == Define.RIG_TYPE or self.kwargs['task'] == Define.GROOM_TYPE:
            self.kwargs['nslyr'] = self.versionEdit.text()
        else:
            self.kwargs['ver'] = self.versionEdit.text()

        msg.debug('AssetTypeItem', 'overwriteVersionCheck', self.kwargs)
        versionPath = rb.Coder().D.Encode(**self.kwargs)

        if os.path.exists(versionPath):
            labelColorSet(self.versionEdit, self.unavailableColor)
            self.overwriteVersion = True
        else:
            labelColorSet(self.versionEdit, self.availableColor)
            self.overwriteVersion = False

    def addVariant(self, variantName):
        item = QtWidgets.QTreeWidgetItem(self, ["modelVariant => %s" % variantName])

        self.nodeDict[variantName] = {"item": item, "high": [], "mid": [], "low": []}
        self.isVariant = True

class AssetClipItem(QtWidgets.QTreeWidgetItem):
    def __init__(self, parent, showName, assetName, nsLayer, node, overWrite, clipTask):
        QtWidgets.QTreeWidgetItem.__init__(self, parent)

        self.versionEdit = QtWidgets.QLineEdit()
        itemFont = QtGui.QFont()
        itemFont.setPointSize(13)
        itemFont.setBold(True)
        self.parent = parent
        self.clipTask = clipTask
        self.versionEdit.setFont(itemFont)
        if type(parent) == QtWidgets.QTreeWidget:
            parent.setItemWidget(self, 1, self.versionEdit)
        else:
            parent.treeWidget().setItemWidget(self, 1, self.versionEdit)
        self.versionEdit.textChanged.connect(lambda : self.overwriteVersionCheck())

        self.showName   = showName
        self.assetName = assetName.split(' ')[-1]
        self.nsLayer   = nsLayer
        self.node = node
        self.overWrite = overWrite

        self.kwargs = self.parent.kwargs
        self.kwargs['nslyr'] = nsLayer
        coder = rb.Coder()
        self.assetDir = coder.D.TASKN.Encode(**self.kwargs)

        self.availableColor = QtGui.QColor(QtCore.Qt.green)
        self.unavailableColor = QtGui.QColor(QtCore.Qt.red)

        self.setFont(0, itemFont)

        self.setText(0, nsLayer)
        self.updateLastVersion()

        self.nodeDict = {}
        self.isVariant = False
        self.isLod = False
        self.isPurpose = False

    def updateLastVersion(self):
        msg.debug(self.assetDir, self.clipTask)
        if self.clipTask == "groom":
            self.versionEdit.setDisabled(True)
            mergeFile = cmds.getAttr('%s.mergeFile' % self.node)
            version = os.path.basename(os.path.dirname(os.path.dirname(mergeFile)))
            self.versionEdit.setText(version)
        else:
            if self.overWrite:
                self.versionEdit.setText(utls.GetLastVersion(self.assetDir))
            else:
                self.versionEdit.setText(utls.GetNextVersion(self.assetDir))

    def overwriteVersionCheck(self):
        if self.clipTask == "groom":
            labelColorSet(self.versionEdit, QtGui.QColor(QtCore.Qt.gray))
        else:
            self.kwargs['nsver'] = str(self.versionEdit.text())

            # try:
            versionPath = rb.Coder().D.TASKNV.Encode(**self.kwargs)

            if os.path.exists(versionPath):
                labelColorSet(self.versionEdit, self.unavailableColor)
                self.overwriteVersion = True
            else:
                labelColorSet(self.versionEdit, self.availableColor)
                self.overwriteVersion = False

class AssetAgentItem(QtWidgets.QTreeWidgetItem):
    def __init__(self, parent, showName, assetName, agentType, node, overWrite):
        QtWidgets.QTreeWidgetItem.__init__(self, parent)

        self.showName = showName
        self.assetName = assetName.split(' ')[-1]
        self.agentType = agentType
        self.node = node
        self.overWrite = overWrite
        self.parent = parent
        # self.assetDir = parent.assetDir
        self.kwargs = self.parent.kwargs
        self.kwargs['nslyr'] = self.node.replace('OriginalAgent_', '').replace('glm_', '')
        coder = rb.Coder()
        self.assetDir = coder.D.Encode(**self.kwargs)

        self.versionEdit = QtWidgets.QLineEdit()
        itemFont = QtGui.QFont()
        itemFont.setPointSize(13)
        itemFont.setBold(True)
        self.versionEdit.setFont(itemFont)
        if type(parent) == QtWidgets.QTreeWidget:
            parent.setItemWidget(self, 1, self.versionEdit)
        else:
            parent.treeWidget().setItemWidget(self, 1, self.versionEdit)
        self.versionEdit.textChanged.connect(lambda : self.overwriteVersionCheck())

        self.availableColor = QtGui.QColor(QtCore.Qt.green)
        self.unavailableColor = QtGui.QColor(QtCore.Qt.red)

        self.setFont(0, itemFont)

        self.setText(0, agentType)

        self.nodeDict = {}
        self.isVariant = False
        self.isLod = False
        self.isPurpose = False

        self.updateLastVersion()

    def updateLastVersion(self):
        if self.overWrite:
            self.versionEdit.setText(utls.GetLastVersion(self.assetDir))
        else:
            self.versionEdit.setText(utls.GetNextVersion(self.assetDir))

    def overwriteVersionCheck(self):
        self.kwargs['ver'] = str(self.versionEdit.text())
        print self.kwargs
        try:
            versionPath = rb.Coder().D.Encode(**self.kwargs)
            print versionPath

            if os.path.exists(versionPath):
                labelColorSet(self.versionEdit, self.unavailableColor)
                self.overwriteVersion = True
            else:
                labelColorSet(self.versionEdit, self.availableColor)
                self.overwriteVersion = False
        except:
            pass


class AssetAgentMotionItem(QtWidgets.QTreeWidgetItem):
    def __init__(self, parent, showName, assetName, motionType, rbRet, overWrite):
        QtWidgets.QTreeWidgetItem.__init__(self, parent)

        self.showName = showName
        self.assetName = assetName.split(' ')[-1]
        self.motionType = motionType
        # self.node = node
        self.overWrite = overWrite
        self.parent = parent
        # self.assetDir = parent.assetDir
        coder = rb.Coder()

        self.kwargs = self.parent.kwargs
        print('self.kwargs:', self.kwargs)
        self.kwargs['nslyr'] = rbRet.nslyr
        self.kwargs['subdir'] = 'motion'
        self.assetDir = coder.D.Encode(**self.kwargs)
        print('self.assetDir:', self.assetDir)
        self.kwargs['nsver'] = utls.GetLastVersion(self.assetDir)
        self.motionDir = coder.D.TASKNVS.Encode(**self.kwargs)

        self.versionEdit = QtWidgets.QLineEdit()
        itemFont = QtGui.QFont()
        itemFont.setPointSize(13)
        itemFont.setBold(True)
        self.versionEdit.setFont(itemFont)
        if type(parent) == QtWidgets.QTreeWidget:
            parent.setItemWidget(self, 1, self.versionEdit)
        else:
            parent.treeWidget().setItemWidget(self, 1, self.versionEdit)
        self.versionEdit.textChanged.connect(lambda : self.overwriteVersionCheck())

        self.availableColor = QtGui.QColor(QtCore.Qt.green)
        self.unavailableColor = QtGui.QColor(QtCore.Qt.red)

        self.setFont(0, itemFont)
        self.setText(0, rbRet.nslyr)

        self.moItem = motionItem(self, self.motionType)
        self.kwargs['motion'] = self.moItem.motionEdit.text()
        self.moItem.motionEdit.textChanged.connect(lambda : self.refreshMotionName())

        self.nodeDict = {}
        self.isVariant = False
        self.isLod = False
        self.isPurpose = False

        self.versionEdit.setText(utls.GetLastVersion(self.assetDir))

    def refreshMotionName(self):
        self.kwargs['motion'] = self.moItem.motionEdit.text()
        print self.kwargs

    def overwriteVersionCheck(self):
        self.kwargs['nsver'] = str(self.versionEdit.text())
        print self.kwargs
        try:
            versionPath = rb.Coder().D.Encode(**self.kwargs).replace('/motion', '')
            print 'versionPath:', versionPath

            if not os.path.exists(versionPath):
                labelColorSet(self.versionEdit, self.unavailableColor)
                self.overwriteVersion = True
            else:
                labelColorSet(self.versionEdit, self.availableColor)
                self.overwriteVersion = False
        except:
            pass


class motionItem(QtWidgets.QTreeWidgetItem):
    def __init__(self, parent, motionType, checked=True):
        QtWidgets.QTreeWidgetItem.__init__(self, parent)

        self.motionEdit = QtWidgets.QLineEdit()
        itemFont = QtGui.QFont()
        itemFont.setPointSize(13)
        itemFont.setBold(True)
        self.motionEdit.setFont(itemFont)
        parent.treeWidget().setItemWidget(self, 0, self.motionEdit)
        self.motionEdit.setText(motionType)


class AssetBranchItem(QtWidgets.QTreeWidgetItem):
    def __init__(self, parent, showName, assetName, branchName, node, overWrite):
        QtWidgets.QTreeWidgetItem.__init__(self, parent)

        self.showName = showName
        self.assetName = assetName.split(' ')[-1]
        self.branchName = branchName
        self.node = node
        self.overWrite = overWrite
        self.assetDir = parent.assetDir
        self.parent = parent

        self.versionEdit = QtWidgets.QLineEdit()
        itemFont = QtGui.QFont()
        itemFont.setPointSize(13)
        itemFont.setBold(True)
        self.versionEdit.setFont(itemFont)
        if type(parent) == QtWidgets.QTreeWidget:
            parent.setItemWidget(self, 1, self.versionEdit)
        else:
            parent.treeWidget().setItemWidget(self, 1, self.versionEdit)
        self.versionEdit.textChanged.connect(lambda : self.overwriteVersionCheck())

        self.availableColor = QtGui.QColor(QtCore.Qt.green)
        self.unavailableColor = QtGui.QColor(QtCore.Qt.red)

        self.setFont(0, itemFont)

        self.setText(0, "branch : %s" % branchName)

        self.nodeDict = {}
        self.isVariant = False
        self.isLod = False
        self.isPurpose = False

        self.updateLastVersion()

    def updateLastVersion(self):
        if self.parent.kwargs['task'] == Define.RIG_TYPE or self.parent.kwargs['task'] == Define.GROOM_TYPE:
            sceneName = cmds.file(q=True, sn=True)
            if sceneName:
                sceneName = os.path.splitext(os.path.basename(sceneName))[0]
            else:
                sceneName = 'xxx'
            self.versionEdit.setText(sceneName)
        else:
            if self.overWrite:
                self.versionEdit.setText(utls.GetLastVersion(self.assetDir))
            else:
                self.versionEdit.setText(utls.GetNextVersion(self.assetDir))

    def overwriteVersionCheck(self):
        msg.debug('branchItem - overwriteVersionCheck')
        if self.parent.kwargs['task'] == Define.RIG_TYPE or self.parent.kwargs['task'] == Define.GROOM_TYPE:
            self.parent.kwargs['nslyr'] = str(self.versionEdit.text())
        else:
            self.parent.kwargs['ver'] = str(self.versionEdit.text())

        # try:
        msg.debug('branchItem', 'overwriteVersionCheck', self.parent.kwargs)
        versionPath = rb.Coder().D.Encode(**self.parent.kwargs)

        if os.path.exists(versionPath):
            labelColorSet(self.versionEdit, self.unavailableColor)
            self.overwriteVersion = True
        else:
            labelColorSet(self.versionEdit, self.availableColor)
            self.overwriteVersion = False
    # except Exception as e:
    #     msg.debug(e.message)
