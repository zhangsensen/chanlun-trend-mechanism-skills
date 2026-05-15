# 发布检查清单

每次公开发布前使用本清单。

## 1. 仓库状态

- `git status --short` 在打 tag 前为空。
- `git remote -v` 指向目标 GitHub 公共仓库。
- 没有追踪生成数据、本地输出、parquet 文件、截图或凭据。
- `.omx/` 继续通过 `.git/info/exclude` 保持本地状态。

## 2. 文档对齐

- `README.md` 描述当前版本、schema 版本、使用命令和边界。
- `CHANGELOG.md` 包含当前发布版本。
- `docs/releases/<version>.md` 存在，并且与 tag 匹配。
- `docs/system.md` 反映当前脚本、输出版本和不变量。
- `skills/chan-trend-mechanism/references/data_schema.md` 与实际 reader 行为一致。
- `skills/chan-trend-mechanism/references/mechanism.md` 与允许的输出用语一致。

## 3. 验证命令

在仓库根目录运行：

```bash
uv run pytest
uv run ruff check .
uv run pyright
python /home/sensen/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/chan-trend-mechanism
# 运行敏感内容扫描。
```

期望结果：

- pytest 显示全部测试通过。
- Ruff 显示 all checks passed。
- Pyright 显示 0 errors。
- Skill validator 显示 valid。
- 敏感内容扫描无命中。

## 4. 发布产物

- tag 名称遵循 `vMAJOR.MINOR.PATCH`。
- GitHub release 标题与 tag 对齐。
- GitHub release body 总结新增能力、边界、验证证据和已知限制。
- Release body 链接或对应 `CHANGELOG.md` 与 `docs/releases/<version>.md`。

## 5. 停止条件

出现任一情况，不创建或发布 release：

- 任一验证命令失败。
- tracked file 命中敏感内容。
- 文档中的输出合同版本与代码常量不一致。
- release notes 提到了未实现或未测试的行为。
