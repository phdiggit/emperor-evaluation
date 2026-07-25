# V4 服务切换契约

三个 release 使用同一套不可变目录规则。Source Cache 负责中央史源预热且 timer 开启；Claim Extractor 的数据库 worker 仍关闭；Emperor Rebuild release 同时供独立单朝代治理会话和单皇帝主控会话读取，不安装治理 queue、worker 或 timer：

- `/opt/emperor-evaluation-v4/<service>/releases/<git-sha>/`：只读 release 内容；
- `/opt/emperor-evaluation-v4/<service>/current`：仅指向上述 releases 子目录的原子 symlink；
- `/opt/emperor-evaluation-v4/<service>/venv/`：服务独立 Python 环境；
- `/etc/emperor-evaluation-v4/<service>.env`：`root:emperor-v4`、`0640`，不得进入 Git；
- `/data1/emperor-evaluation/runtime/services/emperor-v4/`：服务可变状态根；Claim Extractor 的 `CODEX_HOME` 与中性材料批任务均在此目录下；
- `emperor-v4`：无登录 shell 的专用运行用户和组。

`provision-prerequisites.sh` 只创建上述账号/目录、校验并展开 release、建立 `current` 指针、准备独立 venv、安装 Codex executable 和非敏感配置样例。它不创建数据库、不写真实 DSN/认证材料、不安装或启用 systemd unit。单皇帝会话的当前租约位于 `session-control/`，共享编年 current 位于 `shared-neutral-backbones/`；两者都不保存历史运行。

Source Cache 不读取数据库凭据。它从 release 内的 `config/workflow-source-cache.yml` 读取预热目录，从 `/data1/emperor-evaluation/runtime/services/emperor-v4/source-cache/requests/` 读取会话缺页需求。Claim Extractor 环境文件必须定义：

- `EMPEROR_EVAL_V4_CLAIM_EXTRACTOR_DSN`
- `EMPEROR_EVAL_V4_CLAIM_PROFILE`
- `EMPEROR_EVAL_V4_RELEASE_SHA`
- `EMPEROR_EVAL_V4_CODEX_BIN`
- `EMPEROR_EVAL_V4_CODEX_MODEL`
- `EMPEROR_EVAL_V4_CODEX_REASONING_EFFORT`
- `EMPEROR_EVAL_V4_CODEX_TIMEOUT_SECONDS`

Claim 的 Codex 可执行文件固定为 `/opt/emperor-evaluation-v4/bin/codex`，认证状态目录固定为 `/data1/emperor-evaluation/runtime/services/emperor-v4/claim-extractor/codex`，两者必须由 `emperor-v4` 在 `ProtectHome=true` 下读取，不得引用 `/home/penghao/**` 或复用 V3 环境文件。定时 unit 显式把当前 release 的 `src` 加入 `PYTHONPATH`，venv 只承载依赖，不复制某个 release 的业务源码。正式切换前必须依次通过 release hash 校验、`systemd-analyze verify` 和回滚 symlink 演练；预检不得启用 timer、停止历史 unit 或修改生产数据库。

Source Cache 每分钟运行一次，每轮最多枚举一个作品目录或缓存五页固定 revision 纯文本；既有 LocalSourceTextIndex 和通过 `workflow-source-cache-import-v1` 校验的离线固定快照直接作为种子。逻辑史书按中央载体目录依次尝试已批准载体，单一载体的 429 进入六小时冷却、其他瞬时错误进入半小时冷却，但不阻断同书备用载体；只有已批准载体覆盖并集仍缺失的页面才写入 collection `CURRENT.json`。页面 provenance 保留实际 `carrier_id`、revision 与正文 hash。页面状态位于 `/data1/emperor-evaluation/runtime/services/emperor-v4/source-cache/`，索引原子发布到 `/data1/emperor-evaluation/runtime/active/source_text_indexes/workflow-*-current/`。皇帝会话不得自行访问公网史源。

单朝代治理会话复用同一个只读 Codex executable 和 Claim Extractor 的专用认证目录，但不读取数据库凭据。操作者在开启该朝皇帝链前显式串行运行 `dynasty-governance-session-run`；它只读发现覆盖配置书目的固定索引，把通过质量门的唯一 current、公共成果登记和交接物写到 `/data1/emperor-evaluation/runtime/active/dynasty_neutral_materials/<DYNASTY>/`。同一朝代不设常驻 worker、timer 或锁。

服务器不保留可编辑项目工作树。Git commit 是源码事实源；发布者从干净 commit 使用 `python -m emperor_v4.runtime.release build` 构建带 SHA-256 manifest 的 archive，再上传并由 `provision-prerequisites.sh` 展开到 `/opt/emperor-evaluation-v4/<service>/releases/<git-sha>/`。运行时不得通过 `git pull` 或直接复制源码覆盖 `current`。

运维连接统一使用本机 SSH alias `emperor-runtime`；真实 IP 和用户只保存在操作者的 `~/.ssh/config`，不得提交。服务器当前稳定入口为：

- `emperor-v4-source-cache-worker.timer`：中央史源预热，当前开启；
- `emperor-v4-claim-extractor-worker.timer`：当前关闭；
- `emperor-v4-emperor-rebuild-queue.timer`：旧队列入口，必须关闭；
- `/data1/emperor-evaluation/runtime/services/emperor-v4/neutral-material-batches/`：中性材料批任务及其结果；
- `/data1/emperor-evaluation/runtime/active/`：现有活动索引和影子运行资产。

新会话先执行 `ssh emperor-runtime sudo bash /opt/emperor-evaluation-v4/source-cache/current/deploy/v4/verify-server-runtime.sh`，确认 release、唯一活动 timer、状态根和 Codex 运行时，再通过单皇帝会话控制入口认领；不得重新启用旧皇帝 queue。

中性材料批扫描交给模型的页面正文必须来自 `fetch_wikisource_plaintext`，并用同一响应中的 revision id 锁定版本；不得把含 `{{ProperNoun|...}}`、`-{...}-` 等 MediaWiki 标记的原始 revision 正文直接嵌入模型 Prompt。对于 `extracts` 为空的模板转引页，适配器按已锁定 oldid 获取 rendered HTML 后转为纯文本，不得重新按当前标题取正文。批准备按页面原子缓存 revision、plaintext 与 hash，限流或瞬时网络失败后只补缺页。既有原始正文运行只能在单独目录生成 plaintext 派生结果，记录原结果与派生结果 hash，并通过全量引文审计后使用；不得覆盖原结果。

服务器上的中性材料模型批次必须复用 `/data1/emperor-evaluation/runtime/services/emperor-v4/claim-extractor/codex` 认证目录，不使用历史 `.codex` 目录，也不得读取或输出认证内容。`source-cache` release 同时携带制度史抽取、跨书增量比较、确定性材料结算及其结构化输出合同；模型批次仍写入 `neutral-material-batches/`，不进入两个定时服务的数据库状态机。
