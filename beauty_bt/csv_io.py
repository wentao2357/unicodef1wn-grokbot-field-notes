"""CSV loader for flips.csv."""

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

from beauty_bt.models import FlipEvent, FlipType

REQUIRED_COLUMNS = {
    "asof_date",
    "ticker",
    "name",
    "flip",
    "时段",
}


def _parse_date(value: str) -> date:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date: {value!r}")


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return float(text)


def load_flips(path: str | Path, *, periods: set[int] | None = None) -> list[FlipEvent]:
    """Load flip events from CSV. Optionally filter by 时段 set."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"flips CSV not found: {path}")

    events: list[FlipEvent] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"Empty CSV: {path}")
        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            raise ValueError(f"CSV missing columns {sorted(missing)}: {path}")

        for row_num, row in enumerate(reader, start=2):
            flip_raw = (row.get("flip") or "").strip().upper()
            if flip_raw not in {"M", "V"}:
                raise ValueError(f"Row {row_num}: invalid flip {flip_raw!r}")
            flip: FlipType = flip_raw  # type: ignore[assignment]

            period = int(str(row["时段"]).strip())
            if periods is not None and period not in periods:
                continue

            events.append(
                FlipEvent(
                    asof_date=_parse_date(row["asof_date"]),
                    ticker=row["ticker"].strip().upper(),
                    name=(row.get("name") or "").strip(),
                    flip=flip,
                    period=period,
                    day_trend=(row.get("日级别趋势") or "").strip(),
                    current_beauty=(row.get("当前选美") or "").strip(),
                    prior_beauty=(row.get("此前选美") or "").strip(),
                    intensity=_parse_float(row.get("选美强度")),
                    momentum=_parse_float(row.get("选美动量")),
                    state_return=_parse_float(row.get("当前选美状态涨幅")),
                )
            )
    return events
