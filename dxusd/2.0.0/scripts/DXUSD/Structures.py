#coding:utf-8
from __future__ import print_function

import DXRulebook.Interface as rb

import string, copy

import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg


class Arguments(rb.Flags):
    def __init__(self, **kwargs):
        '''
        [flags]
        show,  customdir
        seq,   shot
        asset, branch
        task,  ver
        nslyr, nsver
        subdir
        '''
        self.__name__ = self.__class__.__name__
        # pre-initialiezed flags
        self.pub       = var.T.PUB3
        # other members
        self.meta   = utl.StageMetadata()
        # initialize flags
        rb.Flags.__init__(self, var.USD.upper(), **kwargs)

    def CheckArguments(self, taskCode):
        # ----------------------------------------------------------------------
        # Check arguments
        if not self.customdir and not self.show:
            msg.errmsg('Treat@Arguments : Must set "outdir" or "show"')
            return var.FAILED

        if self.branch and not self.asset:
            msg.errmsg('Treat@Arguments : Must set "asset"')
            return var.FAILED
        elif not self.asset and not self.shot:
            msg.errmsg('Treat@Arguments : Must set "asset" or "shot"')
            return var.FAILED
        elif self.shot and not self.seq:
            msg.errmsg('Treat@Arguments : Must set "seq"')
            return var.FAILED

        # ----------------------------------------------------------------------
        # Check task argument
        if not isinstance(taskCode, (str, unicode)):
            msg.errmsg('Treat@Arguments : Must set "taskCode" argument')
            return var.FAILED

        if not self.task:
            msg.errmsg('Treat@Arguments : Must set "task"')
            return var.FAILED

        if 'TASKV' in taskCode and not self.ver:
            self.ver = utl.GetNextVersion(self.D.TASK)

        if 'N' in taskCode and not self.nslyr:
            msg.errmsg('Treat@AExport : Must set "nslyr"')
            return var.FAILED

        if 'NV' in taskCode and not self.nsver:
            code = '%sN'%taskCode.split('NV')[0]
            self.nsver = utl.GetNextVersion(self.D[code])

        if 'SV' in taskCode:
            if not self.subdir:
                msg.errmsg('Treat@AExport : Must set "subdir"')
                return var.FAILED
            if not self.subver:
                code = '%sN'%taskCode.split('NV')[0]
                self.subver = utl.GetNextVersion(self.D[code])

        if taskCode.endswith('S'):
            snum = len(taskCode[4:-1].split('S')) - 1
            flag = 'subdir%d'%snum if snum else 'subdir'

            if not self.has_key(flag):
                msg.errmsg('Treat@AExport : Must set "%s"'%flag)
                return var.FAILED

        return var.SUCCESS


    def Treat(self):
        '''
        This methode will run before tweaker's doIt(). If you need to treat any
        arguments, override this.
        '''
        return var.SUCCESS

    def AsDict(self, attrs=True):
        data = dict(self)
        if attrs:
            for k, v in self.__dict__.items():
                if not k.startswith('_'):
                    try:
                        data[k] = copy.copy(v)
                    except:
                        data[k] = v
        return data

    @property
    def assetName(self):
        return self.branch if self.IsBranch() else self.asset

    @property
    def assetDir(self):
        return self.D.BRANCH if self.IsBranch() else self.D.ASSET

    @property
    def assetRoot(self):
        if self.shot:
            return self.D.SHOT
        if self.seq:
            return self.D.SEQ
        if self.show:
            return self.D.PUB
        if self.customdir:
            if self.customdir.startswith('/assetlib'):
                return self.customdir


    def __repr__(self):
        res = '[ print arguments of %s ]\n'%self.__name__
        res+= '\t    <Dictionary>\n'
        for key, value in self.items():
            res += '\t\t%s : %s\n'%(key, value)
            if isinstance(value, (str, unicode)) and '\t' in value:
                value = value.replace('\t', '\t\t')
        res+= '\t    <Attributes>\n'
        for key, value in self.__dict__.items():
            if key.startswith('_'):
                continue
            if '\t' in str(value):
                value = str(value).replace('\t\t', '\t\t    ')
            res += '\t\t%s : %s\n'%(key, value)
        return res


class BaseStructure(dict):
    def __init__(self, **kwargs):
        self.__name__ = self.__class__.__name__
        # set member
        self.update(kwargs)

    def __setattr__(self, k, v):
        if k.startswith('_'):
            self.__dict__[k] = v
        else:
            self[k] = v

    def __getattr__(self, k):
        if isinstance(k, (str, unicode)) and k.startswith('_'):
            return self.__dict__[k]
        else:
            return dict.__getitem__(self, k)

    def __repr__(self):
        res = '[ print arguments of %s ]\n'%self.__name__
        for key, value in self.items():
            res += '\t\t%s : %s\n'%(key, value)
        return res


class Layers(dict):
    def __init__(self, **kwargs):
        '''
        [Arguments]
        name (str) : Exporting top group name (eg. asset_model_GRP)
        '''
        self.__dict__['_lyrs']   = list()
        self.__name__ = self.__class__.__name__

        # set member
        self.update(kwargs)

    def __getattr__(self, k):
        if k in self._lyrs:
            return dict.__getitem__(self, k)
        else:
            return self.__dict__[k]

    def __setattr__(self, k, v):
        if k in self._lyrs:
            dict.__setitem__(self, k, v)
        else:
            self.__dict__[k] = v

    def __getitem__(self, k):
        if isinstance(k, int):
            if k >= len(self._lyrs):
                msg.error(KeyError('__getitem__@Layers :',
                                   'Out of range. Given index is %d'%k,
                                   '(Layer count is %s)'%len(self._lyrs)))
            return dict.__getitem__(self, self._lyrs[k])
        elif isinstance(k, slice):
            newLayer = Layers()
            for lyr in self._lyrs[k]:
                newLayer.AddLayer(lyr, self[lyr])
            return newLayer
        else:
            return self.__getattr__(k)

    def __setitem__(self, k, v):
        if isinstance(k, int):
            if k >= len(self._lyrs):
                msg.error(KeyError(), '__setitem__@Layers :',
                                   'Out of range. Given index is %d'%k,
                                   '(It has %d layers)'%len(self._lyrs))
            dict.__setitem__(self, self._lyrs[k], v)
        else:
            if k in self._lyrs:
                dict.__setitem__(self, k, v)
            else:
                self.__setattr__(k, v)

    def __iter__(self):
        for k in self._lyrs:
            yield dict.__getitem__(self, k)

    def __len__(self):
        return len(self._lyrs)

    def __repr__(self):
        res = '[ print arguments of %s ]\n'%self.__name__
        for key in self._lyrs:
            res += '\t\t%s : %s\n'%(key, self[key])
        return res

    def __copy__(self):
        new = Layers(**self)
        new.__dict__['_lyrs'] = list(self.__dict__['_lyrs'])
        return new

    def AddLayer(self, name, value=None, idx=None):
        if name in self._lyrs:
            return

        if idx != None:
            for i in range(len(self._lyrs), idx):
                self._lyrs.append(None)
        else:
            idx = len(self._lyrs)
            self._lyrs.append(None)

        self._lyrs[idx] = name
        self[name] = value

    def Append(self, value=None, idx=None):
        if idx != None:
            for i in range(len(self._lyrs), idx):
                self._lyrs.append(None)
        else:
            idx = len(self._lyrs)
            self._lyrs.append(None)

        name = '__NUM__%d'%idx
        self._lyrs[idx] = name
        dict.__setitem__(self, name, value)

    @property
    def layers(self):
        return list(self._lyrs)
