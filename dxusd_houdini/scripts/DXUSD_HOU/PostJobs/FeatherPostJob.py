#coding:utf-8
from __future__ import print_function

import DXUSD_HOU.Message as msg
import DXUSD_HOU.Vars as var
import DXUSD_HOU.Utils as utl

from DXUSD_HOU.PostJobs import PostJob


class FeatherPostJob(PostJob):
    def Treat(self):
        if self.arg.has_attr('sequenced') and self.arg.sequenced:
            return var.IGNORE

        try:
            self.assetpath = utl.SJoin(self.arg.D.ASSET, self.arg.F.ASSET)
        except Exception as e:
            msg.errmsg(e)
            msg.errmsg('Failed to create asset path')
            return var.FAILED

        if not self.arg.has_attr('dependRigVer') or not self.arg.dependRigVer:
            msg.errmsg('Must set dependRigVer attribute to arguments')
            return var.FAILED

        return var.SUCCESS

    def DoIt(self):
        print(self.assetpath)

        return var.SUCCESS
