from emperor_v4.evaluation.profile_text_quality import audit_record
from emperor_v4.evaluation.profile_text_cleanup import prune_redundant_limitations


def kinds(issues):
    return {(issue.severity, issue.kind) for issue in issues}


def test_truncated_fragment_is_hard_error():
    record = {
        "ruler_id": "RULER-TEST",
        "ruler_name": "测试人物",
        "grade_basis": "这是一段被截断的定档依据，这些正证真实",
    }
    assert ("error", "truncated_fragment") in kinds(audit_record("C2", record))


def test_exact_grade_position_duplicate_is_warning_not_hard_error():
    record = {
        "ruler_id": "RULER-TEST",
        "ruler_name": "测试人物",
        "grade_basis": "跨阶段表现稳定，但仍有明确边界，因此维持当前档位。",
        "position_basis": "跨阶段表现稳定，但仍有明确边界，因此维持当前档位。",
    }
    issues = audit_record("C4", record)
    assert ("warning", "exact_duplicate") in kinds(issues)
    assert not any(issue.severity == "error" for issue in issues)


def test_duplicate_limitation_is_hard_error_and_cleanup_is_lossless():
    text = "晚期反馈链不足，限制上沿。"
    record = {
        "ruler_id": "RULER-TEST",
        "ruler_name": "测试人物",
        "grade_basis": text,
        "limitations": [text, "另有一条独立证据边界。"],
    }
    assert ("error", "duplicates_other_field") in kinds(audit_record("M5", record))
    removed = prune_redundant_limitations(record)
    assert removed == 1
    assert record["grade_basis"] == text
    assert record["limitations"] == ["另有一条独立证据边界。"]
