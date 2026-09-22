# SPEC — Beauty M/V Flip Backtest (Cloud Agent MVP)

中英对照短规格 / Bilingual short spec for Cursor cloud-agent.

## Purpose / 目的

Analysis tool only. **Do NOT invent trades for the desk.**  
仅作回测分析工具，**不得为交易台编造下单建议**。

MVP works off `flips.csv` only. Full SQLite ingest of 数据总表 is **phase-2** (out of scope for this MVP).  
MVP 仅依赖 `flips.csv`；完整 SQLite 入库为二期。

Handbook (do not duplicate): `/workspace/zsxq/us-strategies/数据总表使用手册.md`

## Flip definitions / 翻转定义

| flip | Transition | Bias hypothesis |
|------|------------|-----------------|
| **M** | Crowned/共识 → Fading/松动 | Short bias（共识松动） |
| **V** | Forgotten/沉寂 → Rising/升温 | Long bias（沉寂升温） |

Filter: `当前选美状态持续时间` (`时段`) ∈ {1,2,3}. Prefer `时段=1`; also report 1–3 buckets.

## Backtest rules MVP / 回测规则

1. Flip day = `asof_date` **T** from `flips.csv`.
2. Entry: **next session open** (T+1 open) via FMP historical EOD (`/stable` historical-price-eod).
3. Hold **N ∈ {5, 10, 20}** trading days; exit at **close of day N**.
4. Report **MAE / MFE** (max adverse / favorable excursion) while in trade.
5. Run **M and V separately** (do not pool signs).
6. Stats: equal-weight portfolio + per-ticker; benchmark vs **SPY** over the same hold window.
7. Prefer subset `时段=1`; also break out / report `时段` 1–3.

## CLI / 命令行

```bash
beauty-bt flips --input flips.csv --hold 5,10,20
```

- Price source: FMP **`/stable`** `historical-price-eod`
- Auth: env `FMP_API_KEY`
- Do not hardcode keys. Do not call live FMP in this input-prep step.

## Inputs / 输入

- Primary: `/workspace/uploads/beauty-mv-backtest/flips.csv`
- Columns: `asof_date,ticker,name,flip,时段,日级别趋势,当前选美,此前选美,选美强度,选美动量,当前选美状态涨幅`

## Phase-2 note / 二期备注

Minimal ingest later: full SQLite ingest of all 数据总表 workbooks is phase-2. MVP must succeed with `flips.csv` alone.

## Safety / 安全

- Analysis / research only — not trade recommendations.
- No desk order tickets, no auto-execution.
