"""Batch panel renderer for Chan-style structure outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from structure_analyzer import (
    DEFAULT_DATA_DIR,
    DEFAULT_SYMBOL,
    FORBIDDEN_OUTPUT_TERMS,
    MACD_FALLBACK_SUMMARY,
    analyze_structure,
    parse_as_of,
    write_outputs,
)

PANEL_SCHEMA_VERSION = "chanlun_panel_v0.1"
DEFAULT_OUTPUT_DIR = Path("output/chan_panel")


def _split_values(values: Iterable[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    parsed: list[str] = []
    for value in values:
        parsed.extend(item.strip() for item in value.split(",") if item.strip())
    return tuple(parsed)


def parse_name_map(values: Iterable[str] | None) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for value in values or ():
        if "=" not in value:
            raise ValueError("--names entries must use SYMBOL=Name")
        symbol, name = value.split("=", 1)
        symbol = symbol.strip()
        name = name.strip()
        if not symbol or not name:
            raise ValueError("--names entries must use non-empty SYMBOL=Name")
        parsed[symbol] = name
    return parsed


def build_panel(
    symbols: Iterable[str],
    as_of: Any,
    data_dir: Path = DEFAULT_DATA_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    names: dict[str, str] | None = None,
) -> tuple[dict[str, Any], Path, Path]:
    parsed_as_of = parse_as_of(str(as_of))
    selected_symbols = tuple(symbols)
    if not selected_symbols:
        raise ValueError("at least one symbol is required")

    structure_dir = output_dir / "structures"
    rows: list[dict[str, Any]] = []
    for symbol in selected_symbols:
        result = analyze_structure(
            symbol=symbol,
            as_of=parsed_as_of,
            data_dir=data_dir,
            name=(names or {}).get(symbol),
        )
        json_path, md_path = write_outputs(result, structure_dir)
        current = result.get("current_state_description", {})
        macd = result.get("momentum_context", {}).get("macd", {})
        rows.append(
            {
                "symbol": result["symbol"],
                "name": result["name"],
                "as_of": result["as_of"],
                "posture": current.get("posture", "不确定"),
                "structure_clarity": result["structure_clarity"],
                "background_state": result["background"]["overall"]["state"],
                "operating_status": result["operating_level"]["status"],
                "watch_label": result["operating_level"]["watch_label"],
                "structure_summary": result["structure_summary"],
                "macd_summary": macd.get("summary", MACD_FALLBACK_SUMMARY),
                "missing_timeframes": result["data_quality"]["missing_timeframes"],
                "outputs": {
                    "json": str(json_path),
                    "markdown": str(md_path),
                },
            }
        )

    panel = {
        "schema_version": PANEL_SCHEMA_VERSION,
        "as_of": parsed_as_of.strftime("%Y-%m-%d %H:%M:%S"),
        "data_policy": {
            "bar_policy": "closed_bar_only",
            "uses_backtest": False,
            "json_is_canonical": True,
            "markdown_render": "deterministic_template",
        },
        "symbols": rows,
    }
    _validate_panel(panel)

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"panel_{parsed_as_of.strftime('%Y-%m-%d_%H%M%S')}"
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(panel, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_panel_markdown(panel), encoding="utf-8")
    return panel, json_path, md_path


def _validate_panel(panel: dict[str, Any]) -> None:
    if panel.get("schema_version") != PANEL_SCHEMA_VERSION:
        raise ValueError("panel schema_version mismatch")
    serialized = json.dumps(panel, ensure_ascii=False, sort_keys=True)
    found = [term for term in FORBIDDEN_OUTPUT_TERMS if term in serialized]
    if found:
        raise ValueError(f"Forbidden panel terms found: {found}")


def render_panel_markdown(panel: dict[str, Any]) -> str:
    lines = [
        "# 多标的结构面板",
        "",
        f"- 时间: `{panel['as_of']}`",
        "- 数据口径: 已完成K线；JSON 为 canonical；本 MD 为模板渲染。",
        "",
        "| 标的 | 名称 | 当前状态 | 清晰度 | 大背景 | 操作级别 | 观察位 | 结构摘要 | 动能辅助 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in panel["symbols"]:
        lines.append(
            f"| `{row['symbol']}` | {row['name']} | {row['posture']} | {row['structure_clarity']} | "
            f"{row['background_state']} | {row['operating_status']} | {row['watch_label']} | "
            f"{row['structure_summary']} | {row['macd_summary']} |"
        )
    markdown = "\n".join(lines) + "\n"
    found = [term for term in FORBIDDEN_OUTPUT_TERMS if term in markdown]
    if found:
        raise ValueError(f"Forbidden panel Markdown terms found: {found}")
    return markdown


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", nargs="+", default=[DEFAULT_SYMBOL])
    parser.add_argument("--names", nargs="*", default=[])
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    symbols = _split_values(args.symbols)
    names = parse_name_map(args.names)
    panel, json_path, md_path = build_panel(
        symbols=symbols,
        as_of=args.as_of,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        names=names,
    )
    print(f"json={json_path}")
    print(f"md={md_path}")
    print(f"symbols={len(panel['symbols'])}")


if __name__ == "__main__":
    main()
