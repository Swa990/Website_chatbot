"""Turn markdown tables into one self-contained line per row.

'| Fee | Amount |' + '| Annual | 100 |'  ->  '- Fee: Annual; Amount: 100'
Why: chunking can cut a long table in the middle; with one line per row, every
chunk still says which column each value belongs to.
"""
import re

_SEP_CELL = re.compile(r":?-{3,}:?")


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _convert(block: list[str]) -> list[str]:
    rows = [_cells(l) for l in block]
    rows = [r for r in rows if not all(_SEP_CELL.fullmatch(c) or c == "" for c in r)]
    if not rows:
        return []
    header, body = rows[0], rows[1:]
    if not body:
        return ["- " + "; ".join(c for c in header if c)]
    out = []
    for r in body:
        if len(r) > len(header):  # a row wider than the header: keep the overflow
            header = header + [""] * (len(r) - len(header))
        pairs = [f"{h}: {v}" if h else v for h, v in zip(header, r) if v]
        if pairs:
            out.append("- " + "; ".join(pairs))
    return out


def tables_to_records(md: str) -> str:
    out, block = [], []
    for line in md.splitlines():
        if line.lstrip().startswith("|"):
            block.append(line)
            continue
        if block:
            out += _convert(block)
            block = []
        out.append(line)
    if block:
        out += _convert(block)
    return "\n".join(out)
