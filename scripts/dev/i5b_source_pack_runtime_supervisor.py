from __future__ import annotations

import argparse
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


DEFAULT_WORKFLOW_CODE = "I5B"


@dataclass(frozen=True)
class ChildSpec:
    name: str
    cmd: list[str]


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def log(message: str) -> None:
    print(f"{iso_now()} {message}", flush=True)


def build_child_specs(args: argparse.Namespace) -> list[ChildSpec]:
    python = str(args.python)
    refiner_cmd = [
        python,
        str(args.refiner_script),
        "--profile",
        str(args.profile),
        "--all-list",
        str(args.all_list),
        "--source-pack-root",
        str(args.source_pack_root),
        "--jobs-dir",
        str(args.jobs_dir),
        "--logs-dir",
        str(args.logs_dir),
        "--workflow-code",
        str(getattr(args, "workflow_code", DEFAULT_WORKFLOW_CODE)),
        "--output-dir",
        str(args.refiner_output_dir),
        "--interval-seconds",
        str(args.refiner_interval_seconds),
        "--max-queries-per-object",
        str(args.max_queries_per_object),
    ]
    if args.include_adjacent:
        refiner_cmd.append("--include-adjacent")
    specs = [
        ChildSpec("source-pack-worker", [python, str(args.worker_script)]),
        ChildSpec("query-profile-refiner", refiner_cmd),
    ]
    pipeline_script = getattr(args, "pipeline_script", None)
    if pipeline_script:
        pipeline_cmd = [
            python,
            str(pipeline_script),
            "--profile",
            str(args.profile),
            "--all-list",
            str(args.all_list),
            "--source-pack-root",
            str(args.source_pack_root),
            "--jobs-dir",
            str(args.jobs_dir),
            "--logs-dir",
            str(args.logs_dir),
            "--output-dir",
            str(args.pipeline_output_dir),
            "--workflow-code",
            str(getattr(args, "workflow_code", DEFAULT_WORKFLOW_CODE)),
            "--interval-seconds",
            str(args.pipeline_interval_seconds),
            "--refine-max-queries-per-object",
            str(args.max_queries_per_object),
            "--fetch-max-queries-per-object",
            str(args.fetch_max_queries_per_object),
            "--max-jobs-per-run",
            str(args.pipeline_max_jobs_per_run),
            "--max-refine-rounds-per-person",
            str(args.pipeline_max_refine_rounds_per_person),
        ]
        if args.include_adjacent:
            pipeline_cmd.append("--include-adjacent")
        if args.pipeline_submit_prepared:
            pipeline_cmd.append("--submit-prepared")
        if args.pipeline_submit_refinements:
            pipeline_cmd.append("--submit-refinements")
        specs.append(ChildSpec("source-pack-pipeline", pipeline_cmd))
    return specs


def terminate_children(children: list[subprocess.Popen[str]], *, timeout_seconds: float = 15) -> None:
    for child in children:
        if child.poll() is None:
            child.terminate()
    deadline = time.monotonic() + timeout_seconds
    for child in children:
        while child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.1)
    for child in children:
        if child.poll() is None:
            child.kill()


def run_supervisor(specs: list[ChildSpec]) -> int:
    children: list[subprocess.Popen[str]] = []
    stopping = False

    def handle_stop(signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True
        log(f"received signal={signum}; stopping children")
        terminate_children(children)

    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)
    try:
        for spec in specs:
            log(f"start child={spec.name} cmd={' '.join(spec.cmd)}")
            children.append(subprocess.Popen(spec.cmd, text=True))
        while not stopping:
            for spec, child in zip(specs, children):
                returncode = child.poll()
                if returncode is not None:
                    log(f"child exited name={spec.name} rc={returncode}; stopping service")
                    terminate_children(children)
                    return returncode or 1
            time.sleep(2)
    finally:
        terminate_children(children)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run source-pack worker and query-profile refiner as independent child processes under one service.")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--worker-script", type=Path, required=True)
    parser.add_argument("--refiner-script", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--all-list", type=Path, required=True)
    parser.add_argument("--source-pack-root", type=Path, required=True)
    parser.add_argument("--jobs-dir", type=Path, required=True)
    parser.add_argument("--logs-dir", type=Path, required=True)
    parser.add_argument("--workflow-code", default=DEFAULT_WORKFLOW_CODE, help="Workflow/subitem code passed to the pipeline daemon.")
    parser.add_argument("--refiner-output-dir", type=Path, required=True)
    parser.add_argument("--refiner-interval-seconds", type=float, default=900)
    parser.add_argument("--max-queries-per-object", type=int, default=6)
    parser.add_argument("--fetch-max-queries-per-object", type=int, default=4)
    parser.add_argument("--include-adjacent", action="store_true")
    parser.add_argument("--pipeline-script", type=Path, default=None)
    parser.add_argument("--pipeline-output-dir", type=Path, default=None)
    parser.add_argument("--pipeline-interval-seconds", type=float, default=900)
    parser.add_argument("--pipeline-max-jobs-per-run", type=int, default=0)
    parser.add_argument("--pipeline-max-refine-rounds-per-person", type=int, default=2)
    parser.add_argument("--pipeline-submit-prepared", action="store_true")
    parser.add_argument("--pipeline-submit-refinements", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.pipeline_script and args.pipeline_output_dir is None:
        args.pipeline_output_dir = args.refiner_output_dir
    if args.pipeline_script and not (args.pipeline_submit_prepared or args.pipeline_submit_refinements):
        raise SystemExit("pipeline requires --pipeline-submit-prepared or --pipeline-submit-refinements")
    return run_supervisor(build_child_specs(args))


if __name__ == "__main__":
    raise SystemExit(main())
