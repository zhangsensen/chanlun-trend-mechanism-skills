from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import cast

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "skills" / "chan-trend-mechanism" / "scripts"


def load_script(name: str) -> ModuleType:
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    path = SCRIPTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"skill_{name}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def timestamp(value: str) -> pd.Timestamp:
    return cast(pd.Timestamp, pd.Timestamp(value))


def write_frame(root: Path, timeframe: str, symbol: str, rows: list[dict]) -> None:
    path = root / timeframe
    path.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path / f"{symbol}.parquet", index=False)


def minute_rows(close: float, ma20: float, ma55: float, future_close: float = 999.0) -> list[dict]:
    return [
        {
            "ts_code": "000001.SH",
            "datetime": "2026-05-14 14:00:00",
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": 1,
            "ma20": ma20 - 1,
            "mid": ma20 - 1,
            "ma55": ma55,
            "ma233": 80.0,
        },
        {
            "ts_code": "000001.SH",
            "datetime": "2026-05-14 15:00:00",
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": 1,
            "ma20": ma20,
            "mid": ma20,
            "ma55": ma55,
            "ma233": 80.0,
        },
        {
            "ts_code": "000001.SH",
            "datetime": "2026-05-14 16:00:00",
            "open": future_close,
            "high": future_close,
            "low": future_close,
            "close": future_close,
            "volume": 1,
            "ma20": 1.0,
            "mid": 1.0,
            "ma55": 1.0,
            "ma233": 1.0,
        },
    ]


def daily_rows(close: float, ma20: float, ma55: float) -> list[dict]:
    return [
        {
            "ts_code": "000001.SH",
            "trade_date": "2026-05-13",
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": 1,
            "ma20": ma20 - 1,
            "mid": ma20 - 1,
            "ma55": ma55,
            "ma233": 80.0,
        },
        {
            "ts_code": "000001.SH",
            "trade_date": "2026-05-14",
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": 1,
            "ma20": ma20,
            "mid": ma20,
            "ma55": ma55,
            "ma233": 80.0,
        },
        {
            "ts_code": "000001.SH",
            "trade_date": "2026-05-15",
            "open": 999.0,
            "high": 999.0,
            "low": 999.0,
            "close": 999.0,
            "volume": 1,
            "ma20": 1.0,
            "mid": 1.0,
            "ma55": 1.0,
            "ma233": 1.0,
        },
    ]


def with_macd(
    rows: list[dict],
    prev: tuple[float, float, float],
    curr: tuple[float, float, float],
) -> list[dict]:
    updated = [dict(row) for row in rows]
    updated[0]["macd_dif"], updated[0]["macd_dea"], updated[0]["macd_hist"] = prev
    updated[1]["macd_dif"], updated[1]["macd_dea"], updated[1]["macd_hist"] = curr
    updated[2]["macd_dif"], updated[2]["macd_dea"], updated[2]["macd_hist"] = (9.0, 9.0, 9.0)
    return updated


def write_structure_fixture(root: Path, symbol: str = "000001.SH", include_macd: bool = True) -> None:
    minute_values = {
        "5m": (101.0, 100.0, 95.0),
        "15m": (101.0, 100.0, 95.0),
        "30m": (99.0, 100.0, 95.0),
        "60m": (99.0, 100.0, 95.0),
        "120m": (101.0, 100.0, 95.0),
    }
    macd_by_tf = {
        "60m": ((0.20, 0.10, 0.50), (-0.20, 0.10, -1.00)),
        "120m": ((0.30, 0.10, 0.20), (0.40, 0.20, 0.30)),
    }
    for timeframe, (close, ma20, ma55) in minute_values.items():
        rows = minute_rows(close, ma20, ma55)
        if include_macd and timeframe in macd_by_tf:
            rows = with_macd(rows, *macd_by_tf[timeframe])
        write_frame(root, timeframe, symbol, rows)

    daily_values = {
        "1d": (101.0, 100.0, 95.0),
        "2d": (101.0, 100.0, 105.0),
        "1w": (99.0, 100.0, 95.0),
        "2w": (101.0, 100.0, 95.0),
    }
    for timeframe, (close, ma20, ma55) in daily_values.items():
        rows = daily_rows(close, ma20, ma55)
        if include_macd and timeframe == "1d":
            rows = with_macd(rows, (0.10, 0.20, 0.10), (0.30, 0.20, 0.20))
        write_frame(root, timeframe, symbol, rows)
