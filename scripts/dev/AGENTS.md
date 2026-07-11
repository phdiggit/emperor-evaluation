# scripts/dev/AGENTS.md

本目录承载 retrieval v3 native workflow。根 `AGENTS.md` 与 `scripts/AGENTS.md` 的边界继续适用。

## 当前工作流

1. clean/source candidate 与对象级 source cache。
2. claim extraction、claim cache、owner/quality/event-group 审计。
3. rule-neutral material intake 与 claim route。
4. candidate review、identity gate、binding、material review。
5. factorization、rule scorer、item raw signal。
6. coverage controller、gap router、convergence report。

入口与依赖均使用 `retrieval_v3_*`；`source_excerpt_pool_lib` 仅作为当前 source discovery 的内部依赖，不是独立旧工作流。

## 数据库边界

- 默认 DSN：`EMPEROR_EVAL_RETRIEVAL_V3_DSN`。
- 默认 schema：`retrieval_v3`。
- scorer JSON 的 `claim_id` 只能回查同一 v3 DSN/schema；详情 enrichment 必须经过 v3 schema cursor。
- claim、target、candidate、binding、factor judgment 和 material score 的皇帝 lineage 不一致时硬失败。
- 除显式 `--execute` 外不得写库；event-group apply 和 scorer execute 仍需用户明确授权。

## 子任务与临时文件

- Codex 批任务继续使用 `codex-win agent run-plan` 和 `expected_outputs.kind=jsonl_patch`。
- 跨进程产物放 `tmp/**`；`.tmp/**` 只放 pytest 或可丢弃短期文件。
- 中文 JSON/Markdown 使用 UTF-8、`ensure_ascii=False` 和稳定排序。

## 验证

- 修改模块时运行对应 `tests/test_<module>.py`。
- 收口运行 `python -m pytest -q`；当前仓库剩余测试全部属于 v3 工作流。
- 运行 `python -m compileall -q scripts tests`、registry 完整性测试和 `git diff --check`。
