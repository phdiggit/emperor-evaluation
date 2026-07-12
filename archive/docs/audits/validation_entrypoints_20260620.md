# Validation Entrypoints 20260620

当前仓库保留三个验证入口，职责刻意分开：

## 1. `python scripts/validate/validate_evidence.py`

用途：

- 校验既有 evidence/source/trigger/search/thematic/query 主数据约束
- 继续承担原有业务数据校验职责

不负责：

- 跨 canonical lane 的专题锚点去重
- 批次 canonical 吸收后的 `source_batch` 追溯约束

## 2. `python scripts/validate/validate_canonical_data_integrity.py`

用途：

- 校验 canonical JSONL 的 parseability
- 校验 canonical ID 唯一性
- 校验 thematic anchor lane 内和 lane 间 `anchor_id` 唯一性
- 校验 query/search/thematic 三类 canonicalized 行的 `source_batch` 追溯字段保留
- 校验楚王英 event anchor 与申屠刚 mechanism anchor 的 lane 语义不被回归扁平化
- 校验 `source_polarity=neutral` 的原始极性仍被保留

不负责：

- 替代原有 evidence 业务校验

## 3. `python scripts/validate/validate_all.py`

用途：

- 作为统一入口，顺序运行：
  - `python scripts/validate/validate_evidence.py`
  - `python scripts/validate/validate_canonical_data_integrity.py`
- 任一步失败即返回非零退出码

推荐使用场景：

- PR 前统一自检
- 想要只记一个命令时

CI 入口：

- GitHub Actions `validate.yml` 会调用 `python scripts/validate/validate_all.py`
- 随后会运行聚焦测试：`python -m pytest -q tests/test_canonical_data_integrity.py tests/test_validate_all.py`
