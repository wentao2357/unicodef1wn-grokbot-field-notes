"""Shared dataclasses for flip events and trade results."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

FlipType = Literal["M", "V"]


@dataclass(frozen=True)
class FlipEvent:
    asof_date: date
    ticker: str
    name: str
    flip: FlipType
    period: int  # 时段 = 当前选美状态持续时间
    day_trend: str = ""
    current_beauty: str = ""
    prior_beauty: str = ""
    intensity: float | None = None
    momentum: float | None = None
    state_return: float | None = None


@dataclass(frozen=True)
class Bar:
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class TradeResult:
    flip: FlipEvent
    hold_n: int
    entry_date: date
    exit_date: date
    entry_open: float
    exit_close: float
    # Hypothesis-aligned return: short for M, long for V
    hyp_return: float
    # Raw long return over the window (exit/entry - 1)
    long_return: float
    mae: float
    mfe: float
    spy_long_return: float | None
    excess_vs_spy: float | None
    incomplete: bool = False
    skip_reason: str | None = None


@dataclass
class AggregateStats:
    label: str
    n: int
    mean_hyp: float
    median_hyp: float
    win_rate: float
    mean_mae: float
    mean_mfe: float
    mean_spy: float | None
    mean_excess: float | None
    tickers: dict[str, float] = field(default_factory=dict)
