
class RefList(list):
    """the type of the object returned by RefParser.parse() -- a list of RefRanges."""

    def __str__(self):
        return "[%s]" % ', '.join([str(r) for r in self])

    def __repr__(self):
        return "RefList(%s)" % ', '.join([repr(r) for r in self])        

if __name__ == "__main__":
    import doctest
    doctest.testmod()
