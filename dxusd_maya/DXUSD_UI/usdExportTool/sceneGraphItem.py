from PySide2 import QtWidgets, QtGui, QtCore

import DXRulebook.Interface as rb
import DXUSD.Utils as utl

import re
import os

NAME = 0
ACTION = 1
VISIBLE = 2
FILEPATH = 3

class sceneGraphItem(QtWidgets.QTreeWidgetItem):
    def __init__(self, parent, outDirItem, category, nodeInfo, isOnlyGroom=False, exportDisable=True, isOnlyBake=False):
        QtWidgets.QTreeWidgetItem.__init__(self, parent)

        self.exportCheckBox = QtWidgets.QCheckBox()
        self.exportCheckBox.setChecked(True)
        self.exportCheckBox.clicked.connect(self.exportStatus)
        parent.treeWidget().setItemWidget(self, 0, self.exportCheckBox)

        self.versionLineEdit = QtWidgets.QLineEdit()
        self.versionLineEdit.textChanged.connect(lambda: self.overwriteVersionCheck())
        parent.treeWidget().setItemWidget(self, 1, self.versionLineEdit)

        self.availableColor = QtGui.QColor(QtCore.Qt.green)
        self.unavailableColor = QtGui.QColor(QtCore.Qt.red)
        self.disableColor = QtGui.QColor(QtCore.Qt.gray)
        self.onlyGroomColor = QtGui.QColor(QtCore.Qt.blue)
        self.fontColor = QtGui.QColor(QtCore.Qt.white)
        self.labelColorSet(self.exportCheckBox, self.fontColor)

        self.isOnlyGroom = isOnlyGroom
        self.isOnlyBake = isOnlyBake

        coder = rb.Coder()
        outDirItem['task'] = category

        self.category = category
        self.outDir = ''
        if category == "ani" or category == "groom" or category == "sim":
            nsLayer, nodeName = nodeInfo[NAME].split(":")
            outDirItem['nslyr'] = nsLayer
            nsLayerDir = coder.D.Encode(**outDirItem)
            self.outDir = nsLayerDir

            currentVersion = utl.GetLastVersion(nsLayerDir)
            nextVersion = utl.GetNextVersion(nsLayerDir)

            if isOnlyGroom and category != "groom":
                self.versionLineEdit.setText(currentVersion)
            else:
                self.versionLineEdit.setText(nextVersion)

        elif category == 'layout':
            ret = coder.N.USD.layout.Decode(nodeInfo[NAME])
            if ret.has_key('task'):
                outDirItem['nslyr'] = ret['nslyr']
                if ret.has_key('desc'): outDirItem['desc']  = ret['desc']
                else: outDirItem['desc'] = ret['nslyr']
            else:
                outDirItem['nslyr'] = 'extra'
                outDirItem['desc']  = ret['nslyr']
            outDir = coder.D.Encode(**outDirItem)
            nextVersion = utl.GetNextVersion(outDir)
            self.outDir = outDir

            self.versionLineEdit.setText(nextVersion)

        elif category == "crowd":
            outDir = coder.D.Encode(**outDirItem)
            currentVersion = utl.GetLastVersion(outDir)
            nextVersion = utl.GetNextVersion(outDir)
            self.outDir = outDir

            if self.isOnlyBake:
                self.versionLineEdit.setText(currentVersion)
            else:
                self.versionLineEdit.setText(nextVersion)
        else:
            outDir = coder.D.Encode(**outDirItem)
            nextVersion = utl.GetNextVersion(outDir)
            self.outDir = outDir

            self.versionLineEdit.setText(nextVersion)

        self.exportCheckBox.setText(nodeInfo[NAME])

        if len(nodeInfo) == FILEPATH + 1:
            self.exportCheckBox.setToolTip(nodeInfo[FILEPATH])

        self.parentDisabled = True

        if exportDisable:
            if category == "set":
                if nodeInfo[ACTION] == 2:
                    # reference
                    self.exportCheckBox.setStyleSheet("QCheckBox { color: skyblue; font: bold 15px; }")
                if not nodeInfo[VISIBLE]:
                    self.setItemDisable()
            elif category == "groom":
                pass
            elif category == "crowd":
                if nodeInfo[ACTION] == 0:
                    print "# skel, geom export"
                elif nodeInfo[ACTION] == 1:
                    print "# Mesh drive export"
            else:
                if nodeInfo[ACTION] == 0 or not nodeInfo[VISIBLE]:
                    self.setItemDisable()
        else:
            self.setItemDisable()

    def setItemDisable(self):
        self.setDisabled(True)
        self.versionLineEdit.setDisabled(True)
        self.labelColorSet(self.versionLineEdit, self.disableColor)
        self.exportCheckBox.setChecked(False)
        self.exportCheckBox.setDisabled(True)
        self.labelColorSet(self.exportCheckBox, self.disableColor)
        self.exportCheckBox.setStyleSheet("QCheckBox { color: gray; font: bold 15px; }")

    def exportStatus(self, status):
        self.versionLineEdit.setEnabled(self.exportCheckBox.isChecked())

        if self.exportCheckBox.isChecked() is True and self.parentDisabled:
            self.overwriteVersionCheck()
        else:
            self.labelColorSet(self.versionLineEdit, self.disableColor)

    def overwriteVersionCheck(self):
        versionPath = os.path.join(self.outDir, self.versionLineEdit.text())

        if os.path.exists(versionPath):
            if self.isOnlyGroom and self.category != "groom":
                self.labelColorSet(self.versionLineEdit, self.onlyGroomColor)
                self.overwriteVersion = False
            else:
                self.labelColorSet(self.versionLineEdit, self.unavailableColor)
                self.overwriteVersion = True
        else:
            self.labelColorSet(self.versionLineEdit, self.availableColor)
            self.overwriteVersion = False

    def labelColorSet(self, label, qcolor):
        palette = label.palette()
        palette.setColor(label.foregroundRole(), qcolor)
        label.setPalette(palette)

    def setDisable(self, status):
        self.versionLineEdit.setDisabled(status)
        self.parentDisabled = not status

        if self.exportCheckBox.isChecked() and self.parentDisabled:
            self.overwriteVersionCheck()
        else:
            self.labelColorSet(self.versionLineEdit, self.disableColor)


class categoryItem(QtWidgets.QTreeWidgetItem):
    def __init__(self, parent, category, checked = True, parentNode=None):
        if parentNode:
            QtWidgets.QTreeWidgetItem.__init__(self, parentNode)
        else:
            QtWidgets.QTreeWidgetItem.__init__(self, parent)

        self.exportCheckBox = QtWidgets.QCheckBox()
        self.exportCheckBox.setChecked(checked)
        self.exportCheckBox.clicked.connect(self.exportStatus)
        parent.setItemWidget(self, 0, self.exportCheckBox)

        self.exportCheckBox.setText(category)

    def exportStatus(self, status):
        if self.exportCheckBox.isChecked() == True:
            for index in range(self.childCount()):
                self.child(index).setDisable(False)
        else:
            for index in range(self.childCount()):
                self.child(index).setDisable(True)
            # self.labelColorSet(self.versionLineEdit, self.disableColor)

    def labelColorSet(self, label, qcolor):
        palette = label.palette()
        palette.setColor(label.foregroundRole(), qcolor)
        label.setPalette(palette)


class sceneGraphItemForLayout(QtWidgets.QTreeWidgetItem):
    def __init__(self, parent, outDirItem, category, nslyr):
        QtWidgets.QTreeWidgetItem.__init__(self, parent)

        self.exportCheckBox = QtWidgets.QCheckBox()
        self.exportCheckBox.setChecked(True)
        self.exportCheckBox.clicked.connect(self.exportStatus)
        parent.treeWidget().setItemWidget(self, 0, self.exportCheckBox)

        self.versionLineEdit = QtWidgets.QLineEdit()
        self.versionLineEdit.textChanged.connect(lambda: self.overwriteVersionCheck())
        parent.treeWidget().setItemWidget(self, 1, self.versionLineEdit)

        self.availableColor = QtGui.QColor(QtCore.Qt.green)
        self.unavailableColor = QtGui.QColor(QtCore.Qt.red)
        self.disableColor = QtGui.QColor(QtCore.Qt.gray)
        self.onlyGroomColor = QtGui.QColor(QtCore.Qt.blue)
        self.fontColor = QtGui.QColor(QtCore.Qt.white)
        self.labelColorSet(self.exportCheckBox, self.fontColor)

        coder = rb.Coder()
        outDirItem['task'] = category

        self.category = category
        self.outDir = ''
        outDir = coder.D.Encode(**outDirItem)
        nextVersion = utl.GetNextVersion(outDir)
        self.outDir = outDir

        self.versionLineEdit.setText(nextVersion)
        self.exportCheckBox.setText(nslyr)

        self.parentDisabled = True

    def setItemDisable(self):
        self.setDisabled(True)
        self.versionLineEdit.setDisabled(True)
        self.labelColorSet(self.versionLineEdit, self.disableColor)
        self.exportCheckBox.setChecked(False)
        self.exportCheckBox.setDisabled(True)
        self.labelColorSet(self.exportCheckBox, self.disableColor)
        self.exportCheckBox.setStyleSheet("QCheckBox { color: gray; font: bold 15px; }")

    def exportStatus(self, status):
        self.versionLineEdit.setEnabled(self.exportCheckBox.isChecked())

        if self.exportCheckBox.isChecked() is True and self.parentDisabled:
            self.overwriteVersionCheck()
        else:
            self.labelColorSet(self.versionLineEdit, self.disableColor)

    def overwriteVersionCheck(self):
        versionPath = os.path.join(self.outDir, self.versionLineEdit.text())

        if os.path.exists(versionPath):
            if self.isOnlyGroom and self.category != "groom":
                self.labelColorSet(self.versionLineEdit, self.onlyGroomColor)
                self.overwriteVersion = False
            else:
                self.labelColorSet(self.versionLineEdit, self.unavailableColor)
                self.overwriteVersion = True
        else:
            self.labelColorSet(self.versionLineEdit, self.availableColor)
            self.overwriteVersion = False

    def labelColorSet(self, label, qcolor):
        palette = label.palette()
        palette.setColor(label.foregroundRole(), qcolor)
        label.setPalette(palette)

    def setDisable(self, status):
        self.versionLineEdit.setDisabled(status)
        self.parentDisabled = not status

        if self.exportCheckBox.isChecked() and self.parentDisabled:
            self.overwriteVersionCheck()
        else:
            self.labelColorSet(self.versionLineEdit, self.disableColor)


class sceneGraphItemForCrowd(QtWidgets.QTreeWidgetItem):
    def __init__(self, parent, outDirItem, category, node):
        QtWidgets.QTreeWidgetItem.__init__(self, parent)

        self.exportCheckBox = QtWidgets.QCheckBox()
        self.exportCheckBox.setChecked(True)
        self.exportCheckBox.clicked.connect(self.exportStatus)
        parent.treeWidget().setItemWidget(self, 0, self.exportCheckBox)

        self.versionLineEdit = QtWidgets.QLineEdit()
        self.versionLineEdit.textChanged.connect(lambda: self.overwriteVersionCheck())
        parent.treeWidget().setItemWidget(self, 1, self.versionLineEdit)

        self.availableColor = QtGui.QColor(QtCore.Qt.green)
        self.unavailableColor = QtGui.QColor(QtCore.Qt.red)
        self.disableColor = QtGui.QColor(QtCore.Qt.gray)
        self.fontColor = QtGui.QColor(QtCore.Qt.white)
        self.labelColorSet(self.exportCheckBox, self.fontColor)

        coder = rb.Coder()
        outDirItem['task'] = category
        if outDirItem.has_key('nslyr'):
            outDirItem.pop('nslyr')
        if outDirItem.has_key('desc'):
            outDirItem.pop('desc')

        self.category = category
        self.outDir = ''
        outDir = coder.D.Encode(**outDirItem)
        nextVersion = utl.GetNextVersion(outDir)
        self.outDir = outDir

        self.versionLineEdit.setText(nextVersion)
        self.exportCheckBox.setText(node)

        self.parentDisabled = True

    def setItemDisable(self):
        self.setDisabled(True)
        self.versionLineEdit.setDisabled(True)
        self.labelColorSet(self.versionLineEdit, self.disableColor)
        self.exportCheckBox.setChecked(False)
        self.exportCheckBox.setDisabled(True)
        self.labelColorSet(self.exportCheckBox, self.disableColor)
        self.exportCheckBox.setStyleSheet("QCheckBox { color: gray; font: bold 15px; }")

    def exportStatus(self, status):
        self.versionLineEdit.setEnabled(self.exportCheckBox.isChecked())

        if self.exportCheckBox.isChecked() is True and self.parentDisabled:
            self.overwriteVersionCheck()
        else:
            self.labelColorSet(self.versionLineEdit, self.disableColor)

    def overwriteVersionCheck(self):
        versionPath = os.path.join(self.outDir, self.versionLineEdit.text())

        if os.path.exists(versionPath):
            self.labelColorSet(self.versionLineEdit, self.unavailableColor)
            self.overwriteVersion = True
        else:
            self.labelColorSet(self.versionLineEdit, self.availableColor)
            self.overwriteVersion = False

    def labelColorSet(self, label, qcolor):
        palette = label.palette()
        palette.setColor(label.foregroundRole(), qcolor)
        label.setPalette(palette)

    def setDisable(self, status):
        self.versionLineEdit.setDisabled(status)
        self.parentDisabled = not status

        if self.exportCheckBox.isChecked() and self.parentDisabled:
            self.overwriteVersionCheck()
        else:
            self.labelColorSet(self.versionLineEdit, self.disableColor)


class crowdItem(QtWidgets.QTreeWidgetItem):
    def __init__(self, parent, node, checked=True):
        QtWidgets.QTreeWidgetItem.__init__(self, parent)

        self.exportCheckBox = QtWidgets.QCheckBox()
        self.exportCheckBox.setChecked(checked)
        parent.treeWidget().setItemWidget(self, 0, self.exportCheckBox)
        self.exportCheckBox.setText(node)
