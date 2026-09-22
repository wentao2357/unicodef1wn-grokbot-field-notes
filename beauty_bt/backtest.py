"""M/V flip backtest engine (analysis only)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from statistics import mean, median
from typing import Iterable

from beauty_bt.models import AggregateStats, FlipEvent, TradeResult
from beauty_bt.prices import PriceStore, hold_window_bars


def _hyp_return(flip: str, entry_open: float, exit_close: float) -> float:
    long_ret = (exit_close / entry_open) - 1.0
    if flip == "M":
        # Short-bias hypothesis: profit when price falls
        return -long_ret
    return long_ret


def _mae_mfe(flip: str, entry_open: float, path) -> tuple[float, float]:
    """Max adverse / favorable excursion vs entry open, in return units."""
    if flip == "V":
        # Long: adverse = drop, favorable = rise
        mae = min((b.low / entry_open) - 1.0 for b in path)
        mfe = max((b.high / entry_open) - 1.0 for b in path)
        return mae, mfe
    # Short (M): adverse = rise, favorable = drop
    mae = max((b.high / entry_open) - 1.0 for b in path)  # positive adverse
    mfe = max(1.0 - (b.low / entry_open) for b in path)  # positive favorable
    # Express MAE as negative for shorts when adverse (rise) so lower=worse,
    # matching long convention where MAE is negative.
    return -mae, mfe


def backtest_flip(
    event: FlipEvent,
    *,
    hold_n: int,
    prices: PriceStore,
    spy_prices: PriceStore | None = None,
    lookback_pad_days: int = 5,
    lookahead_pad_days: int = 60,
) -> TradeResult:
    """Backtest a single flip event for hold_n trading days."""
    start = event.asof_date - timedelta(days=lookback_pad_days)
    end = event.asof_date + timedelta(days=lookahead_pad_days)
    bars = prices.get_bars(event.ticker, start=start, end=end)
    window = hold_window_bars(bars, asof=event.asof_date, hold_n=hold_n)
    if window is None:
        return TradeResult(
            flip=event,
            hold_n=hold_n,
            entry_date=event.asof_date,
            exit_date=event.asof_date,
            entry_open=0.0,
            exit_close=0.0,
            hyp_return=0.0,
            long_return=0.0,
            mae=0.0,
            mfe=0.0,
            spy_long_return=None,
            excess_vs_spy=None,
            incomplete=True,
            skip_reason="insufficient_price_history",
        )

    entry_bar, path, exit_bar = window
    long_ret = (exit_bar.close / entry_bar.open) - 1.0
    hyp = _hyp_return(event.flip, entry_bar.open, exit_bar.close)
    mae, mfe = _mae_mfe(event.flip, entry_bar.open, path)

    spy_long: float | None = None
    excess: float | None = None
    store = spy_prices or prices
    spy_bars = store.get_bars("SPY", start=start, end=end)
    spy_window = hold_window_bars(spy_bars, asof=event.asof_date, hold_n=hold_n)
    if spy_window is not None:
        spy_entry, _, spy_exit = spy_window
        spy_long = (spy_exit.close / spy_entry.open) - 1.0
        # Excess vs SPY in hypothesis-aligned space:
        # V long excess = hyp - spy; M short excess = hyp - (-spy) = hyp + spy
        if event.flip == "V":
            excess = hyp - spy_long
        else:
            excess = hyp - (-spy_long)

    return TradeResult(
        flip=event,
        hold_n=hold_n,
        entry_date=entry_bar.date,
        exit_date=exit_bar.date,
        entry_open=entry_bar.open,
        exit_close=exit_bar.close,
        hyp_return=hyp,
        long_return=long_ret,
        mae=mae,
        mfe=mfe,
        spy_long_return=spy_long,
        excess_vs_spy=excess,
        incomplete=False,
    )


def run_backtest(
    events: Iterable[FlipEvent],
    *,
    hold_ns: list[int],
    prices: PriceStore,
    spy_prices: PriceStore | None = None,
) -> list[TradeResult]:
    results: list[TradeResult] = []
    for event in events:
        for n in hold_ns:
            results.append(
                backtest_flip(
                    event,
                    hold_n=n,
                    prices=prices,
                    spy_prices=spy_prices,
                )
            )
    return results


def _agg(label: str, trades: list[TradeResult]) -> AggregateStats | None:
    complete = [t for t in trades if not t.incomplete]
    if not complete:
        return None
    hyps = [t.hyp_return for t in complete]
    maes = [t.mae for t in complete]
    mfes = [t.mfe for t in complete]
    spy_vals = [t.spy_long_return for t in complete if t.spy_long_return is not None]
    excess_vals = [t.excess_vs_spy for t in complete if t.excess_vs_spy is not None]

    by_ticker: dict[str, list[float]] = defaultdict(list)
    for t in complete:
        by_ticker[t.flip.ticker].append(t.hyp_return)
    ticker_means = {k: mean(v) for k, v in sorted(by_ticker.items())}

    return AggregateStats(
        label=label,
        n=len(complete),
        mean_hyp=mean(hyps),
        median_hyp=median(hyps),
        win_rate=sum(1 for x in hyps if x > 0) / len(hyps),
        mean_mae=mean(maes),
        mean_mfe=mean(mfes),
        mean_spy=mean(spy_vals) if spy_vals else None,
        mean_excess=mean(excess_vals) if excess_vals else None,
        tickers=ticker_means,
    )


def summarize(
    results: list[TradeResult],
    *,
    prefer_period_one: bool = True,
) -> list[AggregateStats]:
    """
    Build equal-weight aggregates: M/V × hold × 时段 buckets.
    Prefer 时段=1 as primary; also report 1–3 and each bucket.
    """
    stats: list[AggregateStats] = []
    complete = [r for r in results if not r.incomplete]
    holds = sorted({r.hold_n for r in complete})
    flips = ("M", "V")

    for flip in flips:
        for n in holds:
            subset = [r for r in complete if r.flip.flip == flip and r.hold_n == n]
            if prefer_period_one:
                primary = [r for r in subset if r.flip.period == 1]
                s = _agg(f"{flip} hold={n} 时段=1 (primary)", primary)
                if s:
                    stats.append(s)
            for period in (1, 2, 3):
                bucket = [r for r in subset if r.flip.period == period]
                s = _agg(f"{flip} hold={n} 时段={period}", bucket)
                if s:
                    stats.append(s)
            s = _agg(f"{flip} hold={n} 时段=1-3", subset)
            if s:
                stats.append(s)
    return stats


def date_span_needed(events: list[FlipEvent], hold_n: int) -> tuple[date, date]:
    if not events:
        today = date.today()
        return today, today
    mn = min(e.asof_date for e in events)
    mx = max(e.asof_date for e in events)
    # ~1.5 calendar days per trading day padding
    return mn - timedelta(days=7), mx + timedelta(days=int(hold_n * 2) + 14)
