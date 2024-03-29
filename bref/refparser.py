import logging
import re

from bl.dict import Dict
from bxml.xml import XML

from .book import Book
from .canon import Canon
from .ref import Ref
from .reflist import RefList
from .refrange import RefRange

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
        if type(canon) == Canon:
            self.canon = canon
        else:
            Dict.__init__(self, canon=Canon.from_xml(XML(fn=canon)))
        for book in self.canon.books:
            if book.pattern is not None:
                book.rexp = re.compile(book.pattern, flags=re.I + re.U)

    def match_book(self, bkarg):
        """return the Book record for a given bk arg"""
        for book in self.canon.books:
            if book.name == bkarg or book.title == bkarg or book.abbr == bkarg:
                return book
            elif book.rexp is not None and re.match(book.rexp, bkarg):
                return book

    def chapters_in(self, bk):
        """return the number of chapters in a given book"""
        book = self.match_book(bk)
        return len(book.chapters)

    def verses_in(self, bk, ch):
        """return the number of verses in a given book and chapter"""
        book = self.match_book(bk)
        if len(book.chapters) < int(ch) - 1:
            return 0
        else:
            return int(book.chapters[int(ch) - 1].vss)

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
        if re.match(r"^[\d\-,]+$", refstring):
            refstring = self.refstr_from_ids(refstring)
        else:
            refstring = self.clean_refstring(refstring)
        LOG.debug("%s %s" % (refstring, "[" + (bk or "") + "]"))

        tokens = re.split(r"([.,;\-] ?)", refstring)  # sequence of tokens

        # look for 'f' or 'ff' at the end of numeric tokens
        for i in range(len(tokens) - 1, 0, -1):  # count backwards to avoid conflict
            if re.match("^[0-9]+f$", tokens[i], re.I):
                tokens[i] = re.sub("f", "", tokens[i], re.I)
                tokens.insert(i + 1, "-")
                tokens.insert(
                    i + 2, "F"
                )  # special token: get the next ch or vs number.
            elif re.match("^[0-9]+ff$", tokens[i], re.I):
                tokens[i] = re.sub("f", "", tokens[i], re.I)
                tokens.insert(i + 1, "-")
                tokens.insert(
                    i + 2, "FF"
                )  # special token: get the last ch or vs number.

        # either bk is a parameter or the first token, or this is not a reference
        if self.match_book(tokens[0]) is None:
            if bk is None:
                return RefList()
            else:  # bk is not None
                trybook = self.match_book(bk)
                if trybook is not None:
                    # insert the book and sep at beginning of token list
                    tokens.insert(0, ".")
                    tokens.insert(0, trybook.name)

        # initialize data
        reflist = RefList()
        crng = self.create_range()
        cref = crng[0]

        # initial conditions
        prev = None  # the type of the previous token
        book = Book()
        expect = "BOOK"  # start by looking for a book token

        # state machine operates on each token and can access prev and next tokens
        for i in range(len(tokens)):
            token = tokens[i]
            LOG.debug("token = %r\texpect = %r\tprev = %r" % (token, expect, prev))

            if token == ".":  # .
                if prev == "BOOK":
                    # if one chapter book, expect ch or vs
                    if self.chapters_in(book.name) == 1:
                        expect = "CHORVS"
                    # otherwise, expect ch
                    else:
                        expect = "CH"
                elif prev == "CH":
                    expect = "VS"
            elif re.match(
                "^(?:ch|chap|chapter)?s?$", token, re.I
            ):  # the word "chapter" or some form thereof
                expect = "CH"
            elif token in [
                ";",
                ",",
            ]:  # ; or , -- slightly different, but some overlap as well
                # add crng to reflist and initialize new range
                self.append_range(crng, reflist)

                prevref = cref
                crng = RefRange((Ref(), Ref()))
                cref = crng[0]
                cref.bk = prevref.bk
                LOG.debug("--> new crng = %r" % crng)
                # if no previous token or previous token was a book, expect a book
                if prev in [None, "BOOK"]:
                    expect = "BOOK"
                # if the previous token was a ch, expect a book or a ch
                elif prev == "CH":
                    expect = "BOOKORCH"
                # if prev was a vs, depends on whether it's ; or ,
                else:
                    if token == ",":
                        expect = "VS"
                        cref.ch = prevref.ch
                    if token == ";":
                        expect = "BOOKORCH"
            elif token == "-":  # -
                # switch cref to crng[1]
                cref = crng[1]
                LOG.debug("--> switch to crng[1] = %r" % crng[1])
                # if the previous token was a book, expect a book
                if prev == "BOOK":
                    expect = "BOOK"
                # if the previous token was a ch, expect a book or a ch
                elif prev == "CH":
                    expect = "BOOKORCH"
                # if the previous token was a vs, expect a ch or a vs (depends on following token)
                elif prev == "VS":
                    expect = "CHORVS"
            else:  # content token
                if expect == "BOOK":
                    # if the token matches a book, then assign it as the book for cref
                    trybook = self.match_book(token)
                    if trybook is not None:
                        book = trybook
                        # for k in book.keys(): cref[k] = book[k]
                        cref.bk = book.name
                        cref.id = book.id
                        LOG.debug("--> book = %r" % book.name)
                    # otherwise, the book is null
                    prev = "BOOK"
                elif expect == "BOOKORCH":
                    # if the token matches a book, then assign it as the book for cref
                    trybook = self.match_book(token)
                    if trybook is not None:
                        book = trybook
                        for k in book.keys():
                            cref[k] = book[k]
                        cref.bk = book.name
                        prev = "BOOK"
                        LOG.debug("--> book = %r" % book.name)
                    # otherwise, assign it as the chapter for the cref
                    else:
                        if self.chapters_in(crng[0].bk) == 1 and token != "1":
                            cref.ch = "1"
                            cref.vs = self.get_vs(crng, token)
                            LOG.debug("--> vs = %r" % token)
                            prev = "VS"
                        else:
                            cref.ch = self.get_ch(crng, token)
                            LOG.debug("--> ch = %r" % token)
                            prev = "CH"
                elif expect == "CHORVS":
                    # either prev=='VS' followed by '-',
                    # or prev=='BOOK'
                    # set up following token
                    if i + 1 < len(tokens):
                        following = tokens[i + 1]
                    else:
                        following = None
                    # prev vs
                    if prev == "VS" and tokens[i - 1] == "-":
                        trybook = self.match_book(token)
                        if trybook is not None:
                            book = trybook
                            for k in book.keys():
                                cref[k] = book[k]
                            cref.bk = book.name
                            LOG.debug("--> book = %r" % book.name)
                            prev = "BOOK"
                        elif following == ".":
                            # the token is a ch
                            cref.ch = self.get_ch(crng, token)
                            LOG.debug("--> ch = %r" % cref.ch)
                            prev = "CH"
                        else:
                            # the token is a vs
                            cref.vs = self.get_vs(crng, token)
                            LOG.debug("--> vs = %r" % cref.vs)
                            prev = "VS"
                    # prev one ch book
                    elif prev == "BOOK":
                        if self.chapters_in(cref.bk) == 1:
                            LOG.debug("one-chapter book= %r" % cref.bk)
                            # it's a one-chapter book
                            if token != "1":
                                cref.vs = self.get_vs(crng, token)
                                LOG.debug("--> vs = %r" % token)
                                prev = "VS"
                            elif following == ".":
                                cref.ch = self.get_ch(crng, token)
                                LOG.debug("--> ch = %r" % token)
                                prev = "CH"
                            elif following in ["-", ","]:
                                cref.vs = self.get_vs(crng, token)
                                LOG.debug("--> vs = %r" % token)
                                prev = "VS"
                            else:
                                cref.ch = self.get_ch(crng, token)
                                LOG.debug("--> ch = %r" % token)
                                prev = "CH"
                        else:
                            # multi-chapter book, so this is a ch
                            cref.ch = self.get_ch(crng, token)
                            LOG.debug("--> ch = %r" % token)
                            prev = "CH"
                elif expect == "CH":
                    # the token is a ch
                    cref.ch = self.get_ch(crng, token)
                    LOG.debug("--> ch = %r" % token)
                    prev = "CH"
                elif expect == "VS":
                    trybook = self.match_book(token)
                    if trybook is not None:
                        # the token is a book! yes, it can happen
                        trybook = self.match_book(token)
                        if trybook is not None:
                            book = trybook
                            for k in book.keys():
                                cref[k] = book[k]
                            cref.bk = book.name
                        cref.vs = cref.ch = None  # no ch assignment yet
                        LOG.debug("--> bk = %r" % token)
                        prev = "BOOK"
                    else:
                        cref.vs = self.get_vs(crng, token)
                        LOG.debug("--> vs = %r" % token)
                        prev = "VS"
                # expect 'SEP' after a content token
                expect = "SEP"

        # close out last range
        self.append_range(crng, reflist)

        return reflist

    def get_ch(self, crng, token):
        if token == "F":
            r = self.parse("%s %s" % (crng[0].bk, str(int(crng[0].ch) + 1)))
            LOG.debug("get_ch, F: r = %r" % r)
            return r[0][0].ch
        elif token == "FF":
            r = self.parse("%(bk)s" % crng[0])
            LOG.debug("get_ch, FF: r = %r" % r)
            return r[0][1].ch
        else:
            return token

    def get_vs(self, crng, token):
        if token == "F":
            r = self.parse(
                "%s %s:%s" % (crng[0].bk, crng[0].ch, str(int(crng[0].vs) + 1))
            )
            LOG.debug("get_vs, F: r = %r" % r)
            return r[0][0].vs
        elif token == "FF":
            r = self.parse("%(bk)s %(ch)s" % crng[0])
            LOG.debug("get_vs, FF: r = %r" % r)
            return r[0][1].vs
        else:
            return token

    def append_range(self, rng, liste):
        rng = self.clean_up_range(rng)
        LOG.debug("--> append range = %r" % rng)
        liste.append(rng)

    def create_range(self):
        rng = RefRange((Ref(), Ref()))
        return rng

    def refstring(self, ref):
        return self.clean_refstring(self.format(ref))

    def clean_refstring(self, refstr=""):
        """cleanup refstr:
            ',' = ref separator, hint to verse
            ';' = ref separator, hint to chapter
            '.' = bk/ch/vs separator
            '-' = range separator
        Usage:
        >>> import bibleweb; db=bibleweb.db(); refparser=RefParser(db)
        >>> refparser.clean_refstring("Gen 3:5-4:7; 5:8-10; Exod 3:2-Lev 4:5")
        'Gen.3.5-4.7;5.8-10;Exod.3.2-Lev.4.5'
        >>> refparser.clean_refstring("Song of Songs 4 8 -- 5_3")
        'SongofSongs.4.8-5.3'
        """
        if refstr is None:
            return None
        refstr = re.sub(r"(^\W+|\W+$)", "", refstr)
        refstr = re.sub(r"[\(\)\[\]\{\}\<\>]", "", refstr)  # remove brackets and parens
        refstr = refstr.strip()  # Remove leading and trailing whitespace
        refstr = refstr.strip("-,;.")  # leading and trailing separators
        refstr = refstr.replace("and", ",")
        refstr = refstr.replace("; ", ";")
        refstr = refstr.replace(":", ".")
        refstr = refstr.replace("_", " ")
        refstr = refstr.replace("\\", "")
        refstr = refstr.replace("&#160;", " ")
        refstr = refstr.replace("\u00a0", " ")
        refstr = refstr.replace("\t", " ")
        refstr = refstr.replace("&#150;", "-")
        refstr = refstr.replace("&#151;", "-")
        refstr = refstr.replace("&#8211;", "-")
        refstr = refstr.replace("&#8212;", "-")
        refstr = refstr.replace("&#x2010;", "-")
        refstr = refstr.replace("&#x2011;", "-")
        refstr = refstr.replace("&#x2012;", "-")
        refstr = refstr.replace("&#x2013;", "-")
        refstr = refstr.replace("&#x2014;", "-")
        refstr = refstr.replace("\u2010", "-")
        refstr = refstr.replace("\u2011", "-")
        refstr = refstr.replace("\u2011", "-")
        refstr = refstr.replace("\u2013", "-")
        refstr = refstr.replace("\u2014", "-")
        refstr = refstr.replace("\x96", "-")
        refstr = refstr.replace("\x97", "-")
        refstr = refstr.replace("\r", ";")
        refstr = refstr.replace("\n", ";")
        refstr = refstr.replace(" -", "-")
        refstr = refstr.replace("- ", "-")
        while ";;" in refstr:
            refstr = refstr.replace(";;", ";")
        while "--" in refstr:
            refstr = refstr.replace("--", "-")
        while "  " in refstr:
            refstr = refstr.replace("  ", " ")
        while ".." in refstr:
            refstr = refstr.replace("..", ".")
        while ",," in refstr:
            refstr = refstr.replace(",,", ",")
        refstr = refstr.replace(" ,", ",")
        refstr = refstr.replace(", ", ",")
        refstr = refstr.replace(" ;", ";")
        refstr = refstr.replace("; ", ";")
        refstr = re.sub(r"([123])\s+([A-Za-z])", r"\1\2", refstr)
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
        refstr = re.sub(r"(?i)first\s*", "1", refstr)
        refstr = re.sub(r"(?i)second\s*", "2", refstr)
        refstr = re.sub(r"(?i)third\s*", "3", refstr)
        refstr = refstr.replace(" ", ".")
        refstr = re.sub(r"Song\.[^0-9]*", "Song.", refstr)
        refstr = re.sub(r"\.title", ".0", refstr, flags=re.I)
        refstr = re.sub(r",\s*(heading|title)", "", refstr, flags=re.I)
        refstr = re.sub(r"^The\W+", "", refstr)
        refstr = refstr.replace(".v.", ".1.")

        # Pattern like 1,2Sam should become 1Sam–2Sam
        refstr = re.sub(r"^(\d+),(\d+)(\w+)", r"\1\3-\2\3", refstr)

        # Pattern like 1-2Sam should become 1Sam-2Sam
        refstr = re.sub(r"^(\d+)-(\d+)(\D+)", r"\1\3-\2\3", refstr)

        return refstr

    def clean_up_range(self, rng):
        """fill the range and make sure ch and vs are ints, with any vs sub modifiers in sub"""
        rng = self.fill_range(rng)
        if rng[0].bk is not None and rng[0].id is None:
            rng[0].id = self.match_book(rng[0].bk).id
        rng[0].ch = int(self.clean_intstr(rng[0].ch) or 1)  # rng[0].ch
        rng[1].ch = int(
            self.clean_intstr(rng[1].ch) or self.chapters_in(rng[0].bk)
        )  # rng[1].ch
        if type(rng[0].vs) == str:
            sub = re.search(r"[^0-9\W]+$", rng[0].vs)  # rng[0].vs
            intstr = self.clean_intstr(rng[0].vs)
            if sub is not None and type(intstr) == str and intstr in rng[0].vs:
                LOG.debug("rng[0].vsub = %r" % sub.group(0))
                rng[0].vsub = sub.group(0)
            rng[0].vs = int(self.clean_intstr(rng[0].vs) or 1)
        if type(rng[1].vs) == str:
            sub = re.search(r"[^0-9\W]+$", rng[1].vs)  # rng[1].vs
            intstr = self.clean_intstr(rng[1].vs)
            if sub is not None and type(intstr) == str and intstr in rng[1].vs:
                LOG.debug("rng[1].vsub = %r" % sub.group(0))
                rng[1].vsub = sub.group(0)
            rng[1].vs = int(
                self.clean_intstr(rng[1].vs) or self.verses_in(rng[1].bk, rng[1].ch)
            )
        if rng[0].id is not None and rng[1].id is None:
            rng[1].id = rng[0].id
        return rng

    def fill_range(self, rng):
        """fill a range that does not have all the verses defined.
        Spec:
        >>> import bibleweb
        >>> from bibleweb.models import bible_ref
        >>> db=bibleweb.db()
        >>> rp=RefParser(db)
        >>> rp.fill_range(
        ...     bible_ref.RefRange(
        ...         (bible_ref.Ref(db), bible_ref.Ref(db)))).display()
        ('', '')
        >>> rp.fill_range(
        ...     bible_ref.RefRange(
        ...         (bible_ref.Ref(db, bk='Gen'), bible_ref.Ref(db)))).display()
        ('Gen 1:1', 'Gen 50:26')
        >>> rp.fill_range(
        ...     bible_ref.RefRange(
        ...         (bible_ref.Ref(db, bk='Gen', ch=3), bible_ref.Ref(db)))).display()
        ('Gen 3:1', 'Gen 3:24')
        >>> rp.fill_range(
        ...     bible_ref.RefRange(
        ...         (bible_ref.Ref(db, bk='Gen', ch=3, vs=15), bible_ref.Ref(db)))).display()
        ('Gen 3:15', 'Gen 3:15')
        >>> rp.fill_range(
        ...     bible_ref.RefRange(
        ...         (bible_ref.Ref(db, bk='Gen', ch=3, vs=15), bible_ref.Ref(db, vs=17)))).display()
        ('Gen 3:15', 'Gen 3:17')
        >>> rp.fill_range(
        ...     bible_ref.RefRange(
        ...         (bible_ref.Ref(db, bk='Gen', ch=3), bible_ref.Ref(db, ch=4)))).display()
        ('Gen 3:1', 'Gen 4:26')
        >>> rp.fill_range(
        ...     bible_ref.RefRange(
        ...         (bible_ref.Ref(db, bk='Gen', ch=3, vs=15),
        ...         bible_ref.Ref(db, ch=4, vs=17)))).display()
        ('Gen 3:15', 'Gen 4:17')
        """
        LOG.debug(
            "fill range: %r"
            % ([(rng[0].bk, rng[0].ch, rng[0].vs), (rng[1].bk, rng[1].ch, rng[1].vs)],)
        )
        status = None
        if rng[0].bk is not None:
            for book in self.canon.books:
                if book.name == rng[0].bk:
                    for key in [
                        key
                        for key in book.keys()
                        if key not in ["chapters", "pattern", "rexp"]
                    ]:
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
                                        for key in [
                                            key
                                            for key in book.keys()
                                            if key
                                            not in ["chapters", "pattern", "rexp"]
                                        ]:
                                            rng[0][key] = book[key]
                                        break
                                rng[1].ch = rng[0].ch
                                rng[1].vs = rng[0].vs
                            else:
                                # rng[0] is full, rng[1].bk is not None, the range is to
                                # the end of the second bk
                                status = "the range is to the end of the second bk"
                                rng[1].ch = self.chapters_in(rng[1].bk)
                                rng[1].vs = self.verses_in(rng[1].bk, rng[1].ch)
                        else:
                            # rng[0] is full, rng[1].ch is not None, so the range is in
                            # the same book, to the end of the second ch.
                            status = "the range is in the same book, to the end of the second ch."
                            rng[1].bk = rng[0].bk
                            rng[1].ch = self.chapters_in(rng[1].bk)
                            rng[1].vs = self.verses_in(rng[1].bk, rng[1].ch)
                    else:
                        # rng[0] is full, rng[1].vs is not None, so the range is verses
                        status = "the range is verses either within or between chs"
                        if rng[1].ch is None:
                            rng[1].ch = rng[0].ch
                        if rng[1].bk is None:
                            rng[1].bk = rng[0].bk
                else:
                    # rng[0].vs is None, but rng[0].ch and .bk are defined, so it's
                    # either a whole chapter or a range of chapters
                    status = "it's either a whole chapter or a range of chapters"
                    rng[0].wholech = True
                    rng[0].vs = 1
                    if rng[1].bk is None:  # same book
                        rng[1].bk = rng[0].bk
                        if rng[1].ch is None:
                            rng[1].ch = rng[0].ch
                    else:
                        rng[1].ch = rng[1].ch or self.chapters_in(rng[1].bk)
                        status += ", rng[1].ch=%s" % (str(rng[1].ch))
                    if rng[1].vs is None:
                        rng[1].vs = self.verses_in(rng[1].bk, rng[1].ch) or 0
                        status += ", rng[1].vs=%s" % (str(rng[1].vs))
            else:
                # rng[0].ch is None, but rng[0].bk is defined, so it's either a verse or
                # range in a one ch book, or a range of books
                if rng[0].vs is not None:  # vs or rng in one-chapter book
                    status = "it's a vs or rng in a one-chapter book."
                    rng[0].ch = 1
                    if rng[1].bk is None:
                        rng[1].bk = rng[0].bk
                    if rng[1].ch is None:
                        rng[1].ch = rng[0].ch
                    if rng[1].vs is None:
                        rng[1].vs = rng[0].vs
                else:  # whole book or range of books
                    status = "it's a whole book or range of books."
                    rng[0].ch = 1
                    rng[0].vs = 1
                    if rng[1].bk is None:
                        rng[1].bk = rng[0].bk
                    if rng[1].ch is None:
                        rng[1].ch = self.chapters_in(rng[1].bk)
                        status += ", rng[1].ch=%s is last ch in book" % str(rng[1].ch)
                    if rng[1].vs is None:
                        rng[1].vs = self.verses_in(rng[1].bk, rng[1].ch)
                        status += ", rng[1].vs=%s is last vs in rng[1].ch" % str(
                            rng[1].vs
                        )
        LOG.debug("=> %s" % status)
        LOG.debug(
            "filled range: %r"
            % ([(rng[0].bk, rng[0].ch, rng[0].vs), (rng[1].bk, rng[1].ch, rng[1].vs)],)
        )
        rng[0].name = rng[0].bk
        rng[1].name = rng[1].bk
        return rng

    def item_name(self, inrefs):
        return (
            self.format(
                inrefs,
                cvsep=".",
                bksep=".",
                bkarg="romname",
                vsrsep="-",
                chrsep="-",
                bkrsep="-",
                comma=".",
                semicolon=".",
            )
            .replace(";", ".")
            .replace(" ", "")
        )

    def format(
        self,
        inrefs,
        currbk=0,
        minimize=False,
        with_bk=True,
        html=False,
        uri="",
        qarg="?bref=",
        bkarg="name",
        cvsep=":",
        bksep=" ",
        vsrsep="-",
        chrsep="\u2013",
        bkrsep="\u2014",
        comma=", ",
        semicolon="; ",
    ):
        """Format the output of RefParser.parse(), which is a list of Ref tuples.
        Usage:
        >>> import bibleweb; db=bibleweb.db(); refparser=BibleRefParser(db)
        >>> p = refparser.parse("Exod 3:2-Lev 4:5")
        >>> p.format()
        'Exod 3:2---Lev 4:5'
        >>> p.format(cvsep='.', bkarg='title_es')
        '\\xc9xodo 3.2---L\\xe9vitico 4.5'
        >>> p.format(html=True, bkarg='title')
        u"<a href='?bref=Exod.3.2---Lev.4.5'>Exodus 3:2---Leviticus 4:5</a>"
        >>> p.format(html=True, bkarg='title_es')
        u"<a href='?bref=Exod.3.2---Lev.4.5'>\\xc9xodo 3:2---L\\xe9vitico 4:5</a>"
        """
        # ## ** NOTE REGARDING THE minimize PARAMETER **
        # I would like to include a test for whether the formatted output includes verse
        # numbers when we have the whole chapter, but that requires significant
        # refactoring and retesting of the code. So for now, unless we can find another
        # way to test for chapter length, we have to be content showing the entire
        # reference in detail.

        # normalize inrefs
        # if type(inrefs) in [str, int]:
        #     inrefs = self.parse(inrefs)
        # elif type(inrefs)==Ref:
        #     inrefs = RefList([RefRange((inrefs, Ref()))])
        # elif type(inrefs)==RefRange:
        #     inrefs = RefList([inrefs])

        # KLUDGE: fix Psalm vs Psalms
        for ref in inrefs:
            if (
                ref[0].title == "Psalms"
                and ref[0].bk == ref[1].bk
                and ref[0].ch == ref[1].ch
            ):
                ref[0].title = ref[1].title = "Psalm"

        currch = 0
        currvs = 0
        out = ""
        for startref, endref in inrefs:
            if startref is None or startref == {}:
                continue
            if startref is not None and startref.vsub is not None:
                startref.vsub = startref.vsub.strip("_")  # vsub shd be a letter only.
            if endref is not None and endref.vsub is not None:
                endref.vsub = endref.vsub.strip("_")
            if currbk == startref.bk or with_bk is False:
                if currch == startref.ch:
                    startrefstr = "%s%s%s" % (comma, startref.vs, startref.vsub or "")
                else:
                    if out != "":
                        out += "; "
                    startrefstr = "%s%s%s%s" % (
                        startref.ch,
                        cvsep,
                        startref.vs,
                        startref.vsub or "",
                    )
            else:
                if out != "":
                    out += semicolon
                startrefstr = "%s%s%s%s%s%s" % (
                    startref[bkarg],
                    bksep,
                    startref.ch,
                    cvsep,
                    startref.vs,
                    startref.vsub or "",
                )

            currbk, currch, currvs = startref.bk, startref.ch, startref.vs

            if endref is None or endref == {}:
                endrefstr = ""
            elif currbk == endref.bk or with_bk is False:
                if currch == endref.ch:
                    if currvs == endref.vs:
                        endrefstr = ""
                    else:  # one hyphen to separate a vs
                        endrefstr = "%s%s%s" % (vsrsep, endref.vs, endref.vsub or "")
                else:  # default -- to cvsep. ch:vs
                    endrefstr = "%s%s%s%s%s" % (
                        chrsep,
                        endref.ch,
                        cvsep,
                        endref.vs,
                        endref.vsub or "",
                    )
            else:  # default --- to cvsep. bk ch:vs
                if bkarg not in endref and bkarg in startref:
                    endref[bkarg] = startref[bkarg]
                endrefstr = "%s%s%s%s%s%s%s" % (
                    bkrsep,
                    endref[bkarg],
                    bksep,
                    endref.ch,
                    cvsep,
                    endref.vs,
                    endref.vsub or "",
                )

            if html is True:
                # format the output to be a list of html links to the given href
                if uri is None:
                    uri = ""
                if qarg is None:
                    qarg = ""
                term = self.clean_refstring(
                    ("%(bk)s.%(ch)s.%(vs)s" % startref) + endrefstr
                )
                out += "<a href='%s'>%s</a>" % (
                    uri + qarg + term,
                    startrefstr + endrefstr,
                )
            else:
                out += startrefstr + endrefstr

        return out

    def refstr_from_ids(self, ids):
        """given a ref id or ids, return a reference string.
        The ids string is one or more refids, separated by hyphens (ranges) and commas (instances)
        """
        range_ids = [id.strip() for id in ids.split(",") if id.strip() != ""]
        range_refstrs = []
        for range_id in range_ids:
            range_refstrs.append(
                "-".join(
                    [
                        self.refstr_from_id(rid.strip())
                        for rid in range_id.split("-")
                        if rid.strip() != ""
                    ]
                )
            )
        refstr = self.refstring(self.parse(";".join(range_refstrs)))
        return refstr

    def refstr_from_id(self, id):
        """given a ref id in the canon, return a reference string."""
        idstr = re.sub(r"(^[^\d]+|[^\d]+$)", "", id).replace("000000", "")
        idstr = re.sub(r"000$", "", idstr)
        idstr = re.sub(r"000$", "", idstr)
        if len(idstr) < 4:  # book
            key = idstr.zfill(3) + "001001"
            ref0 = Ref.from_key(key, self.canon)
            return f"{ref0.name}"
        elif len(idstr) < 7:  # ch
            key = idstr.zfill(6) + "001"
            ref0 = Ref.from_key(key, self.canon)
            return f"{ref0.name}.{ref0.ch}"
        else:  # vs
            key = idstr.zfill(9)
            ref0 = Ref.from_key(key, self.canon)
            return f"{ref0.name}.{ref0.ch}.{ref0.vs}"


def test_parse():
    """
    >>> import bibleweb; db=bibleweb.db(); rp=RefParser(db)
    # comma to separate whole chapters
    >>> rp.parse('Ps 24, 26; 28:8-10').display()
    [('Ps 24:1', 'Ps 24:10'), ('Ps 26:1', 'Ps 26:12'), ('Ps 28:8', 'Ps 28:10')]
    >>> rp.parse('Song of Songs 7.1 - 8.5').display()
    [('Song 7:1', 'Song 8:5')]
    >>> rp.parse('Gen, Exod').display()
    [('Gen 1:1', 'Gen 50:26'), ('Exod 1:1', 'Exod 40:38')]
    >>> rp.parse('1Kgs 21-2Kgs 22').display()
    [('1Kgs 21:1', '2Kgs 22:20')]
    >>> rp.parse('Gen, Exod 1').display()
    [('Gen 1:1', 'Gen 50:26'), ('Exod 1:1', 'Exod 1:22')]
    >>> rp.parse('Gen - Exod 1').display()
    [('Gen 1:1', 'Exod 1:22')]
    >>> rp.parse('Gen 1, 2').display()
    [('Gen 1:1', 'Gen 1:31'), ('Gen 2:1', 'Gen 2:25')]
    >>> rp.parse('Gen 1 - 2').display()
    [('Gen 1:1', 'Gen 2:25')]
    >>> rp.parse('Gen 1:1 - 2').display()
    [('Gen 1:1', 'Gen 1:2')]
    >>> rp.parse('Gen 1:1 - 2:5').display()
    [('Gen 1:1', 'Gen 2:5')]
    >>> rp.parse('Gen 1 - 2:5').display()
    [('Gen 1:1', 'Gen 2:5')]
    >>> rp.parse('Gen 1 - 2:5, 7, 9-10').display()
    [('Gen 1:1', 'Gen 2:5'), ('Gen 2:7', 'Gen 2:7'), ('Gen 2:9', 'Gen 2:10')]
    >>> rp.parse('Gen - Rev').display()
    [('Gen 1:1', 'Rev 22:21')]
    >>> rp.parse('Obad 1-2').display()
    [('Obad 1:1', 'Obad 1:2')]
    >>> rp.parse('3Jn 1:1-4').display()
    [('3Jn 1:1', '3Jn 1:4')]
    >>> rp.parse('3Jn 1').display()
    [('3Jn 1:1', '3Jn 1:15')]
    >>> rp.parse('3Jn').display()
    [('3Jn 1:1', '3Jn 1:15')]
    >>> rp.parse('Gen 34:8').display()
    [('Gen 34:8', 'Gen 34:8')]
    >>> rp.parse('Gen 34:8-Deut').display()
    [('Gen 34:8', 'Deut 34:12')]
    >>> rp.parse('Gen 34:8, Deut').display()
    [('Gen 34:8', 'Gen 34:8'), ('Deut 1:1', 'Deut 34:12')]
    >>> rp.parse('Gen 34:8; Deut').display()
    [('Gen 34:8', 'Gen 34:8'), ('Deut 1:1', 'Deut 34:12')]
    >>> rp.parse('Obad 1,3').display()
    [('Obad 1:1', 'Obad 1:1'), ('Obad 1:3', 'Obad 1:3')]
    >>> rp.parse('Gen 1,3').display()
    [('Gen 1:1', 'Gen 1:31'), ('Gen 3:1', 'Gen 3:24')]
    >>> rp.parse('Gen 1:1,3').display()
    [('Gen 1:1', 'Gen 1:1'), ('Gen 1:3', 'Gen 1:3')]
    >>> rp.parse('Gen 1:1;3').display()
    [('Gen 1:1', 'Gen 1:1'), ('Gen 3:1', 'Gen 3:24')]
    # this is a pretty tough edge case - what does the user intend?
    >>> rp.parse('Obad 1;3').display()
    [('Obad 1:1', 'Obad 1:21'), ('Obad 1:3', 'Obad 1:3')]
    # another corner case that I just solved
    >>> rp.parse('Obad 1-3; 1Jn 5').display()
    [('Obad 1:1', 'Obad 1:3'), ('1Jn 5:1', '1Jn 5:21')]
    # it looks like a reference, but it's not
    >>> rp.parse('Something 1:5')
    []
    # chapter range across books should work fine.
    >>> rp.parse('Gen 50 - Exod 1').display()
    [('Gen 50:1', 'Exod 1:22')]
    # it should handle refs correctly.
    >>> rp.parse('2Jn.001.001 - Jude.001.025').display()
    [('2Jn 1:1', 'Jude 1:25')]
    """


if __name__ == "__main__":
    import doctest

    doctest.testmod()
