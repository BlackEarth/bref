
import re, logging

from bl.dict import Dict
from bxml.xml import XML

from .ref import Ref
from .refrange import RefRange
from .reflist import RefList
from .book import Book
from .canon import Canon

LOG = logging.getLogger(__name__)

class RefParser(Dict):
    """Tool to 
        * tell if a string is a Ref, 
        * parse strings into Refs, and 
        * format RefLists and RefRanges.
    """

    def __repr__(self):
        return "RefParser(%s)" % repr(self.canon)

    def __init__(self, canon=None):
        if type(canon)==Canon:
            self.canon = canon
        else:
            Dict.__init__(self, canon=Canon.from_xml(XML(fn=canon)))
        for book in self.canon.books:
            book.rexp = re.compile(book.pattern, flags=re.I+re.U)

    def match_book(self, bkarg):
        """return the Book record for a given bk arg"""
        for book in self.canon.books:
            if re.match(book.rexp, bkarg):
                return book

    def chapters_in(self, bk):
        """return the number of chapters in a given book"""
        book = self.match_book(bk)
        return len(book.chapters)
                
    def verses_in(self, bk, ch):
        """return the number of verses in a given book and chapter"""
        book = self.match_book(bk)
        if len(book.chapters) < int(ch)-1:
            return 0
        else:
            return int(book.chapters[int(ch)-1].vss)

    def clean_intstr(self, intstr=None):
        """return a string that will convert cleanly to an int"""
        if intstr is not None:
            md = re.search("[0-9]+", str(intstr))
            if md is not None:
                return md.group(0)
                
    def parse(self, refstring, bk=None, **args):
        """Parses a reference string.
        Returns a list of Ref items, which are [startref, endref] to represent ranges.

        Input Rules:
        * Either the ref input string must begin with a book name, or a "bk" arg must be given.
        * references are separated by semi-colons, commas, or newlines/linefeeds
            - comma usually indicates a verse break, sometimes a chapter break
            - semi-colon, newline, linefeed all indicate a chapter or book break
        * book, ch, vs separated by periods, spaces, underscores, or colons
        * ranges indicated by one or more hyphens
        * whole chapters indicated by lack of verse number
        * whole books indicated by book name without chapter or verse numbers
        * following references that lack a bookname take it from the previous reference
        """
        refstring = self.clean_refstring(refstring)
        LOG.debug(refstring, '[' + (bk or '') + ']')

        tokens = re.split("([.,;\-] ?)", refstring)       # sequence of tokens
        
        # look for 'f' or 'ff' at the end of numeric tokens
        for i in range(len(tokens)-1, 0, -1):           # count backwards to avoid conflict
            if re.match("^[0-9]+f$", tokens[i], re.I):
                tokens[i] = re.sub('f', '', tokens[i], re.I)
                tokens.insert(i+1, '-')
                tokens.insert(i+2, 'F')                 # special token: get the next ch or vs number.
            elif re.match("^[0-9]+ff$", tokens[i], re.I):
                tokens[i] = re.sub('f', '', tokens[i], re.I)
                tokens.insert(i+1, '-')
                tokens.insert(i+2, 'FF')                # special token: get the last ch or vs number.

        # either bk is a parameter or the first token, or this is not a reference
        if self.match_book(tokens[0]) is None:
            if bk is None :
                return RefList()
            else:   # bk is not None
                trybook = self.match_book(bk)
                if trybook is not None:
                    # insert the book and sep at beginning of token list
                    tokens.insert(0, '.')
                    tokens.insert(0, trybook.name)

        # initialize data
        reflist = RefList()
        crng = self.create_range()
        cref = crng[0]

        # initial conditions
        prev = None         # the type of the previous token
        book = Book()
        expect = 'BOOK'   # start by looking for a book token

        # state machine operates on each token and can access prev and next tokens
        for i in range(len(tokens)):
            token = tokens[i]
            LOG.debug(token, "    expect =", str(expect), "    prev =", str(prev))
                
            if token == '.':                # .
                if prev=='BOOK':
                    # if one chapter book, expect ch or vs
                    if self.chapters_in(book.name)==1:
                        expect = 'CHORVS'
                    # otherwise, expect ch
                    else:
                        expect = 'CH'
                elif prev=='CH':
                    expect = 'VS'
            elif re.match("^(?:ch|chap|chapter)?s?$", token, re.I):      # the word "chapter" or some form thereof
                expect= 'CH'
            elif token in [';', ',']:              # ; or , -- slightly different, but some overlap as well
                # add crng to reflist and initialize new range
                self.append_range(crng, reflist)
                
                prevref = cref
                crng = RefRange((Ref(), Ref()))
                cref = crng[0]
                cref.bk = prevref.bk
                LOG.debug("  --> new crng =", str(crng))
                # if no previous token or previous token was a book, expect a book
                if prev in [None, 'BOOK']:
                    expect = 'BOOK'
                # if the previous token was a ch, expect a book or a ch
                elif prev =='CH':
                    expect = 'BOOKORCH'
                # if prev was a vs, depends on whether it's ; or ,
                else:
                    if token == ',':
                        expect = 'VS'
                        cref.ch = prevref.ch                        
                    if token == ';':
                        expect = 'BOOKORCH'
            elif token == '-':              # -
                # switch cref to crng[1]
                cref = crng[1]
                LOG.debug("  --> switch to crng[1] =", str(crng[1]))
                # if the previous token was a book, expect a book
                if prev == 'BOOK': expect = 'BOOK'
                # if the previous token was a ch, expect a book or a ch
                elif prev == 'CH': expect = 'BOOKORCH'
                # if the previous token was a vs, expect a ch or a vs (depends on following token)
                elif prev == 'VS': expect = 'CHORVS'
            else:                           # content token
                if expect == 'BOOK':
                    # if the token matches a book, then assign it as the book for cref
                    trybook = self.match_book(token)
                    if trybook is not None:
                        book = trybook
                        #for k in book.keys(): cref[k] = book[k]
                        cref.bk = book.name
                        cref.id = book.id
                        LOG.debug("  --> book =", book.name)
                    # otherwise, the book is null
                    prev = 'BOOK'
                elif expect == 'BOOKORCH':
                    # if the token matches a book, then assign it as the book for cref
                    trybook = self.match_book(token)
                    if trybook is not None:
                        book = trybook
                        for k in book.keys(): cref[k] = book[k]
                        cref.bk = book.name
                        prev = 'BOOK'
                        LOG.debug("  --> book =", book.name)
                    # otherwise, assign it as the chapter for the cref
                    else:
                        if self.chapters_in(crng[0].bk) == 1 and token != '1':
                            cref.ch = '1'
                            cref.vs = self.get_vs(crng, token)
                            LOG.debug("  --> vs =", token)
                            prev = 'VS'
                        else:
                            cref.ch = self.get_ch(crng, token)
                            LOG.debug("  --> ch =", token)
                            prev = 'CH'
                elif expect == 'CHORVS':
                    # either prev=='VS' followed by '-',
                    # or prev=='BOOK'
                    # set up following token
                    if i+1 < len(tokens): following = tokens[i+1]
                    else: following = None
                    # prev vs
                    if prev=='VS' and tokens[i-1]=='-':
                        trybook = self.match_book(token)
                        if trybook is not None:
                            book = trybook
                            for k in book.keys(): cref[k] = book[k]
                            cref.bk = book.name
                            LOG.debug("  --> book =", book.name)
                            prev = 'BOOK'
                        elif following == '.':
                            # the token is a ch
                            cref.ch = self.get_ch(crng, token)
                            LOG.debug("  --> ch =", cref.ch)
                            prev = 'CH'
                        else:
                            # the token is a vs
                            cref.vs = self.get_vs(crng, token)
                            LOG.debug("  --> vs =", cref.vs)
                            prev = 'VS'
                    # prev one ch book
                    elif prev=='BOOK': 
                        if self.chapters_in(cref.bk) == 1:
                            LOG.debug("  one-chapter book=", cref.bk)
                            # it's a one-chapter book
                            if token != '1':
                                cref.vs = self.get_vs(crng, token)
                                LOG.debug("  --> vs =", token)
                                prev = 'VS'
                            elif following == '.':
                                cref.ch = self.get_ch(crng, token)
                                LOG.debug("  --> ch =", token)
                                prev = 'CH'
                            elif following in ['-', ',']:
                                cref.vs = self.get_vs(crng, token)
                                LOG.debug("  --> vs =", token)
                                prev = 'VS'
                            else:
                                cref.ch = self.get_ch(crng, token)
                                LOG.debug("  --> ch =", token)
                                prev = 'CH'
                        else:
                            # multi-chapter book, so this is a ch
                            cref.ch = self.get_ch(crng, token)
                            LOG.debug("  --> ch =", token)
                            prev = 'CH'                            
                elif expect == 'CH':
                    # the token is a ch
                    cref.ch = self.get_ch(crng, token)
                    LOG.debug("  --> ch =", token)
                    prev = 'CH'
                elif expect == 'VS':
                    trybook = self.match_book(token)
                    if trybook is not None:
                        # the token is a book! yes, it can happen
                        trybook = self.match_book(token)
                        if trybook is not None:
                            book = trybook
                            for k in book.keys(): cref[k] = book[k]
                            cref.bk = book.name
                        cref.vs = cref.ch = None  # no ch assignment yet
                        LOG.debug("  --> bk =", token)
                        prev = 'BOOK'
                    else:
                        cref.vs = self.get_vs(crng, token)
                        LOG.debug("  --> vs =", token)
                        prev = 'VS'
                # expect 'SEP' after a content token
                expect = 'SEP'
        
        # close out last range 
        self.append_range(crng, reflist)

        return reflist

    def get_ch(self, crng, token):
        if token == 'F':
            r = self.parse("%s %s" % (crng[0].bk, str(int(crng[0].ch) + 1)))
            LOG.debug("get_ch, F: r =", r)
            return r[0][0].ch        
        elif token == 'FF':
            r = self.parse("%(bk)s" % crng[0])
            LOG.debug("get_ch, FF: r =", r)
            return r[0][1].ch        
        else:
            return token
        
    def get_vs(self, crng, token):
        if token == 'F':
            r = self.parse("%s %s:%s" % (crng[0].bk, crng[0].ch, str(int(crng[0].vs) + 1)))
            LOG.debug("get_vs, F: r =", r)
            return r[0][0].vs
        elif token == 'FF':
            r = self.parse("%(bk)s %(ch)s" % crng[0])
            LOG.debug("get_vs, FF: r =", r)
            return r[0][1].vs
        else:
            return token


    def append_range(self, rng, liste):
        rng = self.clean_up_range(rng)
        LOG.debug("  --> append range =", str(rng))
        liste.append(rng)

    def create_range(self):
        rng = RefRange((Ref(), Ref()))
        return rng
        
    def refstring(self, ref):
        return self.clean_refstring(self.format(ref))

    def clean_refstring(self, refstr=u''):
        """ cleanup refstr:
            ',' = ref separator, hint to verse
            ';' = ref separator, hint to chapter
            '.' = bk/ch/vs separator
            '-' = range separator
        Usage:
        >>> import bibleweb; db=bibleweb.db(); refparser=RefParser(db)
        >>> refparser.clean_refstring("Gen 3:5-4:7; 5:8-10; Exod 3:2-Lev 4:5")
        u'Gen.3.5-4.7;5.8-10;Exod.3.2-Lev.4.5'
        >>> refparser.clean_refstring("Song of Songs 4 8 -- 5_3")
        u'SongofSongs.4.8-5.3'
        """
        if refstr is None: return None
        refstr = refstr.strip()                  # Remove leading and trailing whitespace
        refstr = refstr.strip('-,;.')            # leading and trailing separators
        refstr = refstr.replace(u'and', ',')
        refstr = refstr.replace('; ', ';')
        refstr = refstr.replace(':', '.')
        refstr = refstr.replace('_', ' ')
        refstr = refstr.replace('\\', '')
        refstr = refstr.replace(u'&#160;', ' ')
        refstr = refstr.replace(u'\u00a0', ' ')
        refstr = refstr.replace(u'\t', ' ')
        refstr = refstr.replace(u'&#150;', '-')
        refstr = refstr.replace(u'&#151;', '-')
        refstr = refstr.replace(u'&#8211;', '-')
        refstr = refstr.replace(u'&#8212;', '-')
        refstr = refstr.replace(u'&#x2010;', '-')
        refstr = refstr.replace(u'&#x2011;', '-')
        refstr = refstr.replace(u'&#x2012;', '-')
        refstr = refstr.replace(u'&#x2013;', '-')
        refstr = refstr.replace(u'&#x2014;', '-')
        refstr = refstr.replace(u'\u2010', '-')
        refstr = refstr.replace(u'\u2011', '-')
        refstr = refstr.replace(u'\u2011', '-')
        refstr = refstr.replace(u'\u2013', '-')
        refstr = refstr.replace(u'\u2014', '-')
        refstr = refstr.replace(u'\x96', '-')
        refstr = refstr.replace(u'\x97', '-')
        refstr = refstr.replace(u'\r', ';')
        refstr = refstr.replace(u'\n', ';')
        refstr = refstr.replace(' -', '-')
        refstr = refstr.replace('- ', '-')
        while ';;' in refstr: refstr=refstr.replace(';;', ';')
        while '--' in refstr: refstr=refstr.replace('--', '-')
        while '  ' in refstr: refstr=refstr.replace('  ', ' ')
        while '..' in refstr: refstr=refstr.replace('..', '.')
        while ',,' in refstr: refstr=refstr.replace(',,', ',')
        refstr = refstr.replace(u' ,', ',')
        refstr = refstr.replace(u', ', ',')
        refstr = refstr.replace(u' ;', ';')
        refstr = refstr.replace(u'; ', ';')
        refstr = re.sub("([123])\s+([A-Za-z])", r'\1\2', refstr)
        # refstr = refstr.replace('1 ', '1')
        # refstr = refstr.replace('2 ', '2')
        # refstr = refstr.replace('3 ', '3')
        # refstr = refstr.replace('4 ', '4')
        # refstr = refstr.replace('5 ', '5')
        # refstr = refstr.replace('6 ', '6')
        # refstr = refstr.replace('7 ', '7')
        # refstr = refstr.replace('8 ', '8')
        # refstr = refstr.replace('9 ', '9')
        # refstr = refstr.replace('0 ', '0')
        # These number words are sometimes used in the ordinal book names 
        # (1 John, etc.).
        refstr = re.sub('(?i)first\s*', '1', refstr)
        refstr = re.sub('(?i)second\s*', '2', refstr)
        refstr = re.sub('(?i)third\s*', '3', refstr)
        refstr = refstr.replace(' ', '.')
        refstr = re.sub("Song\.[^0-9]*", "Song.", refstr)
        refstr = re.sub("\.title", ".0", refstr, flags=re.I)
        return refstr


    def clean_up_range(self, rng):
        """fill the range and make sure ch and vs are ints, with any vs sub modifiers in sub"""
        rng = self.fill_range(rng)
        if rng[0].bk is not None and rng[0].id is None: rng[0].id = self.match_book(rng[0].bk).id
        rng[0].ch = int(self.clean_intstr(rng[0].ch) or 1)                              # rng[0].ch
        rng[1].ch = int(self.clean_intstr(rng[1].ch) or self.chapters_in(rng[0].bk))    # rng[1].ch
        if type(rng[0].vs) == str:
            sub = re.search("[^0-9\W]+$", rng[0].vs)                                    # rng[0].vs
            intstr = self.clean_intstr(rng[0].vs)
            if sub is not None and type(intstr)==str and intstr in rng[0].vs: 
                LOG.debug("  rng[0].vsub =", sub.group(0))
                rng[0].vsub = sub.group(0)
            rng[0].vs = int(self.clean_intstr(rng[0].vs) or 1)
        if type(rng[1].vs) == str:
            sub = re.search("[^0-9\W]+$", rng[1].vs)                                    # rng[1].vs
            intstr = self.clean_intstr(rng[1].vs)
            if sub is not None and type(intstr)==str and intstr in rng[1].vs: 
                LOG.debug("  rng[1].vsub =", sub.group(0))
                rng[1].vsub = sub.group(0)
            rng[1].vs = int(self.clean_intstr(rng[1].vs) or self.verses_in(rng[1].bk, rng[1].ch))
        if rng[0].id is not None and rng[1].id is None:
            rng[1].id = rng[0].id
        return rng
        
    
    def fill_range(self, rng):
        """fill a range that does not have all the verses defined.
        Spec:
        >>> import bibleweb; from bibleweb.models import bible_ref; db=bibleweb.db(); rp=RefParser(db)
        >>> rp.fill_range(bible_ref.RefRange((bible_ref.Ref(db), bible_ref.Ref(db)))).display()
        (u'', u'')
        >>> rp.fill_range(bible_ref.RefRange((bible_ref.Ref(db, bk='Gen'), bible_ref.Ref(db)))).display()
        (u'Gen 1:1', u'Gen 50:26')
        >>> rp.fill_range(bible_ref.RefRange((bible_ref.Ref(db, bk='Gen', ch=3), bible_ref.Ref(db)))).display()
        (u'Gen 3:1', u'Gen 3:24')
        >>> rp.fill_range(bible_ref.RefRange((bible_ref.Ref(db, bk='Gen', ch=3, vs=15), bible_ref.Ref(db)))).display()
        (u'Gen 3:15', u'Gen 3:15')
        >>> rp.fill_range(bible_ref.RefRange((bible_ref.Ref(db, bk='Gen', ch=3, vs=15), bible_ref.Ref(db, vs=17)))).display()
        (u'Gen 3:15', u'Gen 3:17')
        >>> rp.fill_range(bible_ref.RefRange((bible_ref.Ref(db, bk='Gen', ch=3), bible_ref.Ref(db, ch=4)))).display()
        (u'Gen 3:1', u'Gen 4:26')
        >>> rp.fill_range(bible_ref.RefRange((bible_ref.Ref(db, bk='Gen', ch=3, vs=15), bible_ref.Ref(db, ch=4, vs=17)))).display()
        (u'Gen 3:15', u'Gen 4:17')
        """
        LOG.debug("fill range:", [(rng[0].bk, rng[0].ch, rng[0].vs), (rng[1].bk, rng[1].ch, rng[1].vs)])
        
        if rng[0].bk is not None:
            for book in self.canon.books:
                if book.name == rng[0].bk:
                    for key in [key for key in book.keys() if key not in ['chapters', 'pattern', 'rexp']]:
                        rng[0][key] = book[key]
                    break
            if rng[0].ch is not None:
                if rng[0].vs is not None:
                    if rng[1].vs is None: 
                        if rng[1].ch is None:
                            if rng[1].bk is None:       
                                # rng[0] is full, rng[1] is empty, so the range is one verse
                                status = "the range is one verse, make rng[1] = rng[0]"
                                rng[1].bk = rng[0].bk
                                for book in self.canon.books:
                                    if book.name == rng[1].bk:
                                        for key in [key for key in book.keys() if key not in ['chapters', 'pattern', 'rexp']]:
                                            rng[0][key] = book[key]                                
                                        break
                                rng[1].ch = rng[0].ch
                                rng[1].vs = rng[0].vs
                            else: 
                                # rng[0] is full, rng[1].bk is not None, the range is to the end of the second bk
                                status = "the range is to the end of the second bk"
                                rng[1].ch = self.chapters_in(rng[1].bk)
                                rng[1].vs = self.verses_in(rng[1].bk, rng[1].ch)
                        else: 
                            # rng[0] is full, rng[1].ch is not None, so the range is in the same book, to the end of the second ch.
                            status = "the range is in the same book, to the end of the second ch."
                            rng[1].bk = rng[0].bk
                            rng[1].ch = self.chapters_in(rng[1].bk)
                            rng[1].vs = self.verses_in(rng[1].bk, rng[1].ch)
                    else:
                        # rng[0] is full, rng[1].vs is not None, so the range is verses
                        status = "the range is verses either within or between chs"
                        if rng[1].ch is None: rng[1].ch = rng[0].ch
                        if rng[1].bk is None: rng[1].bk = rng[0].bk
                else:
                    # rng[0].vs is None, but rng[0].ch and .bk are defined, so it's either a whole chapter or a range of chapters
                    status = "it's either a whole chapter or a range of chapters"
                    rng[0].wholech = True
                    rng[0].vs = 1
                    if rng[1].bk is None:   # same book
                        rng[1].bk = rng[0].bk
                        if rng[1].ch is None: rng[1].ch = rng[0].ch
                    else:
                        rng[1].ch = rng[1].ch or self.chapters_in(rng[1].bk)
                        status += ", rng[1].ch=%s" % (str(rng[1].ch))
                    if rng[1].vs is None: 
                        rng[1].vs = self.verses_in(rng[1].bk, rng[1].ch) or 0
                        status += ", rng[1].vs=%s" % (str(rng[1].vs))
            else:
                # rng[0].ch is None, but rng[0].bk is defined, so it's either a verse or range in a one ch book, or a range of books
                if rng[0].vs is not None:   # vs or rng in one-chapter book
                    status = "it's a vs or rng in a one-chapter book."
                    rng[0].ch = 1
                    if rng[1].bk is None: rng[1].bk = rng[0].bk
                    if rng[1].ch is None: rng[1].ch = rng[0].ch
                    if rng[1].vs is None: rng[1].vs = rng[0].vs
                else:                       # whole book or range of books
                    status = "it's a whole book or range of books."
                    rng[0].ch = 1
                    rng[0].vs = 1
                    if rng[1].bk is None: rng[1].bk = rng[0].bk
                    if rng[1].ch is None: 
                        rng[1].ch = self.chapters_in(rng[1].bk)
                        status += ", rng[1].ch=%s is last ch in book" % str(rng[1].ch)
                    if rng[1].vs is None: 
                        rng[1].vs = self.verses_in(rng[1].bk, rng[1].ch)
                        status += ", rng[1].vs=%s is last vs in rng[1].ch" % str(rng[1].vs)
        LOG.debug("=>", status)
        LOG.debug("filled range:", [(rng[0].bk, rng[0].ch, rng[0].vs), (rng[1].bk, rng[1].ch, rng[1].vs)])
        rng[0].name = rng[0].bk
        rng[1].name = rng[1].bk
        return rng

    
    def item_name(self, inrefs):
        return self.format(inrefs, cvsep='.', bksep='.', bkarg='romname', 
            vsrsep='-', chrsep='-', bkrsep='-', comma='.', semicolon='.').replace(';','.').replace(' ','')

    def format(self, inrefs, currbk=0, minimize=False, with_bk=True, 
                html=False, uri='', qarg='?bref=', 
                bkarg='name', cvsep=':', bksep=' ', vsrsep='-', 
                chrsep=u'\u2013', bkrsep=u'\u2014', comma=', ', semicolon='; '):
        """Format the output of RefParser.parse(), which is a list of Ref tuples.
        Usage:
        >>> import bibleweb; db=bibleweb.db(); refparser=BibleRefParser(db)
        >>> p = refparser.parse("Exod 3:2-Lev 4:5")
        >>> p.format()
        u'Exod 3:2---Lev 4:5'
        >>> p.format(cvsep='.', bkarg='title_es')
        u'\\xc9xodo 3.2---L\\xe9vitico 4.5'
        >>> p.format(html=True, bkarg='title')
        u"<a href='?bref=Exod.3.2---Lev.4.5'>Exodus 3:2---Leviticus 4:5</a>"
        >>> p.format(html=True, bkarg='title_es')
        u"<a href='?bref=Exod.3.2---Lev.4.5'>\\xc9xodo 3:2---L\\xe9vitico 4:5</a>"
        """
        # ** NOTE REGARDING THE minimize PARAMETER **
        # I would like to include a test for whether the formatted output includes verse numbers when we have the whole chapter,
        # but that requires significant refactoring and retesting of the code.
        # So for now, unless we can find another way to test for chapter length, we have to be content 
        # showing the entire reference in detail.
        
        # normalize inrefs
        # if type(inrefs) in [str, int]:
        #     inrefs = self.parse(inrefs)
        # elif type(inrefs)==Ref:
        #     inrefs = RefList([RefRange((inrefs, Ref()))])
        # elif type(inrefs)==RefRange:
        #     inrefs = RefList([inrefs])
            
        # KLUDGE: fix Psalm vs Psalms
        for ref in inrefs:
            if ref[0].title=='Psalms' and ref[0].bk == ref[1].bk and ref[0].ch == ref[1].ch:
                ref[0].title = ref[1].title = 'Psalm'
            
        currch = 0
        currvs = 0
        out = ""
        for startref, endref in inrefs:
            if startref is None or startref == {}: continue
            if startref is not None and startref.vsub is not None: startref.vsub = startref.vsub.strip("_") # vsub shd be a letter only.
            if endref is not None and endref.vsub is not None: endref.vsub = endref.vsub.strip("_")
            if currbk==startref.bk or with_bk==False:
                if currch==startref.ch:
                    startrefstr = "%s%s%s" % (comma, startref.vs, startref.vsub or '')
                else:
                    if out != '': out += '; '
                    startrefstr = "%s%s%s%s" % (startref.ch, cvsep, startref.vs, startref.vsub or '')
            else:
                if out != '': out += semicolon
                startrefstr = "%s%s%s%s%s%s" % (startref[bkarg], bksep, startref.ch, cvsep, startref.vs, startref.vsub or '')

            currbk, currch, currvs = startref.bk, startref.ch, startref.vs

            if endref is None or endref=={}:
                endrefstr = ""
            elif currbk==endref.bk or with_bk==False:
                if currch==endref.ch:
                    if currvs == endref.vs:
                        endrefstr = ""
                    else:   # one hyphen to separate a vs
                        endrefstr = "%s%s%s" % (vsrsep, endref.vs, endref.vsub or '')
                else:       # default -- to cvsep. ch:vs
                    endrefstr = "%s%s%s%s%s" % (chrsep, endref.ch, cvsep, endref.vs, endref.vsub or '')
            else:           # default --- to cvsep. bk ch:vs
                if bkarg not in endref and bkarg in startref: endref[bkarg] = startref[bkarg]
                endrefstr = "%s%s%s%s%s%s%s" % (bkrsep, endref[bkarg], bksep, endref.ch, cvsep, endref.vs, endref.vsub or '')

            if html==True:                      # format the output to be a list of html links to the given href
                if uri is None: uri = ""
                if qarg is None:
                    qarg = ''
                term = self.clean_refstring(("%(bk)s.%(ch)s.%(vs)s" % startref) + endrefstr)
                out += "<a href='%s'>%s</a>" % (uri + qarg + term, startrefstr+endrefstr)
            else:
                out += startrefstr + endrefstr

        return out


def test_parse():
    """
    >>> import bibleweb; db=bibleweb.db(); rp=RefParser(db)
    >>> rp.parse('Ps 24, 26; 28:8-10').display()                    # comma to separate whole chapters
    [(u'Ps 24:1', u'Ps 24:10'), (u'Ps 26:1', u'Ps 26:12'), (u'Ps 28:8', u'Ps 28:10')]
    >>> rp.parse('Song of Songs 7.1 - 8.5').display()
    [(u'Song 7:1', u'Song 8:5')]
    >>> rp.parse('Gen, Exod').display()
    [(u'Gen 1:1', u'Gen 50:26'), (u'Exod 1:1', u'Exod 40:38')]
    >>> rp.parse('1Kgs 21-2Kgs 22').display()
    [(u'1Kgs 21:1', u'2Kgs 22:20')]
    >>> rp.parse('Gen, Exod 1').display()
    [(u'Gen 1:1', u'Gen 50:26'), (u'Exod 1:1', u'Exod 1:22')]
    >>> rp.parse('Gen - Exod 1').display()
    [(u'Gen 1:1', u'Exod 1:22')]
    >>> rp.parse('Gen 1, 2').display()
    [(u'Gen 1:1', u'Gen 1:31'), (u'Gen 2:1', u'Gen 2:25')]
    >>> rp.parse('Gen 1 - 2').display()
    [(u'Gen 1:1', u'Gen 2:25')]
    >>> rp.parse('Gen 1:1 - 2').display()
    [(u'Gen 1:1', u'Gen 1:2')]
    >>> rp.parse('Gen 1:1 - 2:5').display()
    [(u'Gen 1:1', u'Gen 2:5')]
    >>> rp.parse('Gen 1 - 2:5').display()
    [(u'Gen 1:1', u'Gen 2:5')]
    >>> rp.parse('Gen 1 - 2:5, 7, 9-10').display()
    [(u'Gen 1:1', u'Gen 2:5'), (u'Gen 2:7', u'Gen 2:7'), (u'Gen 2:9', u'Gen 2:10')]
    >>> rp.parse('Gen - Rev').display()
    [(u'Gen 1:1', u'Rev 22:21')]
    >>> rp.parse('Obad 1-2').display()
    [(u'Obad 1:1', u'Obad 1:2')]
    >>> rp.parse('3Jn 1:1-4').display()
    [(u'3Jn 1:1', u'3Jn 1:4')]
    >>> rp.parse('3Jn 1').display()
    [(u'3Jn 1:1', u'3Jn 1:15')]
    >>> rp.parse('3Jn').display()
    [(u'3Jn 1:1', u'3Jn 1:15')]
    >>> rp.parse('Gen 34:8').display()
    [(u'Gen 34:8', u'Gen 34:8')]
    >>> rp.parse('Gen 34:8-Deut').display()
    [(u'Gen 34:8', u'Deut 34:12')]
    >>> rp.parse('Gen 34:8, Deut').display()
    [(u'Gen 34:8', u'Gen 34:8'), (u'Deut 1:1', u'Deut 34:12')]
    >>> rp.parse('Gen 34:8; Deut').display()
    [(u'Gen 34:8', u'Gen 34:8'), (u'Deut 1:1', u'Deut 34:12')]
    >>> rp.parse('Obad 1,3').display()
    [(u'Obad 1:1', u'Obad 1:1'), (u'Obad 1:3', u'Obad 1:3')]
    >>> rp.parse('Gen 1,3').display()
    [(u'Gen 1:1', u'Gen 1:31'), (u'Gen 3:1', u'Gen 3:24')]
    >>> rp.parse('Gen 1:1,3').display()
    [(u'Gen 1:1', u'Gen 1:1'), (u'Gen 1:3', u'Gen 1:3')]
    >>> rp.parse('Gen 1:1;3').display()
    [(u'Gen 1:1', u'Gen 1:1'), (u'Gen 3:1', u'Gen 3:24')]
    >>> rp.parse('Obad 1;3').display()                          # this is a pretty tough edge case - what does the user intend?
    [(u'Obad 1:1', u'Obad 1:21'), (u'Obad 1:3', u'Obad 1:3')]
    >>> rp.parse('Obad 1-3; 1Jn 5').display()                   # another corner case that I just solved
    [(u'Obad 1:1', u'Obad 1:3'), (u'1Jn 5:1', u'1Jn 5:21')]
    >>> rp.parse('Something 1:5')                               # it looks like a reference, but it's not
    []
    >>> rp.parse('Gen 50 - Exod 1').display()                   # chapter range across books should work fine.
    [(u'Gen 50:1', u'Exod 1:22')]
    >>> rp.parse('2Jn.001.001 - Jude.001.025').display()        # it should handle refs correctly.
    [(u'2Jn 1:1', u'Jude 1:25')]
    """

if __name__ == "__main__":
    import doctest
    doctest.testmod()
