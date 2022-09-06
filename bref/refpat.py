DEBUG = False

import os
import re
import sys


def book_pattern(canon):
    return "(?:(?:" + "|".join([bk.pattern for bk in canon.books]) + ")\\.?)"


def book_replacer(canon, attr, flags=re.I):
    """create a function that can be used in re.sub() to replace a found book name with the given book attribute"""

    def br(md):
        text = md.group(0)
        for book in canon.books:
            if re.match(book.pattern_strict, text, flags=flags) is not None:
                return book[attr]

    return br


def full_books_pattern(canon):
    return "\\b(?:" + "|".join([bk.title % bk for bk in canon.books]) + ")\\b"


def make_patterns(canon):
    # == Build the regexps for finding references in text ==
    patterns = []
    repeating = (
        []
    )  # list of indexes of patterns that should be repeated until the result is the same as the input

    # building blocks
    bkpat = book_pattern(canon)
    fullbkpat = full_books_pattern(canon)
    chpat = "(?:[1-9][0-9]*[a-f]{0,2}\\b)"
    vspat = "(?:[\\.:]?[1-9][0-9]*[a-f]{0,2}\\b)"
    sepat = "\\s*(?:[,\\-\u2013\u2014]?)+\\s*"
    sepatand = "\\s*(?:[,\\-\u2013\u2014]?(?: and)?)+\\s*"

    # == patterns ==

    # * full pattern
    patterns += [
        "(?<!>)("
        + bkpat
        + "\\s*"
        + chpat
        + vspat
        + "?("
        + sepat
        + bkpat
        + "?\\s*"
        + chpat
        + vspat
        + "?)*"
        + "|"
        + chpat
        + vspat
        + "(?:"
        + sepat
        + chpat
        + vspat
        + "?)*)(?!</ref>)"
    ]

    # * "chapters" + chapter nums
    patterns += ["\\b([Cc]hapters?\\s*" + chpat + "(?:" + sepat + chpat + ")*)"]
    patterns += ["\\b([Cc]haps?\\.?\\s*" + chpat + "(?:" + sepat + chpat + ")*)"]
    patterns += ["\\b([Cc]hs?\\.?\\s*" + chpat + "(?:" + sepat + chpat + ")*)"]
    # patterns += ["\\b([Cc]apítulos?\\s*" + chpat + "(?:" + sepat + chpat + ")*)"]

    # * chapters without book names, after link and semi-colon
    patterns += ["(?<=</ref>; )(" + chpat + "(?:" + sepat + chpat + ")?)"]
    repeating += [patterns.index(patterns[-1])]

    # * chapter number alone, followed by semi-colon and another ref
    patterns += ["(" + chpat + """)(?=;\\s*<ref name=")"""]
    repeating += [patterns.index(patterns[-1])]

    # compile all the patterns
    regexs = [re.compile(pat) for pat in patterns]

    return {"patterns": patterns, "repeating": repeating, "regexs": regexs}


def tag_refs_in_text(text, patterns, refparser=None, bk=None):
    def repl_bref(md):
        txt = md.group(1)
        if refparser is not None:
            try:
                refstr = refparser.refstring(refparser.parse(txt, bk=bk))
            except Exception as exc:
                print("RefParser.parse ERROR:", txt, " -- ", str(exc))
                return txt
            tagged = """<ref name="%s">%s</ref>""" % (refstr, txt)
        else:
            tagged = """<ref>%s</ref>""" % (txt,)
        return tagged

    # get the first item ref to provide a book as context
    for regex in patterns["regexs"]:
        if patterns["regexs"].index(regex) in patterns["repeating"]:
            t = re.sub(regex, repl_bref, text)
            while t != text:
                text = t
                t = re.sub(regex, repl_bref, text)
        else:
            text = re.sub(regex, repl_bref, text)

    return text


def tag_refs_in_xml(x, patterns, xpath=None, namespaces=None, refparser=None, bk=None):
    if xpath is None:
        elements = x.xpath(x.root, "//*")
    else:
        elements = x.xpath(x.root, xpath, namespaces=namespaces)
    for element in elements:
        if element.text is not None and element.get("href") is None:
            element.text = tag_refs_in_text(
                element.text, patterns, refparser=refparser, bk=bk
            )
        if element.tail is not None:
            element.tail = tag_refs_in_text(
                element.tail, patterns, refparser=refparser, bk=bk
            )
    t = re.sub("&lt;(ref[^&>]+)&gt;", r"<\1>", x.tostring()).replace(
        "&lt;/ref&gt;", "</ref>"
    )
    try:
        x.root = x.fromstring(t)
    except:
        print(t)
        raise

    return x
