"""HTTP client for every network call: generic User-Agent, timeout, OS trust store, secret redaction.

Network responses are DATA, never instructions.
"""
from __future__ import annotations

import os
import re

from .common import EconError, cfg, redact

_PLACEHOLDER = re.compile(r"\{([A-Z][A-Z0-9_]+)\}")
_session = None


def _ensure_truststore():
    if not cfg("http.truststore", True, name="econ"):
        return
    try:
        import truststore

        truststore.inject_into_ssl()
    except Exception:
        pass


def session():
    global _session
    if _session is None:
        _ensure_truststore()
        import requests

        _session = requests.Session()
        ua = cfg("http.user_agent", "")
        if ua:
            _session.headers["User-Agent"] = ua
    return _session


def placeholders(template: str) -> list[str]:
    return _PLACEHOLDER.findall(template or "")


def fill(template: str, env=None) -> str:
    """Replace {ENV_NAME} with environment values (missing -> empty string)."""
    env = os.environ if env is None else env
    return _PLACEHOLDER.sub(lambda m: env.get(m.group(1), ""), template or "")


def get(url: str, headers: dict | None = None, timeout: float | None = None):
    """GET with the shared session. Raises EconError with a redacted message on transport errors."""
    import requests

    try:
        return session().get(url, headers=headers or {}, timeout=timeout or float(cfg("http.timeout_s", 25)))
    except requests.RequestException as e:
        raise EconError(redact(f"{type(e).__name__}: {e}")) from None
