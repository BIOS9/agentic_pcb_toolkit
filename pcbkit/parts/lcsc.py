"""EasyEDA/LCSC client. The only place pcbkit touches the network.

Deliberately not on the build path. CR-003 rules that vendor data enriches a
build and never gates one, so this module is called by `pcbkit parts fetch` to
populate the cache, and by nothing else.

The remote payload is untrusted input: it is fetched over the network, it lands
on disk, and it is written by a third party. Parse defensively and never
interpolate it into a path.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import urllib.error
import urllib.request
from typing import Any

from pcbkit.parts.models import Classification, Sourcing

API = "https://easyeda.com/api/products/{lcsc}/components?version=6.4.19.5"
TIMEOUT = 20
USER_AGENT = "pcbkit/0.1 (+https://github.com/BIOS9/agentic_pcb_toolkit)"

# LCSC part numbers are C followed by digits. Validated before use because the
# value reaches a URL.
LCSC_RE = re.compile(r"^C\d+$", re.IGNORECASE)


class FetchError(RuntimeError):
    """The part could not be fetched. Never raised during a build."""


def _get(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise FetchError(f"network error fetching {url}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise FetchError(f"{url} returned malformed JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise FetchError(f"{url} returned {type(payload).__name__}, expected an object")
    return payload


def _text(value: Any) -> str:
    """Coerce untrusted payload values to a bounded string."""
    if value is None:
        return ""
    return str(value)[:400]


def parse(lcsc: str, payload: dict[str, Any]) -> Sourcing:
    """Turn an EasyEDA response into a Sourcing record.

    Split out from fetching so the parsing is testable against recorded
    payloads without a network call.
    """
    if not payload.get("success"):
        raise FetchError(f"{lcsc}: API reported failure: {_text(payload.get('message'))}")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise FetchError(f"{lcsc}: response has no result object")

    stock_info = result.get("lcsc") or result.get("szlcsc") or {}
    if not isinstance(stock_info, dict):
        stock_info = {}

    # Manufacturer, MPN and the JLCPCB class live in the symbol header's
    # parameter block rather than at the top level.
    params: dict[str, Any] = {}
    head = ((result.get("dataStr") or {}) if isinstance(result.get("dataStr"), dict) else {}).get("head")
    if isinstance(head, dict) and isinstance(head.get("c_para"), dict):
        params = head["c_para"]

    package_detail = result.get("packageDetail")
    package = ""
    if isinstance(package_detail, dict):
        package = _text(package_detail.get("title"))
    package = package or _text(params.get("package"))

    def number(value: Any, cast):
        try:
            return cast(value)
        except (TypeError, ValueError):
            return None

    return Sourcing(
        lcsc=lcsc.upper(),
        mpn=_text(params.get("Manufacturer Part") or result.get("title")),
        manufacturer=_text(params.get("Manufacturer")),
        package=package,
        description=_text(result.get("description")) or ", ".join(
            _text(t) for t in (result.get("tags") or [])[:3]
        ),
        price=number(stock_info.get("price"), float),
        stock=number(stock_info.get("stock"), int) or 0,
        min_qty=number(stock_info.get("min"), int) or 1,
        step_qty=number(stock_info.get("step"), int) or 1,
        classification=Classification.parse(_text(params.get("JLCPCB Part Class"))),
        assembly=bool(result.get("SMT")),
        fetched=_dt.date.today(),
        source="easyeda",
    )


def fetch(lcsc: str) -> Sourcing:
    """Fetch one part. Requires the network; never called by `build` or `check`."""
    if not LCSC_RE.match(lcsc.strip()):
        raise FetchError(f"{lcsc!r} is not an LCSC part number (expected C followed by digits)")
    lcsc = lcsc.strip().upper()
    return parse(lcsc, _get(API.format(lcsc=lcsc)))
