#coding:utf-8
from __future__ import print_function

import DXUSD_HOU.Message as msg
import DXUSD_HOU.Utils as utl
import DXUSD_HOU.Vars as var
import DXUSD_HOU.Exporters as exp


def _TransferCommonAttrs(arg, lyr):
    arg.sequenced  = lyr.sequenced
    arg.task       = lyr.task.name
    arg.taskCode   = lyr.task.code
    arg.prctype    = lyr.prctype
    arg.srclyr     = lyr.outpath
    arg.timeLayers = lyr.cliprate
    arg.loopRange  = lyr.looprange
    arg.dependency = lyr.dependency


def GeomExport(lyrs):
    for lyr in lyrs:
        arg = exp.AGeomExporter(**lyr.arg)
        _TransferCommonAttrs(arg, lyr)
        exp.GeomExporter(arg)


def InstanceExport(lyrs):
    for lyr in lyrs:
        arg = exp.AInstanceExporter(**lyr.arg)
        _TransferCommonAttrs(arg, lyr)
        exp.InstanceExporter(arg)


def GroomExport(lyrs):
    for lyr in lyrs:
        arg = exp.AGroomExporter(**lyr.arg)
        _TransferCommonAttrs(arg, lyr)
        exp.GroomExporter(arg)

def FeatherExport(lyrs):
    for lyr in lyrs:
        arg = exp.AFeatherExporter(**lyr.arg)
        _TransferCommonAttrs(arg, lyr)
        exp.FeatherExporter(arg)


def CrowdExport(lyrs):
    pass

def VdbExport(lyrs):
    for lyr in lyrs:
        arg = exp.AVdbExporter(**lyr.arg)
        _TransferCommonAttrs(arg, lyr)
        exp.VdbExporter(arg)

def OceanExport(lyrs):
    for lyr in lyrs:
        arg = exp.AVdbExporter(**lyr.arg)
        _TransferCommonAttrs(arg, lyr)
        exp.VdbExporter(arg)

def HouExport(tasks, meta):
    msg.debug('#'*80)
    msg.debug('# Start Exporting')
    msg.debug('#'*80)
    msg.debug(tasks)
    msg.debug('#'*80)

    for task in tasks.items():
        for nslyr in task.items():
            for sublyr in nslyr.items():
                geomlyrs    = []
                instlyrs    = []
                groomlyrs   = []
                featherlyrs = []
                crowdlyrs   = []
                vdblyrs     = []
                oceanlyrs   = []

                for lyr in sublyr.items():
                    if lyr.lyrtype == var.LYRGEOM:
                        geomlyrs.append(lyr)
                    elif lyr.lyrtype == var.LYRINST:
                        instlyrs.append(lyr)
                    elif lyr.lyrtype == var.LYRGROOM:
                        groomlyrs.append(lyr)
                    elif lyr.lyrtype == var.LYRFEATHER:
                        featherlyrs.append(lyr)
                    elif lyr.lyrtype == var.LYRCROWD:
                        crowdlyrs.append(lyr)
                    elif lyr.lyrtype == var.LYRVDB:
                        vdblyrs.append(lyr)
                    elif lyr.lyrtype == var.LYROCEAN:
                        oceanlyrs.append(lyr)

                GeomExport(geomlyrs)
                InstanceExport(instlyrs)
                GroomExport(groomlyrs)
                FeatherExport(featherlyrs)
                CrowdExport(crowdlyrs)
                VdbExport(vdblyrs)
                OceanExport(oceanlyrs)
