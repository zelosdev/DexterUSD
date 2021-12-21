import DXUSD.moduleloader as moduleloader
from DXUSD import Exporters

moduleloader.load(Exporters.__file__, Exporters.__name__, __name__)
moduleloader.load(__file__, __name__)
