# V4 服务切换契约

两个服务使用同一套不可变目录规则，但保持独立 release、venv、环境文件、数据库 schema 和 timer：

- `/opt/emperor-evaluation-v4/<service>/releases/<git-sha>/`：只读 release 内容；
- `/opt/emperor-evaluation-v4/<service>/current`：仅指向上述 releases 子目录的原子 symlink；
- `/opt/emperor-evaluation-v4/<service>/venv/`：服务独立 Python 环境；
- `/etc/emperor-evaluation-v4/<service>.env`：`root:emperor-v4`、`0640`，不得进入 Git；
- `emperor-v4`：无登录 shell 的专用运行用户和组。

Source Cache 环境文件必须定义 `EMPEROR_EVAL_V4_SOURCE_CACHE_DSN` 与 `EMPEROR_EVAL_V4_RELEASE_SHA`，计划文件固定为 `/etc/emperor-evaluation-v4/source-cache-plan.yml`。Claim Extractor 环境文件必须定义：

- `EMPEROR_EVAL_V4_CLAIM_EXTRACTOR_DSN`
- `EMPEROR_EVAL_V4_CLAIM_PROFILE`
- `EMPEROR_EVAL_V4_RELEASE_SHA`
- `EMPEROR_EVAL_V4_CODEX_BIN`
- `EMPEROR_EVAL_V4_CODEX_MODEL`
- `EMPEROR_EVAL_V4_CODEX_REASONING_EFFORT`
- `EMPEROR_EVAL_V4_CODEX_TIMEOUT_SECONDS`

Claim 的 Codex 可执行文件和认证目录必须由 `emperor-v4` 在 `ProtectHome=true` 下读取，不得引用 `/home/penghao/**` 或复用 V3 环境文件。正式切换前必须依次通过 release hash 校验、`systemd-analyze verify`、隔离数据库单次 tick 和回滚 symlink 演练；预检不得启用 timer、停止历史 unit 或修改生产数据库。
