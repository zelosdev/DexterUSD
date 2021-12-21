#coding:utf-8
from __future__ import print_function
import os

from pxr import Sdf, Usd

import DXUSD.Tweakers as twk
import DXUSD.Arcs as arc
import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg


class ASample(twk.ATweaker):
    '''
    >>> ASample
    '''
    def __init__(self, **kwargs):
        ATweaker.__init__(self, **kwargs)

    def Treat(self):
        return var.SUCCESS



class Sample(twk.Tweaker):
    '''
    >>> Sample
    '''
    ARGCLASS = ASample

    def DoIt(self):
        return var.SUCCESS
