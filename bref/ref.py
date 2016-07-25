
import functools
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
        k += "%03d%03d%s" % (self.ch or 0, self.vs or 0, self.vsub or '')
        return k

    # comparison operators
    
    def __lt__(self, other):
        return self.key() < other.key()
 
    def __eq__(self, other):
        return type(self) == type(other) and self.key() == other.key()

if __name__ == "__main__":
    import doctest
    doctest.testmod()
