# -*- coding: utf-8 -*-
#-------------------------------------------------------------------------------
#
#   daeseok.chae rmantd
#
#	2018.04.02
#   2018.05.18 - subprocess style change. stderr, messagebox
#   2018.06.03 - command change. mayapy -> App mayapy
#   2019.06.14 - add $DEVELOPER_LOCATION for debug
#   2020.08.16 - renewal DXUSD-2.0
#
#-------------------------------------------------------------------------------

import os
import string
import subprocess
import getpass

# IP config
import dxConfig
DB_IP = dxConfig.getConf('DB_IP')

# Mongo DB
from pymongo import MongoClient
client = MongoClient(DB_IP)

# QT
from PySide2 import QtWidgets, QtGui, QtCore

# DXRulebook
import DXRulebook.Interface as rb
# from DXUSD.Structures import Arguments

# USD EXPORT TOOL
from ui.usdExportUI import Ui_Form
from sceneGraphItem import sceneGraphItem
from sceneGraphItem import categoryItem
from sceneGraphItem import sceneGraphItemForLayout
from sceneGraphItem import sceneGraphItemForCrowd
from sceneGraphItem import crowdItem

import json

ScriptRoot = os.path.dirname( os.path.abspath(__file__) )

BATCHSCENESCRIPT = '{DCC} rez-env {PACKAGES} -- DXBatchMain {OPTS}'
DXUSD_MAYA_ROOT = os.getenv('REZ_DXUSD_MAYA_ROOT')
SCRIPT_DIR = os.path.join(DXUSD_MAYA_ROOT, 'scripts')

ROOTPATH = os.getenv('DEVELOPER_LOCATION')
if ROOTPATH and ROOTPATH in ScriptRoot:
    pass
else:
    ROOTPATH = '/backstage'

class MainForm(QtWidgets.QWidget):
    def __init__(self, parent, srcFile=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        self.connections()
        self.styleSetting()
        self.defaultSetting()

        self.ui.machineType_comboBox.setCurrentIndex(0)
        if srcFile:
            if type(srcFile) == list:
                self.ui.exportFile_lineEdit.setText(srcFile[0])
            elif type(srcFile) == str:
                self.ui.exportFile_lineEdit.setText(srcFile)

    def connections(self):
        self.ui.doExport_pushButton.clicked.connect(self.doExport)
        self.ui.findExportFile_pushButton.clicked.connect(self.selectExportFile)
        self.ui.findOutDir_pushButton.clicked.connect(self.selectExportDir)
        # self.ui.findOutDir_pushButton.clicked.connect(self.selectExportFile)
        self.ui.openExportFile_pushButton.clicked.connect(self.openDirectory)
        self.ui.openOutDir_pushButton.clicked.connect(self.openDirectory)
        self.ui.exportFile_lineEdit.textChanged.connect(lambda :self.setSceneGraph(self.ui.exportFile_lineEdit.text()))
        self.ui.only_groom_checkBox.clicked.connect(lambda :self.setSceneGraph(self.ui.exportFile_lineEdit.text()))
        self.ui.only_bake_checkBox.clicked.connect(lambda: self.setSceneGraph(self.ui.exportFile_lineEdit.text()))

    def styleSetting(self):
        imagePath = '%s/ui/pxr_usd_w.png'%ScriptRoot
        image = QtGui.QPixmap(imagePath).scaled(30, 30, QtCore.Qt.KeepAspectRatioByExpanding, QtCore.Qt.SmoothTransformation)
        self.ui.titleLogo_label.setPixmap(image)
        imagePath_folder = '%s/ui/folder.png'%ScriptRoot
        self.ui.openExportFile_pushButton.setIcon(QtGui.QIcon(QtGui.QPixmap(imagePath_folder)))
        self.ui.openOutDir_pushButton.setIcon(QtGui.QIcon(QtGui.QPixmap(imagePath_folder)))
        comboBoxStyle = '''
                        QComboBox QAbstractItemView::item { min-height: 20px; min-width: 120px;}
                        background-color: rgb(90,90,90);
                        color : white;
                        '''
        self.ui.machineType_comboBox.setView(QtWidgets.QListView())
        self.ui.machineType_comboBox.setStyleSheet(comboBoxStyle)

    def defaultSetting(self):
        self.ui.userName_label.setText("user:" + getpass.getuser())
        self.ui.startFrame_lineEdit.setText('0')
        self.ui.endFrame_lineEdit.setText('0')
        self.ui.stepFrame_lineEdit.setText('1.0')

    def selectExportFile(self):
        dirtext = os.path.dirname(self.ui.exportFile_lineEdit.text())

        if not os.path.exists(dirtext):
            dirtext = os.getenv("HOME")
        dialog = FindFileDialog(self, "find export file", dirtext)
        result = dialog.exec_()
        if result == 1:
            path = dialog.selectedFiles()[-1]
            self.ui.exportFile_lineEdit.setText(path)
            self.setSceneGraph(path)

    def setSceneGraph(self, mayaFile):
        # tree widget clear
        while self.ui.sceneGraphTreeWidget.topLevelItemCount() > 0:
            self.ui.sceneGraphTreeWidget.takeTopLevelItem(0)
            treeitem = self.ui.sceneGraphTreeWidget.topLevelItem(0)
            if treeitem:
                if treeitem.childCount() > 0:
                    treeitem.takeChildren()

        if not os.path.exists(mayaFile) or not os.path.isfile(mayaFile):
            return
        print '> export scene :', mayaFile

        jsonFile = mayaFile.replace(".mb", ".json")
        sceneName = os.path.basename(mayaFile)
        dirPath = os.path.dirname(mayaFile)

        flags  = rb.Flags(pub='_3d')
        flags.D.SetDecode(dirPath, 'ROOTS')
        flags.F.MAYA.SetDecode(sceneName, 'BASE')
        if flags.has_key('departs'):
            flags.pop("departs")
        outDir = flags.D.SHOT
        self.ui.outDir_lineEdit.setText(outDir)

        flags = rb.Flags()
        flags.D.SetDecode(outDir)
        outDirItem = flags.copy()

        isOnlyGroom = self.ui.only_groom_checkBox.isChecked()
        camEnabled = True

        nameSpaceErrorList = []

        with open(jsonFile, "r") as f:
            sceneGraph = json.load(f)
            print sceneGraph

            # Base Setup
            if sceneGraph.has_key('rezRequest'):
                self.rezRequestConfig = sceneGraph['rezRequest']
            else:
                self.rezRequestConfig = ['maya-' + sceneGraph['mayaVersion'], 'dxusd_maya', 'usd_maya']     # default packages

            self.mayaVersion = sceneGraph["mayaVersion"]
            self.artistName = sceneGraph['artist']

            # Camera
            if len(sceneGraph['camera']) >= 1:
                camItem = categoryItem(self.ui.sceneGraphTreeWidget, 'cam')
                camerasItem = sceneGraphItemForLayout(camItem, outDirItem, "cam", 'cameras')
                for node in sceneGraph['camera']:
                    categoryItem(self.ui.sceneGraphTreeWidget, node[0], parentNode=camerasItem)

            # Layout Environment
            if len(sceneGraph["layout"]) >= 1:
                layItem = categoryItem(self.ui.sceneGraphTreeWidget, 'layout')
                nsLayerItem = {}
                flags = rb.Flags()
                outDirItem['task'] = 'layout'
                for node in sceneGraph['layout']:
                    # [nodeName, export type, GetViz, nodeType]
                    if node[3] == 'extra':
                        outDirItem['nslyr'] = 'extra'
                        outDirItem['desc'] = node[0]
                    else:
                        ret = flags.N.USD.layout.Decode(node[0])
                        outDirItem['nslyr'] = ret['nslyr']
                        outDirItem['desc'] = node[0]

                    if not nsLayerItem.has_key(outDirItem['nslyr']):
                        nsLayerItem[outDirItem['nslyr']] = sceneGraphItemForLayout(layItem, outDirItem, "layout", outDirItem['nslyr'])

                    categoryItem(self.ui.sceneGraphTreeWidget, node[0], parentNode=nsLayerItem[outDirItem['nslyr']])

            # Animation Cache
            if len(sceneGraph["geoCache"]) >= 1:
                geoItem = categoryItem(self.ui.sceneGraphTreeWidget, 'geo')
                for node in sceneGraph['geoCache']:
                    if len(node[0].split(":")) > 2:
                        nameSpaceErrorList.append(node[0])
                        continue
                    sceneGraphItem(geoItem, outDirItem, "ani", node, isOnlyGroom=isOnlyGroom, exportDisable = camEnabled)

            if sceneGraph.has_key('sim') and len(sceneGraph["sim"]) >= 1:
                if sceneGraph.has_key('zenn') and len(sceneGraph["zenn"]) >= 1:
                    simItem = categoryItem(self.ui.sceneGraphTreeWidget, 'groomSim')
                    category = 'groom'
                else:
                    simItem = categoryItem(self.ui.sceneGraphTreeWidget, 'sim')
                    category = 'sim'
                for node in sceneGraph['sim']:
                    if len(node[0].split(":")) > 2:
                        nameSpaceErrorList.append(node[0])
                        continue
                    sceneGraphItem(simItem, outDirItem, category, node, isOnlyGroom=isOnlyGroom)

            if sceneGraph.has_key('crowd') and len(sceneGraph["crowd"]) >= 1:
                def allDisableExport(treeitem):
                    if treeitem.childCount() > 0:
                        for j in range(treeitem.childCount()):
                            treeitem.child(j).exportCheckBox.setChecked(False)
                            allDisableExport(treeitem.child(j))

                for i in range(self.ui.sceneGraphTreeWidget.topLevelItemCount()):
                    treeitem = self.ui.sceneGraphTreeWidget.topLevelItem(i)
                    treeitem.exportCheckBox.setChecked(False)
                    treeitem.exportStatus(False)
                    allDisableExport(treeitem)

                geoItem = categoryItem(self.ui.sceneGraphTreeWidget, 'crowd')

                if 'golaem' in sceneGraph['crowd'][0][-1]:
                    glmItem = sceneGraphItemForCrowd(geoItem, outDirItem, 'crowd', 'golaem')
                    for node in sceneGraph['crowd']:
                        crowdItem(glmItem, node[0], node[2])

                    # Golaem Local Export only
                    self.ui.machineType_comboBox.setCurrentIndex(1)
                else:
                    for node in sceneGraph['crowd']:
                        sceneGraphItem(geoItem, outDirItem, "crowd", node, isOnlyBake=self.ui.only_bake_checkBox.isChecked())

            if nameSpaceErrorList:
                print nameSpaceErrorList
                text = "\n".join(nameSpaceErrorList)
                text += "\ntoo many namespace, please clean up namespace"
                showfinishedDialog("info", text)

            self.ui.sceneGraphTreeWidget.expandAll()


    def selectExportDir(self):
        dirtext = self.ui.outDir_lineEdit.text()

        if not os.path.exists(dirtext):
            dirtext = os.getenv("HOME")

        dialog = FindFileDialog(self, "find export directory", dirtext)
        dialog.setFileMode(QtWidgets.QFileDialog.Directory)
        dialog.setOption(QtWidgets.QFileDialog.ShowDirsOnly, True)
        result = dialog.exec_()
        if result == 1:
            path = dialog.selectedFiles()[-1]
            self.ui.outDir_lineEdit.setText(path)

    def openDirectory(self):
        dirtext = ""
        if self.sender().objectName() == "openExportFile_pushButton":
            if os.path.isdir(self.ui.exportFile_lineEdit.text()):
                dirtext = self.ui.exportFile_lineEdit.text()
            else:
                dirtext = os.path.dirname(self.ui.exportFile_lineEdit.text())
        elif self.sender().objectName() == "openOutDir_pushButton":
            dirtext = self.ui.outDir_lineEdit.text()

        if not os.path.exists(dirtext):
            dirtext = os.getenv("HOME")
        subprocess.Popen(['xdg-open', str(dirtext)])

    # def sgItemToString(self, item):
    #     data = list()
    #     # print '# item :', item.exportCheckBox.text()
    #     for index in range(item.childCount()):
    #         visible  = item.child(index).exportCheckBox.isChecked()
    #         nodeName = item.child(index).exportCheckBox.text()
    #         version  = item.child(index).versionLineEdit.text()
    #         # print '#\t', visible, nodeName, version
    #         print '>>>', item.child(index).childCount()
    #         if visible:
    #             data.append('{VER}={NODE}'.format(VER=version, NODE=nodeName))
    #     if data:
    #         return string.join(data, ' ')

    def sgItemToString(self, parent):
        data = list()
        for index in range(parent.childCount()):
            item = parent.child(index)
            visible  = item.exportCheckBox.isChecked()
            nodeName = item.exportCheckBox.text()
            version  = item.versionLineEdit.text()
            if visible:
                childnum = item.childCount()
                if childnum > 0:
                    children = []
                    for i in range(childnum):
                        childViz  = item.child(i).exportCheckBox.isChecked()
                        childName = item.child(i).exportCheckBox.text()
                        if childViz:
                            children.append(childName)
                    nodeName = ','.join(children)
                data.append('{VER}={NODE}'.format(VER=version, NODE=nodeName))
                # print '>>>', nodeName
        if data:
            return ' '.join(data)


    def getExportOption(self):
        opts = ""
        srcfile = self.ui.exportFile_lineEdit.text()
        outdir = self.ui.outDir_lineEdit.text()
        start = self.ui.startFrame_lineEdit.text()
        end = self.ui.endFrame_lineEdit.text()
        step = self.ui.stepFrame_lineEdit.text()
        rigVerUp = self.ui.rigVersionUp_checkBox.isChecked()
        groomcache  = self.ui.groom_checkBox.isChecked()
        onlygroom = self.ui.only_groom_checkBox.isChecked()
        onlyBake = self.ui.only_bake_checkBox.isChecked()
        dontParallelExport = self.ui.dontParallelCheckBox.isChecked()

        if srcfile:
            if os.path.splitext(self.ui.exportFile_lineEdit.text())[-1] in ['.mb']:
                opts += ' --file %s' % srcfile
            if outdir:
                opts += " --outDir %s" % outdir
            # if self.artistName:
            #     opts += ' --user %s' % self.artistName
            opts += ' --user %s' % getpass.getuser()
            opts += " --mayaver %s" % self.mayaVersion

            for index in range(self.ui.sceneGraphTreeWidget.topLevelItemCount()):
                item = self.ui.sceneGraphTreeWidget.topLevelItem(index)

                # TODO: visible is checked from checkbox
                if item.exportCheckBox.isChecked(): # if visible true
                    if item.exportCheckBox.text() == "geo": # geoCache
                        # has geoCache
                        optstr = self.sgItemToString(item)
                        if optstr:
                            opts += ' --mesh "%s"' % optstr

                    if item.exportCheckBox.text() == "sim": # simulation
                        # has sim
                        optstr = self.sgItemToString(item)
                        if optstr: opts += ' --simMesh "%s"' % optstr

                    if item.exportCheckBox.text() == "cam": # camera
                        # has camera
                        optstr = self.sgItemToString(item)
                        if optstr: opts += ' --camera "%s"' % optstr

                    if item.exportCheckBox.text() == "layout": # layout
                        # has layout
                        optstr = self.sgItemToString(item)
                        if optstr: opts += ' --layout "%s"' % optstr

                    if item.exportCheckBox.text() == "groomSim": # simulation
                        # has geoCache
                        optstr = self.sgItemToString(item)
                        if optstr:
                            self.rezRequestConfig.append('zelos')
                            opts += ' --groomSim "%s"' % optstr

                    if item.exportCheckBox.text() == "crowd": # simulation
                        # has crowd scenes
                        optstr = self.sgItemToString(item)
                        if optstr: opts += ' --crowd "%s"' % optstr

            # frame
            opts += " --frameRange %s %s" % (start, end)
            opts += " --step %s" % step
            if rigVerUp:
                opts += " --rigUpdate"
            if onlygroom:
                self.rezRequestConfig.append('zelos')
                opts += ' --onlyGroom'
            elif groomcache:
                self.rezRequestConfig.append('zelos')
                opts += ' --groom'
            if onlyBake:
                opts += ' --crowdbake'
            if dontParallelExport:
                opts += ' --serial'
        else:
            print 'No export file name. Export cancelled'

        return opts

    def doExport(self):
        opts = self.getExportOption()
        if not opts:
            showfinishedDialog('critical', "Export Fail")
            return

        message_type = 'info'
        text = ""
        errorText = ''
        if self.ui.machineType_comboBox.currentText() == 'LOCAL':
            opts += " --host local --process both"
            text  = " Export Completed "
            if ".mb" in os.path.splitext(self.ui.exportFile_lineEdit.text())[-1]:
                print '# Debug opts : %s' % opts
                command = BATCHSCENESCRIPT.format(DCC=os.getenv('DCCPROC'), PACKAGES=' '.join(self.rezRequestConfig), OPTS=opts)
                # print '>>', command
                p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                while p.poll() == None:
                    output = p.stdout.readline()
                    if output:
                        print output.strip()
                    if output.startswith("AssertionError:"):
                        errorText += output.replace("AssertionError: ", "")
                        message_type = 'critical'
                    if "Local Export Exit" in output:
                        print "HI?!!!!!!!!!!!!!!!!"
                        p.terminate()
                        # p.kill()
            else:
                message_type = "critical"
                errorText = "Scene file check please "
                print "# Scene file check please."
        elif self.ui.machineType_comboBox.currentText() == 'TRACTOR':
            opts += " --host spool"
            text  = " Spool Completed "

            command = BATCHSCENESCRIPT.format(DCC=os.getenv('DCCPROC'), PACKAGES=' '.join(self.rezRequestConfig), OPTS=opts)
            p = subprocess.Popen(command, shell=True)
            p.wait()

        if message_type == 'critical':
            text = errorText
        showfinishedDialog(message_type, text)

    def closeEvent(self, event):
        self.close()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()

### DIALOGUE ###
def showfinishedDialog(type='info', text='Export Completed'):
    dialog = QtWidgets.QMessageBox()
    dialog.setStyleSheet('background-color: rgb(70, 70, 70); color: white;')
    if type == 'critical':
        dialog.setIcon(QtWidgets.QMessageBox.Critical)
    else:
        dialog.setIcon(QtWidgets.QMessageBox.Information)
    dialog.setText(text)
    dialog.setWindowTitle('MESSAGE')
    dialog.addButton('OK',QtWidgets.QMessageBox.YesRole)
    dialog.move(QtWidgets.QDesktopWidget().availableGeometry().center())
    dialog.show()
    dialog.exec_()

class FindFileDialog(QtWidgets.QFileDialog):
    def __init__(self, parent=None, windowName='', dirPath='' ):
        QtWidgets.QFileDialog.__init__(self, parent)
        self.setWindowTitle(windowName)
        self.setStyleSheet('''background-color: rgb(80, 80, 80); color:white;''')
        self.setDirectory(dirPath)
        self.setMinimumSize(1200, 800)


class FindDirectoryDialog(QtWidgets.QFileDialog):
    def __init__(self, parent=None, windowName='', dirPath='' ):
        QtWidgets.QFileDialog.__init__(self, parent)
        self.setWindowTitle(windowName)
        self.setStyleSheet('''background-color: rgb(80, 80, 80); color:white;''')
        self.setDirectory(dirPath)
        self.setMinimumSize(1200, 800)
