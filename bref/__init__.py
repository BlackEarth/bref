
import os
from glob import glob
from bl.dict import Dict
from .canon import Canon
from bxml import XML

canons = Dict(**{
    os.path.basename(fn).split('-')[0]: Canon.from_xml(XML(fn=fn)) 
    for fn in 
    glob(os.path.join(os.path.dirname(__file__), 'resources', 'canons', '*.xml'))
})

if __name__ == "__main__":
    import doctest
    doctest.testmod()
