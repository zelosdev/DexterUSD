#coding:utf-8
from __future__ import print_function

import types
from pxr import Sdf, Usd

import DXUSD.Vars as var
import DXUSD.Message as msg
import DXUSD.Utils as utl


class Arcs:
    '''
    Base composite arcs.

    [Usage]
    # payload and reference
    arc = Arcs(layer, utl.stageMetadata)
    arc.Payload(highGeomLayer, '/asset', purpose=var.RENDER)
    arc.Payload(lowGeomLayer,  '/asset', purpose=var.PROXY)
    arc.Reference(colLayer, '/$D', identifier=False)
    arc.DefaultPrim(assetName='asset')
    arc.DoIt()
    '''
    DEFTOKEN    = '$D'
    SRCTOKEN    = '$S'
    __DEFAULT__ = '__DEFAULT__'
    __SOURCE__  = '__SOURCE__'

    def __init__(self, layer, meta=None, comment=None, custom=None):
        '''
        [Arguments]
        layer (Sdf.Layer)    : target layer
        meta (StageMetadata) : Stage metadata for its layer
        comment (str)        : comment for stage metadata
        custom (dict)        : customLayerData for stage metadata
        '''
        if not isinstance(layer, Sdf.Layer):
            msg.error(TypeError('Given layer is not SdfLayer.'))

        self.layer = layer
        self.meta  = meta if meta else utl.StageMetadata(layer)
        self.comment = comment
        self.custom  = custom

        self.queue = list()
        self.dprim = None

        self.reservedDPrim = None

        # save layers in this list at the end of queue
        self.saveOtherLayers = []


    def DefinePrim(self, path, **kwargs):
        '''
        Define prim. The argument "type" is for the last prim. If given path is
        '/a/b/c' and type is 'SkelRoot', only '/a/b/c' prim type is set to
        'SkelRoot'. '/a', '/a/b' prims are 'xform' if they doesn't exist.

        [Arguments]
        path (Sdf.Path) : prim path

        [**kwargs]
        type (str)      : last prim type
        purpose (str)   : purpose setting. (var.RENDER, var.PROXY)
        kind (str)      : set kind
        custom (str)    : add customData to the prim
        clearCildren (bool) : if True, clear its children (becareful to use)
        vsel (str)      : variant selection
        assetInfo (dict): add assetInfo
        '''

        self.__ResolveDestination(path, specifier=var.DEF, **kwargs)


    def OverPrim(self, path, **kwargs):
        '''
        Over prim.

        [Arguments]
        path (Sdf.Path) : prim path

        [**kwargs]
        type (str)      : last prim type
        purpose (str)   : purpose setting. (var.RENDER, var.PROXY)
        kind (str)      : set kind
        custom (str)    : add customData to the prim
        clearCildren (bool) : if True, clear its children (becareful to use)
        assetInfo (dict): add assetInfo
        '''

        self.__ResolveDestination(path, specifier=var.OVER, **kwargs)

    def ClassPrim(self, path, **kwargs):
        '''
        Class prim

        [Arguments]
        path (Sdf.Path) : prim path

        [**kwargs]
        type (str)      : last prim type
        purpose (str)   : purpose setting. (var.RENDER, var.PROXY)
        kind (str)      : set kind
        custom (str)    : add customData to the prim
        clearCildren (bool) : if True, clear its children (becareful to use)
        assetInfo (dict): add assetInfo
        '''

        self.__ResolveDestination(path, specifier=var.CLASS, **kwargs)


    def DefaultPrim(self, path=None, kind=None, assetName=None, **kwargs):
        '''
        Set default prim. If not set prim path, the first root prim of this
        layer will be the default one. You don't have to define this, becuase
        it will add this function, if not exist in the queue.

        [Arguments]
        path (str)      : default prim path (If None, use the first root prim.)
        kind (str)      : default prim's kind
        assetName (str) : add assetName to default prim

        [**kwargs]
        specifier       : var.DEF, var.OVER, var.CLASS
        type (str)      : last prim type
        purpose (str)   : purpose setting. (var.RENDER, var.PROXY)
        kind (str)      : set kind
        custom (str)    : add customData to the prim
        clearCildren (bool) : if True, clear its children (becareful to use)
        assetInfo (dict): add assetInfo
        '''
        if path:
            self.__ResolveDestination(path, **kwargs)

        self.queue.append((self.__QDefaultPrim, (path, kind, assetName)))


    def ClearPrim(self, path, **kwargs):
        '''
        Clear prim. If you want delete some info of the prim such as identifier,
        then set the argument as 'identifier=True'.

        [Arguments]
        path (Sdf.Path, str) :
        kwargs  : kind, assetName,
                  variants, variantSets
                  payloads, references, relationships, specializes
                  children, properties,
        '''
        self.queue.append((self.__QClearPrim, (path, ), kwargs))


    def AddAttribute(self, path, name, value, attrType=None,
                     variability=Sdf.VariabilityVarying, info = {}, **kwargs):
        '''
        Add attribute to prim.

        [Arguments]
        path (Sdf.Path, str) : prim path
        name (str)           : attribute name
        value                : attribute default value
        type (str, Sdf.ValueTypeNames) : attribute type. if not set, get type
                                         from value type.
        variability (Sdf.Variability) : there are three kinds of variability.
            1. VariabilityVarying : default, animating value
            2. VariabilityUniform : non-animated value
            3. VariabilityConfig  : same as uniform but prim can choose to alter
                                    its collection of built-in properties
        info (dict)          : set info (eg. {'interpolation':'constant'})

        [**kwargs]
        specifier       : var.DEF, var.OVER, var.CLASS
        type (str)      : last prim type
        purpose (str)   : purpose setting. (var.RENDER, var.PROXY)
        kind (str)      : set kind
        custom (str)    : add customData to the prim
        clearCildren (bool) : if True, clear its children (becareful to use)
        assetInfo (dict): add assetInfo
        '''

        # Resolve destination prim
        dst = self.__ResolveDestination(path, **kwargs)
        if dst == var.FAILED:
            return var.FAILED

        self.queue.append((self.__QAddAttribute,
                          (dst, name, value, attrType, variability, info)))


    def DelAttribute(self, path, name):
        '''
        Add attribute to prim.

        [Arguments]
        path (Sdf.Path, str) : prim path
        name (str)           : attribute name
        '''
        # Resolve destination prim
        dst = self.__ResolveDestination(path)
        if dst == var.FAILED:
            return var.FAILED

        self.queue.append((self.__QDelAttribute, (dst, name)))


    def VariantSelect(self, path, variant, select):
        '''
        Select variant for the given path

        [Arguments]
        path (Sdf.Path, str) : prim path
        variant (str)        : variant name
        select (str)         : selection name
        '''
        # Resolve destination prim
        dst = self.__ResolveDestination(path)
        if dst == var.FAILED:
            return var.FAILED

        self.queue.append((self.__QVariantSelect, (dst, variant, select)))


    def CopySpec(self, src, dst, attrs=[], remove=False, **kwargs):
        '''
        Copy source prim spec to destinate prim spec

        [Arguments]
        src (Sdf.PrimSpec, Usd.Prim) :
        dst (Sdf.PrimSpec, Sdf.Path, str) :
        attrs (string[])   :
        remove (bool)      : Remove attribute in src-prim

        [**kwargs]
        type (str)      : last prim type
        purpose (str)   : purpose setting. (var.RENDER, var.PROXY)
        kind (str)      : set kind
        custom (str)    : add customData to the prim
        clearCildren (bool) : if True, clear its children (becareful to use)
        assetInfo (dict): add assetInfo
        '''
        # Resolve source layer
        if not isinstance(src, (Usd.Prim, Sdf.PrimSpec)):
            msg.errmsg('CopySpec@Arcs :',
                       'src must be Sdf.PrimSpec or Usd.Prim')
            return var.FAILED

        # Resolve destination prim
        dst = self.__ResolveDestination(dst, **kwargs)
        if dst == var.FAILED:
            return var.FAILED

        self.queue.append((self.__QCopySpec, (src, dst, attrs, remove)))


    def Sublayer(self, src):
        '''
        [Arguments]
        src (Sdf.Layer, str)   : source layer
        '''
        res = self.__ResolveArcs(src, None, var.ARC.SUB)

        if res != var.SUCCESS:
            msg.warning('Sublayer@Arcs :', 'Ignore composition.(%s)'%str(src))


    def Reference(self, src, dst, identifier=None, srcPrimPath=None, **kwargs):
        '''
        [Arguments]
        src (Sdf.Layer, Sdf.PrimSpec, str): source layer
        dst (Sdf.Path, str) : prim path where reference placed.
        identifier (bool)   : if False, skip adding identifier (default=False)
        srcPrimPath (str)   : source reference's target prim path
                              (when sublayered layer's prim path)
        [**kwargs]
        type (str)      : last prim type
        purpose (str)   : purpose setting. (var.RENDER, var.PROXY)
        kind (str)      : set kind
        custom (str)    : add customData to the prim
        clearCildren (bool) : if True, clear its children (becareful to use)
        assetInfo (dict): add assetInfo
        '''
        res = self.__ResolveArcs(src, dst, var.ARC.REF, identifier=identifier,
                                 srcPrimPath=srcPrimPath, **kwargs)

        if res != var.SUCCESS:
            msg.warning('Reference@Arcs :', 'Ignore composition.(%s)'%str(dst))


    def Payload(self, src, dst, identifier=True, srcPrimPath=None, **kwargs):
        '''
        [Arguments]
        src (Sdf.Layer, Sdf.PrimSpec, str): source layer
        dst (Sdf.Path, str) : prim path where payload placed.
        identifier (bool)   : if False, skip adding identifier (default=True)
        srcPrimPath (str)   : source reference's target prim path
                              (when sublayered layer's prim path)

        [**kwargs]
        type (str)      : last prim type
        purpose (str)   : purpose setting. (var.RENDER, var.PROXY)
        kind (str)      : set kind
        custom (str)    : add customData to the prim
        clearCildren (bool) : if True, clear its children (becareful to use)
        assetInfo (dict): add assetInfo
        '''
        res = self.__ResolveArcs(src, dst, var.ARC.PAY, identifier=identifier,
                                 srcPrimPath=srcPrimPath, **kwargs)

        if res != var.SUCCESS:
            msg.warning('Payload@Arcs :', 'Ignore composition.(%s)'%str(dst))


    def Inherit(self, src, dst, **kwargs):
        '''
        [Arguments]
        src (Sdf.Path, str) : inherit source path
        dst (Sdf.PrimSpec, Sdf.Path, str) ; inherited path

        [**kwargs]
        type (str)      : last prim type
        purpose (str)   : purpose setting. (var.RENDER, var.PROXY)
        kind (str)      : set kind
        custom (str)    : add customData to the prim
        clearCildren (bool) : if True, clear its children (becareful to use)
        assetInfo (dict): add assetInfo
        '''
        res = self.__ResolveArcs(src, dst, var.ARC.INH, **kwargs)

        if res != var.SUCCESS:
            msg.warning('Payload@Arcs :', 'Ignore composition.(%s)'%str(dst))



    def DoIt(self, save=True, meta=True, dprim=True, yup=True, debug=True):
        '''
        Start given compositing args.

        It will resolve your arcs or edits in order to following list
            - define prims
            - set default prim
            - define prims that have '$D' or '$S'
            - compositing arcs
            - edit prims such as adding attribute or clearing prim

        You don't have to care of those order, because it doens't excute your
        commands at calling. It sends the commands to the queue and resolve
        to sort in the order, when you call this function(DoIt).

        [Arguments]
        save (bool) : If true, save its layer. If false, otherwise.
        '''
        if self.__ResolveQueue() != var.SUCCESS:
            msg.errmsg('\t\tDoIt@Arcs :', 'Failed.')
            return var.FAILED

        res = var.SUCCESS

        Sdf.BeginChangeBlock()
        if debug:
            msg.debug('\t\tStart compositing arcs :', self.layer.realPath)

        for f, args, kwargs in self.queue:
            if debug:
                msg.debug('\t\t', f.__name__, args, kwargs)

            # run queues
            res = f(*args, **kwargs)

            if res == var.FAILED:
                msg.errmsg('\t\tDoIt@Arcs :', f.__name__, '>>> Failed :',
                           args, kwargs)
                break
            elif res == var.IGNORE:
                msg.warning('\t\tDoIt@Arcs :', f.__name__, '>>> Ignored :',
                            args, kwargs)
        Sdf.EndChangeBlock()

        # saving
        if res != var.FAILED:
            if not dprim:
                self.dprim = None

            # set stage metadata and save
            if meta:
                self.meta.Set(self.layer, self.dprim,
                              self.comment, self.custom, save)
            else:
                self.layer.Save()

            # save other layers
            for lyr in self.saveOtherLayers:
                lyr.Save(True)

        return var.SUCCESS


    def __ResolveQueue(self):
        prims        = list()
        dprims       = list()
        afterdprims  = list()
        arcs         = list()
        postedit     = list()

        for q in self.queue:
            f = None
            args = list()
            kwargs = dict()

            # resulve function and arguments
            for v in q:
                if isinstance(v, (types.FunctionType, types.UnboundMethodType)):
                    f = v
                elif isinstance(v, (tuple, list)):
                    args.extend(v)
                elif isinstance(v, dict):
                    kwargs.update(v)

            # classify functions
            if f == None:
                continue
            elif f == self.__QDefinePrim:
                q = (f, args, kwargs)
                if q in prims or q in afterdprims:
                    continue

                path = kwargs['path'] if kwargs.has_key('path') else args[0]
                path = str(path)
                if self.__DEFAULT__ in path or self.__SOURCE__ in path or\
                   self.DEFTOKEN    in path or self.SRCTOKEN   in path:
                    afterdprims.append(q)
                else:
                    prims.append(q)

            elif f == self.__QDefaultPrim:
                dprims.append((f, args, kwargs))

            elif f in [self.__QReference, self.__QSublayer, self.__QInherit]:
                arcs.append((f, args, kwargs))

            else:
                postedit.append((f, args, kwargs))

        # if no setting dprim, add default one
        if not dprims:
            if prims:
                dprims.append((self.__QDefaultPrim, (), {}))
            elif self.reservedDPrim:
                dprims.append((self.__QDefaultPrim, (self.reservedDPrim,), {}))


        # set queue
        self.queue = prims
        self.queue.extend(dprims)
        self.queue.extend(afterdprims)
        self.queue.extend(arcs)
        self.queue.extend(postedit)

        return var.SUCCESS


    def __ResolveArcs(self, src, dst, arc, identifier=True, srcPrimPath=None,
                      **kwargs):
        '''
        (Private)
        - Resolve destinate prim
        - Resolve source layer
        - Queue arcs
        '''
        # Resolve source layer
        srcspec = self.__ResolveSource(src, arc)
        if srcspec == var.FAILED:
            return var.FAILED

        dst = self.__ResolveDestination(dst, arc, **kwargs)
        if dst == var.FAILED:
            return var.FAILED

        purpose = kwargs['purpose'] if kwargs.has_key('purpose') else None

        # Queue arcs
        if arc == var.ARC.SUB:
            self.queue.append((self.__QSublayer,
                              (srcspec, )))
        elif arc == var.ARC.REF:
            self.queue.append((self.__QReference, (srcspec, dst, purpose,
                                                   False, identifier,
                                                   srcPrimPath)))
        elif arc == var.ARC.PAY:
            self.queue.append((self.__QReference, (srcspec, dst, purpose, True,
                                                   identifier, srcPrimPath)))
        elif arc == var.ARC.INH:
            self.queue.append((self.__QInherit,
                              (srcspec, dst)))
        else:
            return var.IGNORE

        return var.SUCCESS


    def __ResolveSource(self, src, arc):
        '''
        (Private)
        - Get source layer and default prim
        - Update frame information
        '''
        # if inherit, just return Sdf.Path
        if arc == var.ARC.INH:
            if isinstance(src, Usd.Prim):
                return src.GetPath()
            elif isinstance(src, Sdf.PrimSpec):
                return src.path
            else:
                return Sdf.Path(src)

        # Get source Sdf.Layer
        if isinstance(src, Sdf.PrimSpec):
            srclyr = src.layer
        else:
            srclyr = utl.AsLayer(src)
            if not srclyr:
                msg.errmsg('__ResolveSource@Arcs :',
                          'Given src does not exist.(%s)'%str(src))
                return var.FAILED

        # Get default primSpec. If no default prim, it will find at the
        # subLayers
        srcDPrim = utl.GetDefaultPrim(srclyr, sublayer=True)

        if not srcDPrim:
            if arc == var.ARC.INH:
                msg.errmsg('__ResolveSource@Arcs :',
                          'Given src has no prims.(%s)'%str(src))
                return var.FAILED
            else:
                srcDPrim = srclyr
        # Update stage metatdata when sublayer
        if arc == var.ARC.SUB:
            self.meta.Get(srclyr, compare=True)

        # Set reservedDPrim to find dprim when subLayer
        if arc == var.ARC.SUB or not self.reservedDPrim:
            self.reservedDPrim = srcDPrim

        return src if isinstance(src, Sdf.PrimSpec) else srcDPrim


    def __ResolveDestination(self, dst=None, arc=None, type=None, purpose=None,
                             custom=None, srcspec=None, specifier=None,
                             kind=None, clearChildren=None, assetInfo={}):
        '''
        (Private)
        - Convert tokens to string ($D, $S)
        - Confirm destination prim
        - Resolve variantSets, purpose and clearChildren
        - Queue defining prim
        '''
        if dst == None:
            if arc == var.ARC.SUB:
                return dst
            else:
                msg.errmsg('__ResolveDestination@Arcs :',
                           'No dst path.')
                return var.FAILED
        elif isinstance(dst, Sdf.PrimSpec):
            return dst.path
        else:
            dst = str(dst)

        # Convert token to string
        if self.DEFTOKEN in dst:
            dst = dst.replace(self.DEFTOKEN, self.__DEFAULT__)
        if self.SRCTOKEN in dst:
            dst = dst.replace(self.SRCTOKEN, self.__SOURCE__)

        # Confirm destination prim
        try:
            dst = Sdf.Path(dst)
            if not dst:
                raise Exception('__ResolveDestination@Arcs :',
                                'Given destination prim is not available.(%s)'%\
                                str(dst))
        except Exception as err:
            msg.errmsg(str(err))
            return var.FAILED

        # check clear children
        if arc == var.ARC.PAY:
            clearChildren = True

        # Queue defining prim.
        for primpath in Sdf.Path(dst).GetPrefixes()[:-1]:
            self.queue.append((self.__QDefinePrim, (primpath, )))

        self.queue.append((self.__QDefinePrim,
                          (dst, specifier, type, purpose, kind, custom, srcspec,
                           clearChildren, assetInfo)))
        return dst


    def __ResolveDstPath(self, path, srcspec=None):
        '''
        (Private)

        Rename path, if has __DEFAULT__ or __SOURCE__.
        '''
        if path == None:
            return var.IGNORE
        else:
            path = str(path)

        # $D to __DEFAULT__ and $S to __SOURCE__
        if self.DEFTOKEN in path:
            path = path.replace(self.DEFTOKEN, self.__DEFAULT__)
        if self.SRCTOKEN in path:
            path = path.replace(self.SRCTOKEN, self.__SOURCE__)

        if self.__DEFAULT__ in path:
            path = path.replace(self.__DEFAULT__, str(self.dprim.name))

        if srcspec and self.__SOURCE__ in path:
            if not isinstance(srcspec, Sdf.PrimSpec):
                msg.warning('__ResolveDstPath@Arcs :',
                            'Given path needs prim of source layer.',
                            '(%s)'%path)
                return var.IGNORE

            name = srcspec.name.split(self.dprim.name + '_')[-1]
            path = path.replace(self.__SOURCE__, name if name else srcspec.name)

        path = Sdf.Path(('/%s'%path).replace('//', '/'))

        return path


    def __AddPrim(self, path, type=None, specifier=None):
        '''
        (Private)
        - If not exist prim, create.
        '''
        spec = Sdf.CreatePrimInLayer(self.layer, Sdf.Path(path))
        if type:
            spec.typeName = type

        if specifier != None:
            spec.specifier = specifier

        return spec


    def __AddAttribute(self, spec, name, value, type, variability, info):
        '''
        (Private)
        - If exist attribute, delete then create.
        '''
        # if check attribute exists, then delete
        if name in spec.attributes.keys():
            spec.RemoveProperty(spec.attributes[name])

        attr = Sdf.AttributeSpec(spec, name, type, variability)
        attr.default = value

        for k, v in info.items():
            attr.SetInfo(k, v)

        return attr

    def __AddVariant(self, path, vsel, assetInfo={}):
        '''
        (Private)
        - If not exist variant, create.
        '''
        spec = self.layer.GetPrimAtPath(path)

        if len(vsel) == 2 and vsel[0] and vsel[1]: # vsel = (name, value)
            if vsel[0] not in spec.variantSetNameList.GetAddedOrExplicitItems():
                spec.variantSetNameList.prependedItems.append(vsel[0])

            if vsel[0] in spec.variantSets.keys():
                vset = spec.variantSets[vsel[0]]
            else:
                vset = Sdf.VariantSetSpec(spec, vsel[0])

            if vsel[1] in vset.variants.keys():
                variant = vset.variants[vsel[1]].primSpec
            else:
                variant = Sdf.VariantSpec(vset, vsel[1]).primSpec

            variant.assetInfo.update(assetInfo)

            # if lodVariant, select highest variant
            if vsel[0] == var.T.VAR_LOD:
                for lod in var.T.LODS:
                    if lod in vset.variants.keys():
                        spec.variantSelections.update({vsel[0]:lod})
                        break

            return variant.path
        else:
            return spec.path


    def __QDefinePrim(self, path, specifier=None, type=None,
                      purpose=None, kind=None, custom=None, srcspec=None,
                      clearChildren=None, assetInfo={}):
        '''
        (Private)
        '''
        path = self.__ResolveDstPath(path, srcspec)
        if path == var.IGNORE:
            return path

        if specifier == var.CLASS and not path.IsRootPrimPath():
            msg.errmsg('__QDefinePrim@Arcs :',
                       'Class specifier must be root prim.')
            return var.FAILED

        # confirm type
        if type == None and isinstance(srcspec, Sdf.PrimSpec):
            type = srcspec.typeName

        # check variants
        vsel = None
        if path.IsPrimVariantSelectionPath():
            vsel = path.GetVariantSelection()
            path = path.StripAllVariantSelections()

        # add prim
        spec = self.__AddPrim(path, type, specifier)

        # add variantSelection and update selections
        if vsel:
            path = self.__AddVariant(path, vsel, assetInfo)
            spec.variantSelections.update({vsel[0]:vsel[1]})

        if kind != None:
            utl.SetModelAPI(spec, kind=kind)

        # set custom data
        if isinstance(custom, dict):
            spec.customData.update(custom)

        # purpose
        if purpose:
            # clear current archive
            spec.ClearPayloadList()

            # append purpose prim and attribute
            _path = spec.path.AppendChild(purpose)
            spec = self.__AddPrim(_path, type)
            self.__AddAttribute(spec, 'purpose', purpose,
                               Sdf.ValueTypeNames.Token, Sdf.VariabilityUniform)
        elif clearChildren == True:
                spec.nameChildren.clear()

        # update asset info
        if not vsel:
            spec.assetInfo.update(assetInfo)

        return var.SUCCESS


    def __QDefaultPrim(self, path=None, kind=None, assetName=None):
        '''
        (Private)
        - Find default prim path
        - Set kind and assetName
        - Set default prim
        '''
        spec = None
        if path == None:
            # if path is not set, find default prim in its layer
            spec = utl.GetDefaultPrim(self.layer)
            if not spec:
                msg.warning('__QDefaultPrim@Arcs :',
                            'Its layer has no default prim and root prim.',
                            spec)
                return var.FAILED
        elif isinstance(path, Sdf.PrimSpec):
            spec = path
        else:
            spec = self.layer.GetPrimAtPath(Sdf.Path(path))

        if not spec:
            msg.warning('__QDefaultPrim@Arcs :',
                        'Given path(%s) does not exist.'%str(path),
                        'Use its layers default or root prim.')
            return self.__QDefaultPrim(None, kind, assetName)

        # if default prim is from sublayer, skip setting modelApi
        if spec.layer == self.layer:
            utl.SetModelAPI(spec, name=assetName, kind=kind)

        self.dprim = spec

        return var.SUCCESS


    def __QAddAttribute(self, path, name, value, type=None,
                        variability=Sdf.VariabilityVarying, info={}):
        '''
        (Private)
        '''
        path = self.__ResolveDstPath(path)
        if path == var.IGNORE:
            return path

        spec = self.layer.GetPrimAtPath(path)
        if not spec:
            msg.warning('__QAddAttribute@Arcs :',
                        'Given path is not availabe. (%s)'%str(path))
            return var.IGNORE

        # find type
        try:
            if type == None:
                arraytype = isinstance(value, (tuple, list))
                _v = value[0] if arraytype else value
                if   isinstance(_v, bool):  type = 'bool'
                elif isinstance(_v, int):   type = 'int'
                elif isinstance(_v, float): type = 'float'
                elif isinstance(_v, (str, unicode)): type = 'string'
                else: raise(TypeError)

                type = '%s[]'%type if arraytype else type
                type = Sdf.ValueTypeNames.Find(type)
            elif isinstance(type, str):
                type = Sdf.ValueTypeNames.Find(type)
            elif not isinstance(type, Sdf.ValueTypeNames):
                raise(TypeError)
        except:
            msg.warning('__QAddAttribute@Arcs :',
                        'Given type is not available. (%s)'%str(type))
            return var.IGNORE

        # set variability
        if not isinstance(variability, Sdf.Variability):
            msg.warning('__QAddAttribute@Arcs :',
                        'Given variability is not available. (%s)'%str(type))
            return var.IGNORE

        self.__AddAttribute(spec, name, value, type, variability, info)

        return var.SUCCESS


    def __QDelAttribute(self, path, name):
        '''
        (Private)
        '''
        path = self.__ResolveDstPath(path)
        if path == var.IGNORE:
            return path

        spec = self.layer.GetPrimAtPath(path)
        if not spec:
            msg.warning('__QDelAttribute@Arcs :',
                        'Given path is not availabe. (%s)'%str(path))
            return var.IGNORE

        attr = spec.properties.get(name)
        if attr:
            spec.RemoveProperty(attr)

        return var.SUCCESS


    def __QVariantSelect(self, path, variant, select):
        '''
        (Private)
        '''
        path = self.__ResolveDstPath(path)
        if path == var.IGNORE:
            return path

        spec = self.layer.GetPrimAtPath(path)
        if not spec:
            msg.warning('__QVariantSelect@Arcs :',
                        'Given path is not availabe. (%s)'%str(path))
            return var.IGNORE

        spec.variantSelections.update({variant:select})


    def __QCopySpec(self, src, dst, attrs=[], remove=False):
        '''
        (Private)
        '''
        dst = self.__ResolveDstPath(dst)
        if dst == var.IGNORE:
            return dst

        # CopySpec
        for attr in attrs:
            srcspec = None
            if isinstance(src, Usd.Prim):
                if src.HasProperty(attr):
                    srcspec = src.GetProperty(attr).GetPropertyStack(0)[0]
            elif isinstance(src, Sdf.PrimSpec):
                if attr in src.attributes.keys():
                    srcspec = srcspec.attributes[attr]

            if not srcspec:
                msg.warning('__QCopySpec@Arcs :',
                            'Given attribute(%s) does not exist in prim(%s)'%\
                            (attr, src), dev=True)
                continue

            sapath = srcspec.path
            dapath = dst.AppendProperty(attr)

            Sdf.CopySpec(srcspec.layer, sapath, self.layer, dapath)

            if remove:
                parentspec = srcspec.path.GetParentPath()
                parentspec = srcspec.layer.GetPrimAtPath(parentspec)

                if srcspec.layer not in self.saveOtherLayers:
                    self.saveOtherLayers.append(srcspec.layer)

                # remove attribute
                parentspec.RemoveProperty(srcspec)

        return var.SUCCESS


    def __QClearPrim(self, path, **kwargs):
        '''
        (Private)
        - Resolve path to get prim
        - Clear prim

        # TODO: If user gives specific name or index to value, clear only the
                info refering to given specific value. (For example, variantSets
                has value like 'taskVariant', then delete only the named
                variantSet.)
        '''
        path = self.__ResolveDstPath(path)
        if path == var.IGNORE:
            return path

        spec = self.layer.GetPrimAtPath(path)
        if not spec:
            msg.warning('__QClearPrim@Arcs :',
                        'Given path is not availabe. (%s)'%str(path))
            return var.IGNORE

        kws = dict()
        for k, v in kwargs.items():
            if v:
                kws.update({k:v})

        if kws.has_key('kind'):
            spec.ClearKind()
        if kws.has_key('assetInfo'):
            spec.ClearInfo()
        if kws.has_key('comment'):
            spec.comment = ''
        if kws.has_key('customData'):
            spec.customData.clear()
        if kws.has_key('assetInfo'):
            spec.assetInfo.clear()
        if kws.has_key('variants'):
            spec.variantSelections.clear()
        if kws.has_key('variantSets'):
            for vname in spec.variantSetNameList.GetAddedOrExplicitItems():
                for sel in spec.variantSets[vname].variantList:
                    spec.variantSets[vname].RemoveVariant(sel)
            spec.variantSetNameList.ClearEdits()
            spec.variantSelections.clear()
        if kws.has_key('payloads'):
            spec.ClearPayloadList()
        if kws.has_key('references'):
            spec.ClearReferenceList()
        if kws.has_key('children'):
            spec.nameChildren.clear()
        if kws.has_key('properties'):
            spec.properties.clear()
        if kws.has_key('relationships'):
            spec.relationships.clear()
        if kws.has_key('specializes'):
            spec.specializesList.clear()

        return var.SUCCESS


    def __QReference(self, srcspec, dst, purpose=None, payload=False,
                     identifier=None, srcPrimPath=None):
        '''
        (Private)
        - Resolve and get destinating path and variantSelection
        - Get relative path of source
        - Composite payload or reference
        '''
        dst = self.__ResolveDstPath(dst, srcspec)
        if dst == var.IGNORE:
            return dst

        # add purpose
        if purpose:
            dst = dst.AppendChild(purpose)

        # get primSpec
        spec = self.layer.GetPrimAtPath(dst)

        # get source layer
        if isinstance(srcspec, Sdf.Layer):
            srclyr = srcspec
            srcspec = None
        else:
            srclyr = srcspec.layer

        # create Sdf.Payload or Sdf.Reference arguments
        args = [utl.GetRelPath(self.layer.realPath, srclyr.realPath)]

        if srcPrimPath:
            _path = Sdf.Path(srcPrimPath)
            args.append(_path.MakeAbsolutePath(Sdf.Path.absoluteRootPath))
        else:
            if srcspec and not srclyr.HasDefaultPrim() or \
               srclyr.defaultPrim != srcspec.name:
                args.append(srcspec.path)

        if payload:
            identifier = True if identifier == None else identifier
            utl.SetPayload(spec, Sdf.Payload(*args), identifier)
        else:
            identifier = False if identifier == None else identifier
            utl.SetReference(spec, Sdf.Reference(*args), identifier)

        return var.SUCCESS


    def __QSublayer(self, srcspec):
        '''
        (Private)
        - Get relative path and insert sublayer
        '''
        if isinstance(srcspec, Sdf.Layer):
            srcpath = utl.GetRelPath(self.layer.realPath,
                                     srcspec.realPath)
        else:
            srcpath = utl.GetRelPath(self.layer.realPath,
                                     srcspec.layer.realPath)

        utl.SetSublayer(self.layer, srcpath)

        return var.SUCCESS


    def __QInherit(self, src, dst):
        '''
        (Private)
        '''
        dst = self.__ResolveDstPath(dst)
        if dst == var.IGNORE:
            return dst

        utl.SetInherit(src, self.layer.GetPrimAtPath(dst))
        return var.SUCCESS
