from pathlib import Path
from bl.dict import Dict
from bxml import XML
from bxml.builder import Builder

from .book import Book
from .ns import NS

CANONS_PATH = Path(__file__).absolute().parent.parent / 'bref' / 'resources' / 'canons'


class Canon(Dict):
    def __repr__(self):
        return "Canon(name='%(name)s', lang='%(lang)s')" % self

    @classmethod
    def load_by_name(cls, name):
        filepath = CANONS_PATH / f"{name}-canon.xml"
        xml = XML(fn=str(filepath))
        return cls.from_xml(xml)

    @classmethod
    def from_xml(cls, xml):
        if isinstance(xml, str):
            xml = XML(fn=xml)
        assert xml.root.tag == "{%(bl)s}canon" % NS
        canon = cls(
            name=xml.root.get("name"),
            lang=xml.root.get("lang"),
            books=[
                Book.from_xml(XML(root=book, config=xml.config))
                for book in xml.root.getchildren()
            ],
        )
        return canon

    def to_xml(self, fn=None, config=None):
        E = Builder.single(NS)
        x = XML(
            fn=fn, config=config, root=E.canon({"name": self.name, "lang": self.lang})
        )
        for book in self.books:
            x.root.append(book.to_xml().root)
        return x


if __name__ == "__main__":
    import doctest

    doctest.testmod()
