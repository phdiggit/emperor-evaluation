from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = "docs/文档与脚本登记/scripts_registry.json"
TEXT_SUFFIXES = {
    ".csv",
    ".json",
    ".jsonl",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".sql",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
BLOCKED_BINARY_SUFFIXES = {
    ".db",
    ".docx",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".pptx",
    ".sqlite",
    ".webp",
    ".xlsx",
    ".zip",
}
SUPPORTED_SCHEMA_VERSION = 1
ALLOWED_MODULE_STATUSES = {"active", "migrated", "unmigrated", "stable_entrypoint"}
ALLOWED_LEGACY_WRAPPER_POLICIES = {"active", "retired"}


def _repo_root() -> Path:
    return ROOT.resolve()


def _resolve_repo_path(path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    resolved = candidate.resolve(strict=False)
    root = _repo_root()
    try:
        resolved.relative_to(root)
    except ValueError as exc:  # pragma: no cover - exercised via tests
        raise ValueError(f"path escapes repo root: {path}") from exc
    return resolved


def _repo_relative(path: Path) -> str:
    return normalize_repo_path(str(path.resolve(strict=False).relative_to(_repo_root())))


def _ensure_allowed_text_path(path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix in BLOCKED_BINARY_SUFFIXES:
        raise ValueError(f"binary files are not supported: {path}")
    if suffix not in TEXT_SUFFIXES:
        raise ValueError(f"unsupported text file extension: {path}")


def _read_utf8_text(path: Path) -> str:
    _ensure_allowed_text_path(path)
    return path.read_text(encoding="utf-8-sig")


def read_text_file(path: str | Path) -> str:
    resolved = _resolve_repo_path(path)
    return _read_utf8_text(resolved)


def write_text_file(path: str | Path, source: str | Path) -> None:
    target = _resolve_repo_path(path)
    _ensure_allowed_text_path(target)
    text = Path(source).read_text(encoding="utf-8-sig")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def replace_text_file(path: str | Path, old: str, new: str) -> int:
    target = _resolve_repo_path(path)
    text = _read_utf8_text(target)
    count = text.count(old)
    if count == 0:
        raise ValueError(f"old text not found: {old}")
    target.write_text(text.replace(old, new), encoding="utf-8")
    return count


def git_output_bytes(*args: str, check: bool = True) -> bytes:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=_repo_root(),
        capture_output=True,
        text=False,
        check=False,
    )
    returncode = getattr(result, "returncode", 0)
    if check and returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {stderr}")
    return result.stdout


def git_output_text(*args: str, check: bool = True) -> str:
    return git_output_bytes(*args, check=check).decode("utf-8")


def git_output_lines(*args: str) -> list[str]:
    return git_output_text(*args).splitlines()


def git_ref_sha(ref: str) -> str:
    return git_output_text("rev-parse", ref).strip()


def git_merge_base(base: str, head: str) -> str:
    return git_output_text("merge-base", base, head).strip()


def normalize_repo_path(path: str) -> str:
    return path.strip().replace("\\", "/")


def git_changed_files(*args: str, ignore_prefixes: tuple[str, ...] = (".tmp/",)) -> list[str]:
    paths = {
        normalize_repo_path(line)
        for line in git_output_lines(*args)
        if line.strip()
    }
    return sorted(
        path for path in paths if not any(path.startswith(prefix) for prefix in ignore_prefixes)
    )


def changed_files(base: str = "origin/GPT...HEAD") -> list[str]:
    return git_changed_files("diff", "--name-only", base)


def status_files() -> list[str]:
    paths: set[str] = set()
    for line in git_output_lines("status", "--short", "--untracked-files=normal"):
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.rsplit(" -> ", 1)[1]
        normalized = normalize_repo_path(path)
        if normalized.startswith(".tmp/"):
            continue
        paths.add(normalized)
    return sorted(paths)


def git_tracked_files(ref: str) -> list[str]:
    return sorted(
        normalize_repo_path(line)
        for line in git_output_lines("ls-tree", "-r", "--name-only", ref)
        if line.strip()
    )


def load_registry(path: str | Path = REGISTRY_PATH) -> dict[str, Any]:
    resolved = _resolve_repo_path(path)
    try:
        return json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{normalize_repo_path(str(path))}: invalid JSON: {exc}") from exc


def write_json_output(payload: dict[str, Any], output: str | None = None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output:
        target = _resolve_repo_path(output)
        if not _repo_relative(target).startswith(".tmp/"):
            raise ValueError(f"output must be under .tmp/: {output}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
        return
    _emit_stdout(text)


def _emit_stdout(text: str) -> None:
    sys.stdout.buffer.write(text.encode("utf-8"))


def _emit_stdout_lines(lines: list[str]) -> None:
    payload = "\n".join(lines)
    if payload:
        payload += "\n"
    _emit_stdout(payload)


def _emit_stderr(message: str) -> None:
    sys.stderr.buffer.write((message + "\n").encode("utf-8"))


def _top_level_counts(paths: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in paths:
        top = path.split("/", 1)[0]
        counts[top] = counts.get(top, 0) + 1
    return dict(sorted(counts.items()))


def _script_directory_categories() -> list[tuple[str, str]]:
    directories: dict[str, str] = {}
    try:
        registry = load_registry()
        directories.update(registry.get("directories", {}))
    except (OSError, ValueError):
        pass
    for key in ("dev", "validate", "export", "shared"):
        directories.setdefault(key, f"scripts/{key}")
    categories = [
        (
            key,
            normalize_repo_path(rel_path).rstrip("/"),
        )
        for key, rel_path in directories.items()
        if normalize_repo_path(rel_path).startswith("scripts/")
    ]
    return sorted(categories, key=lambda item: (-len(item[1]), item[0]))


def _script_category(path: str, directory_categories: list[tuple[str, str]] | None = None) -> str | None:
    if not path.startswith("scripts/"):
        return None
    for category, directory in directory_categories or _script_directory_categories():
        if path.startswith(f"{directory}/"):
            return category
    if path.count("/") == 1:
        return "root"
    return "other"


def build_snapshot(ref: str = "origin/GPT") -> dict[str, Any]:
    files = git_tracked_files(ref)
    directory_categories = _script_directory_categories()
    scripts = {key: [] for key, _ in directory_categories}
    scripts.update({"root": [], "other": []})
    for path in files:
        category = _script_category(path, directory_categories)
        if category:
            scripts[category].append(path)
    return {
        "agents_files": [path for path in files if path.endswith("AGENTS.md")],
        "ref": ref,
        "ref_sha": git_ref_sha(ref),
        "registry_path": REGISTRY_PATH,
        "schema_version": 1,
        "scripts": scripts,
        "tests": [path for path in files if path.startswith("tests/")],
        "top_level_counts": _top_level_counts(files),
        "tracked_files": files,
    }


def _parse_name_status(base_sha: str, head: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for line in git_output_lines("diff", "--name-status", "--find-renames", base_sha, head):
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith("R") and len(parts) >= 3:
            entries.append({"old_path": normalize_repo_path(parts[1]), "path": normalize_repo_path(parts[2]), "status": "R"})
        elif len(parts) >= 2:
            entries.append({"old_path": None, "path": normalize_repo_path(parts[1]), "status": status[0]})
    return entries


def _parse_numstat(base_sha: str, head: str) -> dict[str, dict[str, int | None]]:
    stats: dict[str, dict[str, int | None]] = {}
    for line in git_output_lines("diff", "--numstat", "--find-renames", base_sha, head):
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        additions = None if parts[0] == "-" else int(parts[0])
        deletions = None if parts[1] == "-" else int(parts[1])
        path = _parse_numstat_path(parts[-1])
        stats[path] = {"additions": additions, "deletions": deletions}
    return stats


def _parse_numstat_path(path: str) -> str:
    normalized = normalize_repo_path(path)
    if " => " not in normalized:
        return normalized
    arrow_index = normalized.index(" => ")
    open_index = normalized.rfind("{", 0, arrow_index)
    close_index = normalized.find("}", arrow_index)
    if open_index != -1 and close_index != -1:
        prefix = normalized[:open_index]
        suffix = normalized[close_index + 1 :]
        body = normalized[open_index + 1 : close_index]
        return prefix + body.split(" => ", 1)[1] + suffix
    return normalized.split(" => ", 1)[1]


def _tests_related_to(paths: list[str]) -> list[str]:
    tests_dir = _repo_root() / "tests"
    if not tests_dir.exists():
        return []
    needles = {Path(path).name for path in paths}
    needles |= {Path(path).stem for path in paths}
    related: set[str] = set()
    for test_path in sorted(tests_dir.glob("test_*.py")):
        text = test_path.read_text(encoding="utf-8", errors="ignore")
        if any(needle and needle in text for needle in needles):
            related.add(_repo_relative(test_path))
    return sorted(related)


def _registry_modules_for_paths(registry: dict[str, Any], paths: set[str]) -> list[str]:
    matched: list[str] = []
    for module in registry.get("modules", []):
        module_paths = {module.get("implementation"), module.get("legacy_wrapper")}
        if paths & {path for path in module_paths if path}:
            matched.append(module["id"])
    return sorted(matched)


def _match_one(path: str, pattern: str) -> bool:
    normalized = normalize_repo_path(path)
    normalized_pattern = normalize_repo_path(pattern)
    if normalized_pattern.endswith("/**"):
        return normalized.startswith(normalized_pattern[:-3] + "/")
    return fnmatch.fnmatchcase(normalized, normalized_pattern)


def match_patterns(path: str, patterns: list[str]) -> list[str]:
    return [pattern for pattern in patterns if _match_one(path, pattern)]


def _diff_patch_contains(base_sha: str, head: str, path: str, needle: str) -> bool:
    patch = git_output_text("diff", base_sha, head, "--", path, check=False)
    return needle in patch


def _path_risks(
    base_sha: str,
    head: str,
    changed_entries: list[dict[str, Any]],
    registry: dict[str, Any],
    changed_paths: set[str],
) -> list[dict[str, str]]:
    risks: list[dict[str, str]] = []
    for entry in changed_entries:
        path = entry["path"]
        if entry["status"] == "R" and path.endswith(".py"):
            risks.append({"path": path, "risk": "moved_python_file"})
        for needle, risk in (("__file__", "patch_touches_dunder_file"), ("parents[", "patch_touches_parents"), ("ROOT", "patch_touches_root")):
            if _diff_patch_contains(base_sha, head, path, needle):
                risks.append({"path": path, "risk": risk})

    for module in registry.get("modules", []):
        implementation = module.get("implementation")
        wrapper = module.get("legacy_wrapper")
        if implementation and wrapper and {implementation, wrapper} <= changed_paths:
            risks.append({"path": implementation, "risk": f"implementation_and_wrapper_changed:{module['id']}"})
        for entry in changed_entries:
            if entry["status"] == "R" and entry.get("old_path") in {implementation, wrapper}:
                risks.append({"path": entry["path"], "risk": f"registry_module_path_changed:{module['id']}"})
    return sorted(risks, key=lambda item: (item["path"], item["risk"]))


def build_pr_context(base: str = "origin/GPT", head: str = "HEAD") -> dict[str, Any]:
    registry = load_registry()
    base_sha = git_ref_sha(base)
    head_sha = git_ref_sha(head)
    merge_base_sha = git_merge_base(base, head)
    entries = _parse_name_status(merge_base_sha, head)
    stats_by_path = _parse_numstat(merge_base_sha, head)
    changed_files: list[dict[str, Any]] = []
    changed_paths: set[str] = set()
    renames: list[dict[str, str]] = []
    for entry in entries:
        path = entry["path"]
        changed_paths.add(path)
        item = {
            "additions": stats_by_path.get(path, {}).get("additions"),
            "deletions": stats_by_path.get(path, {}).get("deletions"),
            "old_path": entry.get("old_path"),
            "path": path,
            "status": entry["status"],
        }
        changed_files.append(item)
        if entry["status"] == "R" and entry.get("old_path"):
            renames.append({"old_path": entry["old_path"], "path": path})

    forbidden_hits = []
    forbidden_patterns = registry.get("default_forbidden_patterns", [])
    for path in sorted(changed_paths):
        matches = match_patterns(path, forbidden_patterns)
        if matches:
            forbidden_hits.append({"path": path, "patterns": matches})

    return {
        "base": base,
        "base_sha": base_sha,
        "changed_files": sorted(changed_files, key=lambda item: item["path"]),
        "forbidden_hits": forbidden_hits,
        "head": head,
        "head_sha": head_sha,
        "merge_base_sha": merge_base_sha,
        "path_risks": _path_risks(merge_base_sha, head, entries, registry, changed_paths),
        "registry_modules": _registry_modules_for_paths(registry, changed_paths),
        "related_tests": _tests_related_to(sorted(changed_paths)),
        "renames": sorted(renames, key=lambda item: item["path"]),
        "schema_version": 1,
        "stats": {
            "changed": len(changed_files),
            "renamed": len(renames),
        },
    }


def _collect_diff_paths(base: str) -> set[str]:
    return set(git_changed_files("diff", "--name-only", base, ignore_prefixes=()))


def _collect_status_paths() -> set[str]:
    paths: set[str] = set()
    for line in git_output_lines("status", "--short", "--untracked-files=normal"):
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.rsplit(" -> ", 1)[1]
        normalized = normalize_repo_path(path)
        if line.startswith("?? ") and normalized.endswith("/"):
            directory = _resolve_repo_path(normalized)
            if directory.is_dir():
                paths.update(
                    _repo_relative(child)
                    for child in directory.rglob("*")
                    if child.is_file()
                )
                continue
        paths.add(normalized)
    return paths


def collect_changed_paths(base: str) -> list[str]:
    paths = set()
    paths |= _collect_diff_paths(base)
    paths |= set(git_changed_files("diff", "--name-only", "--cached", ignore_prefixes=()))
    paths |= set(git_changed_files("diff", "--name-only", ignore_prefixes=()))
    paths |= _collect_status_paths()
    return sorted(path for path in paths if path)


def check_scope(
    base: str,
    forbid: list[str],
    allow: list[str],
    ignore: list[str],
    registry_path: str = REGISTRY_PATH,
) -> list[str]:
    registry = load_registry(registry_path)
    forbidden = forbid or list(registry.get("default_forbidden_patterns", []))
    ignored = [".tmp/**", *ignore]
    problems: list[str] = []
    for path in collect_changed_paths(base):
        if match_patterns(path, ignored):
            continue
        matches = match_patterns(path, forbidden)
        allow_matches = match_patterns(path, allow) if allow else []
        reasons: list[str] = []
        if matches:
            reasons.append("forbid=" + ",".join(matches))
        if allow and not allow_matches:
            reasons.append("not allowed by --allow")
        if reasons:
            problems.append(f"{path}: {'; '.join(reasons)}")
    return problems


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _byte_count(path: Path) -> int:
    return len(path.read_bytes())


def _root_script_files() -> set[str]:
    return {
        _repo_relative(path)
        for path in (_repo_root() / "scripts").glob("*.py")
        if path.is_file()
    }


def _wrapper_problems(path: str, module: dict[str, Any]) -> list[str]:
    wrapper = _resolve_repo_path(path)
    text = wrapper.read_text(encoding="utf-8")
    lines = text.splitlines()
    max_lines = int(module.get("max_wrapper_lines", 25))
    exception_reason = str(module.get("exception_reason", "")).strip()
    problems: list[str] = []
    if max_lines != 25 and not exception_reason:
        problems.append(f"{path}: custom max_wrapper_lines requires exception_reason")
    if len(lines) > max_lines:
        problems.append(f"{path}: wrapper has {len(lines)} lines, exceeds {max_lines}")
    suspicious = [
        "def validate",
        "def validate_",
        "def export",
        "def build",
        "VALIDATION_STEPS = [",
        "TRIAL_SCORE_MAP =",
        "DIMENSION_RULES =",
    ]
    for needle in suspicious:
        if needle in text:
            problems.append(f"{path}: wrapper appears to contain implementation marker {needle!r}")
    return problems


def _canonical_module_path(implementation: str) -> str:
    path = Path(normalize_repo_path(implementation))
    if path.suffix == ".py":
        path = path.with_suffix("")
    parts = path.parts
    if parts and parts[0] == "scripts":
        parts = parts[1:]
    return ".".join(parts)


def _legacy_wrapper_import_map(registry: dict[str, Any]) -> dict[str, str]:
    imports: dict[str, str] = {}
    modules_by_id = {
        module.get("id"): module
        for module in registry.get("modules", [])
        if module.get("id")
    }
    for module in registry.get("modules", []):
        implementation = module.get("implementation")
        legacy_wrapper = module.get("legacy_wrapper")
        if not implementation or not legacy_wrapper:
            continue
        imports[Path(legacy_wrapper).stem] = _canonical_module_path(implementation)
    retired_wrappers = registry.get("retired_legacy_wrappers", {})
    if not isinstance(retired_wrappers, dict):
        retired_wrappers = {}
    for retired_path, module_id in retired_wrappers.items():
        module = modules_by_id.get(module_id)
        implementation = module.get("implementation") if module else None
        if not implementation:
            continue
        imports[Path(retired_path).stem] = _canonical_module_path(implementation)
    return dict(sorted(imports.items()))


def _implementation_paths(registry: dict[str, Any]) -> list[str]:
    paths: set[str] = set()
    for module in registry.get("modules", []):
        implementation = module.get("implementation")
        if not implementation:
            continue
        if not implementation.endswith(".py"):
            continue
        path = _resolve_repo_path(implementation)
        if path.is_file():
            paths.add(normalize_repo_path(implementation))
    return sorted(paths)


def _legacy_import_problem(path: str, module_name: str, canonical_name: str) -> str:
    return f"{path}: imports legacy wrapper module {module_name!r}; use {canonical_name!r}"


def check_canonical_imports(
    registry_path: str = REGISTRY_PATH,
) -> list[str]:
    try:
        registry = load_registry(registry_path)
    except ValueError as exc:
        return [str(exc)]

    retired_wrappers = registry.get("retired_legacy_wrappers", {})
    if not isinstance(retired_wrappers, dict):
        return [f"{registry_path}: retired_legacy_wrappers must be an object"]

    legacy_imports = _legacy_wrapper_import_map(registry)
    if not legacy_imports:
        return []

    problems: list[str] = []
    for rel_path in _implementation_paths(registry):
        path = _resolve_repo_path(rel_path)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel_path)
        except SyntaxError as exc:
            problems.append(f"{rel_path}: SyntaxError at line {exc.lineno}: {exc.msg}")
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split(".", 1)[0]
                    canonical_name = legacy_imports.get(module_name)
                    if canonical_name:
                        problems.append(_legacy_import_problem(rel_path, module_name, canonical_name))
            elif isinstance(node, ast.ImportFrom) and node.module:
                module_name = node.module.split(".", 1)[0]
                canonical_name = legacy_imports.get(module_name)
                if canonical_name:
                    problems.append(_legacy_import_problem(rel_path, module_name, canonical_name))

    return sorted(set(problems))


def check_agents(registry_path: str = REGISTRY_PATH) -> list[str]:
    problems: list[str] = []
    registry_file = _resolve_repo_path(registry_path)
    try:
        registry = load_registry(registry_path)
    except ValueError as exc:
        return [str(exc)]

    if registry.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        problems.append(f"{registry_path}: unsupported schema_version {registry.get('schema_version')!r}")
    wrapper_policy = registry.get("legacy_wrapper_policy", "active")
    if wrapper_policy not in ALLOWED_LEGACY_WRAPPER_POLICIES:
        problems.append(f"{registry_path}: unsupported legacy_wrapper_policy {wrapper_policy!r}")

    agents = _resolve_repo_path("AGENTS.md")
    scripts_agents = _resolve_repo_path("scripts/AGENTS.md")
    for path in (agents, scripts_agents):
        if not path.exists():
            problems.append(f"{_repo_relative(path)}: file is missing")

    budgets = registry.get("agents_budgets", {})
    for rel_path, budget in budgets.items():
        path = _resolve_repo_path(rel_path)
        if not path.exists():
            problems.append(f"{rel_path}: budget target is missing")
            continue
        max_lines = int(budget.get("max_lines", 0))
        max_bytes = int(budget.get("max_bytes", 0))
        lines = _line_count(path)
        byte_count = _byte_count(path)
        if max_lines and lines > max_lines:
            problems.append(f"{rel_path}: {lines} lines exceeds {max_lines}")
        if max_bytes and byte_count > max_bytes:
            problems.append(f"{rel_path}: {byte_count} bytes exceeds {max_bytes}")

    if agents.exists():
        text = agents.read_text(encoding="utf-8")
        for needle in ("scripts/AGENTS.md", REGISTRY_PATH):
            if needle not in text:
                problems.append(f"AGENTS.md: missing reference to {needle}")
    if scripts_agents.exists() and REGISTRY_PATH not in scripts_agents.read_text(encoding="utf-8"):
        problems.append(f"scripts/AGENTS.md: missing reference to {REGISTRY_PATH}")

    for key, rel_path in sorted(registry.get("directories", {}).items()):
        if not _resolve_repo_path(rel_path).is_dir():
            problems.append(f"{registry_path}: directories.{key} path missing: {rel_path}")

    ids: set[str] = set()
    wrappers: set[str] = set()
    implementations: set[str] = set()
    modules_by_id: dict[str, dict[str, Any]] = {}
    for module in registry.get("modules", []):
        module_id = module.get("id")
        if not module_id:
            problems.append(f"{registry_path}: module missing id")
            continue
        if module_id in ids:
            problems.append(f"{registry_path}: duplicate module id: {module_id}")
        ids.add(module_id)
        modules_by_id[module_id] = module
        if module.get("status") not in ALLOWED_MODULE_STATUSES:
            problems.append(f"{registry_path}: {module_id} has invalid status {module.get('status')!r}")
        implementation = module.get("implementation")
        wrapper = module.get("legacy_wrapper")
        if not implementation:
            problems.append(f"{registry_path}: {module_id} missing implementation")
        elif not _resolve_repo_path(implementation).is_file():
            problems.append(f"{implementation}: implementation path missing for {module_id}")
        else:
            implementations.add(implementation)
        if wrapper:
            if wrapper_policy == "retired":
                problems.append(f"{wrapper}: legacy_wrapper must be null when legacy_wrapper_policy is retired")
            if implementation == wrapper:
                problems.append(f"{wrapper}: implementation and legacy_wrapper are identical for {module_id}")
            if not _resolve_repo_path(wrapper).is_file():
                problems.append(f"{wrapper}: legacy_wrapper path missing for {module_id}")
            else:
                wrappers.add(wrapper)
                problems.extend(_wrapper_problems(wrapper, module))
        for field in ("audit_docs", "required_tests"):
            for rel_path in module.get(field, []):
                if not _resolve_repo_path(rel_path).is_file():
                    problems.append(f"{rel_path}: missing {field} path for {module_id}")

    root_exceptions: set[str] = set()
    for entry in registry.get("root_exceptions", []):
        path = entry.get("path")
        if not path:
            problems.append(f"{registry_path}: root_exceptions entry missing path")
            continue
        resolved = _resolve_repo_path(path)
        if not resolved.is_file():
            problems.append(f"{path}: root exception path missing")
        if resolved.parent != _repo_root() / "scripts":
            problems.append(f"{path}: root exception must be directly under scripts/")
        if path in wrappers:
            problems.append(f"{path}: path cannot be both wrapper and root exception")
        if entry.get("status") not in ALLOWED_MODULE_STATUSES:
            problems.append(f"{path}: invalid root exception status {entry.get('status')!r}")
        root_exceptions.add(path)

    retired_wrappers = registry.get("retired_legacy_wrappers", {})
    retired_wrappers_valid = isinstance(retired_wrappers, dict)
    if not isinstance(retired_wrappers, dict):
        problems.append(f"{registry_path}: retired_legacy_wrappers must be an object")
        retired_wrappers = {}
    retired_modules: dict[str, str] = {}
    retired_stems: dict[str, str] = {}
    for raw_path, module_id in sorted(retired_wrappers.items()):
        path = normalize_repo_path(str(raw_path))
        if path != raw_path:
            problems.append(f"{raw_path}: retired legacy wrapper path must use repo-normalized separators")
        if module_id not in modules_by_id:
            problems.append(f"{path}: retired legacy wrapper references unknown module id {module_id!r}")
        if Path(path).parent.as_posix() != "scripts":
            problems.append(f"{path}: retired legacy wrapper must be directly under scripts/")
        if Path(path).suffix != ".py":
            problems.append(f"{path}: retired legacy wrapper must be a .py file")
        if _resolve_repo_path(path).exists():
            problems.append(f"{path}: retired legacy wrapper path still exists")
        if path in root_exceptions:
            problems.append(f"{path}: retired legacy wrapper cannot be a root exception")
        previous_path = retired_modules.get(str(module_id))
        if previous_path and previous_path != path:
            problems.append(f"{path}: module {module_id!r} has multiple retired legacy wrappers")
        retired_modules[str(module_id)] = path
        stem = Path(path).stem
        previous_module = retired_stems.get(stem)
        if previous_module and previous_module != module_id:
            problems.append(f"{path}: retired legacy wrapper stem {stem!r} maps to multiple module ids")
        retired_stems[stem] = str(module_id)

    uncovered = sorted(_root_script_files() - wrappers - root_exceptions)
    for path in uncovered:
        problems.append(f"{path}: root script is neither legacy_wrapper nor root_exception")
    if wrapper_policy == "retired":
        for path in sorted(_root_script_files()):
            problems.append(f"{path}: scripts root Python wrappers are retired and must not exist")
        if "scripts/publish_pr.ps1" not in root_exceptions:
            problems.append("scripts/publish_pr.ps1: stable root exception is not registered")
    for path in sorted(wrappers & root_exceptions):
        problems.append(f"{path}: duplicate wrapper/root_exception coverage")
    for path in sorted(implementations & wrappers):
        problems.append(f"{path}: path cannot be both implementation and wrapper")

    if retired_wrappers_valid:
        problems.extend(check_canonical_imports(registry_path))

    if registry_file.read_bytes().startswith(b"\xef\xbb\xbf"):
        problems.append(f"{registry_path}: must be UTF-8 without BOM")
    return sorted(problems)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="UTF-8 safe repo helper for Codex work.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    read_parser = subparsers.add_parser("read", help="Read a UTF-8 text file inside the repo.")
    read_parser.add_argument("path")

    write_parser = subparsers.add_parser("write", help="Write a UTF-8 text file from --from.")
    write_parser.add_argument("path")
    write_parser.add_argument("--from", dest="source", required=True)

    replace_parser = subparsers.add_parser(
        "replace", help="Replace all occurrences of --old with --new in a UTF-8 text file."
    )
    replace_parser.add_argument("path")
    replace_parser.add_argument("--old", required=True)
    replace_parser.add_argument("--new", required=True)

    changed_parser = subparsers.add_parser(
        "changed-files", help="Print repo-relative paths from git diff --name-only."
    )
    changed_parser.add_argument("--base", default="origin/GPT...HEAD")

    subparsers.add_parser("status-files", help="Print repo-relative paths from git status.")

    snapshot_parser = subparsers.add_parser("snapshot", help="Build a repository context snapshot.")
    snapshot_parser.add_argument("--ref", default="origin/GPT")
    snapshot_parser.add_argument("--output")

    context_parser = subparsers.add_parser("pr-context", help="Build a PR context summary.")
    context_parser.add_argument("--base", default="origin/GPT")
    context_parser.add_argument("--head", default="HEAD")
    context_parser.add_argument("--output")

    scope_parser = subparsers.add_parser("scope-check", help="Check changed paths against allow/forbid patterns.")
    scope_parser.add_argument("--base", default="origin/GPT...HEAD")
    scope_parser.add_argument("--forbid", action="append", default=[])
    scope_parser.add_argument("--allow", action="append", default=[])
    scope_parser.add_argument("--ignore", action="append", default=[])
    scope_parser.add_argument("--registry", default=REGISTRY_PATH)

    agents_parser = subparsers.add_parser("agents-check", help="Validate AGENTS files and scripts registry.")
    agents_parser.add_argument("--registry", default=REGISTRY_PATH)

    canonical_imports_parser = subparsers.add_parser(
        "canonical-imports-check",
        help="Validate migrated implementations do not import legacy wrapper modules.",
    )
    canonical_imports_parser.add_argument("--registry", default=REGISTRY_PATH)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "read":
            _emit_stdout(read_text_file(args.path))
        elif args.command == "write":
            write_text_file(args.path, args.source)
        elif args.command == "replace":
            _emit_stdout(str(replace_text_file(args.path, args.old, args.new)))
        elif args.command == "changed-files":
            _emit_stdout_lines(changed_files(args.base))
        elif args.command == "status-files":
            _emit_stdout_lines(status_files())
        elif args.command == "snapshot":
            write_json_output(build_snapshot(args.ref), args.output)
        elif args.command == "pr-context":
            write_json_output(build_pr_context(args.base, args.head), args.output)
        elif args.command == "scope-check":
            problems = check_scope(args.base, args.forbid, args.allow, args.ignore, args.registry)
            if problems:
                for problem in problems:
                    _emit_stderr(problem)
                return 1
        elif args.command == "agents-check":
            problems = check_agents(args.registry)
            if problems:
                for problem in problems:
                    _emit_stderr(problem)
                return 1
        elif args.command == "canonical-imports-check":
            problems = check_canonical_imports(args.registry)
            if problems:
                for problem in problems:
                    _emit_stderr(problem)
                return 1
        else:  # pragma: no cover - argparse enforces commands
            raise AssertionError(f"unknown command: {args.command}")
    except Exception as exc:  # pragma: no cover - exercised in CLI tests
        _emit_stderr(f"error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
