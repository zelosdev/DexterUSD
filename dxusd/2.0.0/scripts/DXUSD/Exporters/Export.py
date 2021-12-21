#coding:utf-8
from __future__ import print_function

from DXUSD.Structures import Arguments, Layers

import DXUSD.Vars as var
import DXUSD.Utils as utl
import DXUSD.Message as msg


class AExport(Arguments):
    def __init__(self, **kwargs):
        # need to define in each Exporting()
        # self.dstlyr    = None

        # if not self.has_attr('srclyr'):
        #     self.srclyr    = Layers()

        # if not self.has_attr('nameProduct'):
        #     self.nameProduct    = None

        if not self.has_attr('taskProduct'):
            self.taskProduct    = None

        Arguments.__init__(self, **kwargs)


    def Treat(self):
        # ----------------------------------------------------------------------
        # Decode srclyr's name
        # if self.nameProduct and self.srclyr.name:
        #     # set decoded srclyr.name (eg. 'asset_model_GRP')
        #     try:
        #         self.N.SetDecode(self.srclyr.name, self.nameProduct)
        #     except Exception as E:
        #         msg.errmsg('Treat@%s'%self.__name__,
        #                    'Failed decode "name"(%s)\n'%self.srclyr.name,
        #                    '\t  Product : %s'%self.nameProduct)
        #         return var.FAILED

        # ----------------------------------------------------------------------
        # check arguments
        res = self.CheckArguments(self.taskProduct)
        if res != var.SUCCESS:
            return res

        return var.SUCCESS


class Export(object):
    ARGCLASS = AExport
    def __init__(self, arg, end=True):
        self.__name__ = self.__class__.__name__

        if arg.__name__ == 'Arguments':
            self.arg = self.ARGCLASS(**arg)
        elif arg.__name__ == self.ARGCLASS.__name__:
            self.arg = arg
        else:
            msg.error('__init__@Export : Arguments Failed (%s)'%self.__name__)

        msg.debug()
        msg.debug('#'*70)
        msg.debug('#'*70)
        msg.debug('')
        msg.debug('\t\t\t[ Start %s ]'%self.__name__)
        msg.debug()
        msg.debug('#'*70)
        msg.debug('#'*70)
        msg.debug()

        utl.CheckRes('[ Start Treating ]', self.arg.Treat, 'Treating', 0)

        msg.debug()
        msg.debug('#'*70)
        msg.debug(self.arg)

        msg.debug()
        msg.debug('#'*70)
        utl.CheckRes('[ Start Exporting ]', self.Exporting, 'Exporting', 0)

        msg.debug()
        msg.debug('#'*70)
        utl.CheckRes('[ Start Arguing ]', self.Arguing, 'Arguing', 0)

        msg.debug()
        msg.debug('#'*70)
        utl.CheckRes('[ Start Tweaking ]', self.Tweaking, 'Tweaking', 0)

        msg.debug()
        msg.debug('#'*70)
        utl.CheckRes('[ Start Compositing ]', self.Compositing, 'Compositing', 0)

        if end:
            msg.debug()
            msg.debug('#'*70)
            msg.debug('#'*70)
            msg.debug('')
            msg.debug('[ Complete %s ]'%self.__name__)

    def Arguing(self):
        msg.warning('Arguing@Export : Not overrided.', dev=True)
        return var.IGNORE

    def Exporting(self):
        msg.warning('Exporting@Export : Not overrided.', dev=True)
        return var.IGNORE

    def Tweaking(self):
        msg.warning('Tweaking@Export : Not overrided.', dev=True)
        return var.IGNORE

    def Compositing(self):
        msg.warning('Compositing@Export : Not overrided.', dev=True)
        return var.IGNORE
