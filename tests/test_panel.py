from __future__ import annotations

import json

from helpers import load_script, write_structure_fixture

panel_module = load_script("panel")


def test_panel_builds_multi_symbol_summary(tmp_path) -> None:
    data_dir = tmp_path / "derived"
    write_structure_fixture(data_dir, symbol="000001.SH", include_macd=True)
    write_structure_fixture(data_dir, symbol="399006.SZ", include_macd=True)

    panel, json_path, md_path = panel_module.build_panel(
        symbols=("000001.SH", "399006.SZ"),
        as_of="2026-05-14 15:00:00",
        data_dir=data_dir,
        output_dir=tmp_path / "panel",
        names={"000001.SH": "上证指数", "399006.SZ": "创业板指"},
    )

    assert panel["schema_version"] == "chanlun_panel_v0.1"
    assert len(panel["symbols"]) == 2
    assert panel["symbols"][0]["posture"] == "中性观察"
    assert panel["symbols"][1]["name"] == "创业板指"
    assert "动能项可用" in panel["symbols"][0]["macd_summary"]
    assert json_path.exists()
    assert md_path.exists()
    assert (tmp_path / "panel" / "structures").exists()

    rendered = md_path.read_text(encoding="utf-8")
    serialized = json.dumps(panel, ensure_ascii=False)
    assert "多标的结构面板" in rendered
    for term in panel_module.FORBIDDEN_OUTPUT_TERMS:
        assert term not in rendered
        assert term not in serialized


def test_parse_name_map_requires_symbol_name_pairs() -> None:
    try:
        panel_module.parse_name_map(["000001.SH"])
    except ValueError as exc:
        assert "SYMBOL=Name" in str(exc)
    else:
        raise AssertionError("expected ValueError")
