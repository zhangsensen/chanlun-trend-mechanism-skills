"""Reusable MACD enrichment for multi-timeframe OHLCV parquet data."""

from __future__ import annotations

import argparse
import math
import os
import tempfile
from pathlib import Path
from typing import Iterable

import pandas as pd

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
MACD_COLUMNS = ("macd_dif", "macd_dea", "macd_hist")
DEFAULT_DATA_DIR = Path("data/index/derived")
DEFAULT_TIMEFRAMES = ("1d", "60m", "120m")


def compute_macd_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of ``df`` with fixed 12/26/9 MACD columns added."""
    if "close" not in df.columns:
        raise ValueError("MACD enrichment requires a close column")

    enriched = df.copy()
    try:
        close = pd.Series(
            pd.to_numeric(pd.Series(enriched["close"], index=enriched.index), errors="raise"),
            index=enriched.index,
            dtype="float64",
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("close must contain numeric values") from exc
    if bool(close.isna().any()) or not bool(close.map(math.isfinite).all()):
        raise ValueError("close must contain finite numeric values")

    ema_fast = close.ewm(span=MACD_FAST, adjust=False).mean()
    ema_slow = close.ewm(span=MACD_SLOW, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=MACD_SIGNAL, adjust=False).mean()

    enriched["macd_dif"] = dif
    enriched["macd_dea"] = dea
    enriched["macd_hist"] = dif - dea
    return enriched


def sort_for_timeframe(df: pd.DataFrame) -> pd.DataFrame:
    """Sort by the canonical timestamp column available in a timeframe file."""
    for column in ("datetime", "trade_date", "period_end"):
        if column in df.columns:
            return df.copy().sort_values(
                column,
                key=lambda values: pd.to_datetime(values),
                kind="mergesort",
            ).reset_index(drop=True)

    raise ValueError("timeframe data requires one of datetime, trade_date, or period_end")


def enrich_macd_file(path: Path) -> bool:
    """Enrich one parquet file in place with deterministic MACD columns."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    df = pd.read_parquet(path)
    sorted_df = sort_for_timeframe(df)
    computed = compute_macd_columns(sorted_df)
    enriched = sorted_df.copy()
    for column in MACD_COLUMNS:
        enriched[column] = computed[column]

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)
        enriched.to_parquet(tmp_path, index=False)
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise
    return True


def enrich_tree(
    data_dir: Path = DEFAULT_DATA_DIR,
    timeframes: Iterable[str] = DEFAULT_TIMEFRAMES,
    symbols: Iterable[str] | None = None,
) -> dict[str, int]:
    """Enrich parquet files under timeframe subdirectories and return counters."""
    selected_symbols = tuple(symbols or ())
    counts = {"enriched": 0, "missing_timeframes": 0}

    for timeframe in timeframes:
        timeframe_dir = data_dir / timeframe
        if not timeframe_dir.exists():
            counts["missing_timeframes"] += 1
            continue

        if selected_symbols:
            paths = [timeframe_dir / f"{symbol}.parquet" for symbol in selected_symbols]
        else:
            paths = sorted(timeframe_dir.glob("*.parquet"))

        for path in paths:
            if not path.exists():
                continue
            enrich_macd_file(path)
            counts["enriched"] += 1

    return counts


def _split_values(values: Iterable[str] | None) -> tuple[str, ...] | None:
    if values is None:
        return None

    parsed: list[str] = []
    for value in values:
        parsed.extend(item.strip() for item in value.split(",") if item.strip())
    return tuple(parsed)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich parquet files with fixed 12/26/9 MACD columns.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--timeframes", nargs="+", default=DEFAULT_TIMEFRAMES)
    parser.add_argument("--symbols", nargs="*", default=[])
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    timeframes = _split_values(args.timeframes) or DEFAULT_TIMEFRAMES
    symbols = _split_values(args.symbols)
    counts = enrich_tree(data_dir=args.data_dir, timeframes=timeframes, symbols=symbols)
    print(f"enriched={counts['enriched']}")
    print(f"missing_timeframes={counts['missing_timeframes']}")


if __name__ == "__main__":
    main()
