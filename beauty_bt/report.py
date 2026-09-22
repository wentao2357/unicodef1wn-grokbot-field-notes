"""Rich console reporting for backtest aggregates."""

from __future__ import annotations

from beauty_bt.models import AggregateStats, TradeResult


def _pct(x: float | None) -> str:
    if x is None:
        return "n/a"
    return f"{x * 100:+.2f}%"


def format_stats_table(stats: list[AggregateStats]) -> str:
    lines = [
        "label | n | mean_hyp | median | win% | mean_MAE | mean_MFE | mean_SPY | excess",
        "-" * 100,
    ]
    for s in stats:
        lines.append(
            f"{s.label} | {s.n} | {_pct(s.mean_hyp)} | {_pct(s.median_hyp)} | "
            f"{s.win_rate * 100:.1f}% | {_pct(s.mean_mae)} | {_pct(s.mean_mfe)} | "
            f"{_pct(s.mean_spy)} | {_pct(s.mean_excess)}"
        )
    return "\n".join(lines)


def format_per_ticker(stats: AggregateStats, *, top: int = 15) -> str:
    items = sorted(stats.tickers.items(), key=lambda kv: kv[1], reverse=True)
    head = items[:top]
    tail = items[-top:] if len(items) > top else []
    lines = [f"Per-ticker mean hyp return — {stats.label} (top/bottom {top}):"]
    for t, r in head:
        lines.append(f"  {t:>6}  {_pct(r)}")
    if tail and tail != head:
        lines.append("  ...")
        for t, r in tail:
            lines.append(f"  {t:>6}  {_pct(r)}")
    return "\n".join(lines)


def summarize_skips(results: list[TradeResult]) -> str:
    incomplete = [r for r in results if r.incomplete]
    if not incomplete:
        return "All trades had complete price windows."
    by_reason: dict[str, int] = {}
    for r in incomplete:
        reason = r.skip_reason or "unknown"
        by_reason[reason] = by_reason.get(reason, 0) + 1
    parts = [f"Skipped {len(incomplete)} trade windows:"]
    for k, v in sorted(by_reason.items()):
        parts.append(f"  {k}: {v}")
    return "\n".join(parts)


def print_report(
    stats: list[AggregateStats],
    results: list[TradeResult],
    *,
    show_tickers: bool = True,
) -> None:
    print("=== beauty-bt M/V flip backtest (analysis only) ===")
    print("Hypothesis: M=short (共识→松动), V=long (沉寂→升温). Not trade advice.")
    print()
    print(format_stats_table(stats))
    print()
    print(summarize_skips(results))
    if show_tickers:
        # Primary: 时段=1 rows first
        primaries = [s for s in stats if "时段=1 (primary)" in s.label]
        for s in primaries:
            print()
            print(format_per_ticker(s))
