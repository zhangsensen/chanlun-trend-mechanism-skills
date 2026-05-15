# Mechanism Reference

This skill produces current-state structure observations, not action recommendations.

## Structure Priority

1. Background: `1d`, `2d`, `1w`, `2w`.
2. Operating level: `30m`, `60m`, `120m`.
3. Support and pressure ladder: MA20 midline and MA55 structural line.
4. MACD: auxiliary momentum facts only.
5. Condition branches: if a level is recovered or lost, state the next structural observation.

## Preferred Wording

Use:

- "大背景偏多/弱多/转弱"
- "中轨失守"
- "核心观察"
- "下方看 ... 是否守住"
- "上方看 ... 能否收复"
- "如果跌破 ... 下一层观察 ..."
- "MACD动能项只作为结构辅助背景"

Avoid action-oriented wording. The output should be auditable from the JSON fields and should not imply a trade instruction.

## MACD Phrase Rules

- `above_zero`: `{level}MACD位于零轴上方`
- `below_zero`: `{level}MACD位于零轴下方`
- `near_zero`: `{level}MACD贴近零轴`
- `straddles_zero`: `{level}MACD跨零轴`
- `crossed_zero`: `{level}柱体翻轴`
- `expanding + hist > 0`: `{level}柱体正向扩张`
- `expanding + hist < 0`: `{level}柱体负向扩张`
- `shrinking + hist > 0`: `{level}柱体正向收缩`
- `shrinking + hist < 0`: `{level}柱体负向收缩`

Do not add `structure_alignment` unless a future version defines a tested, deterministic mapping.
