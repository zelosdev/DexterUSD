#coding:utf-8

##########################################
__author__  = 'daeseok.chae in Dexter CGSupervisor'
__date__ = '2020.07.14'
__comment__ = 'import asset for usd'
__windowName__ = "DXUSD AssetImporter 2.0"
##########################################

import os

import maya.OpenMayaUI as mui
import shiboken2 as shiboken
import maya.cmds as cmds
import maya.mel as mel

from .AssetImportUI import Ui_Form

from PySide2 import QtWidgets, QtCore, QtGui

import DXRulebook.Interface as rb
import dxBlockUtils
import DXUSD_MAYA.Message as dxmsg
import DXUSD_MAYA.Utils as utl

from pxr import Sdf, Usd

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

class AssetImportTool(QtWidgets.QWidget):
    def __init__(self, parent = getMayaWindow()):

        # Load dependency plugin
        plugins = ['DXUSD_Maya']
        for p in plugins:
            if not cmds.pluginInfo(p, q=True, l=True):
                cmds.loadPlugin(p)

        QtWidgets.QWidget.__init__(self, parent)

        self.setWindowFlags(QtCore.Qt.Window)

        self.ui = Ui_Form()
        self.ui.setupUi(self)

        self.move(parent.frameGeometry().center() - self.frameGeometry().center())

        self.assetNameColor = QtGui.QBrush(QtGui.QColor(248, 137, 7))
        self.branchColor = QtGui.QBrush(QtGui.QColor(9, 212, 255))
        self.versionColor = QtGui.QBrush(QtGui.QColor(QtCore.Qt.green))
        self.otherColor = QtGui.QBrush(QtGui.QColor(QtCore.Qt.white))

        self.itemFont = QtGui.QFont()
        self.itemFont.setPointSize(13)
        self.itemFont.setBold(True)

        # project auto setup
        scenePath = cmds.file(q=True, sn=True)
        print "File :", scenePath
        if scenePath == "":
            scenePath = cmds.workspace(q = True, rd=True)
            print "WS :", scenePath
        print scenePath


        decoder = rb.Coder('D')
        ret = decoder.ROOTS.Decode(scenePath)
        dxmsg.debug('scenePath-Decode', scenePath, ret)
        self.showName = ret.show
        self.ui.showEdit.setText(self.showName)

        # make completer of show
        customNeedCompleter = []
        customNeedCompleter.append("/assetlib/_3d")

        showCompleter = QtWidgets.QCompleter(customNeedCompleter)
        showCompleter.popup().setFont(self.itemFont)
        self.ui.showEdit.setCompleter(showCompleter)

        # Signal connect
        self.ui.showEdit.returnPressed.connect(lambda : self.changeAssetListCompleter())
        self.ui.assetEdit.returnPressed.connect(lambda: self.makeTreeWidgetFromAssetList())
        self.ui.treeWidget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.ui.treeWidget.customContextMenuRequested.connect(self.rmbClicked)
        self.ui.treeWidget.itemDoubleClicked.connect(self.assetItemDoublieClicked)
        self.ui.importBtn.clicked.connect(self.importAsset)

    def appendNameDir(self, assetNameDir, assetName, branchList):
        if os.path.exists(assetNameDir):
            self.assetList[assetName] = []
            branchDir = os.path.join(assetNameDir, "branch")
            if os.path.exists(branchDir):
                branchUsdFilePath = os.path.join(branchDir, "branch.usd")
                branchLayer = Sdf.Layer.FindOrOpen(branchUsdFilePath)
                if branchLayer:
                    branchPrimPath = Sdf.Path('/' + branchLayer.defaultPrim)
                    branchSpec = branchLayer.GetPrimAtPath(branchPrimPath)
                    branchVsetSpec = branchSpec.variantSets.get('branch')
                    if branchVsetSpec:
                        for branchName in branchVsetSpec.variants.keys():
                            if os.path.isdir(os.path.join(branchDir, branchName)):
                                self.assetList[assetName].append(branchName)
                                branchList.append(branchName)

    def changeAssetListCompleter(self):
        self.assetList = {}
        self.entityDict = {}
        branchList = []
        if self.ui.showEdit.text() == '/assetlib/_3d':
            assetUsdFilePath = os.path.join(self.ui.showEdit.text(), "asset", "asset.usd")
        else:
            assetUsdFilePath = os.path.join('/show', self.ui.showEdit.text(), '_3d', "asset", "asset.usd")

        if os.path.exists(assetUsdFilePath):
            layer = Sdf.Layer.FindOrOpen(assetUsdFilePath)
            if layer:
                primPath = Sdf.Path('/' + layer.defaultPrim)
                spec = layer.GetPrimAtPath(primPath)
                vsetSpec = spec.variantSets.get('asset')
                if vsetSpec:
                    for assetName, variantPath in vsetSpec.variants.items():
                        if variantPath.variantSets.get('entity'): # entity
                            entityVSetSpec = variantPath.variantSets.get('entity')
                            self.entityDict[assetName] = []
                            for entityName in entityVSetSpec.variants.keys():
                                if entityName == 'asset':
                                    assetNameDir = os.path.join(os.path.dirname(assetUsdFilePath), assetName)
                                else:
                                    shotDir = os.path.join('/show', self.ui.showEdit.text(), '_3d', 'shot')
                                    self.entityDict[assetName].append(entityName)
                                    if '_' in entityName:
                                        assetNameDir = os.path.join(shotDir, entityName.split('_')[0], entityName, 'asset', assetName)
                                    else:
                                        assetNameDir = os.path.join(shotDir, entityName.split('_')[0], 'asset', assetName)

                                self.appendNameDir(assetNameDir, assetName, branchList)
                        else:
                            assetNameDir = os.path.join(os.path.dirname(assetUsdFilePath), assetName)
                            self.appendNameDir(assetNameDir, assetName, branchList)

            assetCompleter = QtWidgets.QCompleter(self.assetList.keys() + branchList)
            assetCompleter.popup().setFont(self.itemFont)

            self.ui.assetEdit.setCompleter(assetCompleter)
            self.ui.assetEdit.setDisabled(False)
            self.ui.assetEdit.setText("")
            self.makeTreeWidgetFromAssetList()
        else:
            self.ui.assetEdit.setDisabled(True)
            self.cleanupTreeWidget()

    def cleanupTreeWidget(self):
        while self.ui.treeWidget.topLevelItemCount() > 0:
            self.ui.treeWidget.takeTopLevelItem(0)
            treeitem = self.ui.treeWidget.topLevelItem(0)
            if treeitem:
                if treeitem.childCount() > 0:
                    treeitem.takeChildren()

    def makeTreeWidgetFromAssetList(self):
        self.cleanupTreeWidget()

        for assetName in sorted(self.assetList.keys()):
            QtWidgets.QApplication.processEvents()
            # make assetList
            if self.ui.assetEdit.text().lower() in assetName.lower():
                assetNameItem = QtWidgets.QTreeWidgetItem(self.ui.treeWidget, [assetName, "", "0"])
                assetNameItem.setFont(0, self.itemFont)
                assetNameItem.setForeground(0, self.assetNameColor)
            elif self.assetList.has_key(assetName) and self.assetList[assetName]:
                # has branch
                isInsert = False
                for branchName in self.assetList[assetName]:
                    if self.ui.assetEdit.text() in branchName.lower():
                        isInsert = True
                        break
                if isInsert:
                    assetNameItem = QtWidgets.QTreeWidgetItem(self.ui.treeWidget, [assetName, "", "0"])
                    assetNameItem.setFont(0, self.itemFont)
                    assetNameItem.setForeground(0, self.assetNameColor)

    def makeAssetItemList(self, assetDir, rootItem):
        if os.path.exists(os.path.join(assetDir, "model")):
            modelItem = QtWidgets.QTreeWidgetItem(rootItem, ["model"])
            modelItem.setFont(0, self.itemFont)

            modelDir = os.path.join(assetDir, "model")
            for i in os.listdir(modelDir):
                if os.path.isdir(os.path.join(modelDir, i)):
                    if i[0] == 'v':
                        versionItem = QtWidgets.QTreeWidgetItem(modelItem, [i, os.path.join(modelDir, i)])
                        versionItem.setFont(0, self.itemFont)
                        versionItem.setForeground(0, self.versionColor)

                        versionDir = os.path.join(modelDir, i)
                        for j in os.listdir(versionDir):
                            if "_geom.usd" in j:
                                geomItem = QtWidgets.QTreeWidgetItem(versionItem, [j, os.path.join(versionDir, j), i])
                                geomItem.setFont(0, self.itemFont)

        if os.path.exists(os.path.join(assetDir, "rig")):
            rigItem = QtWidgets.QTreeWidgetItem(rootItem, ["rig"])
            rigItem.setFont(0, self.itemFont)

            rigDir = os.path.join(assetDir, "rig")
            for i in os.listdir(rigDir):
                if os.path.isdir(os.path.join(rigDir, i)):
                    if not 'scenes' in i:
                        versionItem = QtWidgets.QTreeWidgetItem(rigItem, [i, os.path.join(rigDir, i)] )
                        versionItem.setFont(0, self.itemFont)
                        versionItem.setForeground(0, self.versionColor)
                        lodList = ['low', 'mid']
                        for lod in lodList:
                            if os.path.exists(os.path.join(rigDir, 'scenes', i + "_%s.mb" % lod)):  # low check
                                versionItem = QtWidgets.QTreeWidgetItem(rigItem, [i + "_%s" % lod, os.path.join(rigDir, i + "_%s" % lod)])
                                versionItem.setFont(0, self.itemFont)
                                versionItem.setForeground(0, self.versionColor)

        if os.path.exists(os.path.join(assetDir, "clip")):
            clipItem = QtWidgets.QTreeWidgetItem(rootItem, ["clip"])
            clipItem.setFont(0, self.itemFont)

            # clipDir = os.path.join(assetDir, "clip")
            # for nsLayer in os.listdir(clipDir):
            #     if os.path.isdir(os.path.join(clipDir, nsLayer)):
            #         nsLayerItem = QtWidgets.QTreeWidgetItem(clipItem, [nsLayer])
            #         nsLayerItem.setFont(0, self.itemFont)
            #
            #         nsLayerDir = os.path.join(clipDir, nsLayer)
            #         for i in os.listdir(nsLayerDir):
            #             if i[0] == 'v':
            #                 versionItem = QtWidgets.QTreeWidgetItem(nsLayerItem, [i, os.path.join(nsLayerDir, i)])
            #                 versionItem.setFont(0, self.itemFont)
            #                 versionItem.setForeground(0, self.versionColor)
            #
            #                 versionDir = os.path.join(nsLayerDir, i)
            #                 for j in os.listdir(versionDir):
            #                     if os.path.isdir(os.path.join(versionDir, j)):
            #                         geomItem = QtWidgets.QTreeWidgetItem(versionItem, [j, os.path.join(versionDir, j), i])
            #                         geomItem.setFont(0, self.itemFont)

        if os.path.exists(os.path.join(assetDir, "branch")):
            branchItem = QtWidgets.QTreeWidgetItem(rootItem, ["branch"])
            branchItem.setFont(0, self.itemFont)

            branchDir = os.path.join(assetDir, "branch")
            branchUsdFile = os.path.join(branchDir, "branch.usd")
            branchLayer = Sdf.Layer.FindOrOpen(branchUsdFile)

            if branchLayer:
                branchPrimPath = Sdf.Path('/' + branchLayer.defaultPrim)
                branchSpec = branchLayer.GetPrimAtPath(branchPrimPath)
                branchVsetSpec = branchSpec.variantSets.get('branch')
                if branchVsetSpec:
                    for branchName in sorted(branchVsetSpec.variants.keys()):
                        if os.path.exists(os.path.join(branchDir, branchName)):
                            branchNameItem = QtWidgets.QTreeWidgetItem(branchItem,
                                                                        [branchName, os.path.join(branchDir, branchName)])
                            branchNameItem.setFont(0, self.itemFont)
                            branchNameItem.setForeground(0, self.branchColor)

                            modelDir = os.path.join(branchDir, branchName, "model")
                            if os.path.exists(modelDir):
                                modelItem = QtWidgets.QTreeWidgetItem(branchNameItem, ["model"])
                                modelItem.setFont(0, self.itemFont)

                                for i in os.listdir(modelDir):
                                    if os.path.isdir(os.path.join(modelDir, i)):
                                        if i[0] == 'v':
                                            versionItem = QtWidgets.QTreeWidgetItem(modelItem, [i, os.path.join(modelDir, i)])
                                            versionItem.setFont(0, self.itemFont)
                                            versionItem.setForeground(0, self.versionColor)

                                            versionDir = os.path.join(modelDir, i)
                                            for j in os.listdir(versionDir):
                                                if "_geom.usd" in j:
                                                    geomItem = QtWidgets.QTreeWidgetItem(versionItem,
                                                                                         [j, os.path.join(versionDir, j), i])
                                                    geomItem.setFont(0, self.itemFont)

                            rigDir = os.path.join(branchDir, branchName, "rig")
                            if os.path.exists(os.path.join(branchDir, branchName, "rig")):
                                rigItem = QtWidgets.QTreeWidgetItem(branchNameItem, ["rig"])
                                rigItem.setFont(0, self.itemFont)

                                for i in os.listdir(os.path.join(rigDir)):
                                    if os.path.isdir(os.path.join(rigDir, i)):
                                        if not 'scenes' in i:
                                            versionItem = QtWidgets.QTreeWidgetItem(rigItem, [i, os.path.join(rigDir, i)])
                                            versionItem.setFont(0, self.itemFont)
                                            versionItem.setForeground(0, self.versionColor)
                                            lodList = ['low', 'mid']
                                            for lod in lodList:
                                                if os.path.exists(os.path.join(rigDir, 'scenes', i + "_%s.mb" % lod)): # low check
                                                    versionItem = QtWidgets.QTreeWidgetItem(rigItem, [i + "_%s" % lod, os.path.join(rigDir, i + "_%s" % lod)])
                                                    versionItem.setFont(0, self.itemFont)
                                                    versionItem.setForeground(0, self.versionColor)

                            clipDir = os.path.join(branchDir, branchName, "clip")
                            if os.path.exists(clipDir):
                                clipItem = QtWidgets.QTreeWidgetItem(branchNameItem, ["clip"])
                                clipItem.setFont(0, self.itemFont)

                                # clipDir = os.path.join(assetDir, "clip")
                                # for nsLayer in os.listdir(clipDir):
                                #     if os.path.isdir(os.path.join(clipDir, nsLayer)):
                                #         nsLayerItem = QtWidgets.QTreeWidgetItem(clipItem, [nsLayer])
                                #         nsLayerItem.setFont(0, self.itemFont)
                                #
                                #         nsLayerDir = os.path.join(clipDir, nsLayer)
                                #         for i in os.listdir(nsLayerDir):
                                #             if i[0] == 'v':
                                #                 versionItem = QtWidgets.QTreeWidgetItem(nsLayerItem,
                                #                                                         [i, os.path.join(nsLayerDir, i)])
                                #                 versionItem.setFont(0, self.itemFont)
                                #                 versionItem.setForeground(0, self.versionColor)
                                #
                                #                 versionDir = os.path.join(nsLayerDir, i)
                                #                 for j in os.listdir(versionDir):
                                #                     if os.path.isdir(os.path.join(versionDir, j)):
                                #                         geomItem = QtWidgets.QTreeWidgetItem(versionItem, [j,
                                #                                                                            os.path.join(
                                #                                                                                versionDir,
                                #                                                                                j), i])
                                #                         geomItem.setFont(0, self.itemFont)

    def assetItemDoublieClicked(self, assetNameItem, column):

        if self.ui.showEdit.text() == '/assetlib/_3d':
            assetDir = os.path.join(self.ui.showEdit.text(), "asset", assetNameItem.text(0))
        else:
            assetDir = os.path.join('/show', self.ui.showEdit.text(), '_3d', "asset", assetNameItem.text(0))

        if assetNameItem.text(2) == "1" or assetNameItem.parent() is not None:
            return

        assetNameItem.setText(2, "1")
        self.makeAssetItemList(assetDir, assetNameItem)
        if self.entityDict.has_key(assetNameItem.text(0)):
            shotRootDir = os.path.join('/show', self.ui.showEdit.text(), '_3d', 'shot')
            for entityName in self.entityDict[assetNameItem.text(0)]:
                entityItem = QtWidgets.QTreeWidgetItem(assetNameItem, [entityName])
                entityItem.setFont(0, self.itemFont)
                if '_' in entityName:
                    seq = entityName.split('_')[0]
                    shot = entityName
                    entityAssetDir = os.path.join(shotRootDir, seq, shot, 'asset', assetNameItem.text(0))
                else:
                    seq = entityName
                    entityAssetDir = os.path.join(shotRootDir, seq, 'asset', assetNameItem.text(0))
                self.makeAssetItemList(entityAssetDir, entityItem)


    def mConfirmDialog(self, assetName, version, isOverwrite):
        if isOverwrite:
            msg = cmds.confirmDialog(
                title='Overwrite?', message='%s of %s overwrite?' % (version, assetName),
                icon='warning', button=['OK', 'CANCEL']
            )
            assert msg != 'CANCEL', '# msg : stopped process!'

    def rmbClicked(self, pos):
        item = self.ui.treeWidget.currentItem()
        menuTitle = 'Reference {NAME}'
        if cmds.pluginInfo('TaneForMaya', q=True, l=True):
            selected = cmds.ls(sl=True, dag=True, type='TN_Tane')
            if selected:
                menuTitle += ' in Tane'

        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet('''
                                        QMenu::item:selected {
                                        background-color: #81CF3E;
                                        color: #404040; }
                                       ''')



        if item.text(0) in self.assetList:
            menu.addAction(QtGui.QIcon(), menuTitle.format(NAME=item.text(0)), lambda : self.referenceImport(item))
            menu.addAction(QtGui.QIcon(), menuTitle.format(NAME=item.text(0)) + ' (SceneAssembly)', lambda : self.referenceAssemblyImport(item))

        elif item.parent() and "branch" in item.parent().text(0):
            menu.addAction(QtGui.QIcon(), menuTitle.format(NAME=item.text(0)), lambda : self.referenceImport(item))
            menu.addAction(QtGui.QIcon(), menuTitle.format(NAME=item.text(0)) + ' (SceneAssembly)', lambda : self.referenceAssemblyImport(item))

        elif item.parent().parent() and "clip" in item.parent().parent().text(0) and "loop" in item.text(0):
            menu.addAction(QtGui.QIcon(), menuTitle.format(NAME=item.text(0)),lambda: self.referenceImport(item))

        elif item.parent() and "rig" in item.parent().text(0):
            menu.addAction(QtGui.QIcon(), 'Maya Reference: {NAME}'.format(NAME=item.text(0)), lambda: self.referenceMaya(item))
            menu.addAction(QtGui.QIcon(), 'Maya Reference: {NAME} (Multi)'.format(NAME=item.text(0)),
                           lambda: self.multiReferenceMaya(item))

        elif item.parent():
            # print item.text(0), item.parent().text(0)
            # # if not item.parent().text(0) in ['branch','rig','clip']:
            menu.addAction(QtGui.QIcon(), menuTitle.format(NAME=item.text(0)), lambda : self.referenceShotImport(item))
            menu.addAction(QtGui.QIcon(), menuTitle.format(NAME=item.text(0)) + ' (SceneAssembly)', lambda : self.referenceShotAssemblyImport(item))

        else:
            return
        menu.popup(QtGui.QCursor.pos())

    def referenceImport(self, item):
        assetName = item.text(0)
        rootDir   = item.text(1)
        print assetName, rootDir
        if not rootDir:
            if self.ui.showEdit.text() == '/assetlib/_3d':
                rootDir = '{DIR}/asset/{NAME}'.format(DIR=self.ui.showEdit.text(), NAME=assetName)
            else:
                rootDir = '/show/{DIR}/_3d/asset/{NAME}'.format(DIR=self.ui.showEdit.text(), NAME=assetName)

        filename = '{DIR}/{NAME}.usd'.format(DIR=rootDir, NAME=assetName)

        if cmds.pluginInfo('TaneForMaya', q=True, l=True):
            selected = cmds.ls(sl=True, dag=True, type='TN_Tane')
            if selected:
                self.referenceTane(selected[0], assetName, filename)
            else:
                dxBlockUtils.ImportPxrProxy(filename)
        else:
            dxBlockUtils.ImportPxrProxy(filename)


    def referenceShotImport(self,item):
        assetName = item.parent().text(0)
        shotName = item.text(0)
        rootDir   = item.text(1)
        if not rootDir:
            if '_' in shotName:
                seq = shotName.split('_')[0]
                shot = shotName
                rootDir = '/show/{DIR}/_3d/shot/{SEQ}/{SHOT}/asset/{NAME}'.format(DIR=self.ui.showEdit.text(), SEQ =seq ,SHOT = shot ,NAME=assetName)
            else:
                seq = shotName
                rootDir = '/show/{DIR}/_3d/shot/{SEQ}/asset/{NAME}'.format(DIR=self.ui.showEdit.text(), SEQ=seq, NAME=assetName)

        filename = '{DIR}/{NAME}.usd'.format(DIR=rootDir, NAME=assetName)
        if cmds.pluginInfo('TaneForMaya', q=True, l=True):
            selected = cmds.ls(sl=True, dag=True, type='TN_Tane')
            if selected:
                self.referenceTane(selected[0], assetName, filename)
            else:
                dxBlockUtils.ImportPxrProxy(filename)
        else:
            dxBlockUtils.ImportPxrProxy(filename)

    def referenceAssemblyImport(self, item):
        assetName = item.text(0)
        rootDir   = item.text(1)
        if not rootDir:
            if self.ui.showEdit.text() == '/assetlib/_3d':
                rootDir = '{DIR}/asset/{NAME}'.format(DIR=self.ui.showEdit.text(), NAME=assetName)
            else:
                rootDir = '/show/{DIR}/_3d/asset/{NAME}'.format(DIR=self.ui.showEdit.text(), NAME=assetName)

        filename = '{DIR}/{NAME}.usd'.format(DIR=rootDir, NAME=assetName)
        dxBlockUtils.ImportPxrReference(filename)

    def referenceShotAssemblyImport(self, item):
        assetName = item.parent().text(0)
        shotName = item.text(0)
        rootDir   = item.text(1)
        if not rootDir:
            if '_' in shotName:
                seq = shotName.split('_')[0]
                shot = shotName
                rootDir = '/show/{DIR}/_3d/shot/{SEQ}/{SHOT}/asset/{NAME}'.format(DIR=self.ui.showEdit.text(), SEQ =seq ,SHOT = shot ,NAME=assetName)
            else:
                seq = shotName
                rootDir = '/show/{DIR}/_3d/shot/{SEQ}/asset/{NAME}'.format(DIR=self.ui.showEdit.text(), SEQ=seq, NAME=assetName)

        filename = '{DIR}/{NAME}.usd'.format(DIR=rootDir, NAME=assetName)
        dxBlockUtils.ImportPxrReference(filename)


    def referenceTane(self, taneShape, assetName, sourceFile):
        environmentNode = cmds.listConnections(taneShape, s=True, d=False, type='TN_Environment')
        assert environmentNode, '# msg : tane setup error'
        environmentNode = environmentNode[0]
        index = 0
        for idx in range(0, 100):
            if not cmds.connectionInfo("%s.inSource[%d]" % (environmentNode, idx), ied=True):
                index = idx
                break
        proxyShape = cmds.TN_CreateNode(nt='TN_UsdProxy')
        proxyTrans = cmds.listRelatives(proxyShape, p=True)[0]
        cmds.setAttr('%s.visibility' % proxyTrans, 0)
        cmds.setAttr('%s.renderFile' % proxyShape, sourceFile, type='string')
        cmds.connectAttr('%s.outSource' % proxyShape, '%s.inSource[%d]' % (environmentNode, index))

        proxyTrans = cmds.rename(proxyTrans, 'TN_%s' % assetName)

        taneTrans = cmds.listRelatives(taneShape, p=True)[0]
        cmds.parent(proxyTrans, taneTrans)
        cmds.select(taneTrans)


    def importAsset(self):
        item = self.ui.treeWidget.currentItem()
        if not item:
            cmds.confirmDialog(
                title='Warning', message='first, select item',icon='warning', button=['OK']
            )
            return

        selected = cmds.ls(sl=True)
        filePath = item.text(1)

        if "_rig_" in item.text(0):
            assetName = item.text(0).split("_rig_")[0]
            if '/branch/' in filePath:
                assetName = filePath.split('/branch/')[-1].split('/')[0]
            rigFilePath = os.path.join(filePath, "%s_rig.usd" % assetName)
            dxBlockUtils.UsdImport(rigFilePath).doIt()

        else:
            if os.path.isdir(filePath): # version directory
                for fileName in os.listdir(filePath):
                    if "high_geom.usd" in fileName or "mid_geom.usd" in fileName or "low_geom.usd" in fileName:
                        nodeList = utl.UsdImport(os.path.join(filePath, fileName)).doIt()
                        for node in nodeList:
                            self.postProcess(node, selected, version=item.text(0), usdfile=os.path.join(filePath, fileName))

            else:
                nodeList = utl.UsdImport(filePath).doIt()
                for node in nodeList:
                    self.postProcess(node, selected, version=item.text(2), usdfile=filePath)

    # Under Post Process
    def postProcess(self, node, selected, **kwargs):
        # curve post process
        if kwargs.has_key('usdfile'):
            dxBlockUtils.common.ImportGeomPostProcess(kwargs['usdfile'], node).doIt()

        # model version postProcess
        for mesh in cmds.ls(node, dag=True, type='shape', l=True):
            self.setAttribute(mesh, attr="modelVersion", value=kwargs['version'])

        # parenting post process
        if selected:
            cmds.parent(node, selected[0])
        cmds.select(node)

    def setAttribute(self, mesh, attr, value):
        if not cmds.attributeQuery(attr, n=mesh, exists=True):
            cmds.addAttr(mesh, ln=attr, dt='string')
            cmds.setAttr("%s.%s" % (mesh, attr), value, type='string')


    def referenceMaya(self, item):
        assetName = item.text(0).split("_rig_")[0]
        rootDir   = item.text(1)
        rootDir = rootDir.split(item.text(0))[0]
        filename = '{DIR}scenes/{NAME}.mb'.format(DIR=rootDir, NAME=item.text(0))

        namespace = assetName
        if cmds.namespace(exists=namespace) == True:
            namespace += '1'

        node = mel.eval("file -r -gl -namespace \"%s\" -lrd \"all\" -options \"v=0\" \"%s\"" % (namespace, filename))

        try:
            #Add Attribute in reference node
            topNode = cmds.referenceQuery(node, nodes=True)[0] # Result: bear1:bear_rig_GRP #
            assetName = cmds.getAttr('%s.assetName' % topNode) # Result: bear #
            rnNode = cmds.referenceQuery(node, referenceNode=True, topReference=True) # Result: bearRN1 #
            cmds.lockNode(rnNode, lock=False)
            cmds.addAttr(rnNode, longName='assetName', niceName='assetName', dataType="string")
            cmds.setAttr('%s.assetName' % rnNode, assetName, type='string')
            cmds.lockNode(rnNode, lock=True)
        except:
            print '// Error: ref Node set attr error'

    def multiReferenceMaya(self,item):
        assetName = item.text(0).split("_rig_")[0]
        rootDir   = item.text(1)
        rootDir = rootDir.split(item.text(0))[0]
        filename = '{DIR}scenes/{NAME}.mb'.format(DIR=rootDir, NAME=item.text(0))

        namespace = assetName
        if cmds.namespace(exists=namespace) == True:
            namespace += '1'

        # get number
        mi = multiImportDialog()
        mi.show()
        result = mi.exec_()
        if result == 1:
            num = mi.item
            for i in range(num):
                node = mel.eval(
                    "file -r -gl -namespace \"%s\" -lrd \"all\" -options \"v=0\" \"%s\"" % (namespace, filename))
                try:
                    topNode = cmds.referenceQuery(node, nodes=True)[0]
                    assetName = cmds.getAttr('%s.assetName' % topNode)
                    rnNode = cmds.referenceQuery(node, referenceNode=True, topReference=True)
                    cmds.lockNode(rnNode, lock=False)
                    cmds.addAttr(rnNode, longName='assetName', niceName='assetName', dataType="string")
                    cmds.setAttr('%s.assetName' % rnNode, assetName, type='string')
                    cmds.lockNode(rnNode, lock=True)
                except:
                    print '// Error: ref Node set attr error'

# import multiple asset by namespace
class multiImportDialog(QtWidgets.QDialog):
    def __init__(self):
        QtWidgets.QDialog.__init__(self)
        # ui
        label = QtWidgets.QLabel("Number of Copies:")
        self.numRerference = QtWidgets.QSpinBox()
        self.numRerference.setRange(1, 1000)
        self.ok_btn = QtWidgets.QPushButton("Ok")
        self.close_btn = QtWidgets.QPushButton("Close")
        layout2 = QtWidgets.QHBoxLayout()
        layout2.addWidget(self.ok_btn)
        layout2.addWidget(self.close_btn)
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(label)
        layout.addWidget(self.numRerference)
        layout.addLayout(layout2)
        self.setLayout(layout)
        self.setWindowTitle("Multiple Reference Import")
        #connection
        self.ok_btn.clicked.connect(self.outNum)
        self.close_btn.clicked.connect(self.reject)

    def outNum(self):
        self.item = self.numRerference.value()
        self.accept()



def main():
    if cmds.window(__windowName__, exists = True):
        cmds.deleteUI(__windowName__)

    window = AssetImportTool()
    window.setObjectName(__windowName__)
    window.show()
    QtWidgets.QApplication.processEvents()
    window.changeAssetListCompleter()
