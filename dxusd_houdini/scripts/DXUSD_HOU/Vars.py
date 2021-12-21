#coding:utf-8
from __future__ import print_function

import DXUSD.moduleloader as mdl
import DXUSD.Vars as var
DEV = mdl.importModule(__name__, var)
if DEV:
    rb.Reload()

NULL  = '__NULL__'
ORDER = '__ORDER__'
USDPATH = '__USDPATH__'
NSLYR   = '__NSLYR__'
SRCPATH  = '__SRCPATH__'
MASTERUSD = '__MASTERUSD__'
LYRTASK = '__LRYTASK__'
GEOMDPRIM = '__GEOMDPRIM__'

PADDING4 = '`padzero(4, $F)`'
PADDING5 = '`padzero(5, $F)`'

LYRGEOM = 'geom'
LYRINST = 'inst'
LYRGROOM = 'groom'
LYRCROWD = 'crowd'
LYRFEATHER = 'feather'
LYRVDB = 'vdb'
LYROCEAN = 'ocean'

LYRTYPES = [
    LYRGEOM,
    LYRINST,
    LYRGROOM,
    LYRCROWD,
    LYRFEATHER,
    LYRVDB,
    LYROCEAN
]

PRCNONE = 'none'
PRCCLIP = 'clip'
PRCSIM  = 'sim'
PRCFX   = 'fx'

PRCTYPES = [
    PRCNONE,
    PRCCLIP,
    PRCSIM,
    PRCFX
]

DEPEND = 'depend'
PATH = 'path'
VARS = 'vars'
DEPENDPATH  = DEPEND + ':%s:%s:' + PATH
DEPENDVARS  = DEPEND + ':%s:%s:' + VARS
DEPENDNSLYR = DEPEND + ':%s:%s:nslyr'
DEPENDSRCPATH = DEPEND + ':%s:%s:srcpath'
DEPENDGEOMDPRIM = DEPEND + ':%s:%s:geomdprim'

UNKNOWN = '*** UNKOWN ***'
