import DXUSD.moduleloader as moduleloader
from DXUSD import Tweakers

moduleloader.load(Tweakers.__file__, Tweakers.__name__, __name__)
moduleloader.load(__file__, __name__)
