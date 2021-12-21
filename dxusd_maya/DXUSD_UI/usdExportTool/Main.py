# -*- coding: utf-8 -*-
import os
import sys
from PySide2 import QtWidgets
from PySide2 import QtGui
import MainForm

ScriptRoot = os.path.dirname(os.path.abspath(__file__))

def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle(QtWidgets.QStyleFactory.create("plastique"))
    nautilusFile = os.environ.get('NAUTILUS_SCRIPT_SELECTED_FILE_PATHS')
    setFile = ''
    if nautilusFile:
        setFile = nautilusFile.split('\n')[0]
    mainVar = MainForm.MainForm(None, setFile)
    mainVar.move(QtWidgets.QDesktopWidget().availableGeometry().center() - mainVar.frameGeometry().center())
    mainVar.setWindowTitle('USD Export')
    iconpath = '%s/ui/pxr_usd.png' % ScriptRoot
    mainVar.setWindowIcon(QtGui.QIcon(QtGui.QPixmap(iconpath)))
    mainVar.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
