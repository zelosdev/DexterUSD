import maya.api.OpenMaya as OpenMaya


def Print(state, message):
    if state == 'warning':
        OpenMaya.MGlobal.displayWarning(message)
    elif state == 'error':
        OpenMaya.MGlobal.displayError(message)
    else:
        OpenMaya.MGlobal.displayInfo(message)
