from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from emperor_v4.adapters.source_cache_fixture import FrozenSourceMaterialProvider
from emperor_v4.adapters.source_cache_wikisource import WikisourceSourceMaterialProvider
from emperor_v4.application.source_cache_service import ensure_source_cache
from emperor_v4.contracts.source import SourceCacheRequest, SourceCacheSubject
from emperor_v4.persistence.source_cache import ShadowJsonSourceCacheRepository


def _mapping(path: Path) -> Mapping[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"输入根必须为 mapping: {path}")
    return payload


def load_source_cache_request(path: Path) -> SourceCacheRequest:
    return source_cache_request_from_mapping(_mapping(path))


def source_cache_request_from_mapping(payload: Mapping[str, Any]) -> SourceCacheRequest:
    subject = payload.get("subject") or {}
    return SourceCacheRequest(
        request_id=str(payload.get("request_id") or ""),
        idempotency_key=str(payload.get("idempotency_key") or ""),
        subject=SourceCacheSubject(
            person_or_ruler_ref=str(subject.get("person_or_ruler_ref") or ""),
            canonical_name=str(subject.get("canonical_name") or ""),
            aliases=tuple(subject.get("aliases") or ()),
        ),
        evaluation_context=payload.get("evaluation_context") or {},
        source_hints=tuple(payload.get("source_hints") or ()),
        required_source_families=tuple(
            payload.get("required_source_families") or ()
        ),
        mode=str(payload.get("mode") or ""),
        source_policy_version=str(payload.get("source_policy_version") or ""),
        requested_at=str(payload.get("requested_at") or ""),
    )


def run_fixture_ensure(
    *,
    request_path: Path,
    fixture_plan_path: Path,
    state_path: Path,
    service_release_sha: str,
    repo_root: Path,
) -> dict[str, Any]:
    request = load_source_cache_request(request_path)
    run = ensure_source_cache(
        request,
        provider=FrozenSourceMaterialProvider(
            plan_path=fixture_plan_path,
            repo_root=repo_root,
        ),
        repository=ShadowJsonSourceCacheRepository(state_path),
        service_release_sha=service_release_sha,
    )
    return {
        "schema_version": 1,
        "status": "source_cache_fixture_ensure_complete",
        "request": asdict(request),
        "response": run.response,
        "runtime_audit": {
            "cache_hit": run.cache_hit,
            "exact_response_reused": run.cache_hit,
            "provider_call_count": run.provider_call_count,
            "shadow_state_write_count": run.repository_write_count,
            "network_request_count": run.network_request_count,
            "database_write_count": 0,
            "model_call_count": 0,
        },
    }


def run_wikisource_ensure(
    *,
    request_path: Path,
    source_plan_path: Path,
    state_path: Path,
    service_release_sha: str,
    fetch: Any | None = None,
) -> dict[str, Any]:
    request = load_source_cache_request(request_path)
    provider_options = {"fetch": fetch} if fetch is not None else {}
    run = ensure_source_cache(
        request,
        provider=WikisourceSourceMaterialProvider(
            plan_path=source_plan_path,
            **provider_options,
        ),
        repository=ShadowJsonSourceCacheRepository(state_path),
        service_release_sha=service_release_sha,
    )
    return {
        "schema_version": 1,
        "status": "source_cache_wikisource_ensure_complete",
        "request": asdict(request),
        "response": run.response,
        "runtime_audit": {
            "cache_hit": run.cache_hit,
            "exact_response_reused": run.cache_hit,
            "provider_call_count": run.provider_call_count,
            "shadow_state_write_count": run.repository_write_count,
            "network_request_count": run.network_request_count,
            "database_write_count": 0,
            "model_call_count": 0,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="V4 Source Cache runner")
    parser.add_argument("--request", type=Path, required=True)
    plans = parser.add_mutually_exclusive_group(required=True)
    plans.add_argument("--fixture-plan", type=Path)
    plans.add_argument("--wikisource-plan", type=Path)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--service-release-sha", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.wikisource_plan:
        report = run_wikisource_ensure(
            request_path=args.request,
            source_plan_path=args.wikisource_plan,
            state_path=args.state,
            service_release_sha=args.service_release_sha,
        )
    else:
        report = run_fixture_ensure(
            request_path=args.request,
            fixture_plan_path=args.fixture_plan,
            state_path=args.state,
            service_release_sha=args.service_release_sha,
            repo_root=args.repo_root,
        )
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
