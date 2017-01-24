
import functools
import re
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

    @classmethod
    def from_key(Class, key, canon):
        """use a given canon to convert a key into a ref"""
        id, ch, vs = [n.lstrip('0') for n in re.findall('(\d{3})', key)]
        ref = Class(id=id, ch=ch, vs=vs)
        md = re.search("([a-z]+)$", key, flags=re.I)
        if md is not None:
            ref.vsub = md.group(1)
        for book in canon.books:
            if str(book.id) == str(id):
                ref.name = book.name
        return ref

    # comparison operators
    
    def __lt__(self, other):
        return self.key() < other.key()
 
    def __eq__(self, other):
        return type(self) == type(other) and self.key() == other.key()

if __name__ == "__main__":
    import doctest
    doctest.testmod()
