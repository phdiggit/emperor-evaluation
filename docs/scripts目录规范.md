# scripts 目录规范

本规范用于区分开发辅助工具、校验脚本、业务脚本和后续目录治理边界。目录治理应分批、小步推进，不在一个 PR 中搬空 `scripts/` 根目录。

## scripts/dev/

`scripts/dev/` 是开发辅助工具目录，供 Codex、维护者和本地开发使用。

典型示例：

- `repo_tool.py`
- `pr_body_tool.py`

这类脚本用于本地读写、范围核对、PR body 生成和类似维护动作，不应参与业务导出、评分逻辑、证据裁判或正式验证语义。

新增给 Codex 或开发者使用的辅助轮子，必须优先放入 `scripts/dev/`。不得把新的开发辅助脚本直接放入 `scripts/` 根目录。

## scripts/validate/

`scripts/validate/` 是 validator 真实实现目录。新增 validator 应放入这里，不应继续把主逻辑直接放在 `scripts/` 根目录。

已迁移的旧路径可以在 `scripts/` 根目录保留兼容 wrapper，例如：

```text
scripts/validate_config_comments.py
scripts/validate/validate_config_comments.py
```

兼容 wrapper 只负责转发到 `scripts/validate/` 下的真实实现，不承载大段重复逻辑。修改已迁移 validator 时，应优先修改 `scripts/validate/` 下真实实现，再确认旧路径 wrapper 仍可运行。

## scripts/

`scripts/` 根目录当前仍保留历史脚本、总入口、尚未迁移脚本和必要的旧路径兼容 wrapper。

新增 validator 不应继续放在 `scripts/` 根目录。业务导出、build、pipeline、matrix 类脚本后续再分批治理，不得顺手迁移。

任何后续目录治理都应先锁定影响面和测试，再拆分迁移，避免顺手改动业务数据、评分、排名、正式定档、证据事实或证据簇裁判结论。
