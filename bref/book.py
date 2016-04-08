
import ark
from bl.dict import Dict
from bl.xml import XML
from bl.xbuilder import XBuilder

class Book(Dict):

    @classmethod
    def from_xml(c, xml):
        xml.assertValid()
        assert xml.root.tag == "{%(ark)s}book" % ark.NS
        book = c(
                id=xml.root.get('id'),
                name=xml.root.get('name'),
                title=xml.root.find('{%(ark)s}title' % ark.NS).text,
                pattern=xml.root.find('{%(ark)s}pattern' % ark.NS).text,
                chapters=[
                    Dict(**chapter.attrib)
                    for chapter in xml.root.find('{%(ark)s}chapters' % ark.NS).getchildren()
                ])
        return book

    def to_xml(self, fn=None, config=None):
        E = Builder(default=ark.NS.ark, **ark.NS)._
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