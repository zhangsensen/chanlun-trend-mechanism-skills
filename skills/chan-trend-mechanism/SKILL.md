---
name: chan-trend-mechanism
description: Use when analyzing A-share or index OHLCV data with multi-timeframe Chan-style structure, support/pressure ladders, MACD auxiliary context, current-state observations, or deterministic condition branches without action language.
---

# Chan Trend Mechanism

## Overview

Use this skill to turn local, closed-bar OHLCV parquet data into a deterministic multi-timeframe structure reading. The skill describes current structure only: background, operating level, support/pressure ladder, auxiliary MACD context, and if/then condition branches.

## Hard Boundaries

- Do not use private commentary sources, scraping interfaces, session files, credentials, screenshots, or exported posts.
- Do not use action language such as buy, sell, add, reduce, signal, alpha, or edge in generated conclusions.
- Do not let MACD or any indicator override the structural posture. MACD is only auxiliary momentum context.
- Do not infer unavailable bars. Emit missing-data warnings and keep the conclusion narrower.

## Workflow

1. Inspect the user's available data path and symbol universe.
2. If MACD columns are missing and the user wants momentum context, run `scripts/macd_enrichment.py`.
3. For one symbol, run `scripts/structure_analyzer.py`.
4. For multiple indices or symbols, run `scripts/panel.py`.
5. Use the JSON as canonical; treat Markdown as deterministic presentation.

Example commands, replacing the skill directory with the actual local path:

```bash
python skills/chan-trend-mechanism/scripts/macd_enrichment.py \
  --data-dir data/index/derived \
  --timeframes 1d 60m 120m

python skills/chan-trend-mechanism/scripts/structure_analyzer.py \
  --symbol 000001.SH \
  --name 上证指数 \
  --as-of "2026-05-15 15:00:00" \
  --data-dir data/index/derived \
  --output-dir output/chan_states

python skills/chan-trend-mechanism/scripts/panel.py \
  --symbols 000001.SH 399001.SZ 399006.SZ 000688.SH \
  --as-of "2026-05-15 15:00:00" \
  --data-dir data/index/derived \
  --output-dir output/chan_panel
```

## Output Contract

The analyzer emits `chanlun_structure_v0.2` JSON with these core sections:

- `background`: daily and weekly style context from `1d`, `2d`, `1w`, `2w`.
- `operating_level`: current operating structure from `30m`, `60m`, `120m`.
- `support_ladder`: MA20/MA55 support and pressure across all configured timeframes.
- `momentum_context.macd`: fixed 12/26/9 MACD facts for `1d`, `60m`, `120m`.
- `conditional_tree`: mechanical condition branches.
- `current_state_description`: short current-state paragraphs for human reading.

## Interpretation Rules

- Use `1d/2d/1w/2w` to describe background.
- Use `30m/60m/120m` to locate the operating level.
- Use MA20 as the midline and MA55 as the next structural line.
- Use MACD phrases only as mechanical facts: zero-axis location, DIF/DEA cross, histogram expansion/shrinkage/flip.
- Prefer "current observation", "condition", "support", "pressure", "structure improves", and "structure weakens" over any action-oriented wording.

## References

- Read `references/data_schema.md` when adapting external data into the expected parquet layout.
- Read `references/mechanism.md` when writing or reviewing conclusions from the JSON output.
