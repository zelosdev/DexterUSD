#coding:utf-8
import os, sys
from PySide2 import QtWidgets, QtGui, QtCore

class UpdateLoopClipGeomDialog(QtWidgets.QDialog):
    def __init__(self, clipBaseDir, parent=None):
        QtWidgets.QDialog.__init__(self, parent)
        self.setWindowTitle('Update Loop Clip Geom')
        self.setMinimumSize(800, 150)

        self.error = False

        gridLayout = QtWidgets.QGridLayout(self)
        gridLayout.setSizeConstraint(QtWidgets.QLayout.SetDefaultConstraint)

        clipBaseDirText = clipBaseDir
        if not clipBaseDir.endswith('/base'):
            clipBaseDir = '%s/base' % clipBaseDir

        if  not os.path.isdir(clipBaseDir) or clipBaseDir.count('/show/') < 1 or clipBaseDir.count('/clip/') < 1 or not clipBaseDir.endswith('/base'):
            if clipBaseDirText.count('/') > 0:
                clipBaseDirText = 'Directory error'
            self.error = True
            self.setWindowTitle('Error Update Loop Clip Geom')
            label = QtWidgets.QLabel()
            usageText   = clipBaseDirText+'\n'
            usageText += '1. Right click at asset clip directory\n'
            usageText += '  EX> /show/XXX/_3d/asset/XXX/clip/run/v001(/base)\n'
            usageText += '2. Time Scales value required.'
            label.setText(usageText)
            gridLayout.addWidget(label, 0, 0, 1, 1)

        else:
            label = QtWidgets.QLabel()
            label.setText('Clip Base Dir')
            gridLayout.addWidget(label, 0, 0, 1, 1)

            self.clipBaseDir = QtWidgets.QLineEdit()
            self.clipBaseDir.setText(clipBaseDir)
            self.clipBaseDir.setPlaceholderText('If you enter a shot name, only the shot is set. Separate the shot names with spaces.')
            gridLayout.addWidget(self.clipBaseDir, 0, 1, 1, 3)

            label2 = QtWidgets.QLabel()
            label2.setText('Time Scales')
            gridLayout.addWidget(label2, 1, 0, 1, 1)

            self.timeScales = QtWidgets.QLineEdit()
            self.timeScales.setPlaceholderText('0.1,2.0')
            # self.timeScales.setFocusPolicy(QtCore.Qt.StrongFocus)
            gridLayout.addWidget(self.timeScales, 1, 1, 1, 1)

            label3 = QtWidgets.QLabel()
            label3.setText('Loop Range')
            gridLayout.addWidget(label3, 1, 2, 1, 1)

            self.loopRange = QtWidgets.QLineEdit()
            self.loopRange.setPlaceholderText('1001,5000(Optional)')
            gridLayout.addWidget(self.loopRange, 1, 3, 1, 1)
            
            cancelBtn = QtWidgets.QPushButton()
            cancelBtn.setText("&CANCEL")
            cancelBtn.clicked.connect(self.reject)
            gridLayout.addWidget(cancelBtn, 2, 2, 1, 2)

            self.timeScales.setFocus()

        okBtn = QtWidgets.QPushButton()
        okBtn.setText("&OK")
        okBtn.setDefault(True)
        okBtn.clicked.connect(self.accept)
        gridLayout.addWidget(okBtn, 2, 0, 1, 2)

        self.setLayout(gridLayout)
        
        self.exec_()

    def accept(self):
        self.result = True
        self.close()

    def reject(self):
        self.result = False
        self.close()

    def closeEvent(self, event):
        print "Event"
        event.accept()

app = QtWidgets.QApplication(sys.argv)