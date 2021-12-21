#coding:utf-8
from __future__ import print_function
import os

from pxr import Sdf, Usd

from .Tweaker import Tweaker, ATweaker
import DXUSD.Arcs as arc
import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg


class AStripNamespace(ATweaker):
    '''
    >>> AStripNamespace
    '''
    def __init__(self, **kwargs):
        ATweaker.__init__(self, **kwargs)

    def Treat(self):
        return var.SUCCESS



class StripNamespace(Tweaker):
    '''
    >>> StripNamespace
    '''
    ARGCLASS = AStripNamespace

    def DoIt(self):
        return var.SUCCESS
