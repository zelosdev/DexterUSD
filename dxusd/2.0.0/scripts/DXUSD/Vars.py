#coding:utf-8
import os, re

import DXRulebook.Interface as rb
from pxr import Sdf, UsdGeom

# ------------------------------------------------------------------------------
# Common
# ------------------------------------------------------------------------------

# path seperator
SEP  = os.path.sep
_SEP = '.' + SEP

# return values
FAILED  = 0
SUCCESS = 1
IGNORE  = 2


# ------------------------------------------------------------------------------
# USD Common
# ------------------------------------------------------------------------------
_DXVER = '2.0.0'

USD  = 'usd'
USDA = 'usda'
USDC = 'usdc'
USDZ = 'usdz'

_USD    = '.'+USD
_USDA   = '.'+USDA
_TMPUSD = '.tmp'+_USD

PROXY  = UsdGeom.Tokens.proxy
RENDER = UsdGeom.Tokens.render

DEF   = Sdf.SpecifierDef
OVER  = Sdf.SpecifierOver
CLASS = Sdf.SpecifierClass

class ARC:
    SUB = 'subLayer'
    INH = 'inherits'
    VAR = 'variantSets'
    REF = 'references'
    PAY = 'payload'
    SPE = 'specializes'

class KIND:
    MDL = 'model'
    GRP = 'group'
    ASB = 'assembly'
    COM = 'component'
    SUB = 'subcomponent'

# ------------------------------------------------------------------------------
# from rulebook
# ------------------------------------------------------------------------------
T = rb.Tags(USD.upper())
D = rb.Coder('D', USD.upper(), T.PUB3)
F = rb.Coder('F', USD.upper(), T.PUB3)
N = rb.Coder('N', USD.upper(), T.PUB3)
