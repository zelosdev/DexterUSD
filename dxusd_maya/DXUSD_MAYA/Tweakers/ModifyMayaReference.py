#coding:utf-8
from __future__ import print_function
import pprint
import os
from pxr import Gf, Sdf, Usd, Vt

import maya.api.OpenMaya as OpenMaya
import maya.cmds as cmds

import DXUSD.Vars as var

from DXUSD.Tweakers.Tweaker import Tweaker, ATweaker

import DXUSD_MAYA.Message as msg
import DXUSD_MAYA.MUtils as mutl
import DXUSD_MAYA.Utils as utl

'''
refData = {
    refName(Sdf.Path): {
        'filePath': reference file path,
        'nodes': [transform node, ...],
        'offset': dxTimeOffset node offset value,
        'primPath': get node attr,
        'excludePrimPaths': get node attr
    }
}
'''

class AModifyMayaReference(ATweaker):
    def __init__(self, **kwargs):
        '''
        [Arguments]
        geomfiles (list)
        invNodes  (list) : for PointInstancer.invisibleIds
        '''
        self.geomfiles = []
        self.invNodes  = []
        self.namespace = ''
        # initialize
        ATweaker.__init__(self, **kwargs)

    def Treat(self):
        if not self.geomfiles:
            return var.IGNORE

        self.D.SetDecode(utl.DirName(self.geomfiles[0]))
        return var.SUCCESS


class ModifyMayaReference(Tweaker):
    ARGCLASS = AModifyMayaReference
    def DoIt(self):
        # TEST
        print('#### ModifyMayaReference ####')

        for f in self.arg.geomfiles:
            filePath = f.replace('.usd', '.topology.usd')
            if os.path.exists(filePath):
                f = filePath
            msg.debug('\t >>', f)
            self.Treat(f)

        return var.SUCCESS


    def getComputeNodes(self, srclyr):
        nodes = []
        with utl.OpenStage(srclyr, loadAll=False) as stage:
            dprim = stage.GetDefaultPrim()

            def ChildTraverse(prim):
                for p in prim.GetAllChildren():
                    if p.GetTypeName() == 'Xform':
                        mpath = p.GetPath().pathString.replace('/', '|')
                        if self.arg.namespace:
                            mpath = mpath.replace('|', '|%s:' % self.arg.namespace)
                        ntype = cmds.nodeType(mpath)
                        if ntype == 'pxrUsdReferenceAssembly':
                            nodes.append(mpath)
                        elif ntype == 'transform':
                            cns = cmds.listRelatives(mpath, c=True, f=True, type='pxrUsdProxyShape')
                            if cns:
                                nodes.append(cns[0])

                        if not p.HasAuthoredReferences():
                            ChildTraverse(p)

            ChildTraverse(dprim)
        return nodes


    def Treat(self, outfile):
        dstlyr = utl.AsLayer(outfile)
        if not dstlyr:
            return

        nodes = self.getComputeNodes(dstlyr)
        if not nodes:
            msg.debug('>>> %s: not found compute nodes.' % self.__name__)
            return

        # reference data
        self.RDATA = utl.GetReferenceData()
        refData    = self.RDATA.get(nodes)
        if not refData:
            msg.debug('>>> %s: not found reference data.' % self.__name__)
            return

        if msg.DEV:
            msg.debug('>>>> Reference Data')
            pprint.pprint(refData, width=20)

        # cleanup
        editor = Sdf.BatchNamespaceEdit()
        for p in self.RDATA.nullPrims:
            editor.Add(p, Sdf.Path.emptyPath)
        dstlyr.Apply(editor)

        for key, src in refData.items():
            msg.debug(key, src)
            instance = False
            if len(src['nodes']) > 1:
                if not self.arg.invNodes:
                    instance = True
                    self.AddInstanceSource(dstlyr, key, src)

            for n in src['nodes']:
                if self.arg.namespace:
                    n = n.replace('|%s:' % self.arg.namespace, '/')
                spec = dstlyr.GetPrimAtPath(n.replace('|', '/').replace(':', '_'))
                if spec:
                    spec.specifier = Sdf.SpecifierOver
                    spec.typeName  = ''
                    # clear reference
                    spec.referenceList.prependedItems.clear()
                    # clear variants
                    spec.variantSelections.clear()

                    name = self.RDATA.refNameToString(key)
                    spec.assetInfo = {'name': name}
                    spec.SetInfo('kind', 'subcomponent')

                    if instance:
                        spec.SetInfo('instanceable', True)
                        primPath = Sdf.Path('/_inst_src/%s' % name)
                        utl.SetSpecialize(primPath, spec, clear=True)
                    else:
                        relpath  = utl.GetRelPath(outfile, src['filePath'])
                        msg.debug(outfile)
                        msg.debug(src['filePath'])
                        primPath = Sdf.Path.emptyPath
                        if src.has_key('primPath'):
                            primPath = Sdf.Path(src['primPath'])
                        utl.ReferenceAppend(spec, relpath, offset=Sdf.LayerOffset(src['offset']))
                        # variant selection
                        utl.SetVariantSelections(spec, key)
                        # set include prim
                        utl.SetIncludePrim(spec, primPath, src['filePath'])
                        # set exclude prims
                        utl.SetExcludePrims(spec, src)
                        # set txVarNum
                        if src.has_key('txVarNum'):
                            utl.GetAttributeSpec(spec, 'primvars:txVarNum', src['txVarNum'], Sdf.ValueTypeNames.Int,
                                             info={'interpolation': 'constant'})

        # custom data
        default = dstlyr.defaultPrim
        root = dstlyr.GetPrimAtPath('/' + default)
        groupName = default.split('_')[0]
        if self.arg.assetName:
            groupName = self.arg.assetName
        utl.AddCustomData(root, 'groupName', groupName)

        dstlyr.Save()
        del dstlyr


    def AddInstanceSource(self, layer, refName, data):  # data is refData value
        '''
        parent  (Sdf.PrimSpec) :
        refName (Sdf.Path) :
        '''
        root = utl.GetPrimSpec(layer, '/_inst_src', specifier='class')
        name = self.RDATA.refNameToString(refName)
        spec = utl.GetPrimSpec(layer, root.path.AppendChild(name))
        spec.assetInfo = {'name': name}
        # archive source spec
        srcspec  = utl.GetPrimSpec(layer, spec.path.AppendChild('source'), specifier='over')
        srcspec.SetInfo('kind', 'component')
        relpath  = utl.GetRelPath(layer.identifier, data['filePath'])
        primPath = Sdf.Path.emptyPath
        if data.has_key('primPath'):
            primPath = Sdf.Path(data['primPath'])
        utl.ReferenceAppend(srcspec, relpath, offset=Sdf.LayerOffset(data['offset']), clear=True)
        # variant selection
        utl.SetVariantSelections(srcspec, refName)
        # add variant selection - preview = on
        srcspec.variantSelections.update({'preview': 'on'})
        # setup include prim
        utl.SetIncludePrim(spec, primPath, data['filePath'])
        # setup exclude prims
        utl.SetExcludePrims(srcspec, data)
