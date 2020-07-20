from pkg_resources import get_distribution, DistributionNotFound

from orthorec.radonortho import *
from orthorec.solver import *
from orthorec.timing import *
try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:
    # package is not installed
    pass