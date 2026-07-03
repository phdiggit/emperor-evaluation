from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.source_excerpt_pool_lib.common import (  # noqa: E402
    DEFAULT_PROFILE,
    DEFAULT_WORKFLOW_CODE,
    load_source_excerpt_pool_paths,
    normalize_workflow_code,
)
from scripts.dev.source_excerpt_pool_lib.profile import ExcerptPoolError, profile_matches_workflow  # noqa: E402


DEFAULT_ALL_LIST = ROOT / "data" / "configs" / "lists" / "所有君主.yml"
PLACEHOLDER_MARKER = "待识别"


@dataclass(frozen=True)
class ProfileStatus:
    person: str
    query_profile_id: str
    source_group: str
    profile_status: str
    workflow_code: str
    object_count: int
    placeholder_count: int


@dataclass(frozen=True)
class JobStatus:
    person: str
    output_name: str
    job_status: str
    path: str
    workflow_code: str = DEFAULT_WORKFLOW_CODE
    workflow_code_missing: bool = False
    returncode: int | None = None
    started_at: str = ""
    finished_at: str = ""


@dataclass(frozen=True)
class PackStatus:
    person: str
    output_name: str
    pack_status: str
    path: str
    workflow_code: str = DEFAULT_WORKFLOW_CODE
    workflow_code_missing: bool = False
    written_pages: int = 0
    excerpts: int = 0
    errors: int = 0
    objects_without_page_hits: tuple[str, ...] = ()
    objects_without_excerpts: tuple[str, ...] = ()
    updated_at: str = ""


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _as_person_list(payload: Any) -> list[str]:
    if isinstance(payload, list):
        return [str(item).strip() for item in payload if str(item).strip()]
    if isinstance(payload, Mapping):
        persons = payload.get("persons")
        if isinstance(persons, list):
            return [str(item).strip() for item in persons if str(item).strip()]
    return []


def load_persons(path: Path) -> list[str]:
    return _as_person_list(_read_yaml(path))


def _object_names(profile: Mapping[str, Any]) -> list[str]:
    layers = profile.get("object_layers")
    if not isinstance(layers, Mapping):
        return []
    names: list[str] = []
    for values in layers.values():
        if isinstance(values, list):
            names.extend(str(value).strip() for value in values if str(value).strip())
    return names


def classify_profile(profile: Mapping[str, Any]) -> ProfileStatus:
    person = str(profile.get("person") or "").strip()
    workflow_code = normalize_workflow_code(profile.get("workflow_code") or DEFAULT_WORKFLOW_CODE)
    names = _object_names(profile)
    placeholder_count = sum(1 for name in names if PLACEHOLDER_MARKER in name)
    source_group = str(profile.get("source_group") or "").strip()
    if not names:
        profile_status = "empty_profile"
    elif source_group == "all_monarch_backfill" or placeholder_count:
        profile_status = "half_baked_profile"
    else:
        profile_status = "prepared_profile"
    return ProfileStatus(
        person=person,
        query_profile_id=str(profile.get("query_profile_id") or "").strip(),
        source_group=source_group,
        profile_status=profile_status,
        workflow_code=workflow_code,
        object_count=len(names),
        placeholder_count=placeholder_count,
    )


def load_profiles(path: Path, *, workflow_code: str = DEFAULT_WORKFLOW_CODE) -> dict[str, ProfileStatus]:
    workflow_code = normalize_workflow_code(workflow_code)
    profiles: dict[str, ProfileStatus] = {}
    for row in _read_jsonl(path):
        if not profile_matches_workflow(row, workflow_code):
            continue
        profile = classify_profile(row)
        if profile.person:
            if profile.person in profiles:
                raise ExcerptPoolError(f"multiple profiles found for person: {profile.person} workflow_code={workflow_code}")
            profiles[profile.person] = profile
    return profiles


def _strip_job_suffix(name: str) -> tuple[str, str]:
    for suffix, status in (
        (".json.running", "running"),
        (".json.done", "done"),
        (".json.failed", "failed"),
        (".json", "queued"),
    ):
        if name.endswith(suffix):
            return name[: -len(suffix)], status
    return name, "unknown"


def _job_status_from_payload(path_status: str, status_payload: Mapping[str, Any]) -> str:
    status = str(status_payload.get("status") or "").strip()
    if status == "complete":
        return "success"
    if status == "failed":
        return "failed"
    if status == "running":
        return "running"
    if path_status == "done":
        return "success"
    return path_status


def load_jobs(jobs_dir: Path, logs_dir: Path | None = None) -> list[JobStatus]:
    if not jobs_dir.exists():
        return []
    logs_dir = logs_dir or jobs_dir.parent / "logs"
    jobs: list[JobStatus] = []
    for path in sorted(jobs_dir.iterdir()):
        if not path.is_file():
            continue
        base_name, path_status = _strip_job_suffix(path.name)
        if path_status == "unknown":
            continue
        try:
            payload = _read_json(path)
        except Exception:
            payload = {}
        status_path = logs_dir / f"{base_name}.json.status.json"
        status_payload: dict[str, Any] = {}
        if status_path.exists():
            try:
                status_payload = _read_json(status_path)
            except Exception:
                status_payload = {}
        person = str(payload.get("person") or status_payload.get("person") or "").strip()
        output_name = str(payload.get("output_name") or Path(base_name).stem).strip()
        workflow_code_raw = status_payload.get("workflow_code") or payload.get("workflow_code")
        workflow_code = normalize_workflow_code(workflow_code_raw or DEFAULT_WORKFLOW_CODE)
        returncode_raw = status_payload.get("returncode")
        returncode = int(returncode_raw) if isinstance(returncode_raw, int) else None
        jobs.append(
            JobStatus(
                person=person,
                output_name=output_name,
                job_status=_job_status_from_payload(path_status, status_payload),
                path=str(path),
                workflow_code=workflow_code,
                workflow_code_missing=not bool(str(workflow_code_raw or "").strip()),
                returncode=returncode,
                started_at=str(status_payload.get("started_at") or ""),
                finished_at=str(status_payload.get("finished_at") or ""),
            )
        )
    return jobs


def _mtime_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds")


def load_packs(source_pack_root: Path) -> list[PackStatus]:
    if not source_pack_root.exists():
        return []
    packs: list[PackStatus] = []
    for pack_dir in sorted(source_pack_root.iterdir()):
        if not pack_dir.is_dir():
            continue
        manifest: dict[str, Any] = {}
        report: dict[str, Any] = {}
        if (pack_dir / "manifest.json").exists():
            try:
                manifest = _read_json(pack_dir / "manifest.json")
            except Exception:
                manifest = {}
        if (pack_dir / "fetch_report.json").exists():
            try:
                report = _read_json(pack_dir / "fetch_report.json")
            except Exception:
                report = {}
        if not manifest and not report:
            continue
        coverage = report.get("object_coverage") if isinstance(report.get("object_coverage"), Mapping) else {}
        person = str(report.get("person") or manifest.get("person") or "").strip()
        output_name = pack_dir.name
        workflow_code_raw = report.get("workflow_code") or manifest.get("workflow_code")
        workflow_code = normalize_workflow_code(workflow_code_raw or DEFAULT_WORKFLOW_CODE)
        errors = report.get("errors")
        error_count = len(errors) if isinstance(errors, list) else 0
        packs.append(
            PackStatus(
                person=person,
                output_name=output_name,
                pack_status=str(report.get("status") or manifest.get("status") or "unknown"),
                path=str(pack_dir),
                workflow_code=workflow_code,
                workflow_code_missing=not bool(str(workflow_code_raw or "").strip()),
                written_pages=int(report.get("written_pages") or 0),
                excerpts=int(report.get("excerpts") or 0),
                errors=error_count,
                objects_without_page_hits=tuple(str(item) for item in coverage.get("objects_without_page_hits", []) if item),
                objects_without_excerpts=tuple(str(item) for item in coverage.get("objects_without_excerpts", []) if item),
                updated_at=_mtime_iso(pack_dir),
            )
        )
    return packs


def _pack_gap_count(pack: PackStatus) -> int:
    return len(set(pack.objects_without_page_hits) | set(pack.objects_without_excerpts))


def _latest_pack(packs: Sequence[PackStatus]) -> PackStatus | None:
    if not packs:
        return None
    return sorted(
        packs,
        key=lambda item: (
            0 if item.pack_status == "complete" else 1,
            _pack_gap_count(item),
            item.errors,
            -item.excerpts,
            -item.written_pages,
            item.updated_at,
        ),
    )[0]


def _primary_job(jobs: Sequence[JobStatus]) -> JobStatus | None:
    if not jobs:
        return None
    priority = {"running": 0, "queued": 1, "failed": 2, "success": 3, "done": 3}
    return sorted(jobs, key=lambda item: (priority.get(item.job_status, 9), item.started_at, item.path))[0]


def _needs_profile_work(pack: PackStatus | None) -> bool:
    if pack is None:
        return False
    return bool(pack.errors or pack.objects_without_page_hits or pack.objects_without_excerpts)


def _action_status(profile: ProfileStatus | None, job: JobStatus | None, pack: PackStatus | None) -> str:
    if profile is None:
        return "missing_query_profile"
    if profile.profile_status != "prepared_profile":
        return "profile_needs_work"
    if job is not None and job.job_status == "running":
        return "fetch_running"
    if job is not None and job.job_status == "queued":
        return "fetch_queued"
    if job is not None and job.job_status == "failed" and pack is None:
        return "fetch_failed"
    if job is not None and job.job_status in {"success", "done"} and pack is None:
        return "fetch_success_pack_missing"
    if pack is None:
        return "prepared_not_submitted"
    if pack.pack_status != "complete":
        return "pack_incomplete"
    if _needs_profile_work(pack):
        return "fetched_needs_profile_work"
    return "fetched_ok"


def _bucket(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def build_status_report(
    *,
    persons: Sequence[str],
    profiles: Mapping[str, ProfileStatus],
    jobs: Sequence[JobStatus],
    packs: Sequence[PackStatus],
    workflow_code: str = DEFAULT_WORKFLOW_CODE,
) -> dict[str, Any]:
    workflow_code = normalize_workflow_code(workflow_code)
    profiles = {
        person: profile
        for person, profile in profiles.items()
        if normalize_workflow_code(profile.workflow_code) == workflow_code
    }
    jobs = [job for job in jobs if normalize_workflow_code(job.workflow_code) == workflow_code]
    packs = [pack for pack in packs if normalize_workflow_code(pack.workflow_code) == workflow_code]
    job_by_person: dict[str, list[JobStatus]] = {}
    for job in jobs:
        if job.person:
            job_by_person.setdefault(job.person, []).append(job)
    pack_by_person: dict[str, list[PackStatus]] = {}
    for pack in packs:
        if pack.person:
            pack_by_person.setdefault(pack.person, []).append(pack)

    ordered_persons = list(dict.fromkeys([*persons, *profiles.keys(), *job_by_person.keys(), *pack_by_person.keys()]))
    rows: list[dict[str, Any]] = []
    for person in ordered_persons:
        profile = profiles.get(person)
        job = _primary_job(job_by_person.get(person, ()))
        pack = _latest_pack(pack_by_person.get(person, ()))
        action_status = _action_status(profile, job, pack)
        rows.append(
            {
                "person": person,
                "action_status": action_status,
                "profile_status": profile.profile_status if profile else "missing_profile",
                "profile_workflow_code": profile.workflow_code if profile else "",
                "query_profile_id": profile.query_profile_id if profile else "",
                "source_group": profile.source_group if profile else "",
                "object_count": profile.object_count if profile else 0,
                "placeholder_count": profile.placeholder_count if profile else 0,
                "job_status": job.job_status if job else "none",
                "job_output_name": job.output_name if job else "",
                "job_workflow_code": job.workflow_code if job else "",
                "job_workflow_code_missing": job.workflow_code_missing if job else False,
                "pack_status": pack.pack_status if pack else "none",
                "pack_output_name": pack.output_name if pack else "",
                "pack_workflow_code": pack.workflow_code if pack else "",
                "pack_workflow_code_missing": pack.workflow_code_missing if pack else False,
                "written_pages": pack.written_pages if pack else 0,
                "excerpts": pack.excerpts if pack else 0,
                "pack_errors": pack.errors if pack else 0,
                "objects_without_page_hits": list(pack.objects_without_page_hits) if pack else [],
                "objects_without_excerpts": list(pack.objects_without_excerpts) if pack else [],
                "pack_path": pack.path if pack else "",
                "pack_count": len(pack_by_person.get(person, ())),
                "job_count": len(job_by_person.get(person, ())),
            }
        )
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "workflow_code": workflow_code,
        "totals": {
            "persons": len(rows),
            "profiles": len(profiles),
            "jobs": len(jobs),
            "packs": len(packs),
            "jobs_missing_workflow_code": sum(1 for job in jobs if job.workflow_code_missing),
            "packs_missing_workflow_code": sum(1 for pack in packs if pack.workflow_code_missing),
            "by_action_status": _bucket(rows, "action_status"),
            "by_profile_status": _bucket(rows, "profile_status"),
            "by_job_status": _bucket(rows, "job_status"),
            "by_pack_status": _bucket(rows, "pack_status"),
        },
        "rows": rows,
    }


def _default_source_pack_root(*, workflow_code: str = DEFAULT_WORKFLOW_CODE) -> Path:
    paths = load_source_excerpt_pool_paths(workflow_code=workflow_code)
    return paths.get("source_pack_root") or (ROOT / ".tmp" / "source-packs")


def render_markdown(report: Mapping[str, Any]) -> str:
    rows = report.get("rows") if isinstance(report.get("rows"), list) else []
    totals = report.get("totals") if isinstance(report.get("totals"), Mapping) else {}
    workflow_code = normalize_workflow_code(str(report.get("workflow_code") or DEFAULT_WORKFLOW_CODE))
    lines = [
        f"# {workflow_code} 抓包状态台账",
        "",
        f"- generated_at: `{report.get('generated_at') or ''}`",
        f"- workflow_code: `{workflow_code}`",
        f"- persons: `{totals.get('persons', 0)}`",
        f"- profiles: `{totals.get('profiles', 0)}`",
        f"- jobs: `{totals.get('jobs', 0)}`",
        f"- packs: `{totals.get('packs', 0)}`",
        f"- jobs_missing_workflow_code: `{totals.get('jobs_missing_workflow_code', 0)}`",
        f"- packs_missing_workflow_code: `{totals.get('packs_missing_workflow_code', 0)}`",
        "",
        "## 状态计数",
        "",
    ]
    for title, key in (
        ("action_status", "by_action_status"),
        ("profile_status", "by_profile_status"),
        ("job_status", "by_job_status"),
        ("pack_status", "by_pack_status"),
    ):
        counts = totals.get(key) if isinstance(totals.get(key), Mapping) else {}
        lines.append(f"- {title}: " + "；".join(f"{name}={count}" for name, count in counts.items()))
    lines.extend(
        [
            "",
            "## 待处理分组",
            "",
        ]
    )
    labels = {
        "missing_query_profile": "缺检索包",
        "profile_needs_work": "检索包半成品",
        "prepared_not_submitted": "成品但尚未投入",
        "fetch_queued": "检索任务排队中",
        "fetch_running": "检索任务运行中",
        "fetch_failed": "检索任务失败",
        "fetch_success_pack_missing": "检索任务成功但包目录未读到",
        "pack_incomplete": "抓包未完整完成",
        "fetched_needs_profile_work": "抓包成功但需完善检索包",
        "fetched_ok": "抓包成功且暂无明显缺口",
    }
    for status, label in labels.items():
        group = [row for row in rows if isinstance(row, Mapping) and row.get("action_status") == status]
        if not group:
            continue
        lines.extend([f"### {label}", ""])
        lines.append("| 人物 | profile | job | pack | 页数 | excerpts | 缺页对象 | 缺摘录对象 |")
        lines.append("| --- | --- | --- | --- | ---: | ---: | --- | --- |")
        for row in group:
            page_gap = "、".join(row.get("objects_without_page_hits") or [])
            excerpt_gap = "、".join(row.get("objects_without_excerpts") or [])
            lines.append(
                "| {person} | {profile_status} | {job_status} | {pack_status} | {written_pages} | {excerpts} | {page_gap} | {excerpt_gap} |".format(
                    person=row.get("person", ""),
                    profile_status=row.get("profile_status", ""),
                    job_status=row.get("job_status", ""),
                    pack_status=row.get("pack_status", ""),
                    written_pages=row.get("written_pages", 0),
                    excerpts=row.get("excerpts", 0),
                    page_gap=page_gap,
                    excerpt_gap=excerpt_gap,
                )
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize I5B query-profile and source-pack job status.")
    parser.add_argument("--workflow-code", default=DEFAULT_WORKFLOW_CODE, help="Workflow/subitem code for report metadata.")
    parser.add_argument("--all-list", type=Path, default=DEFAULT_ALL_LIST, help="YAML list of all target persons.")
    parser.add_argument("--profile", type=Path, default=None, help="Query-profile JSONL path.")
    parser.add_argument("--source-pack-root", type=Path, default=None, help="Source-pack root directory.")
    parser.add_argument("--jobs-dir", type=Path, default=None, help="Source-pack worker jobs directory.")
    parser.add_argument("--logs-dir", type=Path, default=None, help="Source-pack worker logs directory.")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    workflow_code = normalize_workflow_code(args.workflow_code)
    source_paths = load_source_excerpt_pool_paths(workflow_code=workflow_code)
    profile_path = args.profile or source_paths.get("query_profile") or DEFAULT_PROFILE
    source_pack_root = args.source_pack_root or source_paths.get("source_pack_root") or _default_source_pack_root(workflow_code=workflow_code)
    jobs_dir = args.jobs_dir or source_paths.get("jobs_dir") or source_pack_root.parent / "jobs"
    logs_dir = args.logs_dir or source_paths.get("logs_dir") or source_pack_root.parent / "logs"
    report = build_status_report(
        persons=load_persons(args.all_list) if args.all_list.exists() else [],
        profiles=load_profiles(profile_path, workflow_code=workflow_code) if profile_path.exists() else {},
        jobs=load_jobs(jobs_dir, logs_dir),
        packs=load_packs(source_pack_root),
        workflow_code=workflow_code,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n" if args.format == "json" else render_markdown(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
