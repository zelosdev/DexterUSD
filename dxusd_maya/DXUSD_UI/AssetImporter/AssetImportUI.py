# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'AssetImportUI.ui'
#
# Created: Thu Dec  6 11:57:56 2018
#      by: PyQt4 UI code generator 4.10.3
#
# WARNING! All changes made in this file will be lost!

from PySide2 import QtCore
from PySide2 import QtGui
from PySide2 import QtWidgets

import os
currentDir = os.path.dirname(__file__)

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtWidgets.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtWidgets.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtWidgets.QApplication.translate(context, text, disambig)

class Ui_Form(object):
    def setupUi(self, Form):
        Form.setObjectName(_fromUtf8("Form"))
        Form.resize(678, 834)
        Form.setStyleSheet(_fromUtf8("background-color: rgb(90,90,90)"))
        self.verticalLayout = QtWidgets.QVBoxLayout(Form)
        self.verticalLayout.setSpacing(3)
        self.verticalLayout.setMargin(0)
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setObjectName(_fromUtf8("horizontalLayout"))
        self.label = QtWidgets.QLabel(Form)
        self.label.setMaximumSize(QtCore.QSize(70, 16777215))
        self.label.setStyleSheet(_fromUtf8("background-color: rgb(136, 136, 198);padding:  0 0 0 20 px;"))
        self.label.setText(_fromUtf8(""))
        self.label.setPixmap(QtGui.QPixmap(_fromUtf8("%s/resources/USDLogo.png" % currentDir)))
        self.label.setObjectName(_fromUtf8("label"))
        self.horizontalLayout.addWidget(self.label)
        self.label_2 = QtWidgets.QLabel(Form)
        self.label_2.setMinimumSize(QtCore.QSize(0, 70))
        font = QtGui.QFont()
        font.setPointSize(30)
        font.setBold(True)
        font.setWeight(75)
        self.label_2.setFont(font)
        self.label_2.setStyleSheet(_fromUtf8("background-color: rgb(136, 136, 198);color: rgb(255, 255, 255);"))
        self.label_2.setObjectName(_fromUtf8("label_2"))
        self.horizontalLayout.addWidget(self.label_2)
        self.label_3 = QtWidgets.QLabel(Form)
        self.label_3.setMinimumSize(QtCore.QSize(0, 70))
        font = QtGui.QFont()
        font.setPointSize(11)
        font.setBold(True)
        font.setWeight(75)
        self.label_3.setFont(font)
        self.label_3.setStyleSheet(_fromUtf8("background-color: rgb(136, 136, 198)"))
        self.label_3.setText(_fromUtf8(""))
        self.label_3.setAlignment(QtCore.Qt.AlignBottom|QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing)
        self.label_3.setObjectName(_fromUtf8("label_3"))
        self.horizontalLayout.addWidget(self.label_3)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setContentsMargins(6, -1, 6, -1)
        self.horizontalLayout_2.setObjectName(_fromUtf8("horizontalLayout_2"))
        self.label_4 = QtWidgets.QLabel(Form)
        self.label_4.setMinimumSize(QtCore.QSize(80, 0))
        self.label_4.setMaximumSize(QtCore.QSize(80, 16777215))
        font = QtGui.QFont()
        font.setPointSize(13)
        font.setBold(True)
        font.setWeight(75)
        self.label_4.setFont(font)
        self.label_4.setStyleSheet(_fromUtf8("color : white;background-color: rgb(90,90,90);padding : 0 5 0 5 px;"))
        self.label_4.setObjectName(_fromUtf8("label_4"))
        self.horizontalLayout_2.addWidget(self.label_4)
        self.showEdit = QtWidgets.QLineEdit(Form)
        font = QtGui.QFont()
        font.setPointSize(13)
        font.setBold(True)
        font.setWeight(75)
        self.showEdit.setFont(font)
        self.showEdit.setStyleSheet(_fromUtf8("color : white"))
        self.showEdit.setText(_fromUtf8(""))
        self.showEdit.setObjectName(_fromUtf8("showEdit"))
        self.horizontalLayout_2.addWidget(self.showEdit)
        self.verticalLayout.addLayout(self.horizontalLayout_2)
        self.line = QtWidgets.QFrame(Form)
        self.line.setFrameShape(QtWidgets.QFrame.HLine)
        self.line.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.line.setObjectName(_fromUtf8("line"))
        self.verticalLayout.addWidget(self.line)
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_3.setContentsMargins(6, -1, 6, -1)
        self.horizontalLayout_3.setObjectName(_fromUtf8("horizontalLayout_3"))
        self.label_5 = QtWidgets.QLabel(Form)
        self.label_5.setMinimumSize(QtCore.QSize(80, 0))
        self.label_5.setMaximumSize(QtCore.QSize(80, 16777215))
        font = QtGui.QFont()
        font.setPointSize(13)
        font.setBold(True)
        font.setWeight(75)
        self.label_5.setFont(font)
        self.label_5.setStyleSheet(_fromUtf8("color : white;background-color: rgb(90,90,90);padding : 0 5 0 5 px;"))
        self.label_5.setObjectName(_fromUtf8("label_5"))
        self.horizontalLayout_3.addWidget(self.label_5)
        self.assetEdit = QtWidgets.QLineEdit(Form)
        font = QtGui.QFont()
        font.setPointSize(13)
        font.setBold(True)
        font.setWeight(75)
        self.assetEdit.setFont(font)
        self.assetEdit.setStyleSheet(_fromUtf8("color : white"))
        self.assetEdit.setText(_fromUtf8(""))
        self.assetEdit.setObjectName(_fromUtf8("assetEdit"))
        self.horizontalLayout_3.addWidget(self.assetEdit)
        self.verticalLayout.addLayout(self.horizontalLayout_3)
        self.line_2 = QtWidgets.QFrame(Form)
        self.line_2.setFrameShape(QtWidgets.QFrame.HLine)
        self.line_2.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.line_2.setObjectName(_fromUtf8("line_2"))
        self.verticalLayout.addWidget(self.line_2)
        self.frame = QtWidgets.QFrame(Form)
        self.frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.frame.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame.setObjectName(_fromUtf8("frame"))
        self.gridLayout_2 = QtWidgets.QGridLayout(self.frame)
        self.gridLayout_2.setObjectName(_fromUtf8("gridLayout_2"))
        self.treeWidget = QtWidgets.QTreeWidget(self.frame)
        # self.treeWidget.setStyleSheet(_fromUtf8(""))
        self.treeWidget.setObjectName(_fromUtf8("treeWidget"))
        self.treeWidget.header().setVisible(False)
        self.gridLayout_2.addWidget(self.treeWidget, 0, 0, 1, 1)
        self.verticalLayout.addWidget(self.frame)
        self.importBtn = QtWidgets.QPushButton(Form)
        font = QtGui.QFont()
        font.setPointSize(20)
        font.setBold(True)
        font.setWeight(75)
        self.importBtn.setFont(font)
        self.importBtn.setStyleSheet(_fromUtf8("color : white;background-color: rgb(136, 136, 198);"))
        self.importBtn.setObjectName(_fromUtf8("importBtn"))
        self.verticalLayout.addWidget(self.importBtn)

        self.retranslateUi(Form)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        Form.setWindowTitle(_translate("Form", "Asset USD Import", None))
        self.label_2.setText(_translate("Form", "ASSET IMPORT", None))
        self.label_4.setText(_translate("Form", "SHOW", None))
        self.label_5.setText(_translate("Form", "ASSET ", None))
        self.importBtn.setText(_translate("Form", "MODEL IMPORT", None))

