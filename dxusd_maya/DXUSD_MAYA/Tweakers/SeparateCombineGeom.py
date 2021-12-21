#coding:utf-8
from __future__ import print_function
import os, glob, re

from pxr import Usd, Sdf, UsdUtils, Vt

import DXUSD.Vars as var

from DXUSD.Tweakers.Tweaker import Tweaker, ATweaker
import DXUSD_MAYA.Utils as utl


class ASeparateCombineGeom(ATweaker):
    def __init__(self, **kwargs):
        self.separate_geomfiles = []    # exported subframe geom final filenames
        # initialize
        ATweaker.__init__(self, **kwargs)

    def Treat(self):
        if not self.separate_geomfiles:
            return var.IGNORE

        return var.SUCCESS


class SeparateCombineGeom(Tweaker):
    ARGCLASS = ASeparateCombineGeom
    def DoIt(self):
        print('#### SeparateCombineGeom Stitch ####')

        # for f in self.arg.separate_geomfiles:
        self.Treat()

        return var.SUCCESS

    def Treat(self):
        # source sequence files
        # source = self.getSource(outfile)
        source = self.arg.separate_geomfiles
        splitSoureFile = source[0].split('.')
        outfile = '%s.%s.%s' % (splitSoureFile[0], splitSoureFile[-3], splitSoureFile[-1])

        # for f in source:
        #     self.RemoveMeshProperties(f)

        # create topology
        topologyFile = outfile.replace('.usd', '.topology.usd')
        topologyLayer= utl.AsLayer(topologyFile, create=True, clear=True)
        UsdUtils.StitchClipsTopology(topologyLayer, [source[-1]])

        # create clip
        self.CreateClips(outfile, topologyFile, source)

        # original geomfile
        # geomfile = outfile.split('_geomsub')[0] + '_geom.usd'
        # geomfile = outfile.replace('_geomsub.usd', '_geom.usd')
        # self.vsRemoveMeshProperties(geomfile, outfile)

        # comp subframe geom
        # dstlyr = utl.AsLayer(geomfile)
        # utl.SubLayersAppend(dstlyr, './' + os.path.basename(outfile))
        # dstlyr.Save()
        # del dstlyr


    def getSource(self, filename):
        result = list()
        files  = glob.glob(filename.replace('.usd', '.*.usd'))
        files.sort()
        for f in files:
            frame = re.findall(r'\.(\d+)?\.usd', f)
            if frame:
                result.append(f)
        return result

    def getInfo(self, source):
        dname = None
        times = list()

        for f in source:
            layer = utl.AsLayer(f)
            dname = layer.defaultPrim
            times.append((layer.startTimeCode, layer.endTimeCode))

        return dname, times


    # def RemoveMeshProperties(self, filename):
    #     # remove property names
    #     names = ['faceVertexCounts', 'faceVertexIndices']
    #
    #     layer = utl.AsLayer(filename)
    #     stage = Usd.Stage.Open(layer)
    #     for p in iter(Usd.PrimRange.AllPrims(stage.GetDefaultPrim())):
    #         if p.GetTypeName() == 'Mesh':
    #             ppath = p.GetPrimPath()
    #             spec  = layer.GetPrimAtPath(ppath)
    #             for n in names:
    #                 attr = spec.properties.get(n)
    #                 if attr:
    #                     spec.RemoveProperty(attr)
    #
    #     tmpfile = filename.replace('.usd', '_tmp.usd')
    #     layer.Export(tmpfile)
    #     del stage
    #     del layer
    #
    #     os.remove(filename)
    #     os.rename(tmpfile, filename)
    #
    # def vsRemoveMeshProperties(self, target, source):
    #     # remove property names
    #     names = ['extent', 'points']
    #
    #     outlyr = utl.AsLayer(target)
    #     srclyr = utl.AsLayer(source)
    #
    #     with utl.OpenStage(srclyr) as stage:
    #         for p in iter(Usd.PrimRange.AllPrims(stage.GetDefaultPrim())):
    #             if p.GetTypeName() == 'Mesh':
    #                 ppath = p.GetPrimPath()
    #                 spec  = outlyr.GetPrimAtPath(ppath)
    #                 for n in names:
    #                     attr = spec.properties.get(n)
    #                     if attr:
    #                         spec.RemoveProperty(attr)
    #
    #     outlyr.Save()
    #     del outlyr
    #     del srclyr


    def CreateClips(self, outfile, topology, source):
        dname, times = self.getInfo(source)

        outlyr = utl.AsLayer(outfile, create=True, clear=True)
        outlyr.defaultPrim = dname
        outlyr.startTimeCode = times[0][0]
        outlyr.endTimeCode   = times[-1][1]

        spec = utl.GetPrimSpec(outlyr, '/' + dname, specifier='over')
        utl.SubLayersAppend(outlyr, './' + os.path.basename(topology))

        assetPaths = list()
        for f in source:
            assetPaths.append(Sdf.AssetPath('./' + os.path.basename(f)))

        active_times = list()
        stage_times  = list()
        for i in range(len(times)):
            active_times.append((times[i][0], i))
            stage_times.append((times[i][0], times[i][0]))
            stage_times.append((times[i][1], times[i][1]))

        # clips
        data = {
            'active': Vt.Vec2dArray(active_times),
            'assetPaths': Sdf.AssetPathArray(assetPaths),
            'manifestAssetPath': Sdf.AssetPath('./' + os.path.basename(topology)),
            'primPath': '/' + dname,
            'times': Vt.Vec2dArray(stage_times)
        }
        spec.SetInfo('clips', {'default': data})

        if self.arg.customLayerData:
            tmp = outlyr.customLayerData
            tmp.update(self.arg.customLayerData)
            outlyr.customLayerData = tmp

        outlyr.Save()
        del outlyr
