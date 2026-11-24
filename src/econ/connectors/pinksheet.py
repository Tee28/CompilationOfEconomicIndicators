"""World Bank Pink Sheet monthly prices (gold, crude). Discovers the xlsx link from the commodity-markets page.
xlsx is read with the stdlib (zipfile + xml): no openpyxl dependency."""
from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
import zipfile
from urllib.parse import urljoin

import pandas as pd

from ..common import EconError, utcnow
from .base import Budget, get_text

PAGE_URL = "https://www.worldbank.org/en/research/commodity-markets"
LINK_RE = re.compile(r'href="([^"]*CMO-Historical-Data-Monthly\.xlsx[^"]*)"', re.I)
# series code -> accepted header texts in the sheet (lowercase)
HEADERS = {"GOLD": {"gold"}, "CRUDE_PETRO": {"crude_petro", "crude oil, average", "crude oil average"}}
_M = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_NS = {"m": _M}
_MONTH = re.compile(r"^(\d{4})M(\d{2})$")


def find_link(html: str, base: str = PAGE_URL) -> str:
    m = LINK_RE.search(html or "")
    if not m:
        raise EconError("pinksheet: monthly xlsx link not found on page (layout changed?)")
    return urljoin(base, m.group(1).replace("&amp;", "&"))


def _col(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_sheet_rows(xlsx: bytes, sheet_hint: str = "Monthly Prices") -> list[list]:
    z = zipfile.ZipFile(io.BytesIO(xlsx))
    sst = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", _NS):
            sst.append("".join(t.text or "" for t in si.iter(f"{{{_M}}}t")))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    rid = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    target = None
    for s in wb.find("m:sheets", _NS):
        if sheet_hint.lower() in s.get("name", "").lower():
            target = rels[s.get(rid)]
    if target is None:
        raise EconError(f"pinksheet: sheet '{sheet_hint}' not found")
    path = target.lstrip("/") if target.startswith("/") else "xl/" + target
    rows = []
    for r in ET.fromstring(z.read(path)).iter(f"{{{_M}}}row"):
        vals: dict[int, object] = {}
        for c in r.findall("m:c", _NS):
            v, t = c.find("m:v", _NS), c.get("t")
            if t == "inlineStr":
                val = "".join(x.text or "" for x in c.iter(f"{{{_M}}}t"))
            elif v is None or v.text is None:
                continue
            elif t == "s":
                val = sst[int(v.text)]
            elif t in ("str", "e", "b"):
                val = v.text
            else:
                val = float(v.text)
            vals[_col(c.get("r"))] = val
        if vals:
            rows.append([vals.get(i) for i in range(max(vals) + 1)])
    return rows


def parse(xlsx: bytes, series: str) -> pd.DataFrame:
    """Pure: xlsx bytes -> [date, value] for one series code (GOLD | CRUDE_PETRO)."""
    want = HEADERS.get(series)
    if not want:
        raise EconError(f"pinksheet: unknown series {series}")
    rows = read_sheet_rows(xlsx)
    col = None
    for r in rows[:15]:
        for i, v in enumerate(r):
            if isinstance(v, str) and v.strip().lower() in want:
                col = i
        if col is not None:
            break
    if col is None:
        raise EconError(f"pinksheet: column for {series} not found")
    out = []
    for r in rows:
        if r and isinstance(r[0], str) and (m := _MONTH.match(r[0].strip())) and len(r) > col:
            v = r[col]
            if isinstance(v, (int, float)):
                out.append((pd.Timestamp(int(m.group(1)), int(m.group(2)), 1), float(v)))
    return pd.DataFrame(out, columns=["date", "value"])


class Session:
    """One xlsx download per run, shared by all Pink Sheet series."""

    def __init__(self):
        self.blob = None

    def load(self, budget: Budget) -> bytes:
        if self.blob is None:
            budget.take(2)
            link = find_link(get_text(PAGE_URL, source="pinksheet").text)
            self.blob = get_text(link, source="pinksheet").content
        return self.blob


def fetch(spec, since, budget: Budget, session: Session | None = None) -> pd.DataFrame:
    session = session or Session()
    df = parse(session.load(budget), spec.series)
    if since is not None:
        df = df[df["date"] >= pd.Timestamp(since)]
    return df.assign(series_id=spec.series, source="worldbank_pinksheet", fetched_at=pd.Timestamp(utcnow()))
