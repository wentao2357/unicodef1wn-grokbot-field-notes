# Beauty M/V Flip Extract — SUMMARY

- Source files scanned: **24**
- Sheets scanned: **24**
- Total flip rows: **4323**
- Unique tickers: **1409**
- Date range (asof with flips): **2026-08-21 → 2026-09-22** (21 dates)

## Counts by flip type

| flip | count | meaning |
|------|------:|---------|
| M | 3077 | Crowned/共识 → Fading/松动 (short-bias hyp.) |
| V | 1246 | Forgotten/沉寂 → Rising/升温 (long-bias hyp.) |

## Counts by 时段 (当前选美状态持续时间)

| 时段 | M | V | total |
|-----:|--:|--:|------:|
| 1 | 1088 | 499 | 1587 |
| 2 | 1039 | 406 | 1445 |
| 3 | 950 | 341 | 1291 |

## Counts by asof_date

| asof_date | M | V | total |
|-----------|--:|--:|------:|
| 2026-08-21 | 193 | 53 | 246 |
| 2026-08-24 | 189 | 63 | 252 |
| 2026-08-25 | 153 | 57 | 210 |
| 2026-08-26 | 116 | 40 | 156 |
| 2026-08-27 | 124 | 39 | 163 |
| 2026-08-28 | 142 | 41 | 183 |
| 2026-08-31 | 170 | 53 | 223 |
| 2026-09-01 | 184 | 60 | 244 |
| 2026-09-02 | 217 | 51 | 268 |
| 2026-09-03 | 192 | 49 | 241 |
| 2026-09-04 | 160 | 67 | 227 |
| 2026-09-08 | 107 | 84 | 191 |
| 2026-09-09 | 140 | 104 | 244 |
| 2026-09-10 | 177 | 89 | 266 |
| 2026-09-11 | 177 | 60 | 237 |
| 2026-09-15 | 133 | 47 | 180 |
| 2026-09-16 | 132 | 38 | 170 |
| 2026-09-17 | 143 | 37 | 180 |
| 2026-09-18 | 86 | 59 | 145 |
| 2026-09-21 | 75 | 57 | 132 |
| 2026-09-22 | 67 | 98 | 165 |

## Column-missing / skipped files

July 2026 workbooks use legacy **比价** columns (`当前比价状态` / lead·Weakening·Improving·Lag), not **选美** (`Crowned/Fading/Rising/Forgotten`). Skipped for M/V extract:

- `26-07-01 数据总表（趋势识别＋相对比价＋资金监控）（美股市场）.xlsx` — missing: 当前选美状态, 此前选美状态, 当前选美状态持续时间, 选美强度, 选美动量, 当前选美状态涨幅
- `26-07-15 数据总表（趋势识别＋相对比价＋资金监控）（美股市场）.xlsx` — missing: 当前选美状态, 此前选美状态, 当前选美状态持续时间, 选美强度, 选美动量, 当前选美状态涨幅
- `26-07-29 数据总表（趋势识别＋相对比价＋资金监控＋动能）（美股市场）.xlsx` — missing: 当前选美状态, 此前选美状态, 当前选美状态持续时间, 选美强度, 选美动量, 当前选美状态涨幅

## Filter rules applied

- **M**: `当前选美状态` contains Fading/松动 AND `此前选美状态` contains Crowned/共识 AND `当前选美状态持续时间` ∈ {1,2,3}
- **V**: `当前选美状态` contains Rising/升温 AND `此前选美状态` contains Forgotten/沉寂 AND `当前选美状态持续时间` ∈ {1,2,3}
- `时段` column in CSV = `当前选美状态持续时间`
- asof_date from filename prefix `YY-MM-DD` → `20YY-MM-DD`

## Handbook

Do not duplicate. See: `/workspace/zsxq/us-strategies/数据总表使用手册.md`

## Output

- `/workspace/uploads/beauty-mv-backtest/flips.csv` (4323 rows)
