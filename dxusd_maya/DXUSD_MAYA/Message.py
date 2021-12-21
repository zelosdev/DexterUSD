import os
import DXUSD.Message as msg
import maya.api.OpenMaya as OpenMaya
import maya.cmds as cmds

DEV = not __file__.startswith('/backstage') and \
      not __file__.startswith('/others/backstage')

def message(*args, **kwargs):
    msg.message(args, kwargs)


def warning(*args, **kwargs):
    msg.warning(args, kwargs)


def errmsg(*args, **kwargs):
    msg.errmsg(args, kwargs)


def error(*args, **kwargs):
    msg.error(*args, **kwargs)


def errorQuit(*args, **kwargs):
    try:
        msg.error(*args, **kwargs)
    except Exception as e:
        if cmds.about(batch=True):
            OpenMaya.MGlobal.displayError(e.message)
            cmd = ['/backstage/dcc/DCC', 'rez-env', 'rocketchattoolkit', '--']
            cmd += ['BotMsg', '--artist', kwargs['artist']]
            cmd += ['--message', '\"%s\"' % e.message]
            cmd += ['--bot', 'BadBot']
            os.system(' '.join(cmd))
            os._exit(1)
        else:
            cmds.error(e.message)

def debug(*args, **kwargs):
    msg.debug(*args, **kwargs)

