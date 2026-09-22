# beauty-bt

Analysis-only CLI for **行知美股 选美** M/V flip backtests.

> Research tool only — **no trade tickets, no auto-execution, no desk order recommendations.**

## Install

```bash
python -m pip install -e ".[dev]"
```

Requires Python 3.10+.

## Data

Place flip events at `data/flips.csv` (a copy ships in this repo), or pass any path via `--input`.

Expected columns:

`asof_date,ticker,name,flip,时段,日级别趋势,当前选美,此前选美,选美强度,选美动量,当前选美状态涨幅`

- **M**: Crowned/共识 → Fading/松动 (short-bias hypothesis)
- **V**: Forgotten/沉寂 → Rising/升温 (long-bias hypothesis)
- **时段**: `当前选美状态持续时间` ∈ {1,2,3} (already filtered in the CSV)

Rules (source of truth): [`docs/SPEC.md`](docs/SPEC.md). Extract summary: [`docs/SUMMARY.md`](docs/SUMMARY.md).

## Usage

### Dry-run / fixture (no API key)

Validates CSV → hold windows → MAE/MFE → SPY excess without live prices:

```bash
beauty-bt flips --input data/flips.csv --hold 5,10,20 --dry-run --limit 50
```

Or use the packaged sample fixture with a mini CSV:

```bash
beauty-bt flips \
  --input tests/fixtures/mini_flips.csv \
  --hold 5,10,20 \
  --fixture beauty_bt/fixtures/sample_prices.json
```

### Live FMP prices

Set `FMP_API_KEY` and call FMP **`/stable/historical-price-eod/full`**:

```bash
export FMP_API_KEY=your_key_here
beauty-bt flips --input data/flips.csv --hold 5,10,20
```

Never hardcode API keys.

## Backtest rules (MVP)

1. Flip day = `asof_date` **T**
2. Entry = **next session open** (T+1 open)
3. Hold **N ∈ {5, 10, 20}** trading days; exit at **close of day N**
4. **M and V run separately** (do not pool signs)
5. Stats: equal-weight + per-ticker; **MAE / MFE**; vs **SPY** over the same window
6. Prefer **时段=1** (primary); also report buckets 1–3 and combined 1–3

Hypothesis-aligned return: **V = long** `(exit/entry - 1)`; **M = short** `-(exit/entry - 1)`.

## Tests

```bash
pytest -q
```

Unit tests cover CSV parse and hold-window math without requiring `FMP_API_KEY`.

## Layout

```
beauty_bt/          # package + CLI
data/flips.csv      # primary flip events (4323 rows)
docs/SPEC.md        # bilingual MVP spec
docs/SUMMARY.md     # extract counts / date range
tests/              # dry-run / unit tests
```

## Phase-2 (out of scope)

Full SQLite ingest of 数据总表 workbooks. MVP works with `flips.csv` alone.
