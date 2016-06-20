
from bl.dict import Dict
from bxml import NS
from bxml import XML
from bxml.builder import Builder

from .book import Book

class Canon(Dict):

    def __repr__(self):
        return "Canon(name='%(name)s', lang='%(lang)s')" % self

    @classmethod
    def from_xml(C, xml):
        # xml.assertValid()
        assert xml.root.tag == "{%(bl)s}canon" % NS
        canon = C(
            name = xml.root.get('name'),
            lang = xml.root.get('lang'),
            books = [
                Book.from_xml(XML(root=book, config=xml.config))
                for book in xml.root.getchildren()
            ]
        )
        return canon

    def to_xml(self, fn=None, config=None):
        E = Builder(default=NS.bl, **NS)._
        x = XML(fn=fn, config=config,
            root=E.canon(
                    {'name': self.name,
                    'lang': self.lang}))
        for book in self.books:
            x.root.append(book.to_xml().root)
        return x

if __name__ == "__main__":
    import doctest
    doctest.testmod()
