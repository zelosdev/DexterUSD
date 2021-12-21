#coding:utf-8
from __future__ import print_function

import maya.cmds as cmds

import DXUSD.Exporters as exp
import DXUSD.Utils as utl


class MAYA_ExampleExporter(exp.ExampleExporter):
    def Exporting(self):
        usdfile = self.arg.srclyr.place

        options = [ '',
        'shadingMode=none',
        'materialsScopeName=Looks',
        'exportDisplayColor=0',
        'exportRefsAsInstanceable=0',
        'exportUVs=1',
        'exportMaterialCollections=0',
        'materialCollectionsPath=',
        'exportCollectionBasedBindings=0',
        'exportColorSets=1',
        'exportReferenceObjects=0',
        'renderableOnly=0',
        'filterTypes=;defaultCameras=0',
        'renderLayerMode=defaultLayer',
        'mergeTransformAndShape=1',
        'exportInstances=1',
        'defaultMeshScheme=catmullClark',
        'exportSkels=none',
        'exportSkin=none',
        'exportVisibility=0',
        'stripNamespaces=0',
        'animation=0',
        'eulerFilter=0',
        'startTime=1',
        'endTime=1',
        'frameStride=1',
        'parentScope=',
        'compatibility=none' ]

        cmds.file(usdfile, force=True, es=True, type='pxrUsdExport',
                  options=';'.join(options))

def Export():
    sels = cmds.ls(sl=True)
    for sel in sels:
        name = sel.split('|')[-1]

        arg = exp.AExampleExporter()
        arg.srclyr.name = name
        arg.show = 'pipe'
        arg.ver  = utl.Ver(1)

        MAYA_ExampleExporter(arg)
