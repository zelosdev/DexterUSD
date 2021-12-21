#coding:utf-8
from __future__ import print_function
import os

from pxr import Sdf, Usd

from .Tweaker import Tweaker, ATweaker
import DXUSD.Arcs as arc
import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg


class AModifyReference(ATweaker):
    '''
    >>> AModifyReference
    '''
    def __init__(self, **kwargs):
        ATweaker.__init__(self, **kwargs)

    def Treat(self):
        return var.SUCCESS



class ModifyReference(Tweaker):
    '''
    >>> ModifyReference
    '''
    ARGCLASS = AModifyReference

    def DoIt(self):
        return var.SUCCESS
