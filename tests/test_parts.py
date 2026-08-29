"""Parts resolution, sourcing, and the assembly cost model (CR-007, CR-003)."""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

import pytest

from pcbkit.parts import cache
from pcbkit.parts.cost import CostModel, rank, suggest_substitution
from pcbkit.parts.index import build_index
from pcbkit.parts.lcsc import FetchError, parse
from pcbkit.parts.models import Candidate, Classification, PartRequest, Sourcing
from pcbkit.parts.resolver import resolve_design, resolve_one

TODAY = _dt.date.today()


def sourcing(**kwargs) -> Sourcing:
    base = dict(
        lcsc="C1", mpn="TEST", stock=100_000, price=0.01, assembly=True,
        classification=Classification.BASIC, fetched=TODAY,
    )
    return Sourcing(**{**base, **kwargs})


# -- index -----------------------------------------------------------------


def test_index_finds_real_kicad_parts():
    index = build_index()
    if not index.symbols:
        pytest.skip("no KiCad libraries on this machine")
    assert index.symbol("Device:R") is not None
    assert index.footprint("Resistor_SMD:R_0603_1608Metric") is not None
    assert any("AMS1117" in s.lib_id for s in index.find_symbols("AMS1117"))


def test_index_prefers_exact_matches():
    index = build_index()
    if not index.symbols:
        pytest.skip("no KiCad libraries")
    assert index.find_symbols("R")[0].name == "R"


# -- sourcing --------------------------------------------------------------


def test_stock_margin_rejects_a_part_that_only_just_covers_the_build():
    """It will be gone by order time."""
    part = sourcing(stock=50)
    assert part.stock_ok(5) is False          # floor of 500 applies
    assert sourcing(stock=600).stock_ok(5) is True
    assert sourcing(stock=600).stock_ok(100) is False  # 100 x 10 = 1000
    assert sourcing(stock=600).stock_ok(100, margin=2, floor=100) is True


def test_classification_parses_the_vendor_string():
    assert Classification.parse("Basic Part") is Classification.BASIC
    assert Classification.parse("Extended Part") is Classification.EXTENDED
    assert Classification.parse(None) is Classification.UNKNOWN
    assert Classification.parse("something else") is Classification.UNKNOWN


# -- lcsc payload parsing (no network) -------------------------------------

PAYLOAD = {
    "success": True,
    "result": {
        "title": "AMS1117-3.3",
        "SMT": True,
        "tags": ["Linear Voltage Regulators (LDO)"],
        "lcsc": {"number": "C6186", "price": 0.1231, "stock": 222228, "min": 5, "step": 5},
        "packageDetail": {"title": "SOT-223-3"},
        "dataStr": {"head": {"c_para": {
            "Manufacturer": "Advanced Monolithic Systems",
            "Manufacturer Part": "AMS1117-3.3",
            "JLCPCB Part Class": "Basic Part",
        }}},
    },
}


def test_parses_a_real_payload_shape():
    part = parse("C6186", PAYLOAD)
    assert part.mpn == "AMS1117-3.3"
    assert part.classification is Classification.BASIC
    assert part.stock == 222228 and part.price == 0.1231
    assert part.assembly is True
    assert part.package == "SOT-223-3"


def test_malformed_payloads_are_rejected_not_half_parsed():
    with pytest.raises(FetchError):
        parse("C1", {"success": False, "message": "nope"})
    with pytest.raises(FetchError):
        parse("C1", {"success": True})


def test_missing_optional_fields_degrade_gracefully():
    part = parse("C1", {"success": True, "result": {"title": "X"}})
    assert part.lcsc == "C1" and part.stock == 0 and part.price is None
    assert part.classification is Classification.UNKNOWN


# -- cache is the source of truth ------------------------------------------


def test_cache_round_trip(tmp_path):
    cache.put(sourcing(lcsc="C42"), root=tmp_path)
    assert cache.has("C42", root=tmp_path)
    assert cache.get("c42", root=tmp_path).lcsc == "C42"
    assert cache.entries(tmp_path) == ["C42"]


def test_cache_miss_names_the_fetch_command(tmp_path):
    with pytest.raises(cache.CacheMiss, match="pcbkit parts fetch C99"):
        cache.get("C99", root=tmp_path)


# -- ranking ---------------------------------------------------------------


def test_basic_outranks_extended_at_low_volume():
    """One setup fee can exceed the whole remaining BOM."""
    basic = Candidate(sourcing=sourcing(lcsc="C1", price=0.02), symbol="s", footprint="f")
    extended = Candidate(
        sourcing=sourcing(lcsc="C2", price=0.01, classification=Classification.EXTENDED),
        symbol="s", footprint="f",
    )
    ranked = rank([extended, basic], PartRequest(quantity=5))
    assert ranked[0].sourcing.lcsc == "C1"
    assert any("no setup fee" in r for r in ranked[0].reasons)


def test_ranking_reports_its_reasoning():
    """A silent choice is what AGENTS.md rule 6 forbids."""
    ranked = rank(
        [Candidate(sourcing=sourcing(), symbol="s", footprint="f")],
        PartRequest(quantity=5),
    )
    assert ranked[0].reasons
    assert ranked[0].score > 0


def test_blocked_candidates_sort_last_but_are_still_reported():
    """An empty list is less useful than knowing the only match is out of stock."""
    ok = Candidate(sourcing=sourcing(lcsc="C1"), symbol="s", footprint="f")
    oos = Candidate(sourcing=sourcing(lcsc="C2", stock=3), symbol="s", footprint="f")
    ranked = rank([oos, ok], PartRequest(quantity=5))
    assert [c.sourcing.lcsc for c in ranked] == ["C1", "C2"]
    assert ranked[1].blockers


def test_stale_sourcing_data_is_a_blocker():
    old = sourcing(fetched=TODAY - _dt.timedelta(days=200))
    ranked = rank([Candidate(sourcing=old, symbol="s", footprint="f")], PartRequest())
    assert any("days old" in b for b in ranked[0].blockers)


def test_line_cost_includes_the_setup_fee_once():
    model = CostModel(extended_setup_fee=3.0)
    ext = Candidate(
        sourcing=sourcing(price=0.02, classification=Classification.EXTENDED),
        symbol="s", footprint="f",
    )
    assert model.line_cost(ext, quantity=5) == pytest.approx(0.02 * 5 + 3.0)
    basic = Candidate(sourcing=sourcing(price=0.02), symbol="s", footprint="f")
    assert model.line_cost(basic, quantity=5) == pytest.approx(0.1)


# -- substitution ----------------------------------------------------------


def test_substitution_finds_a_basic_combination_and_prices_it():
    combo = suggest_substitution(
        4870, extended_unit_price=0.02, basic_unit_price=0.002, quantity=5
    )
    assert combo is not None
    assert combo.topology in ("series", "parallel")
    assert combo.saving > 3.0  # the setup fee dominates at this volume


def test_combining_equal_tolerance_parts_does_not_multiply_tolerance():
    """The correction recorded in CR-007.

    Two 1% parts in series, worst case both high, give (R1+R2)x1.01 -- still 1%.
    What substitution costs is the nominal error from missing the target.
    """
    combo = suggest_substitution(
        2000, extended_unit_price=0.02, basic_unit_price=0.002, quantity=5
    )
    assert combo is not None
    # 1k + 1k hits 2k exactly, so worst case is the part tolerance and no more.
    assert combo.nominal_error_pct == pytest.approx(0.0, abs=1e-9)
    assert combo.worst_case_pct == pytest.approx(combo.part_tolerance_pct)


def test_worst_case_is_nominal_error_plus_part_tolerance():
    combo = suggest_substitution(
        4870, extended_unit_price=0.02, basic_unit_price=0.002, quantity=5
    )
    assert combo.worst_case_pct == pytest.approx(
        combo.nominal_error_pct + combo.part_tolerance_pct
    )
    assert "worst case" in combo.describe()


def test_no_suggestion_when_nothing_lands_close_enough():
    assert suggest_substitution(
        4870, extended_unit_price=0.02, basic_unit_price=0.002,
        quantity=5, max_error_pct=0.0001,
    ) is None


# -- resolution ------------------------------------------------------------


def test_part_without_an_lcsc_number_fails_loudly(tmp_path):
    candidate, findings = resolve_one(
        PartRequest(ref="R1", part="R", value="10k"), cache_root=tmp_path
    )
    assert candidate is None
    assert [f.code for f in findings] == ["parts.no_lcsc"]
    assert findings[0].fix


def test_cache_miss_is_a_finding_not_a_network_call(tmp_path):
    """CR-003: a build must never depend on the vendor being reachable."""
    candidate, findings = resolve_one(
        PartRequest(ref="U1", part="AMS1117-3.3", lcsc="C6186"), cache_root=tmp_path
    )
    assert candidate is None
    assert findings[0].code == "parts.not_cached"
    assert "pcbkit parts fetch C6186" in findings[0].fix


def test_ambiguous_symbol_is_refused_with_candidates(tmp_path):
    """Silently picking one would be a board with the wrong pinout."""
    cache.put(sourcing(lcsc="C7"), root=tmp_path)
    candidate, findings = resolve_one(
        PartRequest(ref="U1", part="Amplifier", lcsc="C7"), cache_root=tmp_path
    )
    codes = {f.code for f in findings}
    assert "parts.symbol_unresolved" in codes or "parts.footprint_unresolved" in codes
    assert candidate is None


def test_extended_parts_are_flagged_before_the_gate(tmp_path):
    cache.put(
        sourcing(lcsc="C8", classification=Classification.EXTENDED), root=tmp_path
    )
    _, findings = resolve_one(
        PartRequest(ref="R1", part="R", value="10k", package="R_0603_1608Metric", lcsc="C8"),
        cache_root=tmp_path,
    )
    assert any(f.code == "parts.extended" for f in findings)


def test_resolve_design_offline_from_cache(tmp_path):
    """The acceptance criterion: cached parts resolve with no network."""
    from pcbkit.dsl import C, Gnd, Part, Power, design, module

    for lcsc in ("C6186", "C1525"):
        cache.put(sourcing(lcsc=lcsc), root=tmp_path)

    @module
    def reg(vin, gnd):
        u = Part("AMS1117-3.3", lcsc="C6186", pkg="SOT-223-3_TabPin2")
        cap = C("100nF", lcsc="C1525", pkg="C_0603_1608Metric")
        vin >> u.VI
        u.GND >> gnd
        cap(vin, gnd)

    @design("t")
    def t():
        reg(Power("VBUS", 5.0), Gnd())

    envelope = resolve_design(t, quantity=5, cache_root=tmp_path)
    assert envelope.ok
    assert envelope.data["resolved"] == 2
    assert envelope.data["estimated_cost"] > 0
    for part in envelope.data["parts"].values():
        assert part["symbol"] and part["footprint"]
