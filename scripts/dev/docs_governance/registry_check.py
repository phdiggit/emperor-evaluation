from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from . import constants as c
from .paths import (
    _load_json_file,
    _path_exists,
    _resolve_repo_path,
    _tracked_archive_docs,
    _tracked_current_docs,
    _uses_forward_slashes,
    _valid_repo_target_path,
    _worktree_archive_docs,
    _worktree_current_docs,
    normalize_repo_path,
)


def _strip_markdown_fenced_code(text: str) -> str:
    visible_lines: list[str] = []
    in_fence = False
    fence_marker = ""
    for line in text.splitlines():
        stripped = line.lstrip()
        marker = stripped[:3]
        if marker in {"```", "~~~"}:
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif marker == fence_marker:
                in_fence = False
                fence_marker = ""
            visible_lines.append("")
            continue
        if not in_fence:
            visible_lines.append(line)
    return "\n".join(visible_lines)


def check_registry(registry_path: str = c.REGISTRY_PATH, worktree: bool = False) -> list[str]:
    problems: list[str] = []
    registry_file = _resolve_repo_path(registry_path)
    if not registry_file.exists():
        return [f"{registry_path}: registry file is missing"]
    if registry_file.read_bytes().startswith(b"\xef\xbb\xbf"):
        problems.append(f"{registry_path}: must be UTF-8 without BOM")
    try:
        registry = _load_json_file(registry_path)
    except ValueError as exc:
        return [str(exc)]

    if registry.get("schema_version") != c.SUPPORTED_SCHEMA_VERSION:
        problems.append(f"{registry_path}: unsupported schema_version {registry.get('schema_version')!r}")
    docs_agents = _resolve_repo_path("docs/AGENTS.md")
    if not docs_agents.is_file():
        problems.append("docs/AGENTS.md: file is missing")
    else:
        budget = registry.get("docs_agents_budget", {})
        max_lines = int(budget.get("max_lines", 0))
        max_bytes = int(budget.get("max_bytes", 0))
        lines = len(docs_agents.read_text(encoding="utf-8").splitlines())
        byte_count = len(docs_agents.read_bytes())
        if max_lines and lines > max_lines:
            problems.append(f"docs/AGENTS.md: {lines} lines exceeds {max_lines}")
        if max_bytes and byte_count > max_bytes:
            problems.append(f"docs/AGENTS.md: {byte_count} bytes exceeds {max_bytes}")
    root_agents = _resolve_repo_path("AGENTS.md")
    if not root_agents.is_file() or "docs/AGENTS.md" not in root_agents.read_text(encoding="utf-8"):
        problems.append("AGENTS.md: missing route to docs/AGENTS.md")

    allowed_types = set(registry.get("allowed_document_types", []))
    allowed_statuses = set(registry.get("allowed_lifecycle_statuses", []))
    allowed_actions = set(registry.get("allowed_proposed_actions", []))
    allowed_content_roles = set(registry.get("allowed_content_roles", []))
    allowed_placement_actions = set(registry.get("allowed_placement_actions", []))
    if allowed_types != c.ALLOWED_DOCUMENT_TYPES:
        problems.append(f"{registry_path}: allowed_document_types do not match supported set")
    if allowed_statuses != c.ALLOWED_LIFECYCLE_STATUSES:
        problems.append(f"{registry_path}: allowed_lifecycle_statuses do not match supported set")
    if allowed_actions != c.ALLOWED_PROPOSED_ACTIONS:
        problems.append(f"{registry_path}: allowed_proposed_actions do not match supported set")
    if allowed_content_roles != c.ALLOWED_CONTENT_ROLES:
        problems.append(f"{registry_path}: allowed_content_roles do not match supported set")
    if allowed_placement_actions != c.ALLOWED_PLACEMENT_ACTIONS:
        problems.append(f"{registry_path}: allowed_placement_actions do not match supported set")

    documents = registry.get("documents", [])
    if not isinstance(documents, list):
        return sorted(problems + [f"{registry_path}: documents must be a list"])
    by_path: dict[str, dict[str, Any]] = {}
    for doc in documents:
        path = doc.get("path")
        if not path:
            problems.append(f"{registry_path}: document missing path")
            continue
        if path in by_path:
            problems.append(f"{path}: duplicate document path")
        by_path[path] = doc
        if not _path_exists(path):
            problems.append(f"{path}: document path missing")
        document_type = doc.get("document_type")
        lifecycle_status = doc.get("lifecycle_status")
        proposed_action = doc.get("proposed_action")
        content_role = doc.get("content_role")
        placement_action = doc.get("placement_action")
        if document_type not in c.ALLOWED_DOCUMENT_TYPES:
            problems.append(f"{path}: invalid document_type {document_type!r}")
        if lifecycle_status not in c.ALLOWED_LIFECYCLE_STATUSES:
            problems.append(f"{path}: invalid lifecycle_status {lifecycle_status!r}")
        if proposed_action not in c.ALLOWED_PROPOSED_ACTIONS:
            problems.append(f"{path}: invalid proposed_action {proposed_action!r}")
        if content_role not in c.ALLOWED_CONTENT_ROLES:
            problems.append(f"{path}: invalid content_role {content_role!r}")
        if placement_action not in c.ALLOWED_PLACEMENT_ACTIONS:
            problems.append(f"{path}: invalid placement_action {placement_action!r}")
        replacement = doc.get("replacement_path")
        if replacement and not _path_exists(replacement):
            problems.append(f"{path}: replacement_path does not exist: {replacement}")
        reason = str(doc.get("reason") or "").strip()
        placement_reason = str(doc.get("placement_reason") or "").strip()
        placement_targets = doc.get("placement_targets")
        if not isinstance(placement_targets, list):
            problems.append(f"{path}: placement_targets must be a list")
            placement_targets = []
        for target in placement_targets:
            if not isinstance(target, str):
                problems.append(f"{path}: placement_targets entries must be strings")
                continue
            if not _valid_repo_target_path(target):
                problems.append(f"{path}: placement_targets must be repo-relative controlled paths using forward slashes: {target}")
        if not isinstance(doc.get("semantic_verification_required"), bool):
            problems.append(f"{path}: semantic_verification_required must be boolean")
        if placement_action not in c.KEEP_OR_REVIEW_PLACEMENT_ACTIONS:
            if not placement_targets:
                problems.append(f"{path}: placement_action={placement_action} requires non-empty placement_targets")
            if not placement_reason:
                problems.append(f"{path}: placement_action={placement_action} requires non-empty placement_reason")
        if content_role == "generated_output" and placement_action == "keep_in_docs":
            problems.append(f"{path}: content_role=generated_output cannot use placement_action=keep_in_docs")
        if content_role == "mixed" and placement_action not in {"split_keep_rules_generate_state", "review"}:
            problems.append(f"{path}: content_role=mixed requires placement_action split_keep_rules_generate_state or review")
        if content_role == "instance_record" and placement_action == "absorb_into_canonical_data_then_export":
            if doc.get("semantic_verification_required") is not True:
                problems.append(
                    f"{path}: instance_record with absorb_into_canonical_data_then_export requires semantic_verification_required=true"
                )
        if content_role == "instance_record" and lifecycle_status == "delete_candidate":
            problems.append(f"{path}: content_role=instance_record cannot use lifecycle_status=delete_candidate")
        if placement_action == "keep_archive_exception" and not path.startswith(c.ARCHIVE_DOCS_ROOT):
            problems.append(f"{path}: placement_action=keep_archive_exception is only allowed under {c.ARCHIVE_DOCS_ROOT}")
        if placement_action == "keep_governance_exception" and not path.startswith("docs/文档与脚本登记/"):
            allowed_governance_paths = set(registry.get("governance_exception_paths", []))
            if path not in allowed_governance_paths:
                problems.append(
                    f"{path}: placement_action=keep_governance_exception is only allowed under docs/文档与脚本登记/ or governance_exception_paths"
                )
        if lifecycle_status == "generated" and placement_action in {"keep_in_docs", "keep_archive_exception"}:
            problems.append(f"{path}: lifecycle_status=generated conflicts with placement_action={placement_action}")
        if proposed_action == "regenerate_only" and placement_action == "keep_in_docs":
            problems.append(f"{path}: proposed_action=regenerate_only conflicts with placement_action=keep_in_docs")
        if proposed_action == "delete" or lifecycle_status == "delete_candidate":
            if not reason:
                problems.append(f"{path}: delete candidate requires non-empty reason")
            if doc.get("human_confirmation_required") is not True:
                problems.append(f"{path}: delete candidate requires human_confirmation_required=true")
        if doc.get("unique_source_risk") is True and proposed_action == "delete":
            problems.append(f"{path}: unique_source_risk=true cannot use proposed_action=delete")
        if document_type == "generated_view" and not doc.get("generator_candidates") and lifecycle_status != "needs_human_confirmation":
            problems.append(f"{path}: generated_view requires generator_candidates or needs_human_confirmation")
        if document_type == "canonical_spec" and lifecycle_status == "active" and proposed_action == "delete":
            problems.append(f"{path}: active canonical document cannot be marked delete")
        for field in ("inbound_references", "referenced_by_tests", "generator_candidates"):
            for candidate in doc.get(field, []):
                if not _path_exists(candidate):
                    problems.append(f"{path}: {field} path does not exist: {candidate}")

    project_driver_paths = registry.get("project_driver_paths")
    if not isinstance(project_driver_paths, list) or not project_driver_paths:
        problems.append(f"{registry_path}: project_driver_paths must be a non-empty list")
        project_driver_paths = []
    archived_paths = registry.get("archived_document_paths") or {}
    archived_old_paths = set(archived_paths) if isinstance(archived_paths, dict) else set()
    archived_new_paths = set(archived_paths.values()) if isinstance(archived_paths, dict) else set()
    retired_generated_paths = registry.get("retired_generated_document_paths", {})
    retired_mixed_paths = registry.get("retired_mixed_document_paths", {})
    replacement_targets = {
        str(doc.get("replacement_path"))
        for doc in documents
        if doc.get("replacement_path")
    }
    for driver_path in project_driver_paths:
        if not isinstance(driver_path, str) or not driver_path:
            problems.append(f"{registry_path}: project_driver_paths entries must be non-empty strings")
            continue
        if not _valid_repo_target_path(driver_path) or not driver_path.startswith("docs/"):
            problems.append(f"{driver_path}: project driver path must be a repo-relative docs path")
            continue
        driver_doc = by_path.get(driver_path)
        if driver_doc is None:
            problems.append(f"{driver_path}: project driver is not registered in documents")
            continue
        if not _path_exists(driver_path):
            problems.append(f"{driver_path}: project driver path missing")
            continue
        expected_driver_fields = {
            "document_type": "canonical_spec",
            "lifecycle_status": "active",
            "proposed_action": "keep",
            "content_role": "rule_or_method",
            "placement_action": "keep_in_docs",
            "unique_source_risk": True,
        }
        for field, expected in expected_driver_fields.items():
            if driver_doc.get(field) != expected:
                problems.append(f"{driver_path}: project driver requires {field}={expected!r}")
        if driver_path in archived_old_paths or driver_path in archived_new_paths:
            problems.append(f"{driver_path}: project driver must not appear in archived_document_paths")
        if driver_path in replacement_targets or driver_doc.get("replacement_path"):
            problems.append(f"{driver_path}: project driver must not be replaced by replacement_path")
        if driver_doc.get("lifecycle_status") in {"archive_candidate", "delete_candidate"}:
            problems.append(f"{driver_path}: project driver cannot be an archive/delete candidate")
        if driver_doc.get("proposed_action") in {"archive", "delete"}:
            problems.append(f"{driver_path}: project driver cannot use proposed_action={driver_doc.get('proposed_action')}")
        text = _resolve_repo_path(driver_path).read_text(encoding="utf-8")
        if not text.strip():
            problems.append(f"{driver_path}: project driver document must not be empty")
        for marker in c.PROJECT_DRIVER_REQUIRED_MARKERS:
            if marker not in text:
                problems.append(f"{driver_path}: project driver document missing marker: {marker}")

    current_docs = _worktree_current_docs() if worktree else _tracked_current_docs()
    archive_docs = _worktree_archive_docs() if worktree else _tracked_archive_docs()
    expected_docs = (set(current_docs) | set(archive_docs)) - {normalize_repo_path(registry_path)}
    actual_docs = set(by_path)
    for missing in sorted(expected_docs - actual_docs):
        mode = "worktree" if worktree else "tracked"
        problems.append(f"{missing}: {mode} docs file is not covered by docs registry")
    for extra in sorted(actual_docs - expected_docs):
        mode = "worktree" if worktree else "tracked"
        problems.append(f"{extra}: registry path is not a {mode} docs file")

    public_policy = registry.get("docs_public_experience_policy") or {}
    if public_policy and not isinstance(public_policy, dict):
        problems.append(f"{registry_path}: docs_public_experience_policy must be an object")
        public_policy = {}
    enforce_current_adr_closed = public_policy.get("current_adr_root_closed") is True
    enforce_chinese_filenames = public_policy.get("human_markdown_filename_requires_chinese") is True
    enforce_chinese_body = public_policy.get("human_markdown_body_requires_chinese") is True
    density_threshold = int(public_policy.get("module_density_threshold", c.MODULE_DENSITY_THRESHOLD))
    technical_filename_exceptions_raw = public_policy.get("technical_filename_exceptions", sorted(c.TECHNICAL_DOC_FILENAMES))
    if not isinstance(technical_filename_exceptions_raw, list) or not all(
        isinstance(item, str) for item in technical_filename_exceptions_raw
    ):
        problems.append(f"{registry_path}: technical_filename_exceptions must be a list of strings")
        technical_filename_exceptions_raw = sorted(c.TECHNICAL_DOC_FILENAMES)
    technical_filename_exceptions = set(technical_filename_exceptions_raw) | c.TECHNICAL_DOC_FILENAMES
    english_marker_exceptions_raw = public_policy.get("english_prose_marker_exceptions", [])
    if not isinstance(english_marker_exceptions_raw, list) or not all(
        isinstance(item, str) for item in english_marker_exceptions_raw
    ):
        problems.append(f"{registry_path}: english_prose_marker_exceptions must be a list of strings")
        english_marker_exceptions_raw = []
    english_marker_exceptions = set(english_marker_exceptions_raw)

    current_markdown_docs = sorted(path for path in current_docs if path.endswith(".md"))
    direct_module_counts: dict[str, int] = defaultdict(int)
    for path in current_markdown_docs:
        if enforce_current_adr_closed and path.startswith(c.CURRENT_ADR_ROOT):
            problems.append(f"{path}: current docs/adr is closed; move ADR history to archive/docs/adr or merge into a Chinese module document")
        filename = path.rsplit("/", 1)[-1]
        filename_has_exception = filename in technical_filename_exceptions or path in technical_filename_exceptions
        if enforce_chinese_filenames and not filename_has_exception:
            if not c.CJK_RE.search(filename):
                problems.append(f"{path}: human-facing Markdown filename must contain Chinese characters")
            if c.ADR_FILENAME_RE.search(filename):
                problems.append(f"{path}: human-facing Markdown filename must not contain ADR unless listed in technical_filename_exceptions")
        if enforce_chinese_body:
            try:
                text = _resolve_repo_path(path).read_text(encoding="utf-8")
            except UnicodeDecodeError:
                problems.append(f"{path}: Markdown file must be UTF-8")
                text = ""
            if text and not c.CJK_RE.search(text):
                problems.append(f"{path}: human-facing Markdown body must contain Chinese prose")
            if text and path not in english_marker_exceptions:
                visible_text = _strip_markdown_fenced_code(text)
                for marker_name, marker_re in c.ENGLISH_GOVERNANCE_PROSE_MARKERS:
                    if marker_re.search(visible_text):
                        problems.append(
                            f"{path}: human-facing Markdown body contains English governance/ADR prose marker outside code blocks: {marker_name}"
                        )
        parts = path.split("/")
        if len(parts) == 3:
            direct_module_counts["/".join(parts[:2])] += 1

    density_reviews = registry.get("docs_module_density_reviews", [])
    if not isinstance(density_reviews, list):
        problems.append(f"{registry_path}: docs_module_density_reviews must be a list")
        density_reviews = []
    density_by_module: dict[str, dict[str, Any]] = {}
    for review in density_reviews:
        if not isinstance(review, dict):
            problems.append(f"{registry_path}: docs_module_density_reviews entries must be objects")
            continue
        module_path = review.get("module_path")
        if not isinstance(module_path, str) or not module_path.startswith("docs/"):
            problems.append(f"{registry_path}: docs_module_density_reviews entries require module_path under docs/")
            continue
        density_by_module[module_path] = review
        if review.get("review_status") != "reviewed":
            problems.append(f"{module_path}: density review must use review_status=reviewed")
        if not str(review.get("decision") or "").strip():
            problems.append(f"{module_path}: density review requires non-empty decision")
    for module_path, count in sorted(direct_module_counts.items()):
        if count <= density_threshold:
            continue
        review = density_by_module.get(module_path)
        if review is None:
            problems.append(f"{module_path}: {count} direct Markdown files exceeds {density_threshold} without density review")
            continue
        if review.get("direct_markdown_count") != count:
            problems.append(f"{module_path}: density review direct_markdown_count must be {count}")

    topic_reviews = registry.get("docs_topic_family_reviews", [])
    if not isinstance(topic_reviews, list):
        problems.append(f"{registry_path}: docs_topic_family_reviews must be a list")
        topic_reviews = []
    for review in topic_reviews:
        if not isinstance(review, dict):
            problems.append(f"{registry_path}: docs_topic_family_reviews entries must be objects")
            continue
        family_name = str(review.get("family_name") or "").strip()
        paths = review.get("paths")
        if not family_name:
            problems.append(f"{registry_path}: docs_topic_family_reviews entries require family_name")
        if not isinstance(paths, list) or not paths:
            problems.append(f"{family_name or registry_path}: topic family review requires non-empty paths")
            continue
        for path in paths:
            if path not in current_markdown_docs:
                problems.append(f"{family_name}: topic family path is not a current Markdown doc: {path}")
        if len(paths) > 3 and review.get("review_status") != "reviewed":
            problems.append(f"{family_name}: topic family with more than 3 docs requires review_status=reviewed")
        if not str(review.get("decision") or "").strip():
            problems.append(f"{family_name}: topic family review requires non-empty decision")

    exact_groups: dict[str, list[str]] = defaultdict(list)
    for doc in documents:
        group = doc.get("duplicate_group") or doc.get("exact_duplicate_group")
        if group:
            exact_groups[str(group)].append(doc.get("path", ""))
    for group, paths in sorted(exact_groups.items()):
        if len(paths) < 2:
            problems.append(f"{registry_path}: duplicate group {group} has fewer than two members")

    archived_paths = registry.get("archived_document_paths", {})
    if archived_paths is None:
        archived_paths = {}
    if not isinstance(archived_paths, dict):
        problems.append(f"{registry_path}: archived_document_paths must be an object")
    else:
        new_to_old: dict[str, list[str]] = defaultdict(list)
        for old_path, new_path in archived_paths.items():
            if not isinstance(old_path, str) or not isinstance(new_path, str):
                problems.append(f"{registry_path}: archived_document_paths entries must map strings to strings")
                continue
            new_to_old[new_path].append(old_path)
            if not _uses_forward_slashes(old_path) or not _uses_forward_slashes(new_path):
                problems.append(f"{old_path}: archived_document_paths must use forward slashes")
            if not old_path.startswith("docs/") or old_path.startswith(c.DOCS_ARCHIVE_OLD_ROOT) or "/../" in old_path:
                problems.append(f"{old_path}: archived old path must be a retired docs path outside {c.DOCS_ARCHIVE_OLD_ROOT}")
            if not new_path.startswith(c.ARCHIVE_DOCS_ROOT):
                problems.append(f"{old_path}: archived path must be under {c.ARCHIVE_DOCS_ROOT}: {new_path}")
            if _path_exists(old_path):
                problems.append(f"{old_path}: archived old path still exists")
            if not _path_exists(new_path):
                problems.append(f"{old_path}: archived path does not exist: {new_path}")
            if old_path in by_path:
                problems.append(f"{old_path}: archived old path is still registered as a document")
            new_doc = by_path.get(new_path)
            if new_doc is None:
                problems.append(f"{old_path}: archived path is not registered as a document: {new_path}")
                continue
            if new_doc.get("lifecycle_status") != "historical":
                problems.append(f"{new_path}: archived document must use lifecycle_status=historical")
            if new_doc.get("proposed_action") != "keep":
                problems.append(f"{new_path}: archived document must use proposed_action=keep")
            if new_doc.get("human_confirmation_required") is not False:
                problems.append(f"{new_path}: archived document must use human_confirmation_required=false")
        for new_path, old_values in sorted(new_to_old.items()):
            if len(old_values) > 1:
                problems.append(f"{new_path}: archived path is mapped from multiple old paths")

    if retired_generated_paths is None:
        retired_generated_paths = {}
    if not isinstance(retired_generated_paths, dict):
        problems.append(f"{registry_path}: retired_generated_document_paths must be an object")
    else:
        target_to_old: dict[str, list[str]] = defaultdict(list)
        for old_path, target_path in retired_generated_paths.items():
            if not isinstance(old_path, str) or not isinstance(target_path, str):
                problems.append(f"{registry_path}: retired_generated_document_paths entries must map strings to strings")
                continue
            if (
                not _valid_repo_target_path(old_path)
                or not old_path.startswith("docs/")
                or old_path.startswith(c.DOCS_ARCHIVE_OLD_ROOT)
            ):
                problems.append(f"{old_path}: retired generated old path must be under docs/ outside {c.DOCS_ARCHIVE_OLD_ROOT}")
                continue
            if not _valid_repo_target_path(target_path) or not target_path.startswith("exports/"):
                problems.append(f"{old_path}: retired generated target must be under exports/: {target_path}")
                continue
            target_to_old[target_path].append(old_path)
            if _path_exists(old_path):
                problems.append(f"{old_path}: retired generated old path still exists")
            if old_path in by_path:
                problems.append(f"{old_path}: retired generated old path is still registered as a document")
            if old_path in project_driver_paths:
                problems.append(f"{old_path}: project driver cannot be a retired generated old path")
            if old_path in archived_old_paths:
                problems.append(f"{old_path}: retired generated old path conflicts with archived_document_paths")
            target = _resolve_repo_path(target_path)
            if not target.is_file():
                problems.append(f"{old_path}: retired generated target does not exist or is not a file: {target_path}")
        for target_path, old_values in sorted(target_to_old.items()):
            if len(old_values) > 1:
                problems.append(f"{target_path}: retired generated target is mapped from multiple old paths")

    if retired_mixed_paths is None:
        retired_mixed_paths = {}
    if not isinstance(retired_mixed_paths, dict):
        problems.append(f"{registry_path}: retired_mixed_document_paths must be an object")
    else:
        retired_generated_old_paths = set(retired_generated_paths) if isinstance(retired_generated_paths, dict) else set()
        target_to_old: dict[str, list[str]] = defaultdict(list)
        for old_path, target_path in retired_mixed_paths.items():
            if not isinstance(old_path, str) or not isinstance(target_path, str):
                problems.append(f"{registry_path}: retired_mixed_document_paths entries must map strings to strings")
                continue
            if (
                not _valid_repo_target_path(old_path)
                or not old_path.startswith("docs/")
                or old_path.startswith(c.DOCS_ARCHIVE_OLD_ROOT)
            ):
                problems.append(f"{old_path}: retired mixed old path must be under docs/ outside {c.DOCS_ARCHIVE_OLD_ROOT}")
                continue
            if (
                not _valid_repo_target_path(target_path)
                or not (target_path.startswith("exports/") or target_path.startswith(c.ARCHIVE_DOCS_ROOT))
            ):
                problems.append(f"{old_path}: retired mixed target must be under exports/ or {c.ARCHIVE_DOCS_ROOT}: {target_path}")
                continue
            target_to_old[target_path].append(old_path)
            if _path_exists(old_path):
                problems.append(f"{old_path}: retired mixed old path still exists")
            if old_path in by_path:
                problems.append(f"{old_path}: retired mixed old path is still registered as a document")
            if old_path in project_driver_paths:
                problems.append(f"{old_path}: project driver cannot be a retired mixed old path")
            if old_path in archived_old_paths:
                problems.append(f"{old_path}: retired mixed old path conflicts with archived_document_paths")
            if old_path in retired_generated_old_paths:
                problems.append(f"{old_path}: retired mixed old path conflicts with retired_generated_document_paths")
            target = _resolve_repo_path(target_path)
            if not target.is_file():
                problems.append(f"{old_path}: retired mixed target does not exist or is not a file: {target_path}")
        for target_path, old_values in sorted(target_to_old.items()):
            if len(old_values) > 1:
                problems.append(f"{target_path}: retired mixed target is mapped from multiple old paths")

    return sorted(set(problems))
