from __future__ import annotations

import pandas as pd
import pytest

from helpers import load_script

macd_enrichment = load_script("macd_enrichment")


def test_compute_macd_columns_uses_fixed_12_26_9() -> None:
    df = pd.DataFrame(
        {
            "datetime": pd.date_range("2026-01-01", periods=40, freq="h"),
            "close": [str(100 + i * 0.5) for i in range(40)],
        }
    )

    result = macd_enrichment.compute_macd_columns(df)
    close = df["close"].astype(float)
    ema_fast = close.ewm(span=12, adjust=False).mean()
    ema_slow = close.ewm(span=26, adjust=False).mean()
    expected_dif = ema_fast - ema_slow
    expected_dea = expected_dif.ewm(span=9, adjust=False).mean()
    expected_hist = expected_dif - expected_dea

    assert macd_enrichment.MACD_COLUMNS == ("macd_dif", "macd_dea", "macd_hist")
    pd.testing.assert_series_equal(result["macd_dif"], expected_dif, check_names=False)
    pd.testing.assert_series_equal(result["macd_dea"], expected_dea, check_names=False)
    pd.testing.assert_series_equal(result["macd_hist"], expected_hist, check_names=False)
    pd.testing.assert_series_equal(result["close"], df["close"])


def test_compute_macd_columns_rejects_invalid_close() -> None:
    df = pd.DataFrame(
        {
            "datetime": pd.date_range("2026-01-01", periods=3, freq="h"),
            "close": ["100.0", "bad", "101.0"],
        }
    )

    with pytest.raises(ValueError, match="close"):
        macd_enrichment.compute_macd_columns(df)


def test_enrich_macd_file_preserves_rows_and_sorts_datetime(tmp_path) -> None:
    path = tmp_path / "sample.parquet"
    df = pd.DataFrame(
        {
            "datetime": pd.to_datetime(
                ["2026-01-01 02:00:00", "2026-01-01 00:00:00", "2026-01-01 01:00:00"]
            ),
            "close": [101.0, 100.0, 100.5],
            "ma20": [100.1, 99.9, 100.0],
        }
    )
    df.to_parquet(path, index=False)

    assert macd_enrichment.enrich_macd_file(path) is True
    stored = pd.read_parquet(path)

    assert stored["datetime"].is_monotonic_increasing
    assert len(stored) == len(df)
    for column in macd_enrichment.MACD_COLUMNS:
        assert column in stored.columns
        assert bool(stored[column].notna().all())


def test_enrich_tree_empty_symbols_enriches_all_files(tmp_path) -> None:
    timeframe_dir = tmp_path / "60m"
    timeframe_dir.mkdir()
    for symbol in ("000001.SH", "000002.SH"):
        df = pd.DataFrame(
            {
                "datetime": pd.date_range("2026-01-01", periods=3, freq="h"),
                "close": [100.0, 100.5, 101.0],
            }
        )
        df.to_parquet(timeframe_dir / f"{symbol}.parquet", index=False)

    counts = macd_enrichment.enrich_tree(data_dir=tmp_path, timeframes=("60m",), symbols=())

    assert counts == {"enriched": 2, "missing_timeframes": 0}
    for path in sorted(timeframe_dir.glob("*.parquet")):
        stored = pd.read_parquet(path)
        for column in macd_enrichment.MACD_COLUMNS:
            assert column in stored.columns
