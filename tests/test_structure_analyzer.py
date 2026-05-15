from __future__ import annotations

import json

from helpers import load_script, timestamp, write_frame, write_structure_fixture

structure_analyzer = load_script("structure_analyzer")


def test_parse_as_of_date_defaults_to_close_time() -> None:
    assert structure_analyzer.parse_as_of("2026-05-14") == timestamp("2026-05-14 15:00:00")


def test_load_timeframe_bar_accepts_period_end_timestamp_column(tmp_path) -> None:
    data_dir = tmp_path / "derived"
    write_frame(
        data_dir,
        "60m",
        "000001.SH",
        [
            {
                "period_end": "2026-05-14 14:00:00",
                "close": 100.0,
                "ma20": 99.0,
                "ma55": 95.0,
            },
            {
                "period_end": "2026-05-14 15:00:00",
                "close": 101.0,
                "ma20": 100.0,
                "ma55": 95.0,
            },
            {
                "period_end": "2026-05-14 16:00:00",
                "close": 999.0,
                "ma20": 1.0,
                "ma55": 1.0,
            },
        ],
    )

    bar, warning = structure_analyzer.load_timeframe_bar(
        data_dir=data_dir,
        symbol="000001.SH",
        timeframe="60m",
        as_of=timestamp("2026-05-14 15:00:00"),
    )

    assert warning is None
    assert bar is not None
    assert bar.dt == timestamp("2026-05-14 15:00:00")
    assert bar.close == 101.0


def test_analyzer_uses_closed_bars_and_classifies_structure(tmp_path) -> None:
    data_dir = tmp_path / "derived"
    write_structure_fixture(data_dir, include_macd=False)

    result = structure_analyzer.analyze_structure(
        "000001.SH",
        timestamp("2026-05-14 15:00:00"),
        data_dir=data_dir,
        name="上证指数",
    )

    assert result["schema_version"] == "chanlun_structure_v0.2"
    assert result["data_policy"]["bar_policy"] == "closed_bar_only"
    assert result["data_policy"]["uses_backtest"] is False
    assert result["data_policy"]["uses_macd"] is True
    assert result["data_policy"]["macd_role"] == "auxiliary_momentum_context"
    assert result["timeframes"]["60m"]["close"] == 99.0
    assert result["timeframes"]["60m"]["relation_to_ma20"] == "below"
    assert result["operating_level"]["status"] == "回踩级别升级"
    assert result["operating_level"]["watch_level"] == "120m"
    assert "close_below_60m_ma20" in result["operating_level"]["reason_codes"]


def test_analyzer_emits_macd_fallback_without_macd_columns(tmp_path) -> None:
    data_dir = tmp_path / "derived"
    write_structure_fixture(data_dir, include_macd=False)

    result = structure_analyzer.analyze_structure(
        "000001.SH",
        timestamp("2026-05-14 15:00:00"),
        data_dir=data_dir,
        name="上证指数",
    )

    macd = result["momentum_context"]["macd"]
    assert macd["enabled"] is False
    assert macd["parameters"] == {"fast": 12, "slow": 26, "signal": 9}
    assert set(macd["timeframes"]) == {"1d", "60m", "120m"}
    assert "structure_alignment" not in json.dumps(macd, ensure_ascii=False)
    assert any("MACD动能项不可用" in item for item in result["unknowns"])


def test_macd_summary_distinguishes_histogram_direction() -> None:
    summary = structure_analyzer.build_macd_summary(
        {
            "1d": {
                "available": True,
                "label": "日线",
                "hist": 0.5,
                "zero_axis_state": "above_zero",
                "hist_state": "expanding",
                "cross_state": "dif_above_dea",
            },
            "60m": {
                "available": True,
                "label": "60F",
                "hist": -0.7,
                "zero_axis_state": "above_zero",
                "hist_state": "expanding",
                "cross_state": "dif_below_dea",
            },
            "120m": {
                "available": True,
                "label": "120F",
                "hist": -0.2,
                "zero_axis_state": "above_zero",
                "hist_state": "shrinking",
                "cross_state": "dif_below_dea",
            },
        }
    )

    assert "日线柱体正向扩张" in summary
    assert "60F柱体负向扩张" in summary
    assert "120F柱体负向收缩" in summary
    assert "60F柱体扩张" not in summary


def test_analyzer_emits_current_state_description_without_action_language(tmp_path) -> None:
    data_dir = tmp_path / "derived"
    write_structure_fixture(data_dir, include_macd=True)

    result = structure_analyzer.analyze_structure(
        "000001.SH",
        timestamp("2026-05-14 15:00:00"),
        data_dir=data_dir,
        name="上证指数",
    )
    rendered = structure_analyzer.render_markdown(result)
    serialized = json.dumps(result, ensure_ascii=False)

    description = result["current_state_description"]
    text = "\n".join(description["paragraphs"])
    assert description["posture"] == "中性观察"
    assert "当前状态：上证指数大背景是偏多" in text
    assert "60F中轨已经失守" in text
    assert "120F中轨100.000是否守住" in text
    assert "60F中轨100.000能否收复" in text
    assert "动能项辅助看" in text
    assert "structure_alignment" not in serialized
    assert "## 当前状态描述" in rendered
    assert "当前状态: `中性观察`" in rendered
    for term in structure_analyzer.FORBIDDEN_OUTPUT_TERMS:
        assert term not in text
        assert term not in rendered
        assert term not in serialized


def test_macd_does_not_change_structure_classification(tmp_path) -> None:
    plain_dir = tmp_path / "plain"
    macd_dir = tmp_path / "macd"
    write_structure_fixture(plain_dir, include_macd=False)
    write_structure_fixture(macd_dir, include_macd=True)

    as_of = timestamp("2026-05-14 15:00:00")
    plain = structure_analyzer.analyze_structure("000001.SH", as_of, data_dir=plain_dir, name="上证指数")
    with_macd = structure_analyzer.analyze_structure("000001.SH", as_of, data_dir=macd_dir, name="上证指数")

    assert with_macd["structure_clarity"] == plain["structure_clarity"]
    assert with_macd["background"] == plain["background"]
    assert with_macd["operating_level"] == plain["operating_level"]
    assert with_macd["support_ladder"] == plain["support_ladder"]
    assert with_macd["conditional_tree"] == plain["conditional_tree"]
