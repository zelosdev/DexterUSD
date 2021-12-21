'''
usdfile = '/show/pipe/_3d/asset/bear/bear.payload.usd'
usdfile = '/show/pipe/_3d/shot/S26/S26_0450/S26_0450.payload.usd'
stage = Usd.Stage.Open(usdfile)

for p in stage.Traverse():
    #print p.HasAttribute('xformOpOrder')
    print UsdXformToMayaTransform(p)
'''

# dxBlock common utils
from pxr import Usd, UsdGeom, UsdUtils, Sdf, Vt, Gf, UsdMaya
import maya.cmds as cmds
import Import
import string

import Represent
import DXUSD_MAYA.Message as msg
import pprint
import os
import DXUSD.Utils as utl
import extra as xbExtra


class MayaAttrs:
    def __init__(self):
        # the attributes in attrList are only supported
        self.attrList = [
            'translateX',   'translateY',   'translateZ',
            'rotatePivotX', 'rotatePivotY', 'rotatePivotZ',
            'rotateX',      'rotateY',      'rotateZ',
            'scalePivotX',  'scalePivotY',  'scalePivotZ',
            'scaleX',       'scaleY',       'scaleZ',
            'shearXY',      'shearXZ',      'shearYZ',
            'rotateOrder',  'visibility',   'transform'
        ]
        # this attrGroups is attrList's parent attribute in maya.
        # attrGroups index * 3 means the first elemnet attribute of attrList.
        # (attrGroups[3] = rotate : attrList[3*3] = rotateX)
        self.attrGroups = ['translate', 'rotatePivot', 'rotate', 'scalePivot', 'scale', 'shear']

        # add attrList as this class's attributes
        for attr in self.attrList:
            setattr(self, attr, None)


    def __str__(self):
        # for debugging. it will return "attr:values" as string
        res = ''
        for attr in self.attrList:
            value = getattr(self, attr)
            if value != None:
                res += '%s:%s\n' % (attr, str(value))
        return res


    def __repr__(self):
        return self.__str__()


    def __getattr__(self, name):
        # when attribute in attrGroups is got, this will return a list of
        # elements of the attribute. (eg. sacle > [scaleX, scaleY, scaleZ])
        # if all element attributes have no values, it will return None.
        if name in self.attrList:
            return getattr(self, name)
        elif name in self.attrGroups:
            attrs = self.getAttrListFromGroup(name)
            hasValue = False
            values = []
            for attr in attrs:
                value = getattr(self, attr)
                if value == None:
                    # if the element attribute is None,
                    # then the default value is added.
                    if name == 'scale':
                        values.append(1)
                    else:
                        values.append(0)
                else:
                    values.append(value)
                    hasValue = True

            if not hasValue:
                return None
            else:
                return values


    def __setAttr(self, attr, node, toAttr=None):
        values = getattr(self, attr)

        if attr == 'transform':
            # TODO: when use xform to set transform, if any attributes locked,
            #       need to unlock them.
            if isinstance(values, dict) and cmds.objectType(node, isAType='transform'):
                cmds.warning('MayaAttrs@xBlockUtils::sequenced "transform" attribute can set keyframe only with fourByFourMatrix node.')
            else:
                nodeType = cmds.objectType(node)
                if nodeType == 'transform':
                    cmds.xform(node, m=value)
                elif nodeType == 'fourByFourMatrix':
                    attrs = []
                    for i in range(4):
                        for j in range(4):
                            attrs.append('in%d%d' % (i, j))
                    if isinstance(values, dict):
                        for time, value in values.items():
                            for i in range(16):
                                cmds.setKeyframe(node, at=attrs[i], v=value[i], t=time)
                    else:
                        for i in range(16):
                            cmds.setAttr('%s.%s'%(node, attrs[i]), values[i])
                else:
                    cmds.warning('MayaAttrs@xBlockUtils::"transform" attribute does not support %s node' % nodeType)
        else:
            if toAttr != None:
                attr = toAttr

            # unlock attribute
            cmds.setAttr('%s.%s'%(node, attr), l=False)

            if isinstance(values, dict):
                for time, value in values.items():
                    cmds.setKeyframe(node, at=attr, v=value, t=time)
            else:
                cmds.setAttr('%s.%s'%(node, attr), values)


    def getAttrListFromGroup(self, name):
        attrs = []
        idx = self.attrGroups.index(name) * 3
        for i in range(3):
            attrs.append(self.attrList[idx + i])

        return attrs


    def setAttr(self, attr, node, toAttr=None):
        attrs = []
        if attr in self.attrList:
            attrs.append(attr)
        elif attr in self.attrGroups:
            attrs = self.getAttrListFromGroup(attr)
        else:
            cmds.warning('MayaAttrs@dxBlockUtils::"%s" is not available' % attr)

        for attr in attrs:
            self.__setAttr(attr, node, toAttr)


    def setAllAttrs(self, node):
        # this function ignores "transform". if you want set transform attribute,
        # use setAttr('transform', node)
        for attr in self.attrList[:-1]:
            if getattr(self, attr) != None:
                self.__setAttr(attr, node)


def __UsdXformToMayaAttr(Op, res):
    '''
    USD attribute to maya attribute
    "res" argument is MayaAttrs class. If some attributes have values, it will set them to res.
    The values with timeSamples, use dict() that the key is time and the value is the value at the time.
    eg. no time sample > res.translateX = 1.0
    eg. time sample    > res.translateX = { 3:1.0, 4:1.3, ... }

    usd attributes to maya attributes

     XformOp Type Index

     1 : UsdGeom.XformOp.TypeTranslate
     2 : UsdGeom.XformOp.TypeScale
     3 : UsdGeom.XformOp.TypeRotateX
     4 : UsdGeom.XformOp.TypeRotateY
     5 : UsdGeom.XformOp.TypeRotateZ
     6 : UsdGeom.XformOp.TypeRotateXYZ    (ro:0)
     7 : UsdGeom.XformOp.TypeRotateXZY    (ro:3)
     8 : UsdGeom.XformOp.TypeRotateYXZ    (ro:4)
     9 : UsdGeom.XformOp.TypeRotateYZX    (ro:1)
    10 : UsdGeom.XformOp.TypeRotateZXY    (ro:2)
    11 : UsdGeom.XformOp.TypeRotateZYX    (ro:5)
    12 : UsdGeom.XformOp.TypeOrient
    13 : UsdGeom.XformOp.TypeTransform

    attrList = [ 'translateX', 'translateY', 'translateZ' ]
    >> no time samples
    values   = [ {None:1.0},   {None:1.2},   {None:-3.0} ]

    >> with time samples
    values   = [ {1:1.0,  2:1.3, ... },
                 {1:-0.1, 2:1.5, ... },
                 {3:-0.1, 7:0.5, ... } ]

    >> trasform attribute
    attrList = [ 'trasform']
    values   = [ {1:[1.0, 0.0, 0.0, 0.0, 1.0, 0.0, ..... 1.0],
                  2:[1.0, 0.0, 0.0, 0.0, 1.0, 0.0, ..... 1.0],
                  3: ... } ]

    '''
    name = None
    type = None
    attrList    = []

    # rotateOrder is not a attribute of USD, but the OpType number tells which
    # rotate order of it. So, this maya attribute should be got in other ways.
    rotateOrder = None

    #---------------------------------------------------------------------------
    # set name and type.
    if isinstance(Op, Usd.Attribute):
        name = Op.GetName()
    elif isinstance(Op, UsdGeom.XformOp):
        name = Op.GetOpName().split(':')[-1]
        type = Op.GetOpType()
    else:
        return

    if type == None: # means not XformOp
        if name == 'visibility':
            attrList = ['visibility']

    elif type.value == 0: # ?
        pass

    elif type.value <= 2: # translate, scale
        _attrList = None
        if name == 'pivot':
            _attrList = ['rotatePivot', 'scalePivot']
        else:
            _attrList = [name]

        for item in _attrList:
            attrList.extend(['%s%s'%(item, v) for v in 'XYZ'])

    elif type.value <= 5: # rotateX, rotateY, rotateZ
        xyz = type.displayName[-1]
        _attr = name
        if name != type.displayName: # except rotateX(Y, Z)
            _attr += xyz
        attrList = [_attr]

    elif type.value <= 11: # rotateXYZ~ZYX
        xyz = type.name[-3:]
        _attr = name[:-3] if xyz in name else name
        attrList = ['%s%s'%(_attr, v) for v in xyz]

        if name == type.displayName: # only rotate (except rotateAxis)
            rotateOrder = [0,3,4,1,2,5][type.value-6]

    elif type.value == 12: # TODO: orient?
        pass

    elif type.value == 13: # transform
        if name == 'shear':
            attrList = ['shear%s'%v for v in ['XY', 'XZ', 'YZ']]
        elif name == 'transform':
            attrList = [name]

    #---------------------------------------------------------------------------
    # get values with timeSamples
    timeSamples = Op.GetTimeSamples()
    values      = []
    hasKeys     = len(timeSamples) > 1

    for i in range(len(attrList)):
        values.append(dict())

    if not hasKeys:
        timeSamples = [None]

    for t in range(len(timeSamples)):
        time = 0 if timeSamples[t] == None else Usd.TimeCode(timeSamples[t])
        value = Op.Get(time)
        if value == None:
            if name == 'scale':
                value = [1, 1, 1]
            else:
                value = [0, 0, 0]

        # ----------------------------------------------------------------------
        # trimming values
        if name == 'shear':
            value = [value[1][0], value[2][0], value[2][1]]
        elif name == 'visibility':
            value = [value == 'inherited']
        elif name == 'transform':
            _value = []
            for i in range(4):
                for j in range(4):
                    _value.append(value[i][j])
            value = [_value]
        elif name == 'pivot':
            _value = []
            for i in range(2):
                _value.extend([v for v in value])
            value = _value
        elif isinstance(value, float):
            value = [value]

        for i in range(len(attrList)):
            values[i].update({timeSamples[t]:value[i]})

    # --------------------------------------------------------------------------
    # set values to res
    for i in range(len(attrList)):
        if hasKeys:
            setattr(res, attrList[i], values[i])
        else:
            setattr(res, attrList[i], values[i][None])

    if rotateOrder != None:
        setattr(res, 'rotateOrder', rotateOrder)


def GetMayaTransformAttrs(prim):
    res        = MayaAttrs()
    usdAttrs   = []
    extraAttrs = ['visibility']

    # --------------------------------------------------------------------------
    # check prim argument and get properties from xformOpOrder and visibility

    # if prim is not Usd.Prim instance or it doesn't have xformOpOrder,
    # it will return {} with warning
    if not isinstance(prim, Usd.Prim) or not prim.HasAttribute('xformOpOrder'):
        cmds.warning('GetMayaTransformAttrs@dxBlockUtils::Given prim is not available')
        return res

    # make a list for xform properties, if xformOpOrder has !invert! or
    # no attribute in prim, it skips.
    xformOpOrder = prim.GetAttribute('xformOpOrder').Get()
    if xformOpOrder:
        for attr in xformOpOrder:
            if not '!invert!' in attr and prim.HasAttribute(attr):
                attr = prim.GetAttribute(attr)
                usdAttrs.append(UsdGeom.XformOp(attr))

    # make a list for extra properties.
    for attr in extraAttrs:
        if prim.HasAttribute(attr):
            usdAttrs.append(prim.GetAttribute(attr))

    # --------------------------------------------------------------------------
    # get property value
    for attr in usdAttrs:
        __UsdXformToMayaAttr(attr, res)

    return res

def ImportAllCurves(filename, topNode):
    stage  = Usd.Stage.Open(filename)
    curves = []
    for p in stage.Traverse():
        curve = ImportCurveToMaya(p, topNode)
        if curve:
            curves.append(curve)

    return curves


def ImportCurveToMaya(prim, top):
    # check curve types. Only support those types
    supportedCurveTypes = [
        'BasisCurves',
        'NurbsCurves'
    ]
    if not prim.GetTypeName() in supportedCurveTypes:
        return

    # --------------------------------------------------------------------------
    name = prim.GetName()
    path = '%s|%s' % (top, '|'.join(str(prim.GetPrimPath()).split('/')[2:]))
    degree = 3
    curveGeom   = None
    vertexCount = None
    pointRange  = None

    # --------------------------------------------------------------------------
    # get curve infos
    if prim.GetTypeName() == 'BasisCurves':
        curveGeom = UsdGeom.BasisCurves(prim)

        # now only support bspline attributes.
        # TODO: bezier, catmullRom, hermite, power

        if not curveGeom.GetBasisAttr().Get() == 'bspline':
            cmds.warning('ImportCurveToMaya@xBlockUtils::BasisCurves type only support bspline')
            return

        # set degree from curve type
        curveType = curveGeom.GetTypeAttr().Get()
        if curveType == 'cubic':
            degree = 3
            pointRange = [2, -2]
        elif curveType == 'linear':
            degree = 1

        vertexCount  = curveGeom.GetCurveVertexCountsAttr().Get()
        if not vertexCount:
            if cmds.objExists(path):
                cmds.setAttr('%s.%s'%(path, 'visibility'), False)
            return
        else:
            vertexCount = vertexCount[0] - 2*(degree - 1)

    elif prim.GetTypeName() == 'NurbsCurves':
        # cmds.warning('ImportCurveToMaya@xBlockUtils::NurbsCurves not supported')

        curveGeom = UsdGeom.NurbsCurves(prim)

        # set degree from curve type
        curveOrder = curveGeom.GetOrderAttr().Get()
        vertexCount = curveGeom.GetCurveVertexCountsAttr().Get()

        if not vertexCount:
            if cmds.objExists(path):
                cmds.setAttr('%s.%s'%(path, 'visibility'), False)
            return
        else:
            curveOrder = curveOrder[0]
            degree = curveOrder - 1
            vertexCount = vertexCount[0]

    # --------------------------------------------------------------------------
    # get points
    pointsAttr  = curveGeom.GetPointsAttr()
    timeSamples = pointsAttr.GetTimeSamples()
    points      = []

    knots = [0]*(degree - 1)
    knots.extend(range(vertexCount - (degree - 1)))
    knots.extend([knots[-1]]*(degree - 1))

    if len(timeSamples) <= 1:
        timeSamples = [None]

    for t in range(len(timeSamples)):
        time = 0 if timeSamples[t] == None else Usd.TimeCode(timeSamples[t])
        ps = pointsAttr.Get(time)
        if pointRange != None:
            ps = ps[pointRange[0]:pointRange[1]]

        points.append(ps)

    # --------------------------------------------------------------------------
    # create curve
    curve = cmds.curve(degree=degree, knot=knots, point=points[0])
    curveShape = None
    # merged = len(prim.GetAuthoredPropertiesInNamespace('xformOp')) > 0
    merged = True # if use merged by xformOp, use upper line

    if cmds.objExists(path):
        cmds.delete(path)


    # Curves can merge with transform or not, so for the first, check those are
    # merged or not.
    if merged:
        # set path to curve's parent
        path = '|'.join(path.split('|')[:-1])
        curve = cmds.parent(curve, path, r=True)[0]
        curve = cmds.rename(curve, name)

        curve = '%s|%s' % (path, curve.split('|')[-1])
        curveShape = cmds.listRelatives(curve, shapes=True, fullPath=True)[0]

    else:
        # get curve shape and transform node
        _curve = curve
        _shape = cmds.listRelatives(curve, shapes=True, fullPath=True)[0]
        curve  = '|'.join(path.split('|')[:-1])

        # parent shape to transform
        curveShape = cmds.parent(_shape, curve, shape=True, add=True)[0]
        curveShape = cmds.rename(curveShape, name)
        # delete old shape
        cmds.delete(_curve)

        # rename shape



    # --------------------------------------------------------------------------
    # if deformed, add blendshapes
    if len(timeSamples) > 1:
        targets = []
        blsNum = 1
        for point in points:
            c = cmds.curve(degree=degree, knot=knots, point=point)
            c = cmds.rename(c, '%s_%d' % (name, blsNum))
            blsNum += 1

            shape = cmds.listRelatives(c, shapes=True)[0]
            shape = cmds.parent(shape, curve, add=True, shape=True)[0]

            cmds.delete(c)
            targets.append(shape)

        targets.append(curveShape)

        bls = cmds.blendShape(*targets)[0]
        targetAttrs = [v.split('|')[-1] for v in targets[:-1]]

        # turn on intermediateObject attribute for all target shapes
        for shape in targets[:-1]:
            cmds.setAttr('%s.intermediateObject' % shape, True)

        for i in range(len(timeSamples)):
            t = timeSamples[i]

            if i > 0: # skip the first frame
                cmds.setKeyframe('%s.%s' % (bls, targetAttrs[i]), t=t-1, v=0)

            cmds.setKeyframe('%s.%s' % (bls, targetAttrs[i]), t=t, v=1)

            if i < len(timeSamples) - 1: # skip the last frame
                cmds.setKeyframe('%s.%s' % (bls, targetAttrs[i]), t=t+1, v=0)

    # --------------------------------------------------------------------------
    # set transform node

    # set trasform attribute (xform, visibility)
    if merged:
        mayaAttrs = GetMayaTransformAttrs(prim)
        mayaAttrs.setAllAttrs(curve)

    # --------------------------------------------------------------------------
    # set widths
    widthsAttr = curveGeom.GetWidthsAttr()
    widths     = widthsAttr.Get()
    bwAttr = 'rman__torattr___curveBaseWidth'
    twAttr = 'rman__torattr___curveTipWidth'
    
    baseWidthAttr = curveGeom.GetPrim().GetAttribute('primvars:torattr___curveBaseWidth')
    tipWidthAttr = curveGeom.GetPrim().GetAttribute('primvars:torattr___curveTipWidth')

    cmds.addAttr(curveShape, ln=bwAttr, at='float')
    cmds.addAttr(curveShape, ln=twAttr, at='float')

    if baseWidthAttr and tipWidthAttr:
        print baseWidthAttr.Get(), tipWidthAttr.Get()
        cmds.setAttr('%s.%s' % (curveShape, bwAttr), baseWidthAttr.Get())
        cmds.setAttr('%s.%s' % (curveShape, twAttr), tipWidthAttr.Get())
    elif len(widths):
        cmds.setAttr('%s.%s' % (curveShape, bwAttr), widths[0])
        cmds.setAttr('%s.%s' % (curveShape, twAttr), widths[-1])

    # set material set
    SetUsdAttributes(curveShape, curveGeom.GetPrim().GetAuthoredPropertiesInNamespace('userProperties'), override=True)

    # set prim path
    primPath = prim.GetPath().pathString
    splitPath = primPath.split('/')
    splitPath[1] = top.split('|')[-1].split(':')[-1]
    objPathStr = string.join(splitPath, '|')
    root = cmds.ls(top, l=True)[0]
    objPath = Import.GetObject(objPathStr, root)
    if objPath:
        if not cmds.attributeQuery('primPath', n=objPath, ex=True):
            cmds.addAttr(objPath, ln='primPath', dt='string')
        cmds.setAttr('%s.primPath' % objPath, primPath, type='string')

    return curve


# ----------------------------------------------------------------------------
#
#   Import Geom Post Process
#
# ----------------------------------------------------------------------------
class ImportGeomPostProcess:
    def __init__(self, filename, rootNode):
        self.filename = filename

        self.rootNode = cmds.ls(rootNode, l=True)[0]

        self.specializes_DATA = {}
        self.geomList = []
        self.filename = filename


    def doIt(self):
        self.stage = Usd.Stage.Open(self.filename)
        dprim = self.stage.GetDefaultPrim()

        # curve
        curves = list()
        for p in iter(self.stage.Traverse()):
            ptype = p.GetTypeName()

            path = self.getMayaPath(p, dprim)
            shape= cmds.ls(path, dag=True, s=True, ni=True)

            # Add Curves
            supportedCurveTypes = ['BasisCurves', 'NurbsCurves']

            if ptype in supportedCurveTypes:
                curve = ImportCurveToMaya(p, self.rootNode)
                if curve:
                    curves.append(curve)

            if shape:
                # Add userProperties
                self.AddUserProperties(p, shape[0])
                # Add subdivisionScheme
                if ptype == 'Mesh':
                    self.AddSubivisionScheme(p, shape[0])

        geomPrim = self.stage.GetPrimAtPath('/%s' % dprim.GetName())
        # self.mainName = dprim.GetName()
        self.walk(geomPrim)

        cmds.select(self.rootNode)
        xbExtra.puraCollapsed()

    def walk(self, prim):
        for p in prim.GetAllChildren():
            if Represent.Expanded().IsGeom(p):
                geomType = p.GetTypeName()
                if geomType == "Mesh":
                    pass
            else:
                if p.HasAuthoredSpecializes():
                    self.specializes_doIt(p)
                elif p.HasAuthoredReferences():
                    self.references_doIt(p)
                else:
                    self.walk(p)

    def createReferenceNode(self, prim, filePath, primPath="", excludePrimPaths="", variants=[]):
        refNode = cmds.createNode('pxrUsdProxyShape')
        cmds.setAttr('%s.filePath' % refNode, filePath, type='string')
        cmds.setAttr('%s.primPath' % refNode, primPath, type='string')
        cmds.setAttr('%s.excludePrimPaths' % refNode, excludePrimPaths, type='string')
        Represent.Expanded().setVariants(refNode, variants)

        # if prim.Get
        sceneGraphPath = prim.GetPath().pathString
        mayaPath = sceneGraphPath.replace('/', '|')
        splitMayaPath = mayaPath.split('|')
        dagPath = self.rootNode + '|' + '|'.join(splitMayaPath[2:])
        parentPath = self.rootNode + '|' + '|'.join(splitMayaPath[2:-1])

        if cmds.objExists(dagPath):
            cmds.delete(dagPath)

        refNode = cmds.rename(cmds.listRelatives(refNode, p=True)[0], prim.GetName())
        refNode = cmds.parent(refNode, parentPath)[0]
        self.setDefault(refNode)
        Represent.Expanded().setXformOp(prim, refNode)
        return refNode

    def setDefault(self, node):
        for m in ['translate', 'rotate', 'scale']:
            cmds.setAttr('%s.%s' % (node, m), 0, 0, 0, type="double3")
            if m == 'scale':
                cmds.setAttr('%s.%s' % (node, m), 1, 1, 1, type="double3")


    def references_doIt(self, prim):
        stack = prim.GetPrimStack()
        primPath = ''  # stack[0].path
        info = self.references_getInfo(stack[0])
        if info.has_key('primPath'):
            primPath = info['primPath']
        refNode = self.createReferenceNode(prim, filePath=info.get('assetPath', ''), primPath=primPath,
                                           excludePrimPaths=info.get('excludePrimPaths', ''),
                                           variants=info.get('variants', []))

    def references_getInfo(self, spec):
        identifier = spec.layer.identifier
        assetPath = spec.referenceList.prependedItems[0].assetPath
        fullPath = os.path.abspath(os.path.join(utl.DirName(identifier), assetPath))
        data = {
            'assetPath': fullPath,
            'variants': Represent.Expanded().GetVariants(spec)
        }
        # custom data
        if spec.customData.has_key('excludePrimPaths'):
            data['excludePrimPaths'] = spec.customData.get('excludePrimPaths')
        if spec.customData.has_key('primPath'):
            data['primPath'] = spec.customData.get('primPath')
        return data

    def specializes_doIt(self, prim):
        if prim.IsInstanceable():
            msg.debug('>', prim.GetPath().pathString, 'instanceable')
            stack = prim.GetPrimStack()
            primPath = ''
            info = self.specializes_getInfo(stack[-1])
            if info.has_key('primPath'):
                primPath = info['primPath']
            refNode = self.createReferenceNode(prim, filePath=info.get('assetPath', ''), primPath=primPath,
                                               excludePrimPaths=info.get('excludePrimPaths', ''),
                                               variants=info.get('variants', []))

    def specializes_getInfo(self, spec):
        source = spec.nameChildren.get('source')
        if not source:
            return

        if not self.specializes_DATA.has_key(spec.path):
            info = self.references_getInfo(source)
            self.specializes_DATA[spec.path] = info

        return self.specializes_DATA[spec.path]


    def getMayaPath(self, prim, dprim):
        path = prim.GetPrimPath().pathString.replace('/', '|')
        if not path.startswith(self.rootNode):
            path = path.replace('|' + dprim.GetName(), self.rootNode)
        return path


    def AddUserProperties(self, prim, shape):
        SetUsdAttributes(shape, prim.GetAuthoredPropertiesInNamespace('userProperties'), override=True)


    def AddSubivisionScheme(self, prim, shape):
        geom = UsdGeom.Mesh(prim)
        attr = geom.GetSubdivisionSchemeAttr()
        if attr:
            scheme = attr.Get()
            if not cmds.attributeQuery('USD_ATTR_subdivisionScheme', n=shape, ex=True):
                cmds.addAttr(shape, ln='USD_ATTR_subdivisionScheme', nn='subdivisionScheme', dt='string')
            cmds.setAttr('%s.USD_ATTR_subdivisionScheme' % shape, scheme, type='string')


class SetUsdAttributes:
    '''
    UsdAttribute -> Set or Add attributes. not support animated data
    '''
    def __init__(self, shape, usdAttrs, override=False):
        self.shape = shape
        self.usdAttrs = usdAttrs
        self.override = override
        self.doIt()

    def doIt(self):
        for attr in self.usdAttrs:
            val = attr.Get(0)
            ln  = attr.GetBaseName()
            typ = attr.GetTypeName().type.typeName
            if cmds.attributeQuery(ln, n=self.shape, ex=True):
                if self.override:
                    self.setAttribute(self.shape, ln, val, typ)
            else:
                self.addAttribute(self.shape, ln, typ)
                self.setAttribute(self.shape, ln, val, typ)


    def addAttribute(self, shape, ln, typ):
        _atmap = {'double': 'double', 'float': 'float', 'int': 'long'}
        if typ == 'string':
            cmds.addAttr(shape, ln=ln, nn=ln, dt='string')
        else:
            cmds.addAttr(shape, ln=ln, nn=ln, at=_atmap[typ])

    def setAttribute(self, shape, ln, val, typ):
        if typ == 'string':
            cmds.setAttr(shape + '.' + ln, val, type='string')
        else:
            cmds.setAttr(shape + '.' + ln, val)

