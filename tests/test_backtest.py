"""CSV parse + hold-window math tests (no live FMP)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from beauty_bt.backtest import backtest_flip, run_backtest, summarize
from beauty_bt.csv_io import load_flips
from beauty_bt.prices import FixturePriceStore, hold_window_bars

ROOT = Path(__file__).resolve().parents[1]
MINI_CSV = Path(__file__).resolve().parent / "fixtures" / "mini_flips.csv"
SAMPLE_PRICES = ROOT / "beauty_bt" / "fixtures" / "sample_prices.json"
DATA_FLIPS = ROOT / "data" / "flips.csv"


def test_load_mini_flips():
    events = load_flips(MINI_CSV)
    assert len(events) == 4
    assert {e.flip for e in events} == {"M", "V"}
    assert events[0].ticker == "AAA"
    assert events[0].period == 1


def test_load_flips_period_filter():
    events = load_flips(MINI_CSV, periods={1})
    assert len(events) == 2
    assert all(e.period == 1 for e in events)


def test_load_real_flips_csv_counts():
    events = load_flips(DATA_FLIPS)
    assert len(events) == 4323
    m = sum(1 for e in events if e.flip == "M")
    v = sum(1 for e in events if e.flip == "V")
    assert m == 3077
    assert v == 1246
    assert {e.period for e in events} == {1, 2, 3}


def test_hold_window_t_plus_1_open_exit_close_day_n():
    store = FixturePriceStore(path=SAMPLE_PRICES)
    bars = store.get_bars("AAA", start=date(2026, 8, 1), end=date(2026, 10, 1))
    # asof Fri 2026-08-21 → next session Mon 2026-08-24
    window = hold_window_bars(bars, asof=date(2026, 8, 21), hold_n=5)
    assert window is not None
    entry, path, exit_bar = window
    assert entry.date == date(2026, 8, 24)
    assert entry.open == 101.0
    assert len(path) == 5
    assert exit_bar.date == date(2026, 8, 28)
    assert exit_bar.close == 106.0


def test_hold_window_incomplete():
    store = FixturePriceStore(path=SAMPLE_PRICES)
    bars = store.get_bars("AAA", start=date(2026, 8, 1), end=date(2026, 10, 1))
    # asof near end of series — hold 20 may be incomplete depending on fixture length
    window = hold_window_bars(bars, asof=date(2026, 9, 22), hold_n=20)
    assert window is None


def test_v_long_and_m_short_hypothesis_returns():
    store = FixturePriceStore(path=SAMPLE_PRICES)
    events = load_flips(MINI_CSV, periods={1})
    v = next(e for e in events if e.flip == "V")
    m = next(e for e in events if e.flip == "M")

    v_res = backtest_flip(v, hold_n=5, prices=store)
    m_res = backtest_flip(m, hold_n=5, prices=store)

    assert not v_res.incomplete
    assert not m_res.incomplete
    # AAA: entry open 101 (8/24), exit close day5 = 106 (8/28) → long +4.95%
    assert v_res.entry_date == date(2026, 8, 24)
    assert pytest.approx(v_res.long_return, rel=1e-6) == (106 / 101) - 1
    assert pytest.approx(v_res.hyp_return, rel=1e-6) == v_res.long_return

    # BBB: entry open 48.5 (8/24), exit close 43.5 (8/28) → long negative, short hyp positive
    assert m_res.entry_date == date(2026, 8, 24)
    assert pytest.approx(m_res.long_return, rel=1e-6) == (43.5 / 48.5) - 1
    assert pytest.approx(m_res.hyp_return, rel=1e-6) == -m_res.long_return
    assert m_res.hyp_return > 0


def test_mae_mfe_signs():
    store = FixturePriceStore(path=SAMPLE_PRICES)
    events = load_flips(MINI_CSV, periods={1})
    v = next(e for e in events if e.flip == "V")
    m = next(e for e in events if e.flip == "M")
    v_res = backtest_flip(v, hold_n=5, prices=store)
    m_res = backtest_flip(m, hold_n=5, prices=store)
    # Rising AAA: MAE should be <= 0, MFE >= 0
    assert v_res.mae <= 0
    assert v_res.mfe >= 0
    # Falling BBB short: MAE negative (adverse rise expressed as -), MFE positive
    assert m_res.mae <= 0
    assert m_res.mfe >= 0


def test_spy_benchmark_attached():
    store = FixturePriceStore(path=SAMPLE_PRICES)
    events = load_flips(MINI_CSV, periods={1})
    v = next(e for e in events if e.flip == "V")
    res = backtest_flip(v, hold_n=5, prices=store)
    assert res.spy_long_return is not None
    assert res.excess_vs_spy is not None
    # SPY entry 501 (8/24) → exit 506 (8/28)
    assert pytest.approx(res.spy_long_return, rel=1e-6) == (506 / 501) - 1


def test_summarize_separates_m_and_v():
    store = FixturePriceStore(path=SAMPLE_PRICES)
    events = load_flips(MINI_CSV)
    results = run_backtest(events, hold_ns=[5], prices=store)
    stats = summarize(results)
    labels = [s.label for s in stats]
    assert any(lab.startswith("M ") for lab in labels)
    assert any(lab.startswith("V ") for lab in labels)
    # Primary 时段=1 present
    assert any("时段=1 (primary)" in lab for lab in labels)


def test_do_not_pool_signs_in_equal_weight():
    """M and V aggregates must be computed separately."""
    store = FixturePriceStore(path=SAMPLE_PRICES)
    events = load_flips(MINI_CSV, periods={1})
    results = run_backtest(events, hold_ns=[5], prices=store)
    stats = {s.label: s for s in summarize(results)}
    m = stats["M hold=5 时段=1 (primary)"]
    v = stats["V hold=5 时段=1 (primary)"]
    assert m.n == 1
    assert v.n == 1
    # Opposite raw directions → hyp means should both be positive on this fixture
    assert m.mean_hyp > 0
    assert v.mean_hyp > 0
