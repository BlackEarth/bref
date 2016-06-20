
from bl.dict import Dict
from bxml import NS
from bxml import XML
from bxml.builder import Builder

class Book(Dict):

    @classmethod
    def from_xml(C, xml):
        # xml.assertValid()
        assert xml.root.tag == "{%(bl)s}book" % NS
        book = C(
            id=xml.root.get('id'),
            name=xml.root.get('name'),
            title=xml.root.find('{%(bl)s}title' % NS).text,
            pattern=xml.root.find('{%(bl)s}pattern' % NS).text,
            chapters=[
                Dict(**chapter.attrib)
                for chapter in 
                xml.root.find('{%(bl)s}chapters' % NS).getchildren()
            ]
        )
        for e in [e for e in xml.root.xpath("*")
                if e.tag.replace("{%(bl)s}" % NS, "") not in ['title', 'pattern', 'chapters']]:
            attr = e.tag.replace("{%(bl)s}" % NS, "")
            book[attr] = e.text
        return book

    def to_xml(self, fn=None, config=None):
        E = Builder(default=NS.bl, **NS)._
        x = XML(fn=fn, config=config,
            root=E.book(
                {'id': self.id,
                'name': self.name},
                E.title(self.title or ''),
                E.pattern(self.pattern or ''),
                E.chapters([
                    E.chapter(**chapter)
                    for chapter in self.chapters])))
        return x

if __name__ == "__main__":
    import doctest
    doctest.testmod()
