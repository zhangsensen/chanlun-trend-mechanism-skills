# 系统文档

## 目标

本仓库只打包一个独立 Codex skill：`chan-trend-mechanism`。
它把本地 closed-bar OHLCV parquet 数据转换成确定性的缠论风格多周期结构观察。

项目公开保证三件事：

1. JSON 输出是 canonical。
2. Markdown 输出是 JSON 的确定性模板渲染。
3. MACD 只作为辅助动能背景，不改变结构分类。

## Harness 约束

这个 skill 不把大模型当作判断源。判断源是 `structure_analyzer.py` 输出的 canonical JSON，大模型只负责把已经确定的字段组织成人类可读文本。

约束层包括：

- 数据约束：只读本地 closed-bar parquet，缺失数据进入 `data_quality` 和 `unknowns`。
- 顺序约束：先大级别背景，再操作级别，再支撑压力阶梯，再条件分支，最后才是 MACD 辅助。
- 词汇约束：输出必须是结构观察，不允许动作化表达。
- 动能约束：`momentum_context.macd` 只能补充动能事实，不能覆盖 `background`、`operating_level` 或 `support_ladder`。
- 渲染约束：Markdown 从 JSON 模板化生成；人工总结也必须能回溯到 JSON 字段。

推荐的人类可读映射：

| 叙述内容 | 主要来源字段 |
| --- | --- |
| 当前状态 | `current_state_description.posture`, `operating_level.status` |
| 大级别背景 | `background.overall.state` |
| 核心观察位 | `operating_level.watch_level`, `operating_level.watch_label`, `support_ladder` |
| 上方/下方条件 | `conditional_tree` |
| 动能辅助 | `momentum_context.macd.summary` |
| 不确定项 | `data_quality.warnings`, `unknowns`, `structure_clarity` |

## 组件

| 组件 | 路径 | 职责 |
| --- | --- | --- |
| Skill 合同 | `skills/chan-trend-mechanism/SKILL.md` | 定义使用场景、硬边界、工作流、输出合同和用语规则。 |
| 结构分析器 | `skills/chan-trend-mechanism/scripts/structure_analyzer.py` | 读取单个标的的多周期数据，输出 `chanlun_structure_v0.2`。 |
| MACD 补列工具 | `skills/chan-trend-mechanism/scripts/macd_enrichment.py` | 在 parquet 文件中就地写入固定 `12/26/9` MACD 字段。 |
| 面板工具 | `skills/chan-trend-mechanism/scripts/panel.py` | 对多个标的运行结构分析器，输出 `chanlun_panel_v0.1`。 |
| 数据格式说明 | `skills/chan-trend-mechanism/references/data_schema.md` | 说明 parquet 目录、字段、时间戳和 MACD 口径。 |
| 机制用语说明 | `skills/chan-trend-mechanism/references/mechanism.md` | 说明结构优先级和允许使用的表述。 |
| 测试 | `tests/` | 锁定 closed-bar 行为、MACD 行为、输出边界和面板渲染。 |

## 数据流

```text
本地 parquet 文件
  -> 时间戳标准化
  -> 按 --as-of 选择已完成 K 线
  -> MA20/MA55/MA233 快照
  -> 大级别背景分类
  -> 操作级别分类
  -> 支撑压力阶梯
  -> 可选 MACD 辅助背景
  -> 条件树
  -> canonical JSON
  -> 确定性 Markdown
```

## 周期语义

| 分组 | 周期 | 用途 |
| --- | --- | --- |
| 大级别背景 | `1d`, `2d`, `1w`, `2w` | 判断大背景状态：`偏多`、`弱多`、`转弱` 或 `不确定`。 |
| 操作级别 | `30m`, `60m`, `120m` | 判断当前观察级别和失守的中轨。 |
| 支撑压力阶梯 | `5m`, `15m`, `30m`, `60m`, `120m`, `1d`, `2d`, `1w`, `2w` | 输出 MA20/MA55 支撑或压力。 |
| MACD | `1d`, `60m`, `120m` | 只输出辅助动能事实。 |

## 输出版本

| 输出 | 版本 | 生产脚本 |
| --- | --- | --- |
| 结构 JSON | `chanlun_structure_v0.2` | `structure_analyzer.py` |
| 面板 JSON | `chanlun_panel_v0.1` | `panel.py` |

## 不变量

- 分析器只读取配置数据目录下的本地 parquet 文件。
- 分析器选择 normalized timestamp 小于等于 `--as-of` 的最新一行。
- date-only 的日线或更高周期数据按 15:00 已收盘 K 线处理。
- 缺失周期进入 `data_quality.missing_timeframes`。
- 缺失 MACD 字段只产生 fallback summary，不改变结构字段。
- 分析器和面板输出校验会拒绝动作化表达。
- `structure_alignment` 在未来有测试过的确定性映射前不输出。

## 运行依赖

运行依赖保持很小：

- `pandas`
- `pyarrow`

开发验证依赖：

- `pytest`
- `ruff`
- `pyright`

项目不需要运行服务、网络调用、数据库、浏览器或外部数据供应商。

## 发布验证

发布验证流程见 `docs/release-checklist.md`。
最低发布门槛：

```bash
uv run pytest
uv run ruff check .
uv run pyright
python /path/to/skill-creator/scripts/quick_validate.py skills/chan-trend-mechanism
# 运行敏感内容扫描。
```
