# -*- coding: utf-8 -*-
import os
import datetime
import getpass
import shutil

class dxTmp():
    def __init__(self, originFile):
        self.orgFile = originFile
        self.backupDirName = "backup"

        self.setTimeStampFormat()
        self.username = getpass.getuser()
        self.isPub = False
        self.dirPrefix = ""

        self.tmpFilePath = ""
        self.calcTmpFile()

    def setDirPrefix(self, prefix = ""):
        self.dirPrefix = prefix

    def setBackupDirName(self, backup = "backup"):
        self.backupDirName = backup

    def setTimeStampFormat(self, format = "%d%m%y-%H%M%S"):
        self.timestampFormat = format

    def changePub(self):
        self.isPub = True

    def calcTmpFile(self):
        directory = os.path.dirname(self.orgFile)
        filename, extension = os.path.splitext(os.path.basename(self.orgFile))
        timestamp = datetime.datetime.now().strftime(self.timestampFormat)

        newFileName = "{originFileName}--{user}_{timestamp}{extension}".format(originFileName = filename,
                                                                               user = self.username,
                                                                               timestamp = timestamp,
                                                                               extension = extension)

        self.tmpFilePath = "{DIR}/{BACKUP}/{FILENAME}".format(DIR = directory,
                                                              BACKUP = self.backupDirName,
                                                              FILENAME = newFileName)

        if self.dirPrefix:
            self.tmpFilePath = self.dirPrefix + self.tmpFilePath

        if self.isPub:
            self.tmpFilePath = self.tmpFilePath.replace("/dev/", "/pub/")

    def save(self):
        if not os.path.exists(os.path.dirname(self.tmpFilePath)):
            os.makedirs(os.path.dirname(self.tmpFilePath))

        shutil.copyfile(self.orgFile, self.tmpFilePath)
        return self.tmpFilePath

    def __str__(self):
        return self.tmpFilePath