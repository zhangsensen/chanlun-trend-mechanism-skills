# 缠论趋势机制 Skill

缠论多周期结构分析 Skill：读取本地行情数据，生成结构观察、关键线位和动能辅助。

这个项目是一个独立的 Codex skill 仓库，面向本地 A 股指数或其他 OHLCV parquet 数据，输出多周期结构观察、支撑压力阶梯、MACD 辅助背景和条件分支。它只描述当前结构，不提供操作建议、预测或收益承诺。

## 项目定位

- **Skill ID**: `chan-trend-mechanism`
- **当前版本**: `v0.1.0`
- **核心输出**: `chanlun_structure_v0.2` JSON
- **面板输出**: `chanlun_panel_v0.1` JSON
- **数据口径**: closed-bar only，只读取 `--as-of` 之前已经完成的 K 线
- **适用场景**: 本地指数/标的 OHLCV 数据的多周期结构观察

## 能做什么

- 从 `5m`, `15m`, `30m`, `60m`, `120m`, `1d`, `2d`, `1w`, `2w` 多周期 parquet 文件中选择已完成 K 线。
- 用 `1d/2d/1w/2w` 描述大级别背景。
- 用 `30m/60m/120m` 定位当前操作级别。
- 输出 MA20 中轨与 MA55 结构线的支撑压力阶梯。
- 读取或补齐固定 `12/26/9` MACD 字段，并作为辅助动能背景呈现。
- 输出机械条件分支，例如收复或跌破某一级别中轨后的下一层观察。
- 对多个标的生成结构面板。

## 明确不做什么

- 不读取截图、登录态、会话文件、外部接口或凭据。
- 不读取回测、事件研究、walk-forward、收益评估或规则状态文件。
- 不让 MACD 覆盖结构判断；MACD 只作为辅助动能事实。
- 不推断缺失 K 线；缺失数据会进入 `data_quality.warnings` 和 `unknowns`。
- 不输出操作指令、预测或收益承诺。

## 仓库结构

```text
skills/chan-trend-mechanism/
  SKILL.md                         # Codex skill 主合同
  agents/openai.yaml               # skill 展示元信息
  references/data_schema.md        # parquet 数据约定
  references/mechanism.md          # 结构机制与用语约定
  scripts/structure_analyzer.py    # 单标的结构分析器
  scripts/macd_enrichment.py       # MACD 补列工具
  scripts/panel.py                 # 多标的面板
tests/
  helpers.py
  test_structure_analyzer.py
  test_macd_enrichment.py
  test_panel.py
docs/
  system.md
  release-checklist.md
  releases/v0.1.0.md
```

## 安装与本地验证

```bash
git clone git@github.com:zhangsensen/chanlun-trend-mechanism-skills.git
cd chanlun-trend-mechanism-skills
uv sync
uv run pytest
uv run ruff check .
uv run pyright
```

如果要把它注册到本机 Codex skills，可将 `skills/chan-trend-mechanism` 复制或软链接到你的 Codex skills 目录。也可以直接在本仓库内通过脚本使用。

## 数据格式

默认数据目录：

```text
data/index/derived/
  5m/SYMBOL.parquet
  15m/SYMBOL.parquet
  30m/SYMBOL.parquet
  60m/SYMBOL.parquet
  120m/SYMBOL.parquet
  1d/SYMBOL.parquet
  2d/SYMBOL.parquet
  1w/SYMBOL.parquet
  2w/SYMBOL.parquet
```

必需字段：

- `close`
- 时间字段之一：`datetime`, `trade_date`, `period_end`
- `ma20` 或 `mid`
- `ma55`

可选字段：

- `ma233`
- `macd_dif`, `macd_dea`, `macd_hist`
- `ts_code`, `open`, `high`, `low`, `volume`, `amount`

完整约定见 [data_schema.md](skills/chan-trend-mechanism/references/data_schema.md)。

## 使用示例

补齐 MACD 字段：

```bash
python skills/chan-trend-mechanism/scripts/macd_enrichment.py \
  --data-dir data/index/derived \
  --timeframes 1d 60m 120m
```

生成单标的结构输出：

```bash
python skills/chan-trend-mechanism/scripts/structure_analyzer.py \
  --symbol 000001.SH \
  --name 上证指数 \
  --as-of "2026-05-15 15:00:00" \
  --data-dir data/index/derived \
  --output-dir output/chan_states
```

生成多标的面板：

```bash
python skills/chan-trend-mechanism/scripts/panel.py \
  --symbols 000001.SH 399001.SZ 399006.SZ 000688.SH \
  --names 000001.SH=上证指数 399001.SZ=深证成指 399006.SZ=创业板指 000688.SH=科创50 \
  --as-of "2026-05-15 15:00:00" \
  --data-dir data/index/derived \
  --output-dir output/chan_panel
```

## 怎么看输出

这个 skill 的价值不是让模型自由发挥，而是先用脚本把结构状态、关键线位、动能事实和条件分支固定下来，再让模型只按这些字段组织语言。也就是说，它本质上是一个分析 harness：约束输入、约束判断顺序、约束输出词汇，避免大模型凭感觉扩写、补数据或给出动作化结论。

建议按这个顺序读：

1. 先看 `current_state_description.posture` 和 `operating_level.status`，确认当前状态。
2. 再看 `background.overall.state`，确认大级别背景。
3. 再看 `operating_level.watch_level` 和 `support_ladder`，定位核心观察线。
4. 再看 `conditional_tree`，确认上方收复和下方跌破后的结构分支。
5. 最后看 `momentum_context.macd.summary`，只作为动能辅助，不反过来覆盖结构判断。

### 示例：上证指数 2026-05-15

下面示例展示的是这个 skill 期望生成的人类可读表述。实际使用时，数值必须来自本地 closed-bar parquet 数据和 analyzer 输出的 canonical JSON。

```text
上证指数

结论：中性观察 / 关键支撑观察

上证当前大背景仍是偏多，但 120F中轨 4173.31 已经失守，说明回踩级别继续上移。现在核心看日线中轨 4118.62，2026-05-15 分钟周期收在 4135.39，离日线中轨已经很近。

上方要看能否重新收复 120F中轨 4173.31。收不回去，短级别压力还在。下方如果日线中轨 4118.62 也失守，下一层看双日中轨 4032.83。

动能辅助：日线 MACD 仍在零轴上方，但柱体正向收缩；60F 已跨零轴且柱体负向扩张，120F 也是负向扩张。短级别动能明显偏弱。
```

这个示例对应的判定路径是：

- `background.overall.state` 给出大背景：偏多。
- `operating_level.status` 给出当前状态：关键支撑观察。
- `120m` 中轨失守后，观察级别上移到日线中轨。
- `support_ladder` 提供 120F中轨、日线中轨、双日中轨等具体线位。
- `conditional_tree` 给出“收复 120F中轨”和“跌破日线中轨”的条件分支。
- `momentum_context.macd` 只描述零轴、柱体扩张/收缩等事实，不生成独立结论。

## 输出合同

`structure_analyzer.py` 输出 JSON 和 Markdown。JSON 是 canonical；Markdown 只是确定性模板渲染。

核心字段：

- `schema_version`: 当前为 `chanlun_structure_v0.2`
- `data_policy`: 数据来源与 closed-bar 约束
- `data_quality`: 可用周期、缺失周期和 warning
- `timeframes`: 各周期 close、MA20、MA55、MA233、距离和 reason codes
- `background`: `1d/2d/1w/2w` 背景状态
- `operating_level`: `30m/60m/120m` 当前观察级别
- `support_ladder`: MA20/MA55 支撑压力阶梯
- `momentum_context.macd`: 固定 `12/26/9` MACD 辅助事实
- `conditional_tree`: 机械条件分支
- `current_state_description`: 面向人工阅读的当前状态段落
- `structure_clarity`: `high`, `medium`, `low`

系统细节见 [system.md](docs/system.md)。

## 发布验证

每次发布前至少运行：

```bash
uv run pytest
uv run ruff check .
uv run pyright
python /path/to/skill-creator/scripts/quick_validate.py skills/chan-trend-mechanism
# 运行敏感内容扫描。
```

当前 release checklist 见 [release-checklist.md](docs/release-checklist.md)。

## 版本记录

- [CHANGELOG.md](CHANGELOG.md)
- [v0.1.0 发布说明](docs/releases/v0.1.0.md)

## License

MIT License. See [LICENSE](LICENSE).
