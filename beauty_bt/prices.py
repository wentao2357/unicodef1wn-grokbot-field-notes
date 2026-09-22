"""Financial Modeling Prep historical EOD client + fixture/dry-run store."""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Protocol

import httpx

from beauty_bt.models import Bar

FMP_BASE = "https://financialmodelingprep.com/stable"
DEFAULT_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample_prices.json"


class PriceStore(Protocol):
    def get_bars(
        self,
        symbol: str,
        *,
        start: date,
        end: date,
    ) -> list[Bar]:
        ...


def _parse_bar(row: dict) -> Bar:
    d = row["date"]
    if isinstance(d, date):
        bar_date = d
    else:
        bar_date = datetime.strptime(str(d)[:10], "%Y-%m-%d").date()
    return Bar(
        date=bar_date,
        open=float(row["open"]),
        high=float(row["high"]),
        low=float(row["low"]),
        close=float(row["close"]),
        volume=float(row.get("volume") or 0),
    )


class FmpPriceClient:
    """Live FMP `/stable/historical-price-eod/full` client."""

    def __init__(self, api_key: str | None = None, *, timeout: float = 30.0):
        self.api_key = api_key or os.environ.get("FMP_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "FMP_API_KEY is not set. Export it for live runs, "
                "or use --dry-run with fixtures."
            )
        self.timeout = timeout
        self._cache: dict[tuple[str, date, date], list[Bar]] = {}

    def get_bars(self, symbol: str, *, start: date, end: date) -> list[Bar]:
        key = (symbol.upper(), start, end)
        if key in self._cache:
            return self._cache[key]

        params = {
            "symbol": symbol.upper(),
            "from": start.isoformat(),
            "to": end.isoformat(),
            "apikey": self.api_key,
        }
        url = f"{FMP_BASE}/historical-price-eod/full"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            payload = resp.json()

        rows = payload if isinstance(payload, list) else payload.get("historical", [])
        bars = sorted((_parse_bar(r) for r in rows), key=lambda b: b.date)
        self._cache[key] = bars
        return bars


class FixturePriceStore:
    """In-memory / JSON fixture prices for dry-run and tests."""

    def __init__(self, data: dict[str, list[dict]] | None = None, path: Path | None = None):
        if data is None:
            path = path or DEFAULT_FIXTURE
            with Path(path).open(encoding="utf-8") as fh:
                data = json.load(fh)
        self._bars: dict[str, list[Bar]] = {
            sym.upper(): sorted((_parse_bar(r) for r in rows), key=lambda b: b.date)
            for sym, rows in (data or {}).items()
        }

    def get_bars(self, symbol: str, *, start: date, end: date) -> list[Bar]:
        bars = self._bars.get(symbol.upper(), [])
        return [b for b in bars if start <= b.date <= end]


def trading_day_index(bars: list[Bar], after: date) -> int | None:
    """Index of first bar with date > after (next session after T)."""
    for i, bar in enumerate(bars):
        if bar.date > after:
            return i
    return None


def hold_window_bars(
    bars: list[Bar],
    *,
    asof: date,
    hold_n: int,
) -> tuple[Bar, list[Bar], Bar] | None:
    """
    Entry = next session open after asof (T+1 open).
    Hold N trading days; exit at close of day N.

    Day-1 is the entry session itself. So exit bar index = entry_idx + (N - 1).
    Returns (entry_bar, path_bars inclusive, exit_bar) or None if incomplete.
    """
    if hold_n < 1:
        raise ValueError("hold_n must be >= 1")
    entry_idx = trading_day_index(bars, after=asof)
    if entry_idx is None:
        return None
    exit_idx = entry_idx + hold_n - 1
    if exit_idx >= len(bars):
        return None
    path = bars[entry_idx : exit_idx + 1]
    return bars[entry_idx], path, bars[exit_idx]


def synthesize_calendar(
    start: date,
    end: date,
    *,
    skip_weekends: bool = True,
) -> list[date]:
    days: list[date] = []
    d = start
    while d <= end:
        if not skip_weekends or d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def build_synthetic_fixture(
    symbols: list[str],
    *,
    start: date,
    end: date,
    seed: float = 100.0,
) -> dict[str, list[dict]]:
    """Deterministic OHLC series for dry-run demos (not market data)."""
    calendar = synthesize_calendar(start, end)
    out: dict[str, list[dict]] = {}
    for i, sym in enumerate(symbols):
        px = seed * (1.0 + 0.01 * i)
        rows: list[dict] = []
        for j, d in enumerate(calendar):
            # Mild deterministic drift + oscillation
            drift = 1.0 + (0.001 if sym != "SPY" else 0.0005) * ((-1) ** (i + j))
            o = px
            c = px * drift
            h = max(o, c) * 1.01
            l = min(o, c) * 0.99
            rows.append(
                {
                    "date": d.isoformat(),
                    "open": round(o, 4),
                    "high": round(h, 4),
                    "low": round(l, 4),
                    "close": round(c, 4),
                    "volume": 1_000_000,
                }
            )
            px = c
        out[sym.upper()] = rows
    return out
