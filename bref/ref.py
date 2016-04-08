# ref.py -- class for dealing with references

DEBUG = False

import re, functools, os.path
from time import time
from bl.dict import Dict

@functools.total_ordering
class Ref(Dict):
    """Holds a single reference, with keys 'id' (int), 'name' (str), 'ch' (int), 'vs' (int).
    """

    def __init__(self, **args):
        Dict.__init__(self, **args)
        if self.id is not None: self.id = int(self.id)
        if self.ch is not None: self.ch = int(self.ch)
        if self.vs is not None: self.vs = int(self.vs)
    
    # -- Other Methods -- 

    def __repr__(self):
        s = "Ref(%s)" % ", ".join(["%s=%s" % (k, repr(self[k])) for k in self.keys()])
        return s

    def __str__(self):
        "returns this Ref as a normalized string"
        r = "%s.%d.%d%s" % (self.name or str(self.id) or '', self.ch or 0, self.vs or 0, self.vsub or '')
        return r

    def key(self):
        """returns a sortkey for this Ref
        """
        k = ""
        if self.id is not None: 
            k += "%03d" % int(self.id)
        elif self.name is not None:
            k += self.name
        else:
            k += '000'
        if self.wholech==True:      # give whole chapters a key of vs=0
            k += "%03d000" % self.ch
        else:
            k += "%03d%03d%s" % (self.ch or 0, self.vs or 0, self.vsub or '')
        return k

    # comparison operators
    
    def __lt__(self, other):
        return self.key() < other.key()
 
    def __eq__(self, other):
        return type(self) == type(other) and self.key() == other.key()


@functools.total_ordering
class RefRange(tuple):
    """the type of the object returned by RefParser.parse_one() -- a tuple of two references representing a range."""

    def __str__(self):
        return "%s-%s" % (str(self[0]), str(self[1]))

    def __repr__(self):
        return "RefRange(%s, %s)" % (repr(self[0]), repr(self[1]))

    def __lt__(self, other):
        return (self[0] < other[0]) or (
            (self[0]==other[0]) and 
                (self[1] < other[1]))   # shorter ranges sort first

    def __eq__(self, other):
        return (self[0]==other[0]) and (self[1]==other[1])

    def __hash__(self):
        # if __eq__() true, __hash__() will be the same (though the inverse is not true)
        return int(re.sub('\D', '', self[0].key()+self[1].key()))


class RefList(list):
    """the type of the object returned by RefParser.parse() -- a list of RefRanges."""

    def __str__(self):
        return "[%s]" % ', '.join([str(r) for r in self])

    def __repr__(self):
        return "RefList(%s)" % ', '.join([repr(r) for r in self])        


if __name__ == "__main__":
    DEBUG = False
    import doctest
    doctest.testmod()
