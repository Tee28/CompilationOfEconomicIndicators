"""Offline connector tests: http.get is monkeypatched with fixtures; no network, no real keys."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from econ import connectors, http, registry, store
from econ.common import EconError, Paths
from econ.connectors import fred, oecd, pinksheet
from econ.connectors.base import Budget, BudgetExhausted
from econ.quality import check_frame, health_entry

FX = Path(__file__).parent / "fixtures"


class Resp:
    def __init__(self, text="", content=None, status=200):
        self.text, self.status_code = text, status
        self.content = content if content is not None else text.encode()

    def json(self):
        return json.loads(self.text)


def make_xlsx() -> bytes:
    """Minimal Pink Sheet-like workbook: header rows + 'YYYYMmm' rows (synthetic, structure only)."""
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    strings = ["Monthly Prices", "Crude oil, average", "Gold", "($/bbl)", "($/toz)", "2026M08", "2026M09", "2026M10"]
    sst = "".join(f"<si><t>{s}</t></si>" for s in strings)
    rows = ('<row r="5"><c r="B5" t="s"><v>1</v></c><c r="C5" t="s"><v>2</v></c></row>'
            '<row r="6"><c r="B6" t="s"><v>3</v></c><c r="C6" t="s"><v>4</v></c></row>')
    for i, (m, o, g) in enumerate([(5, 70.5, 3350.0), (6, 68.25, 3400.5), (7, 66.0, "..")]):
        r = 7 + i
        gold = f'<c r="C{r}" t="str"><v>{g}</v></c>' if isinstance(g, str) else f'<c r="C{r}"><v>{g}</v></c>'
        rows += f'<row r="{r}"><c r="A{r}" t="s"><v>{m}</v></c><c r="B{r}"><v>{o}</v></c>{gold}</row>'
    files = {
        "xl/workbook.xml": f'<workbook {ns} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                           '<sheets><sheet name="Monthly Prices" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                                      '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
        "xl/sharedStrings.xml": f"<sst {ns}>{sst}</sst>",
        "xl/worksheets/sheet1.xml": f"<worksheet {ns}><sheetData>{rows}</sheetData></worksheet>",
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for k, v in files.items():
            z.writestr(k, v)
    return buf.getvalue()


@pytest.fixture
def routes(monkeypatch):
    """Install a fake http.get; returns the (mutable) route table and the list of requested URLs."""
    table, seen = {}, []

    def fake_get(url, headers=None, timeout=None):
        seen.append(url)
        for key, resp in table.items():
            if key in url:
                return resp
        return Resp("not found", status=404)

    monkeypatch.setattr(http, "get", fake_get)
    return table, seen


@pytest.fixture
def paths(tmp_path):
    return Paths(data=tmp_path / "data")


def spec_of(iid):
    return registry.load()[iid]


# ---------------------------------------------------------------- fred
def test_fred_parse_drops_missing_and_marks_vintage():
    js = json.loads((FX / "fred_cpi_vintages.json").read_text())
    df = fred.parse(js, vintage=True)
    assert len(df) == 3 and df["realtime_start"].notna().all()
    daily = fred.parse(json.loads((FX / "fred_dgs10.json").read_text()), vintage=False)
    assert len(daily) == 2 and daily["realtime_start"].isna().all()


def test_fred_vintages_stored_as_revisions(routes, paths, monkeypatch):
    table, seen = routes
    monkeypatch.setenv("FRED_API_KEY", "SECRETKEY123456")
    table["CPIAUCSL"] = Resp((FX / "fred_cpi_vintages.json").read_text())
    out = connectors.fetch_all(registry.load(), paths, "2026-11-24", ids=["cpi"])
    assert out[0].status == "ok" and out[0].rows == 3  # 2 dates + 1 revision row
    assert "realtime_start=2010-01-01" in seen[0]
    old = store.read_frame("fred", "CPIAUCSL", "2024-03-20", 0, paths)
    new = store.read_frame("fred", "CPIAUCSL", "2024-06-30", 0, paths)
    assert old.loc[old["date"] == "2024-02-01", "value"].iloc[0] == pytest.approx(310.326)
    assert new.loc[new["date"] == "2024-02-01", "value"].iloc[0] == pytest.approx(310.4)


def test_fred_missing_key_is_skipped(routes, paths, monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    out = connectors.fetch_all(registry.load(), paths, "2026-11-24", ids=["dgs10"])
    assert out[0].status == "skipped" and "FRED_API_KEY" in out[0].note
    assert routes[1] == []


def test_fred_error_redacts_key_and_degrades(routes, paths, monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "SECRETKEY123456")
    routes[0]["DGS10"] = Resp("boom", status=500)
    out = connectors.fetch_all(registry.load(), paths, "2026-11-24", ids=["dgs10", "dgs2"])
    assert out[0].status == "failed" and "SECRETKEY" not in out[0].note
    assert len(out) == 2  # the other series was still attempted


def test_budget_exhausted():
    b = Budget(1, "fred")
    b.take(1)
    with pytest.raises(BudgetExhausted):
        b.take(1)


def test_budget_override_limits_calls(routes, paths, monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "SECRETKEY123456")
    routes[0]["observations"] = Resp((FX / "fred_dgs10.json").read_text())
    out = connectors.fetch_all(registry.load(), paths, "2026-11-24", ids=["dgs10", "dgs2", "t10y2y"], budget=1)
    assert [o.status for o in out] == ["ok", "failed", "failed"]
    assert len(routes[1]) == 1


# ---------------------------------------------------------------- pink sheet
def test_pinksheet_link_and_parse():
    link = pinksheet.find_link((FX / "pinksheet_page.html").read_text())
    assert link.endswith("CMO-Historical-Data-Monthly.xlsx") and link.startswith("https://")
    x = make_xlsx()
    gold = pinksheet.parse(x, "GOLD")
    assert list(gold["value"]) == [3350.0, 3400.5] and gold["date"].iloc[0] == pd.Timestamp("2026-08-01")
    assert list(pinksheet.parse(x, "CRUDE_PETRO")["value"]) == [70.5, 68.25, 66.0]
    with pytest.raises(EconError):
        pinksheet.find_link("<html></html>")


def test_pinksheet_fetch_downloads_once(routes, paths):
    table, seen = routes
    table["commodity-markets"] = Resp((FX / "pinksheet_page.html").read_text())
    table["CMO-Historical"] = Resp(content=make_xlsx())
    out = connectors.fetch_all(registry.load(), paths, "2026-11-10", ids=["gold_pink", "oil_pink"])
    assert [o.status for o in out] == ["ok", "ok"] and [o.rows for o in out] == [2, 3]
    assert len(seen) == 2


# ---------------------------------------------------------------- oecd
def test_oecd_parse_and_fetch(routes, paths):
    df = oecd.parse((FX / "oecd_cli.csv").read_text())
    assert len(df) == 3 and df["date"].iloc[-1] == pd.Timestamp("2026-10-01")
    routes[0]["DF_CLI"] = Resp((FX / "oecd_cli.csv").read_text())
    out = connectors.fetch_all(registry.load(), paths, "2026-11-24", ids=["oecd_cli"])
    assert out[0].status == "ok" and out[0].rows == 3
    assert "USA.M.LI.IX._Z.AA.IX._Z.H" in routes[1][0]
    with pytest.raises(EconError):
        oecd.parse("a,b\n1,2\n")


# ---------------------------------------------------------------- quality
def test_quality_flags():
    sp = spec_of("dgs10")
    good = pd.DataFrame({"date": pd.date_range("2026-10-01", periods=40), "value": [4.0 + 0.01 * i for i in range(40)]})
    assert check_frame(good, sp, "2026-11-12") == []
    codes = {i["code"] for i in check_frame(good, sp, "2026-12-30")}
    assert "stale" in codes
    bad = good.copy()
    bad.loc[39, "value"] = 400.0
    assert {"outlier", "unit_jump"} <= {i["code"] for i in check_frame(bad, sp, "2026-11-12")}
    assert check_frame(good.iloc[0:0], sp)[0]["level"] == "error"
    h = health_entry(check_frame(good, sp, "2026-12-30"), good["date"].max(), "2026-12-30")
    assert h["ok"] and h["lag_days"] > 40 and "stale" in h["note"]


# ---------------------------------------------------------------- CLI
def test_cmd_fetch_dry_run_no_network(routes, paths):
    res = connectors.cmd_fetch(SimpleNamespace(id=None, dry_run=True, asof="2026-11-24", data_dir=str(paths.data),
                                               ledger_dir=None, out_dir=None, site_dir=None))
    assert res.code == 0 and "dry-run" in res.text and len(res.text.splitlines()) <= 40
    assert routes[1] == []
    assert not (paths.data / "raw").exists()
