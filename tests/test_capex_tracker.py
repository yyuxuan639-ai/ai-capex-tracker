"""
Tests with synthetic data shaped like the SEC companyfacts API.
Run:  python -m pytest tests/
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import capex_tracker as ct


def fact(start, end, val, form="10-Q", filed="2025-01-01", accn="0000-00-000001"):
    return {"start": start, "end": end, "val": val, "form": form,
            "filed": filed, "accn": accn}


def company(tag, facts):
    return {"facts": {"us-gaap": {tag: {"units": {"USD": facts}}}}}


# A June fiscal year company (like Microsoft): FY2025 = Jul 2024 - Jun 2025
JUNE_FY = company("PaymentsToAcquirePropertyPlantAndEquipment", [
    fact("2024-07-01", "2024-09-30", 10e9),
    fact("2024-07-01", "2024-12-31", 22e9),
    fact("2024-07-01", "2025-03-31", 36e9),
    fact("2024-07-01", "2025-06-30", 55e9, form="10-K", filed="2025-07-30"),
    # same 6-month period repeated later with a restated value: later filing wins
    fact("2024-07-01", "2024-12-31", 23e9, filed="2025-05-01"),
])


def test_ytd_converted_to_single_quarters():
    q = ct.derive_quarters(ct.dedupe(ct.extract_capex_facts("TEST", JUNE_FY)))
    vals = dict(zip(q["cal_quarter"], q["capex_usd"] / 1e9))
    # restated 6M YTD is 23, so Q2 = 23 - 10 = 13 and Q3 = 36 - 23 = 13
    assert vals == {"2024Q3": 10, "2024Q4": 13, "2025Q1": 13, "2025Q2": 19}


def test_fiscal_quarter_maps_to_calendar_quarter():
    # Oracle-style quarter, Jun-Aug, belongs in calendar Q3
    import pandas as pd
    assert ct.calendar_quarter(pd.Timestamp("2025-06-01"), pd.Timestamp("2025-08-31")) == "2025Q3"


def test_alternate_tag_is_picked_up():
    data = company("PaymentsToAcquireProductiveAssets", [
        fact("2025-01-01", "2025-03-31", 25e9),
    ])
    q = ct.derive_quarters(ct.dedupe(ct.extract_capex_facts("TEST", data)))
    assert q.iloc[0]["tag"] == "PaymentsToAcquireProductiveAssets"


def test_missing_quarter_is_skipped_not_misstated():
    data = company("PaymentsToAcquirePropertyPlantAndEquipment", [
        fact("2025-01-01", "2025-03-31", 10e9),
        # 6M YTD missing; 9M arrives directly
        fact("2025-01-01", "2025-09-30", 40e9),
    ])
    q = ct.derive_quarters(ct.dedupe(ct.extract_capex_facts("TEST", data)))
    assert list(q["cal_quarter"]) == ["2025Q1"]  # no fake 6-month "quarter"


def test_incomplete_latest_quarter_is_trimmed_but_early_gaps_kept():
    import pandas as pd
    wide = pd.DataFrame(
        {"CRWV": [None, 2.0, 3.0, None], "ORCL": [1.0, 1.0, 1.0, 1.0]},
        index=["2025Q1", "2025Q2", "2025Q3", "2025Q4"],
    )
    out = ct.trim_incomplete_tail(wide)
    # 2025Q4 only has Oracle -> dropped; 2025Q1 gap (pre-IPO) -> kept
    assert list(out.index) == ["2025Q1", "2025Q2", "2025Q3"]


def test_manual_override_fills_gap(tmp_path, monkeypatch):
    import pandas as pd
    f = tmp_path / "ov.csv"
    f.write_text("ticker,cal_quarter,capex_usd_millions,source\nTEST,2025Q2,250,10-Q p.5\n")
    monkeypatch.setattr(ct, "OVERRIDES_FILE", f)
    q = pd.DataFrame([{"ticker": "TEST", "cal_quarter": "2025Q1", "capex_usd": 1e8}])
    out = ct.apply_overrides(q, "TEST")
    assert list(out["cal_quarter"]) == ["2025Q1", "2025Q2"]
    assert out.iloc[1]["capex_usd"] == 250e6


def test_build_metric_never_mixes_tags_inside_a_fiscal_year():
    # Tag A covers Q1 only; tag B covers the 6M YTD. Mixing them would give Q2 = 30-10.
    data = {"facts": {"us-gaap": {
        "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": [
            fact("2025-01-01", "2025-03-31", 10e9)]}},
        "PaymentsToAcquireProductiveAssets": {"units": {"USD": [
            fact("2025-01-01", "2025-03-31", 12e9),
            fact("2025-01-01", "2025-06-30", 30e9)]}},
    }}}
    q = ct.build_metric("TEST", data, "capex")
    vals = dict(zip(q["cal_quarter"], q["value_usd"] / 1e9))
    assert vals == {"2025Q1": 10, "2025Q2": 18}  # Q1 from preferred tag, Q2 = 30 - 12


def test_metrics_match_definitions():
    import pandas as pd
    idx = ["2024Q1", "2024Q2", "2024Q3", "2024Q4", "2025Q1", "2025Q2"]
    panel = pd.DataFrame({
        "capex":   [10, 11, 12, 13, 20, 26],
        "revenue": [100, 100, 100, 100, 100, 100],
        "ocf":     [30, 30, 30, 30, 30, 30],
        "da":      [5, 5, 5, 5, 10, 13],
    }, index=idx, dtype=float)
    m = ct.compute_metrics(panel)
    assert m.loc["2025Q1", "capex_yoy"] == 1.0            # 20 / 10 - 1
    assert m.loc["2025Q2", "capex_ttm"] == 12 + 13 + 20 + 26
    assert m.loc["2025Q2", "capex_intensity"] == 0.26
    assert m.loc["2025Q2", "fcf_ttm"] == 120 - 71
    assert abs(m.loc["2025Q2", "fcf_margin_ttm"] - 49 / 400) < 1e-12
    assert m.loc["2025Q2", "capex_to_da"] == 2.0
    assert m.loc["2025Q2", "trend"] == "Accelerating"     # 136% YoY vs 100%
