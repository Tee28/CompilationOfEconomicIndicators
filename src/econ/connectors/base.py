"""Shared connector plumbing: call budget, result record, GET helper."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..common import EconError, redact


class BudgetExhausted(EconError):
    pass


class Budget:
    """Per-run call budget for one source. take() raises BudgetExhausted when spent."""

    def __init__(self, limit: int, source: str = ""):
        self.limit, self.used, self.source = int(limit), 0, source

    def take(self, n: int = 1) -> None:
        if self.used + n > self.limit:
            raise BudgetExhausted(f"{self.source}: call budget {self.limit} exhausted")
        self.used += n


@dataclass
class Outcome:
    id: str
    source: str
    status: str  # ok | skipped | failed | planned
    rows: int = 0
    note: str = ""
    issues: list = field(default_factory=list)


def get_text(url: str, params: dict | None = None, headers: dict | None = None, source: str = ""):
    """GET through econ.http; status >= 400 -> EconError with a redacted URL. Returns the Response."""
    from urllib.parse import urlencode

    from .. import http

    full = url + (("?" + urlencode(params)) if params else "")
    r = http.get(full, headers=headers)
    if r.status_code >= 400:
        raise EconError(redact(f"{source or 'http'} {r.status_code} for {full}"))
    return r
