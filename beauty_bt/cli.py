"""CLI entrypoint: `beauty-bt flips --input ... --hold 5,10,20`."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional

import typer

from beauty_bt.backtest import date_span_needed, run_backtest, summarize
from beauty_bt.csv_io import load_flips
from beauty_bt.prices import (
    DEFAULT_FIXTURE,
    FixturePriceStore,
    FmpPriceClient,
    build_synthetic_fixture,
)
from beauty_bt.report import print_report

app = typer.Typer(
    name="beauty-bt",
    help=(
        "Analysis-only backtest for 行知美股 选美 M/V flips. "
        "No trade tickets / no auto-execution."
    ),
    no_args_is_help=True,
)


def _parse_holds(raw: str) -> list[int]:
    holds = [int(x.strip()) for x in raw.split(",") if x.strip()]
    if not holds or any(h < 1 for h in holds):
        raise typer.BadParameter("hold must be a comma-separated list of positive ints")
    return holds


def _parse_periods(raw: str) -> set[int]:
    periods = {int(x.strip()) for x in raw.split(",") if x.strip()}
    if not periods:
        raise typer.BadParameter("periods must be non-empty")
    return periods


@app.command("flips")
def flips_cmd(
    input: Path = typer.Option(  # noqa: A002 — match CLI flag --input
        Path("data/flips.csv"),
        "--input",
        "-i",
        help="Path to flips.csv (asof_date,ticker,flip,时段,...)",
    ),
    hold: str = typer.Option(
        "5,10,20",
        "--hold",
        help="Comma-separated trading-day hold windows",
    ),
    periods: str = typer.Option(
        "1,2,3",
        "--periods",
        "-p",
        help="时段 buckets to include (default 1,2,3)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Use fixture/synthetic prices; no live FMP calls",
    ),
    fixture: Optional[Path] = typer.Option(
        None,
        "--fixture",
        help="JSON price fixture path (implies --dry-run)",
    ),
    write_fixture: Optional[Path] = typer.Option(
        None,
        "--write-fixture",
        help="With --dry-run, write generated synthetic fixture JSON here",
    ),
    limit: Optional[int] = typer.Option(
        None,
        "--limit",
        help="Optional max flip rows (for quick smoke tests)",
    ),
    show_tickers: bool = typer.Option(
        True,
        "--show-tickers/--no-show-tickers",
        help="Print per-ticker means for primary 时段=1 buckets",
    ),
) -> None:
    """
    Backtest M and V flips separately.

    Entry = next session open after asof_date T (T+1 open).
    Exit = close of trading day N. Benchmark = SPY same window.
    """
    hold_ns = _parse_holds(hold)
    period_set = _parse_periods(periods)

    if not input.exists():
        typer.echo(
            f"Input not found: {input}\n"
            "Place flips.csv at data/flips.csv or pass --input PATH.",
            err=True,
        )
        raise typer.Exit(code=2)

    events = load_flips(input, periods=period_set)
    if limit is not None:
        events = events[:limit]
    if not events:
        typer.echo("No flip events after filters.", err=True)
        raise typer.Exit(code=1)

    use_dry = dry_run or fixture is not None
    if use_dry:
        if fixture is not None:
            prices = FixturePriceStore(path=fixture)
        else:
            # Build synthetic series covering the event span + hold padding
            tickers = sorted({e.ticker for e in events} | {"SPY"})
            start, end = date_span_needed(events, max(hold_ns))
            # Keep dry-run fixtures tractable when many tickers
            if len(tickers) > 40 and limit is None:
                typer.echo(
                    f"Dry-run with {len(tickers)} symbols — synthesizing prices "
                    "(pass --limit for a smaller smoke test).",
                )
            data = build_synthetic_fixture(tickers, start=start, end=end)
            if write_fixture is not None:
                write_fixture.parent.mkdir(parents=True, exist_ok=True)
                write_fixture.write_text(json.dumps(data, indent=2), encoding="utf-8")
                typer.echo(f"Wrote synthetic fixture: {write_fixture}")
            prices = FixturePriceStore(data=data)
        typer.echo(
            f"[dry-run] {len(events)} flips, holds={hold_ns}, "
            f"fixture={fixture or 'synthetic'}"
        )
    else:
        try:
            prices = FmpPriceClient()
        except RuntimeError as exc:
            typer.echo(str(exc), err=True)
            typer.echo(
                "Hint: export FMP_API_KEY=... or re-run with --dry-run",
                err=True,
            )
            raise typer.Exit(code=2) from exc
        typer.echo(
            f"[live FMP] {len(events)} flips, holds={hold_ns} "
            f"(stable/historical-price-eod/full)"
        )

    results = run_backtest(events, hold_ns=hold_ns, prices=prices)
    stats = summarize(results, prefer_period_one=True)
    print_report(stats, results, show_tickers=show_tickers)


@app.command("version")
def version_cmd() -> None:
    """Print package version."""
    from beauty_bt import __version__

    typer.echo(__version__)


@app.callback()
def main() -> None:
    """beauty-bt — 选美 M/V flip backtest (research only)."""


if __name__ == "__main__":
    app()
