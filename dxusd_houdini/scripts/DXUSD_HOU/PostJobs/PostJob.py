#coding:utf-8
from __future__ import print_function

import DXUSD_HOU.Vars as var


class PostJob(object):
    def __init__(self, arg):
        self.__name__ = self.__class__.__name__
        self.arg = arg


    def Treat(self):
        return var.SUCCESS


    def DoIt(self):
        msg.errmsg('doIt@Tweaker : Must override doIt methode.')
        return var.FAILED
