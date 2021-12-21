#coding:utf-8
from __future__ import print_function

import DXRulebook.Interface as rb
import DXUSD.moduleloader as md
import DXUSD.Structures as srt
md.importModule(__name__, srt)

import DXUSD_HOU.Message as msg
import DXUSD_HOU.Vars as var


class Items(object):
    def __init__(self, name=None, parent=None):
        self.name = name
        self._items = dict()
        self._idx = 0
        self._parent = parent # class instance
        self._child  = None   # class type

    def __getitems__(self, k):
        if k in self._items.keys():
            return self._items[k]
        elif isinstance(k, int):
            return self.items[k]
        else:
            return self.self._child(k)

    def __len__(self):
        return len(self._items)

    def __repr__(self):
        res = ''
        for item in self.items():
            res += str(item)
        return res

    def keys(self):
        keys = self._items.keys()
        keys.sort()
        return keys

    def items(self):
        return [self._items[v] for v in self.keys()]

    def parent(self):
        return self._parent

    def Add(self, name):
        if name not in self._items.keys():
            self._items[name] = self._child(name, self)
        return self._items[name]


class Tasks(Items):
    def __init__(self, arg):
        Items.__init__(self)
        self._child = Tasks.Task
        self.arg    = arg

    def __repr__(self):
        res  = '###### Tasks Result ######\n'
        # res += 'Args : %s\n\n'%str(self.arg)
        res += Items.__repr__(self)
        return res

    def Add(self, name, code):
        item = Items.Add(self, name)
        item.code = code
        return item

    class Task(Items):
        def __init__(self, name, parent):
            Items.__init__(self, name, parent)
            self._child = Tasks.NSLayer
            self.code = None
            self.vers = list()
            self.arg  = Arguments(**parent.arg)
            self.arg.task = name

        def __repr__(self):
            res = '[ %s (%s) ] - %s\n'
            res = res%(self.arg.task, self.code, str(self.vers))
            res += '\t%s'%str(self.arg)
            res += Items.__repr__(self)
            return res


    class NSLayer(Items):
        def __init__(self, name, parent):
            Items.__init__(self, name, parent)
            self._child = Tasks.SubLayer
            self.vers = list()
            self.arg  = parent.arg

        def __repr__(self):
            res = ''
            if self.name != var.NULL:
                res += '\n\t[ NS Layer ]\n'
                res += '\t %s - %s\n'%(self.name, str(self.vers))
            res += Items.__repr__(self)
            return res


    class SubLayer(Items):
        def __init__(self, name, parent):
            Items.__init__(self, name, parent)
            self._child = Tasks.Layer
            self.vers = list()
            self.arg  = parent.arg

        def __repr__(self):
            res = ''
            if self.name != var.NULL:
                res += '\n\t[ Sub Layer ]\n'
                res += '\t %s - %s\n'%(self.name, str(self.vers))
            res += Items.__repr__(self)
            return res


    class Layer:
        def __init__(self, name, parent):
            self.name = name
            self._parent = parent
            self.arg  = Arguments(**parent.arg)

            self.cliprate = None
            self.looprange = None

            self.inputnode = ''
            self.lyrtype = ''
            self.prctype = ''
            self.simprc = False
            self.extra = '{}'
            self.sequenced = None
            self.dependency = {}

        @property
        def task(self):
            return self._parent._parent._parent

        @property
        def outpath(self):
            try:
                return self.arg.D[self.task.code]
            except Exception as e:
                msg.errmsg(e)
                msg.errmsg('@Tasks.Layer : Failed decoding outpath')
                return None

        def CheckOutpath(self):
            return self.outpath != None

        def __repr__(self):
            res = '\n\t[ Layers ]\n'
            if not self.outpath or not self.name:
                res += '\t >>> Cannot resolve output file path\n'
            else:
                res += '\t >>> %s\n'%utl.SJoin(self.outpath, self.name)

            res += '\t    Layer Type : %s\n'%str(self.lyrtype)
            res += '\t    Post Process : %s\n'%str(self.prctype)
            res += '\t    Simulation : %s\n'%str(self.simprc)
            res += '\t    Sequenced : %s\n'%str(self.sequenced)
            res += '\t    Extra args : %s\n'%str(self.extra)
            if self.prctype == var.PRCCLIP:
                res += '\t    Clip Rate : %s\n'%self.cliprate
                res += '\t    Loop Range : %s\n'%str(self.looprange)

            if self.inputnode:
                res += '\t    Input Node : %s\n'%self.inputnode

            if self.dependency:
                res += str(self.dependency)

            return res


class DependentFile(srt.BaseStructure):
    def __init__(self, **kwargs):
        self.file = None
        self.arg  = rb.Flags(var.USD.upper(), pub=var.T.PUB3)
        srt.BaseStructure.__init__(self, **kwargs)

        self.SetDecode()

    def __nonzero__(self):
        return True if self.file else False

    @property
    def dirname(self):
        return utl.DirName(self.file)

    @property
    def basename(self):
        return utl.BaseName(self.file)

    @property
    def task(self):
        return self.__GetArgument('task')

    @property
    def ver(self):
        return self.__GetArgument('ver')

    @property
    def nslyr(self):
        return self.__GetArgument('nslyr')

    def __GetArgument(self, name):
        return self.arg[name] if self.arg.has_key(name) else None

    def CopyArgs(self):
        return rb.Flags(var.USD.upper(), **self.arg)

    def SetFile(self, file):
        self.file = file
        self.SetDecode()

    def SetDecode(self):
        try:
            if self.file:
                self.arg.D.SetDecode(self.file)
        except Exception as e:
            msg.errmsg(e)
            msg.warning('Given file is not available\n\t - %s'%self.file)
            self.file = None


class Dependency(srt.BaseStructure):
    def __init__(self):
        '''
        asset, branch, shot dict
        {
            (var.USDPATH) : (path),
            (var.NSLYR) : (nslyr name)
            (var.ORDER) : [(vset), ...]
            (vset) : (variant)
            ...
            (var.LYRTASK) : task
            (var.SRCPATH) : source layer path
            (var.GEOMDPRIM) : (Geometry default prim)
        }
        '''
        srt.BaseStructure.__init__(self)
        self.asset = dict()
        self.branch = dict()
        self.shot = dict()


    def __repr__(self):
        res = '\n\t    [Dependency]\n'
        if not (self.asset or self.branch or self.shot):
            return '\n\t    [Dependency] : None\n'

        for kind, data in self.items():
            if not data:
                continue

            res += '\t\t> %s : %s\n'%(kind, data[var.NSLYR])
            res += '\t\t    PATH : %s\n'%data[var.USDPATH]

            if kind == var.T.SHOT:
                res += '\t\t    SOURCE PATH : %s\n'%data.get(var.SRCPATH, '')
            else:
                res += '\t\t    GEOM DPRIM : %s\n'%data.get(var.GEOMDPRIM, '')

            res += '\t\t    Layer TASK : %s\n'%data.get(var.LYRTASK, '')

            for vset in data[var.ORDER]:
                if not vset in data.keys():
                    continue
                res += '\t\t    - %s : %s\n'%(vset, data[vset])

        return res


    def __AssetGet(self, attr):
        if self.branch:
            return self.branch.get(attr, '')
        return self.asset.get(attr, '')

    def HasBranch(self):
        return True if self.branch else False

    def HasAsset(self):
        return True if self.asset else False

    def HasShot(self):
        return True if self.shot else False

    @property
    def assetnslyr(self):
        return self.__AssetGet(var.NSLYR)

    @property
    def shotnslyr(self):
        return self.shot.get(var.NSLYR, '')

    @property
    def shottask(self):
        return self.shot.get(var.LYRTASK, '')

    @property
    def assettask(self):
        return self.__AssetGet(var.LYRTASK)

    @property
    def shotpath(self):
        return self.shot.get(var.USDPATH)

    @property
    def assetpath(self):
        return self.__AssetGet(var.USDPATH)

    @property
    def srcpath(self):
        return self.shot.get(var.SRCPATH)

    @property
    def geomdprim(self):
        return self.__AssetGet(var.GEOMDPRIM)
