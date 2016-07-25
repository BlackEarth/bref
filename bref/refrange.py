
import re, functools

@functools.total_ordering
class RefRange(list):
    """the type of the object returned by RefParser.parse_one() -- a list of two references representing a range."""

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

if __name__ == "__main__":
    import doctest
    doctest.testmod()
