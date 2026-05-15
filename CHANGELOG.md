# 更新日志

本文件记录项目的重要版本变化。

## v0.1.0 - 2026-05-15

缠论趋势机制 Codex Skill 的首个独立公开版本。

### 新增

- 新增 `skills/chan-trend-mechanism/SKILL.md`，作为公开 skill 合同。
- 新增确定性的单标的结构分析器，输出 `chanlun_structure_v0.2` JSON。
- 新增固定 `12/26/9` 参数的 MACD 补列工具。
- 新增多标的结构面板工具，输出 `chanlun_panel_v0.1` JSON。
- 新增数据格式说明和机制用语说明。
- 新增 synthetic tests，覆盖结构分析、MACD 补列、面板渲染、closed-bar 选择、禁用输出词、MACD 不改变结构分类等行为。
- 新增公开 README、系统文档、发布检查清单、v0.1.0 发布说明和 MIT License。
- README 新增 2026-05-15 上证指数人类可读输出示例。
- README 和系统文档补充 harness 说明，明确大模型只组织 canonical JSON 字段，不作为判断源。
- README 和 GitHub 描述使用面向国内用户的中文短句。
- 公开文档统一使用通用敏感内容边界。

### 验证

- `uv run pytest`
- `uv run ruff check .`
- `uv run pyright`
- `quick_validate.py skills/chan-trend-mechanism`
- tracked files 敏感内容扫描
