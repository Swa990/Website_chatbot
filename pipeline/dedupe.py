# """Remove site-wide boilerplate (mega-menus, footers) that survived cleaning.

# Idea: a link-only line (menu item) that appears on many pages is navigation,
# not content. Headings, table rows and normal sentences are never touched.
# """
# import re
# from collections import Counter

# LINK_LINE = re.compile(r"^\s*(?:[*\-+]\s+)?\[[^\]]*\]\([^)]*\)\s*$")


# def find_boilerplate(pages_md: list[str], min_share: float = 0.3, min_pages: int = 4) -> set[str]:
#     n = len(pages_md)
#     if n < 10:  # too few pages to judge
#         return set()
#     counts = Counter()
#     for md in pages_md:
#         counts.update({l.strip() for l in md.splitlines() if LINK_LINE.match(l)})
#     limit = max(min_pages, min_share * n)
#     return {line for line, c in counts.items() if c >= limit}


# def strip_boilerplate(md: str, boiler: set[str]) -> str:
#     kept = [l for l in md.splitlines() if l.strip() not in boiler]
#     return "\n".join(kept).strip()


"""Remove text that repeats on most pages (mega-menu, footer, running PDF headers).

A line is 'repeated' if it appears on >= min_share of the documents. Headings and
table rows are never removed. Links are compared by their text only, because menu
links can point to the current page (different URL on each page).
"""
import re
from collections import Counter

_LINK_URL = re.compile(r"\]\([^)]*\)")


def line_key(line: str) -> str:
    return re.sub(r"\s+", " ", _LINK_URL.sub("]", line.strip()))


def _candidate(line: str) -> bool:
    s = line.strip()
    return bool(s) and not s.startswith("#") and not s.startswith("|")


def find_repeated(docs: list[str], min_share: float = 0.5, min_docs: int = 10) -> set[str]:
    n = len(docs)
    if n < min_docs:  # too few documents to tell navigation from content
        return set()
    counts = Counter()
    for md in docs:
        counts.update({line_key(l) for l in md.splitlines() if _candidate(l)})
    return {k for k, c in counts.items() if c >= min_share * n}


def strip_repeated(md: str, repeated: set[str]) -> str:
    kept = [l for l in md.splitlines() if not (_candidate(l) and line_key(l) in repeated)]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()