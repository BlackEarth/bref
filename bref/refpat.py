DEBUG = False

import re, os, sys

def book_pattern(canon):
    return r"(?:(?:" + r"|".join([bk.pattern for bk in canon.books]) + r")\.?)"

def book_replacer(canon, attr, flags=re.I):
    """create a function that can be used in re.sub() to replace a found book name with the given book attribute"""
    def br(md):
        text = md.group(0)
        for book in canon.books:
            if re.match(book.pattern, text, flags=flags) is not None:
                return book[attr]
    return br

def make_patterns(canon):
    # == Build the regexps for finding references in text ==
    patterns = []
    repeating = []  # list of indexes of patterns that should be repeated until the result is the same as the input

    # building blocks
    bkpat = book_pattern(canon)
    fullbkpat = r"\\b(?:" \
                + r"|".join([bk.title % bk for bk in canon.books]) \
                + r")\\b"
    chpat = r"(?:[1-9][0-9]*[a-f]{0,2}\\b)"
    vspat = r"(?:[\.:]?[1-9][0-9]*[a-f]{0,2}\\b)"
    sepat = r"\\s*(?:[,\-\u2013\u2014]?)+\\s*"
    sepatand = r"\\s*(?:[,\-\u2013\u2014]?(?: and)?)+\\s*"

    # == patterns == 

    # * full pattern
    patterns += [r"(?<!>)(" + bkpat + r"\\s*" + chpat + vspat + r"?(" + sepat + bkpat + r"?\\s*" + chpat + vspat + r"?)*" \
                + r"|" + chpat + vspat + r"(?:" + sepat + chpat + vspat + r"?)*)(?!</a>)"]

    # * "chapters" + chapter nums
    patterns += [r"\\b([Cc]hapters?\\s*" + chpat + r"(?:" + sepat + chpat + r")*)"]
    patterns += [r"\\b([Cc]haps?\\.?\\s*" + chpat + r"(?:" + sepat + chpat + r")*)"]
    patterns += [r"\\b([Cc]hs?\\.?\\s*" + chpat + r"(?:" + sepat + chpat + r")*)"]

    # * chapters without book names, after link and semi-colon
    patterns += [r"(?<=</a>; )(" + chpat + r"(?:" + sepat + chpat + r")?)"]
    repeating += [patterns.index(patterns[-1])]

    # * chapter number alone, followed by semi-colon and another bref
    patterns += [r"(" + chpat + r""")(?=;\\s*<a href="\?bref=)"""]
    repeating += [patterns.index(patterns[-1])]

    # compile all the patterns
    regexs = [re.compile(pat, re.U) for pat in patterns]

    return {'patterns': patterns, 'repeating': repeating, 'regexs': regexs}

def tag_refs_in_text(text, patterns, refparser=None):
    def repl_bref(md):
        txt = md.group(1)
        if refparser is not None:
            refstr = refparser.refstring(refparser.parse(txt))
            tagged = r"""<ref name="%s">%s</ref>""" % (refstr, txt)
        else:
            tagged = r"""<ref>%s</ref>""" % (txt,)
        return tagged
    # get the first item ref to provide a book as context
    for regex in patterns['regexs']:
        if patterns['regexs'].index(regex) in patterns['repeating']:
            t = re.sub(regex, repl_bref, text)
            while t != text:
                text = t
                t = re.sub(regex, repl_bref, text)
        else:
            text = re.sub(regex, repl_bref, text)
    return text

def tag_refs_in_xml(x, patterns, xpath=None, namespaces=None):
    if xpath is None:
        elements = x.xpath(x.root, "//*")
    else:
        elements = x.xpath(x.root, xpath, namespaces=namespaces)
    for element in elements:
        if element.text is not None and element.get('href') is None:
            element.text = tag_refs_in_text(element.text, patterns)
        if element.tail is not None:
            element.tail = tag_refs_in_text(element.tail, patterns)
    t = x.tostring().replace("&lt;ref&gt;", "<ref>").replace("&lt;/ref&gt;", "</ref>")
    x.root = x.fromstring(t)
    return x


