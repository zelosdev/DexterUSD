#coding:utf-8
from __future__ import print_function

import hou
import DXUSD_HOU.Message as msg
import DXUSD_HOU.Vars as var
import DXUSD_HOU.Utils as utl
import DXUSD_HOU.Structures as srt

import HOU_Base.NodeUtils as ntl

from DXUSD.Structures import Arguments
from pxr import Sdf
import os


LYRPARMS = ['nslyr', 'lyrname', 'dprim', 'sublyr']

def ShowLayerResParms(node, *args):
    for parmname in LYRPARMS:
        hide = parmname not in args
        if hide:
            node.parm(parmname).set('')
        node.parm(parmname).hide(hide)
        node.parm(parmname+'tgl').hide(hide)


def GetVariants(node, i, kind):
    res = {var.ORDER:[]}
    for j in range(node.parm('%svariantfolder%d'%(kind, i)).evalAsInt()):
        key = node.parm('%svariantset%d_%d'%(kind, i, j)).evalAsString()
        val = node.parm('%svariants%d_%d'%(kind, i, j)).evalAsString()
        res[key] = val
        res[var.ORDER].append(key)

    return res



def GetDependency(node):
    res = srt.Dependency()

    checked = []
    for i in range(node.parm('dependencyfolder').evalAsInt()):
        soppath = node.parm('dependencysoppath%d'%i).evalAsNode()
        nslyrname = node.parm('nslyrname%i'%i).evalAsString()
        if soppath:
            if soppath in checked:
                continue
            else:
                checked.append(soppath)
        else:
            continue

        # check shot
        if node.parm('shotvariantfolder%d'%i).evalAsInt():
            if res.shot:
                msg.warning('Already has another shot dependency')
                continue

            masterusd = node.parm('shotmasterpath%d'%i).evalAsString()
            path = utl.DirName(masterusd)
            try:
                args = var.D.Decode(path)
            except Exception as e:
                msg.errmsg(e)
                warnmsg = 'Failed decoding usdpath%d of %s node'
                msg.warning(warnmsg%(i, soppath))
                continue

            # args.nslyr = node.parm('shotnamespace%d'%i).evalAsString()

            vlist = GetVariants(node, i, var.T.SHOT)
            # reverse order becuase the last task version is used for this
            order = list(vlist[var.ORDER])
            order.reverse()


            # path = var.D.TASKNV.Encode(**args)
            # file = var.F[args.task].MASTER.Encode(**args)
            vlist[var.USDPATH] = masterusd # utl.SJoin(path, file)
            vlist[var.NSLYR] = nslyrname
            vlist[var.LYRTASK] = args.get(var.T.TASK)

            # find shot usd for source layer
            # TODO: 만약 sim 인 경우 ani 소스레이어 필요하다.
            if node.parm('assetvariantfolder%d'%i).evalAsInt():
                srcpath = node.parm('assetmasterpath%d'%i).evalAsString()
                vlist[var.SRCPATH] = srcpath

            res.shot = vlist

        # check asset and branch
        elif node.parm('assetvariantfolder%d'%i).evalAsInt():
            path = utl.DirName(node.parm('assetusdpath%d'%i).evalAsString())
            masterusd = node.parm('assetmasterpath%d'%i).evalAsString()
            geomdprim = node.parm('assetgeomdprim%d'%i).evalAsString()

            try:
                args = var.D.Decode(path)
            except Exception as e:
                msg.errmsg(e)
                warnmsg = 'Failed decoding assetusdpath%d of %s node'
                msg.warning(warnmsg%(i, soppath))
                continue

            for kind in [var.T.ASSET, var.T.BRANCH]:
                if res[kind]:
                    msg.warning('Already has %s dependency.'%kind)
                    continue

                vlist = GetVariants(node, i, kind)

                # check task
                if not vlist.has_key(var.T.TASK):
                    continue

                vlist[var.USDPATH] = masterusd
                vlist[var.NSLYR] = nslyrname
                vlist[var.GEOMDPRIM] = geomdprim
                vlist[var.LYRTASK] = vlist.get(var.T.TASK)

                res[kind] = vlist

    # set override variants
    # TODO: dependency structure have been changed, so below code and houdini
    # parameter also must be edited.
    #
    # for i in range(node.parm('overvariantsfolder').evalAsInt()):
    #     vset = node.parm('overvariantset%d'%i).evalAsString()
    #     val  = node.parm('overvariant%d'%i).evalAsString()
    #
    #     if not (vset and val):
    #         continue
    #
    #     if ':' in vset:
    #         # find variantSet in asset
    #         vset = key.split(':')
    #         key  = 'asset:%s'%vset[0]
    #         vset = vset[1]
    #         if not res[key].has_key(vset):
    #             res[key][var.ORDER].append(vset)
    #         res[key][vset] = val
    #     else:
    #         # find variantSet in shot
    #         if res.has_key(var.T.SHOT):
    #             if not res[var.T.SHOT].has_key(vset):
    #                 res[var.T.SHOT][var.ORDER].append(vset)
    #             res[var.T.SHOT][vset] = val
    #         else:
    #             res[var.T.SHOT] = {vset:val, var.ORDER:[vset]}

    return res


def IsSequenced(node, pub=None, frange=[]):
    # check frange
    for i in range(len(frange), 3):
        frange.append(0)

    # get info from layer node
    if node.parm('customrendertgl').evalAsInt():
        if node.parm('trange').evalAsInt() > 0:
            for i in range(3):
                frange[i] = int(node.parm('f%d'%(i+1)).evalAsFloat())
            return True
        return False

    prctype = node.parm('processtype').evalAsString()
    isSim   = node.parm('simprocess').evalAsInt()

    # --------------------------------------------------------------------------
    # get info from pubnode
    if not pub:
        pub = []
        ntl.RetrieveByNodeType(node, 'dxusdROP_publish', pub, output=True)
        pub = hou.node(pub[0]) if pub else None

    if pub:
        try:
            if pub.parm('trange').evalAsInt() > 0:
                for i in range(3):
                    frange[i] = int(pub.parm('f%d'%(i+1)).evalAsFloat())
                isSim = True
            else:
                respath = pub.parm('resultpath').evalAsString()
                if respath == var.UNKNOWN:
                    raise ValueError('Unknown result path')
                else:
                    isSim = var.D.Decode(respath).IsShot()
        except Exception as e:
            msg.errmsg(e)
            msg.warning('Failed checking shot or not (assumes from trange)')

    if prctype == var.PRCCLIP or isSim:
        isSim = True

    if isSim and (not frange or frange == [0, 0, 0]):
        msg.warning('This layer is sequenced, so must set frame range')

    return isSim

def GetResolvedPubData(node, pub):
    '''
    [Inputs]
        - node (hou.node) : dxusdROP_layer node
        - pub (hou.node)  : dxusdROP_publish node
    [Return (dict)]
        return resolved publish node data
    '''
    if not pub or pub.type().name() != 'dxusdROP_publish':
        return {}

    for i in range(1, pub.parm('tasks').evalAsInt()+1):
        for j in range(1, pub.parm('nslyrs%d'%i).evalAsInt()+1):
            for k in range(1, pub.parm('sublyrs%d_%d'%(i, j)).evalAsInt() + 1):
                parm = pub.parm('layers%d_%d_%d'%(i, j, k))
                for l in range(1, parm.evalAsInt() + 1):
                    nodepath = pub.parm('inputropnode%d_%d_%d_%d'%(i, j, k, l))
                    if node.path() == nodepath.evalAsString():
                        _n = 'layerdata%d_%d_%d_%d'%(i, j, k, l)
                        res = pub.parm(_n).evalAsJSONMap()

                        _n = 'layeroutputfile%d_%d_%d_%d'%(i, j, k, l)
                        res['outfile'] = pub.parm(_n).evalAsString()
                        return res
    return {}


def GetCustomLayerData(node, pub):
    '''
    [Inputs]
        - node (hou.node) : dxusdROP_layer node
        - pub (hou.node)  : dxusdROP_publish node
    [Return (dict)]
        return custom layer data
    '''
    data = dict()
    # get dependency from publish node
    resdata = GetResolvedPubData(node, pub)
    depdata = utl.DependInfoToDict(resdata)

    # set dxusd version and hip file path
    data[var.T.CUS_DXUSD]     = var._DXVER
    data[var.T.CUS_SCENEFILE] = hou.hipFile.path()

    # set frames
    frange = []
    isSeq = IsSequenced(node, pub, frange)

    if isSeq:
        data[var.T.CUS_START] = frange[0]
        data[var.T.CUS_END]   = frange[1]
        data[var.T.CUS_STEP]  = float(frange[2])


    # --------------------------------------------------------------------------
    # for asset, branch
    for k in [var.T.BRANCH, var.T.ASSET]:
        if not depdata[k]:
            continue

        # set task
        dtask = None
        if depdata[k].has_key(var.T.TASK):
            dtask = depdata[k][var.T.TASK]

        # set rigFile
        if resdata['sequenced'] and not data.has_key(var.T.CUS_RIGFILE):
            rigver = depdata[k].get(var.T.VAR_RIGVER)
            if rigver: # and utl.Ver(0) not in rigver:
                # when groom simulation without ani
                args = var.D.Decode(utl.DirName(depdata.assetpath))
                args.task = var.T.RIG
                args.nslyr = depdata[k].get(var.T.VAR_RIGVER)
                rigpath = var.D.TASKN.Encode(**args)
                rigfile = var.F[args.task].MASTER.Encode(**args)
                data[var.T.CUS_RIGFILE] = utl.SJoin(rigpath, rigfile)
            else:
                data[var.T.CUS_RIGFILE] = depdata[k][var.USDPATH]

        # set other data by layer type
        if resdata['lyrtype'] == var.LYRGROOM:
            #data[var.T.CUS_GROOMFILE] = hou.hipFile.path()

            if dtask == var.T.RIG:
                rigfile = depdata[k][var.USDPATH]

                if node.parm('groom_shottgl').evalAsInt() == 1:
                    data[var.T.CUS_GROOMFILE] = ext.GetGroomFile(rigfile)

        elif resdata['lyrtype'] == var.LYRFEATHER:
            if not data.has_key(var.T.CUS_FEATHERFILE):
                if dtask == var.T.GROOM:
                    data[var.T.CUS_FEATHERFILE] = depdata[k][var.USDPATH]

            # add rig source files when exporting wings
            exptype = node.parm('feather_exporttype').evalAsString()
            exprig  = node.parm('feather_exportrigsourcetgl').evalAsInt()
            if exptype == 'dxusdOP_FeatherWings' and exprig:
                rigfile = utl.SJoin(resdata['outpath'], resdata['outfile'])
                rigprim = node.parm('feather_exportrigsource').evalAsString()
                data[var.T.CUS_RIGSOURCEFILE] = rigfile
                data[var.T.CUS_RIGSOURCEPRIM] = rigprim

    # --------------------------------------------------------------------------
    # for shot
    if depdata.HasShot():
        if not data.has_key(var.T.CUS_INPUTCACHE):
            if depdata.shottask in (var.T.ANI, var.T.SIM):
                data[var.T.CUS_INPUTCACHE] = depdata.shot[var.USDPATH]
        if not data.has_key(var.T.CUS_RIGFILE) and \
           depdata.shottask in (var.T.ANI, var.T.GROOM):
            data[var.T.CUS_RIGFILE] = depdata.shot[var.SRCPATH]
        if not data.has_key(var.T.CUS_FEATHERFILE) and \
           depdata.shottask == var.T.GROOM:
            lyr = utl.AsLayer(depdata.shot[var.USDPATH])
            if lyr:
                fth = lyr.customLayerData.get(var.T.CUS_FEATHERFILE)
                data[var.T.CUS_FEATHERFILE] = fth

    return data


def GetGroomFile(rigFile, variant=None):    # rigFile is *.usd or *.mb
    arg = Arguments()
    arg.D.SetDecode(utl.DirName(rigFile))
    arg.task = 'groom'
    if variant and arg.asset != variant:
        arg.branch = variant
    gmaster = utl.SJoin(arg.D.TASK, arg.F.TASK)

    srclyr  = utl.AsLayer(gmaster)
    if not srclyr:
        m = 'Groom.GetGroomFile >>> not found groom :'
        msg.debug(m, gmaster)
        return

    if rigFile.split('.')[-1] == 'usd':
        rig_version = arg.nslyr
    else:
        rig_version = utl.BaseName(rigFile).split('.')[0]

    primPath = Sdf.Path('/' + srclyr.defaultPrim)
    primPath = primPath.AppendVariantSelection(var.T.VAR_RIGVER, rig_version)
    spec = srclyr.GetPrimAtPath(primPath)
    if not spec:
        m = 'Groom.GetGroomFile >>> not found prim :'
        msg.debug(m, primPath.pathString)
        return

    gfile = None
    vsetSpec = spec.variantSets.get(var.T.VAR_GROOMVER)
    if vsetSpec:
        data = vsetSpec.variants
        vers = data.keys()
        vers.sort()
        gfile = utl.SJoin(arg.D.TASK, 'scenes', vers[-1] + '.hip')
        arg.nslyr = vers[-1]

    if gfile:
        msg.debug('Groom.GetGroomFile >>> Find groom file :', gfile)
        if os.path.exists(arg.D.TASKN):
            return gfile
        else:
            m = 'Groom.GetGroomFile >>> Find Groom USD. But not exists file :'
            msg.warning(m, arg.D.TASKN)


def ResolveInputs(kwargs):
    node = kwargs['node']
    type = node.parm('lyrtype').evalAsString()
    obj = node.parm('%s_objpath'%type)
    obj = obj.evalAsNode() if obj else None

    if type == var.LYRGEOM:
        if obj:
            lyrname = node.parm('geom_objpath').evalAsString()
            lyrname = lyrname.split('/')[-1]
            if obj.type().name() == 'DxusdOP_layout':
                node.parm('tgl').set(1)
                lyrname = obj.parm('lyrname').evalAsString()
                node.parm('geom_lyrname').set(lyrname)

    elif type == var.LYRINST:
        imptype = node.parm('inst_importtype').evalAsString()
        # find sop path
        prts = []
        inst = []
        if obj:
            if imptype == 'scenegraphinst':
                pass

            elif imptype == 'pointinst':
                for n in obj.children():
                    path = n.path()
                    if n.type().name() == 'dxusdSOP_instancingPoints':
                        node.parm('inst_scatterpointspath').set(path or '')
                    if n.type().name() == 'dxusdSOP_importPrototypes':
                        node.parm('inst_scatterprototypespath').set(path or '')


        else:
            node.parm('inst_scatterprototypespath').set('')
            node.parm('inst_scatterpointspath').set('')

    elif type == var.LYRGROOM:
        if obj:
            groomlop = hou.node('%s/groom_lop/import_groom'%node.path())
            groomlop.hdaModule().CheckSOPPath({'node':groomlop})

    elif type == var.LYRCROWD:
        pass

    elif type == var.LYRVDB:
        pass

    elif type == var.LYRFEATHER:
        featherlop = hou.node('%s/feather_lop/import_feather'%node.path())
        featherlop.hdaModule().UI_UpdateObjPath({'node':featherlop})


def ResolveDependency(kwargs):
    node = kwargs['node']
    type = node.parm('lyrtype').evalAsString()
    obj  = node.parm('%s_objpath'%type).evalAsNode()
    prctype = node.parm('processtype').evalAsString()
    isSim   = node.parm('simprocess').evalAsInt()
    needAst = node.parm('needasset').evalAsInt()
    isSeq   = IsSequenced(node)
    dependencyfolder = node.parm('dependencyfolder')
    required = []
    impnodes = []

    # set default number of dependencies by prctype
    numdependency = 0
    if prctype in [var.PRCFX, var.PRCCLIP]:
        if needAst:
            numdependency += 1
    else:
        if isSeq:
            numdependency += 1

    if isSim:
        numdependency += 1

    # check this is called from dependency list ui
    if kwargs.has_key('script_multiparm_index'):
        idx = int(kwargs['script_multiparm_index'])
        if idx >= 0:
            required.append(idx)

    if required:
        # called from dependency ui
        soppath = node.parm('dependencysoppath%d'%required[0]).evalAsString()
        impnodes.append(soppath)

    else:
        # set target node to find import node in its history networks
        targetNode = None

        # ---------------------------------------------------------------------
        # Geometry
        if type == var.LYRGEOM:
            if numdependency > 0:
                targetNode = node.parm('geom_objpath').evalAsNode()
                if targetNode and targetNode.type().name() == 'geo':
                    targetNode = targetNode.subnetOutputs()[0]

        # ---------------------------------------------------------------------
        # Instance
        elif type == var.LYRINST:
            numdependency = 0
            pass
            # if numdependency > 0:
            #     targetNode = node.parm('inst_objpath').evalAsNode()
            #     targetNode = hou.node('/obj/WORK/FX_floatingMaterial_inplace_less/dxusdSOP_import1')

                # targetNode = node.parm('inst_scatterprototypespath').evalAsNode()
                #
                # if targetNode.type().name() == 'dxusdSOP_importPrims':
                #     targetNode = targetNode.subnetOutputs()[0]

        # ---------------------------------------------------------------------
        # Groom
        elif type == var.LYRGROOM:
            # Hair Path 파라메터는 삭제하고, groom_objpath 사용
            # groom_objpath에 연결된 hairgen 노드의 가이드에 따라 sequence 인지 아닌지
            # 결정 해야 한다. (guide deform, guide simulation)
            numdependency = 1
            targetNode = node.parm('groom_hairpath').evalAsNode()
            if 'shot' in node.parm('groom_hairpath').evalAsString():
                numdependency = 2

        # ---------------------------------------------------------------------
        # Crowd
        elif type == var.LYRCROWD:
            pass

        # ---------------------------------------------------------------------
        # VDB
        elif type == var.LYRVDB:
            numdependency = 0

        # ---------------------------------------------------------------------
        # Feather
        elif type == var.LYRFEATHER:
            numdependency = 1
            expparm = node.parm('feather_exporttype')
            typename = expparm.menuLabels()[expparm.evalAsInt()].lower()
            sopparm = 'feather_%spath'%typename

            targetNode = node.parm(sopparm)
            if targetNode:
                targetNode = targetNode.evalAsNode()
            elif typename == 'wings' and obj and \
                 obj.type().name() == 'dxusdOP_FeatherWings':
                targetNode = obj.parm('basemeshpath').evalAsNode()

            # set number of dependency
            if typename == 'deformer':
                numdependency = 2
            elif typename == 'designer':
                numdependency = 0

        # ---------------------------------------------------------------------
        # find import nodes
        if targetNode:
            ntl.RetrieveByNodeType(targetNode, 'dxusdSOP_import', impnodes,
                                   firstMatch=False)
        # update dependency
        iter = range(numdependency)
        dependencyfolder.set(numdependency)

        node.setUserData('importnodes', ' '.join(impnodes))

        for i in range(min(numdependency, len(impnodes))):
            required.append(i)
            node.parm('dependencysoppath%d'%i).set(impnodes[i])

    # set dependency
    for s, i in enumerate(required):
        impnode = hou.node(impnodes[s])
        if impnode:
            usdpath = impnode.parm('usdpath').evalAsString()
            node.parm('usdpath%d'%i).set(usdpath)

            lyrns = impnode.parm('nslyrname').evalAsString()
            subfix = impnode.parm('nslyrnamesubfix').evalAsString()
            if subfix:
                lyrns = '%s%s'%(lyrns, subfix)

            node.parm('nslyrname%d'%i).set(lyrns)

            for kind in ('shot', 'asset', 'branch'):
                num = impnode.parm('%svariantfolder'%kind).evalAsInt()
                node.parm('%svariantfolder%d'%(kind, i)).set(num)

                if kind == 'shot':
                    masterpath   = impnode.parm('shotmasterpath').evalAsString()
                    nslyr        = impnode.parm('shotnamespace').evalAsString()
                    assetusdpath = impnode.parm('assetusdpath').evalAsString()
                    node.parm('shotmasterpath%d'%i).set(masterpath)
                    node.parm('shotnamespace%d'%i).set(nslyr)
                    node.parm('assetusdpath%d'%i).set(assetusdpath)
                else:
                    masterpath = impnode.parm('assetmasterpath').evalAsString()
                    geomdprim = impnode.parm('assetgeomdprim').evalAsString()
                    node.parm('assetmasterpath%d'%i).set(masterpath)
                    node.parm('assetgeomdprim%d'%i).set(geomdprim)

                for j in range(num):
                    vset = impnode.parm('%svariantset%d'%(kind, j))
                    vset = vset.evalAsString()
                    node.parm('%svariantset%d_%d'%(kind, i, j)).set(vset)

                    v = impnode.parm('%svariants%d'%(kind, j))
                    v = v.evalAsString()
                    node.parm('%svariants%d_%d'%(kind, i, j)).set(v)
        else:
            node.parm('dependencysoppath%d'%i).set('')
            node.parm('usdpath%d'%i).set('')
            for kind in ('shot', 'asset', 'branch'):
                node.parm('%svariantfolder%d'%(kind, i)).set(0)


def ResolveLayer(kwargs):
    node = kwargs['node']
    type = node.parm('lyrtype').evalAsString()

    prctype = node.parm('processtype').evalAsString()
    isSim   = node.parm('simprocess').evalAsInt()
    prcname    = node.parm('processname').evalAsString()
    subprcname = node.parm('subprocessname').evalAsString()

    info = {}
    for k in LYRPARMS:
        info.update({k:None})

    obj = node.parm('%s_objpath'%type)
    obj = obj.evalAsNode() if obj else None

    isSeq = IsSequenced(node)

    # --------------------------------------------------------------------------
    # get dependency
    depend = GetDependency(node)

    # --------------------------------------------------------------------------
    # layer 형태에 따라 Layer Resolution 정보를 등록한다.
    # ['nslyr', 'sublyr', 'lyrname', 'dprim']

    if type == var.LYRGEOM:
        soppath  = node.parm('geom_objpath').evalAsString()
        soppath = soppath.split('/')[-1]

        ShowLayerResParms(node, 'dprim', 'lyrname')
        info['dprim'] = 'Geom'
        info['lyrname'] = soppath if soppath else var.UNKNOWN
        info['nslyr']  = prcname
        info['sublyr'] = subprcname

        if prctype == var.PRCCLIP:
            ShowLayerResParms(node, 'dprim','nslyr', 'lyrname')
            # info['nslyr'] = depend.assetnslyr
            info['dprim'] = info['nslyr'] if isSim else depend.geomdprim

        elif prctype == var.PRCFX:
            ShowLayerResParms(node, 'dprim', 'nslyr', 'sublyr', 'lyrname')
            info['dprim'] = info['nslyr'] if isSim else depend.geomdprim
            info['nslyr'] = depend.shotnslyr or depend.assetnslyr
        elif isSeq: # ani
            ShowLayerResParms(node, 'dprim', 'nslyr', 'lyrname')
            info['nslyr'] = depend.assetnslyr
            info['dprim'] = info['nslyr'] if isSim else depend.geomdprim
            depnode = node.parm('dependencysoppath0').evalAsNode()
            if depnode:
                info['dprim'] = depnode.parm('assetgeomdprim').evalAsString()

    # --------------------------------------------------------------------------
    elif type == var.LYRINST:
        soppath = node.parm('inst_objpath').evalAsString()
        soppath = soppath.split('/')[-1]

        ShowLayerResParms(node, 'dprim', 'lyrname')
        info['dprim'] = 'Geom'
        info['lyrname'] = soppath if soppath else var.UNKNOWN
        info['nslyr'] = prcname
        info['sublyr'] = subprcname

        if prctype == var.PRCCLIP:
            ShowLayerResParms(node, 'dprim', 'nslyr', 'lyrname')
            # info['nslyr'] = depend.assetnslyr
            #info['dprim'] = info['nslyr'] if isSim else depend.geomdprim
            info['dprim'] = 'Geom'

        elif prctype == var.PRCFX:
            ShowLayerResParms(node, 'dprim', 'nslyr', 'sublyr', 'lyrname')
            info['dprim'] = info['nslyr'] if isSim else depend.geomdprim
            info['nslyr'] = depend.shotnslyr or depend.assetnslyr

        elif isSeq:  # ani
            ShowLayerResParms(node, 'dprim', 'nslyr', 'lyrname')
            info['nslyr'] = depend.assetnslyr
            info['dprim'] = info['nslyr'] if isSim else depend.geomdprim


    # --------------------------------------------------------------------------
    elif type == var.LYRGROOM:
        soppath  = node.parm('groom_hairpath').evalAsString()
        soppath  = soppath.split('/')[-1]

        ShowLayerResParms(node, 'nslyr', 'lyrname', 'dprim')

        info['dprim'] = 'Groom'
        info['lyrname'] = soppath if soppath else var.UNKNOWN


        if   prctype == var.PRCCLIP:
            info['nslyr'] = node.parm('processname').evalAsString()
        elif prctype == var.PRCFX:
            info['nslyr']  = node.parm('processname').evalAsString()
            info['sublyr'] = node.parm('subprocessname').evalAsString()
        else: # none or sim
            if isSeq:
                if depend.has_key(var.T.SHOT):
                    for data in depend[var.T.SHOT].values():
                        info['nslyr'] = data[var.NSLYR]
                        break
            else:
                info['nslyr'] = obj.path().split('/')[2] if obj else var.UNKNOWN
    # --------------------------------------------------------------------------
    elif type == var.LYRCROWD:
        if   prctype == var.PRCCLIP:
            pass
        elif prctype == var.PRCFX:
            pass
        else:
            pass

    # --------------------------------------------------------------------------
    elif type == var.LYRVDB:
        soppath  = node.parm('vdb_objpath').evalAsString()
        soppath = soppath.split('/')[-1]
        # vdbpath = node.parm('vdb_filesoppath').evalAsString()
        # vdbpath = vdbpath.split('/')[-1]
        # if '_' in vdbpath:
        #     vdbpath = vdbpath.split('_')[0]

        ShowLayerResParms(node, 'dprim', 'lyrname')
        info['dprim'] = 'Vdb'
        info['lyrname'] = soppath if soppath else var.UNKNOWN
        info['nslyr']  = prcname
        info['sublyr'] = subprcname

        if prctype == var.PRCCLIP:
            ShowLayerResParms(node, 'dprim', 'nslyr', 'lyrname')
            info['nslyr'] = depend.assetnslyr
            info['dprim'] = info['nslyr'] if isSim else depend.geomdprim

        elif prctype == var.PRCFX:
            ShowLayerResParms(node, 'dprim', 'nslyr', 'sublyr', 'lyrname')
            info['dprim'] = 'Geom'
            info['nslyr'] = depend.shotnslyr or depend.assetnslyr
            # info['sublyr'] = vdbpath

        elif isSeq: # ani
            ShowLayerResParms(node, 'dprim', 'nslyr', 'lyrname')
            info['nslyr'] = depend.assetnslyr
            info['dprim'] = info['nslyr'] if isSim else depend.geomdprim


    # --------------------------------------------------------------------------
    elif type == var.LYROCEAN:
        if   prctype == var.PRCCLIP:
            pass
        elif prctype == var.PRCFX:
            pass
        else:
            ShowLayerResParms(node, 'dprim', 'nslyr')
            info['dprim'] = 'Geom'
            if obj:
                nslyr= obj.path()
                nslyr = nslyr.split('/')[-2]
                info['nslyr'] = nslyr

    # --------------------------------------------------------------------------
    elif type == var.LYRFEATHER:
        typeparm = node.parm('feather_exporttype')
        ftype  = typeparm.menuLabels()[typeparm.evalAsInt()].lower()
        soppath  = node.parm('feather_%spath'%ftype)
        if soppath:
            soppath = soppath.evalAsString().split('/')[-1]
        else:
            soppath = obj.name() if obj else var.UNKNOWN

        ShowLayerResParms(node, 'nslyr', 'lyrname', 'dprim')

        info['dprim'] = 'Groom'
        info['lyrname'] = soppath.split('/')[-1] if soppath else var.UNKNOWN
        info['nslyr']  = obj.path().split('/')[2] if obj else var.UNKNOWN
        info['sublyr'] = subprcname

        if prctype == var.PRCCLIP:
            info['nslyr'] = depend.shotnslyr
            info['dprim'] = prcname if isSim else depend.geomdprim
        elif prctype == var.PRCFX:
            ShowLayerResParms(node, 'dprim', 'nslyr', 'sublyr', 'lyrname')
            info['dprim'] = prcname if isSim else depend.geomdprim
            info['nslyr'] = depend.shotnslyr or depend.assetnslyr
        elif isSeq or ftype == 'deformer': # ani
            info['nslyr'] = depend.shotnslyr
            info['dprim'] = depend.shotnslyr

        # set dependent feather for simuation
        if ftype == 'simulation' and depend.shotpath:
            # find high geom
            ref = None
            try:
                path = utl.DirName(depend.shotpath)
                flgs = var.D.Decode(path)
                flgs.lod = var.T.HIGH
                file = var.F.groom.LOD.Encode(**flgs)
                path = utl.SJoin(path, file)
                lyr = utl.AsLayer(path)
                if not lyr:
                    m = 'Caanot find high geom of feather (%s)'
                    raise ValueError(m%path)

                prim = lyr.GetPrimAtPath(lyr.defaultPrim)
                while prim.name != 'Laminations':
                    if not prim.nameChildren:
                        raise Exception('Cannot find lamination for dependency')
                    prim = prim.nameChildren[0]

                if not prim.hasReferences:
                    raise Exception('Given lamination has not reference')

                ref = prim.referenceList.prependedItems[0].assetPath
                ref = utl.GetAbsPath(path, ref)

            except Exception as e:
                msg.errmsg(e)

            if ref:
                node.parm('simulationdependency').set(ref)




    # --------------------------------------------------------------------------
    # set
    for k, v in info.items():
        if v != None:
            node.parm(k).set(v)