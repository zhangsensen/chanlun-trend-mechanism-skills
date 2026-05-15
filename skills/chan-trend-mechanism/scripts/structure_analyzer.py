"""Deterministic multi-timeframe Chan-style structure analyzer.

The analyzer reads current multi-timeframe OHLCV bars, emits a canonical JSON
structure, and renders Markdown mechanically from that JSON. It intentionally
does not read event-study, bootstrap, walk-forward, rule-status, or other
non-OHLCV artifacts.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pandas as pd


SCHEMA_VERSION = "chanlun_structure_v0.2"
DEFAULT_SYMBOL = "000001.SH"
DEFAULT_NAME = "上证指数"
DEFAULT_DATA_DIR = Path("data/index/derived")
DEFAULT_OUTPUT_DIR = Path("output/chan_states")

TIMEFRAMES = ("5m", "15m", "30m", "60m", "120m", "1d", "2d", "1w", "2w")
BACKGROUND_TIMEFRAMES = ("1d", "2d", "1w", "2w")
OPERATING_TIMEFRAMES = ("30m", "60m", "120m")
LADDER_TIMEFRAMES = ("5m", "15m", "30m", "60m", "120m", "1d", "2d", "1w", "2w")
NEAR_MID_BAND_PCT = 0.2
MACD_TIMEFRAMES = ("1d", "60m", "120m")
MACD_PARAMETERS = {"fast": 12, "slow": 26, "signal": 9}
MACD_REL_TOL = 1e-4
ZERO_AXIS_TOL = 1e-4
MACD_FALLBACK_SUMMARY = "MACD动能项不可用，本轮仅按中轨/55线结构判断。"

ZERO_AXIS_PHRASES = {
    "above_zero": "{label}MACD位于零轴上方",
    "below_zero": "{label}MACD位于零轴下方",
    "near_zero": "{label}MACD贴近零轴",
    "straddles_zero": "{label}MACD跨零轴",
}
HIST_STATE_PHRASES = {
    "crossed_zero": "{label}柱体翻轴",
    "flat": "{label}柱体走平",
}
HIST_DIRECTIONAL_PHRASES = {
    ("expanding", "positive"): "{label}柱体正向扩张",
    ("expanding", "negative"): "{label}柱体负向扩张",
    ("shrinking", "positive"): "{label}柱体正向收缩",
    ("shrinking", "negative"): "{label}柱体负向收缩",
}
CROSS_STATE_PHRASES = {
    "golden_cross_recent": "{label}DIF上穿DEA",
    "dead_cross_recent": "{label}DIF下穿DEA",
}

FORBIDDEN_OUTPUT_TERMS = (
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "胜率",
    "预测",
    "信号",
    "alpha",
    "edge",
    "交易",
)

PERIOD_LABELS = {
    "5m": "5F",
    "15m": "15F",
    "30m": "30F",
    "60m": "60F",
    "120m": "120F",
    "1d": "日线",
    "2d": "双日",
    "1w": "周线",
    "2w": "双周",
}


@dataclass(frozen=True)
class SelectedBar:
    timeframe: str
    dt: pd.Timestamp
    close: float
    ma20: float | None
    ma55: float | None
    ma233: float | None
    prev_ma20: float | None
    macd_dif: float | None = None
    macd_dea: float | None = None
    macd_hist: float | None = None
    prev_macd_dif: float | None = None
    prev_macd_dea: float | None = None
    prev_macd_hist: float | None = None


def parse_as_of(value: str | None) -> pd.Timestamp:
    """Parse CLI as_of; date-only values mean that day's 15:00 closed bar."""
    if value is None:
        return cast(pd.Timestamp, pd.Timestamp.now(tz="Asia/Shanghai").tz_localize(None))
    ts = _checked_timestamp(value, "as_of")
    if " " not in value and "T" not in value:
        ts = ts + pd.Timedelta(hours=15)
    if ts.tzinfo is not None:
        return cast(pd.Timestamp, ts.tz_localize(None))
    return cast(pd.Timestamp, ts)


def _checked_timestamp(value: Any, label: str) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if bool(pd.isna(ts)):
        raise ValueError(f"{label} must be a valid timestamp")
    return cast(pd.Timestamp, ts)


def output_stem(symbol: str, as_of: pd.Timestamp) -> str:
    return f"{symbol}_{as_of.strftime('%Y-%m-%d_%H%M%S')}_structure"


def read_index_name(symbol: str, universe_path: Path = Path("data/index/metadata/index_universe.csv")) -> str:
    if not universe_path.exists():
        return DEFAULT_NAME if symbol == DEFAULT_SYMBOL else symbol
    universe = pd.read_csv(universe_path)
    if {"ts_code", "name"}.issubset(universe.columns):
        matched = universe.loc[universe["ts_code"].eq(symbol), "name"]
        if not matched.empty:
            return str(matched.iloc[0])
    return DEFAULT_NAME if symbol == DEFAULT_SYMBOL else symbol


def _to_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def load_timeframe_bar(
    data_dir: Path,
    symbol: str,
    timeframe: str,
    as_of: pd.Timestamp,
) -> tuple[SelectedBar | None, str | None]:
    path = data_dir / timeframe / f"{symbol}.parquet"
    if not path.exists():
        return None, f"missing_{timeframe}_file"

    df = pd.read_parquet(path).copy()
    if "datetime" in df.columns:
        df["dt"] = pd.to_datetime(df["datetime"])
    elif "trade_date" in df.columns:
        df["dt"] = pd.to_datetime(df["trade_date"]) + pd.Timedelta(hours=15)
    elif "period_end" in df.columns:
        df["dt"] = pd.to_datetime(df["period_end"])
    else:
        return None, f"missing_{timeframe}_datetime"

    if "ma20" not in df.columns and "mid" in df.columns:
        df["ma20"] = df["mid"]
    if "mid" not in df.columns and "ma20" in df.columns:
        df["mid"] = df["ma20"]

    df = df.sort_values("dt").drop_duplicates("dt").reset_index(drop=True)
    closed = df[df["dt"] <= as_of]
    if closed.empty:
        return None, f"no_closed_{timeframe}_bar"

    selected_idx = len(closed) - 1
    row = df.iloc[selected_idx]
    prev = df.iloc[selected_idx - 1] if selected_idx > 0 else None
    return (
        SelectedBar(
            timeframe=timeframe,
            dt=_checked_timestamp(row["dt"], f"{timeframe}_dt"),
            close=float(row["close"]),
            ma20=_to_float(row.get("ma20")),
            ma55=_to_float(row.get("ma55")),
            ma233=_to_float(row.get("ma233")),
            prev_ma20=_to_float(prev.get("ma20")) if prev is not None else None,
            macd_dif=_to_float(row.get("macd_dif")),
            macd_dea=_to_float(row.get("macd_dea")),
            macd_hist=_to_float(row.get("macd_hist")),
            prev_macd_dif=_to_float(prev.get("macd_dif")) if prev is not None else None,
            prev_macd_dea=_to_float(prev.get("macd_dea")) if prev is not None else None,
            prev_macd_hist=_to_float(prev.get("macd_hist")) if prev is not None else None,
        ),
        None,
    )


def line_distance_pct(close: float, value: float | None) -> float | None:
    if value is None or value == 0:
        return None
    return (close / value - 1.0) * 100.0


def relation_to_line(close: float, value: float | None) -> str:
    distance = line_distance_pct(close, value)
    if distance is None:
        return "unknown"
    if abs(distance) <= NEAR_MID_BAND_PCT:
        return "near"
    assert value is not None
    if close > float(value):
        return "above"
    if close < float(value):
        return "below"
    return "near"


def reason_codes_for_bar(bar: SelectedBar) -> list[str]:
    codes: list[str] = []
    relation = relation_to_line(bar.close, bar.ma20)
    if relation == "above":
        codes.append("close_above_ma20")
    elif relation == "below":
        codes.append("close_below_ma20")
    elif relation == "near":
        codes.append("near_ma20")
        if bar.ma20 is not None and bar.close >= bar.ma20:
            codes.append("close_above_or_equal_ma20")
        elif bar.ma20 is not None:
            codes.append("close_below_ma20")
    else:
        codes.append("ma20_missing")

    if bar.ma20 is None or bar.ma55 is None:
        codes.append("ma55_or_ma20_missing")
    elif bar.ma20 > bar.ma55:
        codes.append("ma20_above_ma55")
    else:
        codes.append("ma20_not_above_ma55")

    if bar.prev_ma20 is not None and bar.ma20 is not None:
        if bar.ma20 > bar.prev_ma20:
            codes.append("ma20_slope_up")
        elif bar.ma20 < bar.prev_ma20:
            codes.append("ma20_slope_down")
        else:
            codes.append("ma20_slope_flat")

    if (
        bar.ma20 is not None
        and bar.ma55 is not None
        and bar.ma233 is not None
        and bar.close > bar.ma20 > bar.ma55 > bar.ma233
    ):
        codes.append("ma_full_bull_align")

    return codes


def classify_background_bar(bar: SelectedBar | None) -> dict[str, Any]:
    if bar is None:
        return {
            "timeframe": "",
            "label": "",
            "state": "不确定",
            "reason_codes": ["data_incomplete"],
        }

    codes = reason_codes_for_bar(bar)
    if bar.ma20 is None or bar.ma55 is None:
        state = "不确定"
        codes.append("data_incomplete")
    elif bar.close >= bar.ma20 and bar.ma20 > bar.ma55:
        state = "偏多"
    elif bar.close >= bar.ma20:
        state = "弱多"
    else:
        state = "转弱"

    return {
        "timeframe": bar.timeframe,
        "label": PERIOD_LABELS[bar.timeframe],
        "state": state,
        "close": round(bar.close, 3),
        "ma20": round(bar.ma20, 3) if bar.ma20 is not None else None,
        "ma55": round(bar.ma55, 3) if bar.ma55 is not None else None,
        "close_vs_ma20_pct": _rounded_distance(bar.close, bar.ma20),
        "reason_codes": sorted(set(codes)),
    }


def _rounded_distance(close: float, value: float | None) -> float | None:
    distance = line_distance_pct(close, value)
    return round(distance, 3) if distance is not None else None


def classify_overall_background(states: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [item for item in states if item.get("state") != "不确定"]
    if not valid:
        return {"state": "不确定", "reason_codes": ["background_data_missing"]}

    counts = {state: sum(1 for item in valid if item["state"] == state) for state in ("偏多", "弱多", "转弱")}
    if counts["偏多"] >= 2 and states[0].get("state") in {"偏多", "弱多"}:
        state = "偏多"
    elif counts["转弱"] >= 2 or states[0].get("state") == "转弱":
        state = "转弱"
    elif counts["偏多"] + counts["弱多"] >= 2:
        state = "弱多"
    else:
        state = "不确定"

    codes = [f"{item['timeframe']}_{item['state']}" for item in valid]
    return {"state": state, "reason_codes": codes}


def build_timeframe_snapshot(bars: dict[str, SelectedBar | None]) -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    for timeframe in TIMEFRAMES:
        bar = bars.get(timeframe)
        if bar is None:
            snapshot[timeframe] = {
                "label": PERIOD_LABELS[timeframe],
                "available": False,
                "reason_codes": ["data_incomplete"],
            }
            continue
        snapshot[timeframe] = {
            "label": PERIOD_LABELS[timeframe],
            "available": True,
            "dt": bar.dt.strftime("%Y-%m-%d %H:%M:%S"),
            "close": round(bar.close, 3),
            "ma20": round(bar.ma20, 3) if bar.ma20 is not None else None,
            "ma55": round(bar.ma55, 3) if bar.ma55 is not None else None,
            "ma233": round(bar.ma233, 3) if bar.ma233 is not None else None,
            "close_vs_ma20_pct": _rounded_distance(bar.close, bar.ma20),
            "close_vs_ma55_pct": _rounded_distance(bar.close, bar.ma55),
            "relation_to_ma20": relation_to_line(bar.close, bar.ma20),
            "reason_codes": sorted(set(reason_codes_for_bar(bar))),
        }
    return snapshot


def next_higher_timeframe(timeframe: str) -> str | None:
    if timeframe not in LADDER_TIMEFRAMES:
        return None
    idx = LADDER_TIMEFRAMES.index(timeframe)
    if idx + 1 >= len(LADDER_TIMEFRAMES):
        return None
    return LADDER_TIMEFRAMES[idx + 1]


def classify_operating_level(
    bars: dict[str, SelectedBar | None],
    background_state: str,
) -> dict[str, Any]:
    broken = [
        timeframe
        for timeframe in OPERATING_TIMEFRAMES
        if (bar := bars.get(timeframe)) is not None
        and bar.ma20 is not None
        and bar.close < bar.ma20
    ]
    near = [
        timeframe
        for timeframe in OPERATING_TIMEFRAMES
        if (bar := bars.get(timeframe)) is not None
        and relation_to_line(bar.close, bar.ma20) == "near"
    ]

    reason_codes: list[str] = []
    if near:
        reason_codes.extend([f"near_{item}_ma20" for item in near])

    if not broken:
        level = "30m"
        watch = "30m"
        status = "主涨段观察" if background_state in {"偏多", "弱多"} else "关键支撑观察"
        reason_codes.append("operating_midlines_not_broken")
    else:
        break_level = broken[-1]
        watch = next_higher_timeframe(break_level) or break_level
        level = watch
        reason_codes.append(f"close_below_{break_level}_ma20")
        if break_level == "30m":
            status = "X段候选" if background_state in {"偏多", "弱多"} else "关键支撑观察"
        elif break_level == "60m":
            status = "回踩级别升级"
        elif break_level == "120m":
            status = "关键支撑观察"
        else:
            status = "不确定"

    daily = bars.get("1d")
    if daily is not None and daily.ma20 is not None and daily.close < daily.ma20:
        status = "结构转弱观察"
        reason_codes.append("close_below_1d_ma20")

    return {
        "primary_level": level,
        "primary_label": PERIOD_LABELS[level],
        "watch_level": watch,
        "watch_label": PERIOD_LABELS[watch],
        "status": status,
        "broken_levels": broken,
        "near_levels": near,
        "reason_codes": sorted(set(reason_codes)),
    }


def build_support_ladder(bars: dict[str, SelectedBar | None]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for timeframe in LADDER_TIMEFRAMES:
        bar = bars.get(timeframe)
        if bar is None:
            rows.append(
                {
                    "timeframe": timeframe,
                    "label": PERIOD_LABELS[timeframe],
                    "available": False,
                    "reason_codes": ["data_incomplete"],
                }
            )
            continue
        for line_name, value in (("MA20", bar.ma20), ("MA55", bar.ma55)):
            distance = line_distance_pct(bar.close, value)
            if value is None or distance is None:
                rows.append(
                    {
                        "timeframe": timeframe,
                        "label": f"{PERIOD_LABELS[timeframe]}{line_name}",
                        "line": line_name,
                        "available": False,
                        "reason_codes": [f"{line_name.lower()}_missing"],
                    }
                )
                continue
            relation = relation_to_line(bar.close, value)
            if relation == "near":
                side = "贴线"
            elif bar.close > value:
                side = "下方支撑"
            else:
                side = "上方压力"
            rows.append(
                {
                    "timeframe": timeframe,
                    "label": f"{PERIOD_LABELS[timeframe]}{line_name}",
                    "line": line_name,
                    "available": True,
                    "value": round(value, 3),
                    "distance_pct": round(distance, 3),
                    "side": side,
                    "relation": relation,
                    "reason_codes": [f"{relation}_{timeframe}_{line_name.lower()}"],
                }
            )
    return rows


def build_conditional_tree(
    bars: dict[str, SelectedBar | None],
    operating: dict[str, Any],
) -> list[dict[str, Any]]:
    tree: list[dict[str, Any]] = []
    broken = operating.get("broken_levels") or []
    break_level = broken[-1] if broken else None
    watch_level = str(operating["watch_level"])

    if break_level:
        tree.append(
            {
                "condition": f"如果重新收复{PERIOD_LABELS[break_level]}中轨",
                "structure_rewrite": f"{PERIOD_LABELS[break_level]}回踩解除，重新观察{PERIOD_LABELS[watch_level]}主干恢复",
                "reason_codes": [f"recapture_{break_level}_ma20"],
            }
        )
    else:
        tree.append(
            {
                "condition": f"如果继续守住{PERIOD_LABELS[watch_level]}中轨",
                "structure_rewrite": f"{PERIOD_LABELS[watch_level]}主干维持，低级别只按正常回踩处理",
                "reason_codes": [f"hold_{watch_level}_ma20"],
            }
        )

    next_level = next_higher_timeframe(watch_level)
    if next_level:
        tree.append(
            {
                "condition": f"如果跌破{PERIOD_LABELS[watch_level]}中轨",
                "structure_rewrite": f"回踩级别上移，下一层观察{PERIOD_LABELS[next_level]}中轨",
                "reason_codes": [f"break_{watch_level}_ma20", f"watch_{next_level}_ma20"],
            }
        )

    if bars.get("1d") is not None:
        tree.append(
            {
                "condition": "如果跌破日线中轨",
                "structure_rewrite": "大级别背景转入结构转弱观察",
                "reason_codes": ["break_1d_ma20"],
            }
        )
    return tree


def structure_clarity(
    bars: dict[str, SelectedBar | None],
    operating: dict[str, Any],
    warnings: list[str],
) -> str:
    required_missing = any(bars.get(tf) is None for tf in ("60m", "120m", "1d"))
    if required_missing:
        return "low"
    if warnings:
        return "medium"
    if operating.get("near_levels"):
        return "medium"
    if any(
        relation_to_line(bar.close, bar.ma20) == "near"
        for bar in bars.values()
        if bar is not None
    ):
        return "medium"
    return "high"


def build_summary(
    background: dict[str, Any],
    operating: dict[str, Any],
) -> str:
    state = background["overall"]["state"]
    status = operating["status"]
    watch_label = operating["watch_label"]
    broken = operating.get("broken_levels") or []
    if broken:
        broken_label = PERIOD_LABELS[broken[-1]]
        return f"{state}背景下，{broken_label}中轨已失守，当前按{status}处理，核心观察{watch_label}中轨。"
    return f"{state}背景下，操作级别中轨未出现明确失守，当前按{status}处理，核心观察{watch_label}中轨。"


def posture_for_description(background: dict[str, Any], operating: dict[str, Any]) -> str:
    background_state = str(background["overall"]["state"])
    status = str(operating["status"])
    broken = operating.get("broken_levels") or []
    if background_state == "转弱" or status == "结构转弱观察":
        return "偏防守"
    if not broken and background_state in {"偏多", "弱多"}:
        return "偏进攻"
    return "中性观察"


def _ladder_line_value(
    ladder: list[dict[str, Any]],
    timeframe: str,
    line: str = "MA20",
) -> float | None:
    label = f"{PERIOD_LABELS[timeframe]}{line}"
    for row in ladder:
        if row.get("timeframe") == timeframe and row.get("line") == line:
            value = row.get("value")
            return float(value) if value is not None else None
        if row.get("label") == label:
            value = row.get("value")
            return float(value) if value is not None else None
    return None


def _line_text(timeframe: str, value: float | None) -> str:
    suffix = f"{value:.3f}" if value is not None else "未知"
    return f"{PERIOD_LABELS[timeframe]}中轨{suffix}"


def build_current_state_description(
    result: dict[str, Any],
) -> dict[str, Any]:
    background = result["background"]
    operating = result["operating_level"]
    ladder = result["support_ladder"]
    macd_summary = result.get("momentum_context", {}).get("macd", {}).get("summary", MACD_FALLBACK_SUMMARY)

    background_state = str(background["overall"]["state"])
    status = str(operating["status"])
    watch_level = str(operating["watch_level"])
    watch_text = _line_text(watch_level, _ladder_line_value(ladder, watch_level))
    broken = operating.get("broken_levels") or []
    posture = posture_for_description(background, operating)
    name = str(result["name"])

    paragraphs: list[str] = []
    if broken:
        break_level = str(broken[-1])
        break_text = _line_text(break_level, _ladder_line_value(ladder, break_level))
        paragraphs.append(
            f"当前状态：{name}大背景是{background_state}，{PERIOD_LABELS[break_level]}中轨已经失守，"
            f"当前按{status}处理，核心观察{PERIOD_LABELS[watch_level]}中轨。"
        )
        paragraphs.append(
            f"观察重点：下方看{watch_text}是否守住；上方看{break_text}能否收复。"
        )
    else:
        paragraphs.append(
            f"当前状态：{name}大背景是{background_state}，操作级别中轨未出现明确失守，"
            f"当前按{status}处理，核心观察{PERIOD_LABELS[watch_level]}中轨。"
        )
        paragraphs.append(f"观察重点：继续看{watch_text}是否守住。")

    next_level = next_higher_timeframe(watch_level)
    if next_level:
        next_text = _line_text(next_level, _ladder_line_value(ladder, next_level))
        paragraphs.append(f"下方条件：如果跌破{watch_text}，下一层观察{next_text}。")
    else:
        paragraphs.append(f"下方条件：如果跌破{watch_text}，结构需要重新评估。")

    momentum_text = macd_summary.removeprefix("动能项可用：")
    paragraphs.append(f"动能项辅助看：{momentum_text}")

    return {
        "posture": posture,
        "paragraphs": paragraphs,
        "reason_codes": list(operating.get("reason_codes", [])),
    }


def _macd_fields_available(bar: SelectedBar | None) -> bool:
    if bar is None:
        return False
    return all(
        value is not None
        for value in (bar.macd_dif, bar.macd_dea, bar.macd_hist)
    )


def _rel_close(value: float, reference: float) -> float:
    return abs(value) / max(abs(reference), 1.0)


def classify_macd_cross_state(bar: SelectedBar) -> str:
    prev_macd_dif = bar.prev_macd_dif
    prev_macd_dea = bar.prev_macd_dea
    macd_dif = bar.macd_dif
    macd_dea = bar.macd_dea
    if (
        prev_macd_dif is None
        or prev_macd_dea is None
        or macd_dif is None
        or macd_dea is None
    ):
        return "unknown"
    prev_dif = float(prev_macd_dif)
    prev_dea = float(prev_macd_dea)
    dif = float(macd_dif)
    dea = float(macd_dea)
    if abs(dif - dea) / max(abs(dea), 1.0) < MACD_REL_TOL:
        return "flat"
    if prev_dif <= prev_dea and dif > dea:
        return "golden_cross_recent"
    if prev_dif >= prev_dea and dif < dea:
        return "dead_cross_recent"
    if dif > dea:
        return "dif_above_dea"
    if dif < dea:
        return "dif_below_dea"
    return "flat"


def classify_macd_zero_axis_state(bar: SelectedBar) -> str:
    if bar.macd_dif is None or bar.macd_dea is None:
        return "unknown"
    dif = float(bar.macd_dif)
    dea = float(bar.macd_dea)
    if max(_rel_close(dif, bar.close), _rel_close(dea, bar.close)) < ZERO_AXIS_TOL:
        return "near_zero"
    if dif > 0 and dea > 0:
        return "above_zero"
    if dif < 0 and dea < 0:
        return "below_zero"
    if (dif > 0 > dea) or (dea > 0 > dif):
        return "straddles_zero"
    return "near_zero"


def classify_macd_hist_state(bar: SelectedBar) -> str:
    if bar.prev_macd_hist is None or bar.macd_hist is None:
        return "unknown"
    prev_hist = float(bar.prev_macd_hist)
    hist = float(bar.macd_hist)
    if abs(hist - prev_hist) / max(abs(prev_hist), 1.0) < MACD_REL_TOL:
        return "flat"
    if (prev_hist < 0 < hist) or (prev_hist > 0 > hist):
        return "crossed_zero"
    if abs(hist) > abs(prev_hist):
        return "expanding"
    if abs(hist) < abs(prev_hist):
        return "shrinking"
    return "flat"


def classify_macd_timeframe(
    timeframe: str,
    bar: SelectedBar | None,
) -> dict[str, Any]:
    label = PERIOD_LABELS[timeframe]
    if not _macd_fields_available(bar):
        return {
            "available": False,
            "label": label,
            "reason_codes": [f"missing_{timeframe}_macd"],
        }
    assert bar is not None
    assert bar.macd_dif is not None
    assert bar.macd_dea is not None
    assert bar.macd_hist is not None
    return {
        "available": True,
        "label": label,
        "dif": round(float(bar.macd_dif), 6),
        "dea": round(float(bar.macd_dea), 6),
        "hist": round(float(bar.macd_hist), 6),
        "cross_state": classify_macd_cross_state(bar),
        "zero_axis_state": classify_macd_zero_axis_state(bar),
        "hist_state": classify_macd_hist_state(bar),
        "reason_codes": [f"{timeframe}_macd_available"],
    }


def build_macd_summary(timeframes: dict[str, dict[str, Any]]) -> str:
    phrases: list[str] = []
    for timeframe in MACD_TIMEFRAMES:
        item = timeframes.get(timeframe, {})
        if not item.get("available"):
            continue
        label = str(item.get("label") or PERIOD_LABELS[timeframe])
        zero_phrase = ZERO_AXIS_PHRASES.get(str(item.get("zero_axis_state")))
        if zero_phrase:
            phrases.append(zero_phrase.format(label=label))
        if len(phrases) >= 6:
            return "动能项可用：" + "，".join(phrases) + "，当前只作为结构辅助背景。"
        hist_phrase = macd_hist_phrase(item, label)
        if hist_phrase:
            phrases.append(hist_phrase)
        if len(phrases) >= 6:
            return "动能项可用：" + "，".join(phrases) + "，当前只作为结构辅助背景。"
        cross_phrase = CROSS_STATE_PHRASES.get(str(item.get("cross_state")))
        if cross_phrase:
            phrases.append(cross_phrase.format(label=label))
        if len(phrases) >= 6:
            return "动能项可用：" + "，".join(phrases) + "，当前只作为结构辅助背景。"

    if not phrases:
        return MACD_FALLBACK_SUMMARY
    return "动能项可用：" + "，".join(phrases) + "，当前只作为结构辅助背景。"


def macd_hist_phrase(item: dict[str, Any], label: str) -> str | None:
    hist_state = str(item.get("hist_state"))
    phrase_template = HIST_STATE_PHRASES.get(hist_state)
    if phrase_template:
        return phrase_template.format(label=label)
    if hist_state not in {"expanding", "shrinking"}:
        return None
    hist = item.get("hist")
    if hist is None:
        return None
    direction = "positive" if float(hist) >= 0 else "negative"
    directional_template = HIST_DIRECTIONAL_PHRASES.get((hist_state, direction))
    if directional_template is None:
        return None
    return directional_template.format(label=label)


def build_macd_context(bars: dict[str, SelectedBar | None]) -> dict[str, Any]:
    timeframes = {
        timeframe: classify_macd_timeframe(timeframe, bars.get(timeframe))
        for timeframe in MACD_TIMEFRAMES
    }
    enabled = any(item.get("available") for item in timeframes.values())
    return {
        "enabled": enabled,
        "parameters": dict(MACD_PARAMETERS),
        "timeframes": timeframes,
        "summary": build_macd_summary(timeframes),
    }


def unknowns_for_policy(
    bars: dict[str, SelectedBar | None],
    macd_context: dict[str, Any] | None = None,
) -> list[str]:
    unknowns: list[str] = []
    if macd_context is None or not macd_context.get("enabled", False):
        unknowns.append(MACD_FALLBACK_SUMMARY)
    if bars.get("5m") is None or bars.get("15m") is None:
        unknowns.append("低级别触发数据不完整，5F/15F 只作缺省处理。")
    return unknowns


def analyze_structure(
    symbol: str,
    as_of: pd.Timestamp,
    data_dir: Path = DEFAULT_DATA_DIR,
    name: str | None = None,
) -> dict[str, Any]:
    resolved_name = name or read_index_name(symbol)
    bars: dict[str, SelectedBar | None] = {}
    warnings: list[str] = []
    for timeframe in TIMEFRAMES:
        bar, warning = load_timeframe_bar(data_dir, symbol, timeframe, as_of)
        bars[timeframe] = bar
        if warning:
            warnings.append(warning)

    background_states = [
        classify_background_bar(bars.get(timeframe)) for timeframe in BACKGROUND_TIMEFRAMES
    ]
    background = {
        "overall": classify_overall_background(background_states),
        "timeframes": background_states,
    }
    operating = classify_operating_level(bars, str(background["overall"]["state"]))
    ladder = build_support_ladder(bars)
    tree = build_conditional_tree(bars, operating)
    snapshot = build_timeframe_snapshot(bars)
    momentum_context = {"macd": build_macd_context(bars)}
    unknowns = unknowns_for_policy(bars, momentum_context["macd"])
    clarity = structure_clarity(bars, operating, warnings)

    result = {
        "schema_version": SCHEMA_VERSION,
        "symbol": symbol,
        "name": resolved_name,
        "as_of": as_of.strftime("%Y-%m-%d %H:%M:%S"),
        "data_policy": {
            "bar_policy": "closed_bar_only",
            "uses_backtest": False,
            "uses_macd": True,
            "macd_role": "auxiliary_momentum_context",
            "json_is_canonical": True,
            "markdown_render": "deterministic_template",
        },
        "data_quality": {
            "available_timeframes": [tf for tf, bar in bars.items() if bar is not None],
            "missing_timeframes": [tf for tf, bar in bars.items() if bar is None],
            "warnings": warnings,
        },
        "timeframes": snapshot,
        "background": background,
        "operating_level": operating,
        "momentum_context": momentum_context,
        "support_ladder": ladder,
        "conditional_tree": tree,
        "structure_summary": build_summary(background, operating),
        "unknowns": unknowns,
        "structure_clarity": clarity,
    }
    result["current_state_description"] = build_current_state_description(result)
    validate_output_contract(result)
    return result


def validate_output_contract(result: dict[str, Any]) -> None:
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("schema_version mismatch")
    policy = result.get("data_policy", {})
    if policy.get("uses_backtest") is not False:
        raise ValueError("Analyzer output must not use backtest artifacts")
    if policy.get("uses_macd") is not True:
        raise ValueError("Analyzer v0.2 must expose MACD auxiliary context")
    if policy.get("macd_role") != "auxiliary_momentum_context":
        raise ValueError("MACD role must remain auxiliary momentum context")
    if "momentum_context" not in result:
        raise ValueError("Missing momentum_context")
    if policy.get("bar_policy") != "closed_bar_only":
        raise ValueError("P0 analyzer must use closed bars only")
    if result.get("structure_clarity") not in {"high", "medium", "low"}:
        raise ValueError("Invalid structure_clarity")
    serialized_momentum = json.dumps(
        result.get("momentum_context", {}),
        ensure_ascii=False,
        sort_keys=True,
    )
    if "structure_alignment" in serialized_momentum:
        raise ValueError("P1b must not output structure_alignment")

    def visit(value: Any) -> list[str]:
        strings: list[str] = []
        if isinstance(value, dict):
            for nested in value.values():
                strings.extend(visit(nested))
        elif isinstance(value, list):
            for nested in value:
                strings.extend(visit(nested))
        elif isinstance(value, str):
            strings.append(value)
        return strings

    text = "\n".join(visit(result))
    found = [term for term in FORBIDDEN_OUTPUT_TERMS if term in text]
    if found:
        raise ValueError(f"Forbidden output terms found: {found}")


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        f"# {result['name']} 缠论结构分析",
        "",
        f"- 标的: `{result['symbol']}`",
        f"- 时间: `{result['as_of']}`",
        f"- 结构清晰度: `{result['structure_clarity']}`",
        "- 数据口径: 已完成K线；JSON 为 canonical；本 MD 为模板渲染。",
        "",
        "## 大级别背景",
        "",
        "| 周期 | 状态 | 收盘 | 中轨 | 55线 | 距中轨 | reason_codes |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in result["background"]["timeframes"]:
        lines.append(
            f"| {item.get('label', '')} | {item.get('state', '不确定')} | "
            f"{_fmt_num(item.get('close'))} | {_fmt_num(item.get('ma20'))} | "
            f"{_fmt_num(item.get('ma55'))} | {_fmt_pct(item.get('close_vs_ma20_pct'))} | "
            f"{', '.join(item.get('reason_codes', []))} |"
        )

    current_description = result.get("current_state_description", {})
    lines.extend(
        [
            "",
            "## 当前状态描述",
            "",
            f"- 当前状态: `{current_description.get('posture', '不确定')}`",
        ]
    )
    for paragraph in current_description.get("paragraphs", []):
        lines.append(f"- {paragraph}")

    op = result["operating_level"]
    lines.extend(
        [
            "",
            "## 当前操作级别",
            "",
            f"- 主观察级别: `{op['primary_label']}`",
            f"- 结构状态: `{op['status']}`",
            f"- 观察中轨: `{op['watch_label']}`",
            f"- reason_codes: `{', '.join(op.get('reason_codes', []))}`",
            "",
            "## 支撑阶梯",
            "",
            "| 级别 | 线 | 位置 | 距离 | 状态 | reason_codes |",
            "| --- | --- | ---: | ---: | --- | --- |",
        ]
    )
    for row in result["support_ladder"]:
        if not row.get("available", False):
            continue
        if row.get("line") not in {"MA20", "MA55"}:
            continue
        lines.append(
            f"| {row['label']} | {row['line']} | {_fmt_num(row.get('value'))} | "
            f"{_fmt_pct(row.get('distance_pct'))} | {row.get('side', '')} | "
            f"{', '.join(row.get('reason_codes', []))} |"
        )

    lines.extend(["", "## 条件树", ""])
    for branch in result["conditional_tree"]:
        lines.append(
            f"- {branch['condition']}: {branch['structure_rewrite']} "
            f"(`{', '.join(branch.get('reason_codes', []))}`)"
        )

    lines.extend(
        [
            "",
            "## 动能辅助",
            "",
            f"- {result.get('momentum_context', {}).get('macd', {}).get('summary', MACD_FALLBACK_SUMMARY)}",
            "",
            "## 结构结论",
            "",
            f"- {result['structure_summary']}",
            "",
            "## 不确定项",
            "",
        ]
    )
    for item in result["unknowns"]:
        lines.append(f"- {item}")

    markdown = "\n".join(lines) + "\n"
    found = [term for term in FORBIDDEN_OUTPUT_TERMS if term in markdown]
    if found:
        raise ValueError(f"Forbidden Markdown terms found: {found}")
    return markdown


def _fmt_num(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{float(value):.3f}"


def _fmt_pct(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{float(value):.3f}%"


def write_outputs(result: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = output_stem(result["symbol"], _checked_timestamp(result["as_of"], "result_as_of"))
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    json_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_markdown(result), encoding="utf-8")
    return json_path, md_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL)
    parser.add_argument("--name")
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    as_of = parse_as_of(args.as_of)
    result = analyze_structure(
        symbol=args.symbol,
        as_of=as_of,
        data_dir=args.data_dir,
        name=args.name,
    )
    json_path, md_path = write_outputs(result, args.output_dir)
    print(f"json={json_path}")
    print(f"md={md_path}")
    print(f"structure_clarity={result['structure_clarity']}")
    print(f"operating_status={result['operating_level']['status']}")


if __name__ == "__main__":
    main()
