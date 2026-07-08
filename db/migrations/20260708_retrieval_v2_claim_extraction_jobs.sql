create schema if not exists retrieval_v2;

-- retrieval_v2 claim extraction worker 原则：
-- 1. 本迁移只建立抓包侧 claim 抽取队列，不导入 claim，不接消费端，不触发评分。
-- 2. worker 只处理 uncovered candidate slices，把 claim-only judge 结果写回 claim cache。
-- 3. 取值有限的字段使用 PostgreSQL enum type，不用 text + check 承载状态机。

do $$
begin
    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v2'
           and t.typname = 'rv2_claim_extraction_job_status'
    ) then
        execute 'create type retrieval_v2.rv2_claim_extraction_job_status as enum (''ready'', ''running'', ''succeeded'', ''failed'', ''retry_wait'', ''cancelled'')';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v2'
           and t.typname = 'rv2_claim_extraction_run_status'
    ) then
        execute 'create type retrieval_v2.rv2_claim_extraction_run_status as enum (''running'', ''succeeded'', ''failed'', ''cancelled'')';
    end if;
end;
$$;

comment on type retrieval_v2.rv2_claim_extraction_job_status is 'claim 抽取队列任务状态；ready 可领取，retry_wait 可重试，succeeded 表示已导入缓存。';
comment on type retrieval_v2.rv2_claim_extraction_run_status is 'claim 抽取任务单次运行状态。';

create table if not exists retrieval_v2.claim_extraction_jobs (
    id bigint generated always as identity primary key,
    job_code text not null,
    idem_key text not null,
    status retrieval_v2.rv2_claim_extraction_job_status not null default 'ready',
    priority integer not null default 100,
    emperor_name text not null default '',
    target_code text not null default '',
    rule_code text not null default '',
    capture_profile text not null default '',
    candidate_payload_path text not null default '',
    run_root text not null default '',
    cache_root text not null default '',
    uncovered_slice_count integer not null default 0,
    job_payload jsonb not null default '{}'::jsonb,
    attempt_count integer not null default 0,
    max_attempts integer not null default 3,
    locked_by text,
    locked_at timestamptz,
    lease_until timestamptz,
    last_error text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv2_claim_extraction_jobs_code_uk unique (job_code),
    constraint rv2_claim_extraction_jobs_idem_uk unique (idem_key),
    constraint rv2_claim_extraction_jobs_code_not_blank check (btrim(job_code) <> ''),
    constraint rv2_claim_extraction_jobs_idem_not_blank check (btrim(idem_key) <> ''),
    constraint rv2_claim_extraction_jobs_priority_positive check (priority > 0),
    constraint rv2_claim_extraction_jobs_attempts_ck check (attempt_count >= 0 and max_attempts > 0),
    constraint rv2_claim_extraction_jobs_uncovered_ck check (uncovered_slice_count >= 0),
    constraint rv2_claim_extraction_jobs_payload_ck check (jsonb_typeof(job_payload) = 'object')
);

create table if not exists retrieval_v2.claim_extraction_job_runs (
    id bigint generated always as identity primary key,
    run_code text not null,
    job_id bigint not null references retrieval_v2.claim_extraction_jobs(id) on delete cascade,
    worker_id text not null default '',
    started_at timestamptz not null default now(),
    ended_at timestamptz,
    status retrieval_v2.rv2_claim_extraction_run_status not null default 'running',
    input_fingerprint text not null default '',
    output_fingerprint text not null default '',
    run_root text not null default '',
    claim_count integer not null default 0,
    usage_payload jsonb not null default '{}'::jsonb,
    error_type text not null default '',
    error_msg text not null default '',
    run_payload jsonb not null default '{}'::jsonb,
    constraint rv2_claim_extraction_job_runs_code_uk unique (run_code),
    constraint rv2_claim_extraction_job_runs_code_not_blank check (btrim(run_code) <> ''),
    constraint rv2_claim_extraction_job_runs_claim_count_ck check (claim_count >= 0),
    constraint rv2_claim_extraction_job_runs_usage_payload_ck check (jsonb_typeof(usage_payload) = 'object'),
    constraint rv2_claim_extraction_job_runs_run_payload_ck check (jsonb_typeof(run_payload) = 'object')
);

create index if not exists rv2_claim_extraction_jobs_ready_idx
on retrieval_v2.claim_extraction_jobs(priority, created_at)
where status in ('ready', 'retry_wait');

create index if not exists rv2_claim_extraction_jobs_target_idx
on retrieval_v2.claim_extraction_jobs(target_code, rule_code, capture_profile, status);

create index if not exists rv2_claim_extraction_job_runs_job_idx
on retrieval_v2.claim_extraction_job_runs(job_id, started_at desc);

comment on table retrieval_v2.claim_extraction_jobs is '抓包侧 claim 抽取队列表：保存 uncovered candidate slices 的异步抽取任务。';
comment on table retrieval_v2.claim_extraction_job_runs is 'claim 抽取任务运行记录表：记录每次 worker attempt 的输入、输出、usage 和错误。';

comment on column retrieval_v2.claim_extraction_jobs.id is '本表内部主键。';
comment on column retrieval_v2.claim_extraction_jobs.job_code is 'claim 抽取任务稳定代码。';
comment on column retrieval_v2.claim_extraction_jobs.idem_key is 'claim 抽取任务幂等键；同一 uncovered candidates 不得重复创建任务。';
comment on column retrieval_v2.claim_extraction_jobs.status is 'claim 抽取任务状态。';
comment on column retrieval_v2.claim_extraction_jobs.priority is '任务优先级；数字越小越优先。';
comment on column retrieval_v2.claim_extraction_jobs.emperor_name is '目标皇帝名称；用于库存和日志检索。';
comment on column retrieval_v2.claim_extraction_jobs.target_code is '目标 target_code；未知时留空。';
comment on column retrieval_v2.claim_extraction_jobs.rule_code is '任务所属 rule_code 或宽包虚拟 rule_code。';
comment on column retrieval_v2.claim_extraction_jobs.capture_profile is '任务所属抓包 profile，例如 personnel_political_wide。';
comment on column retrieval_v2.claim_extraction_jobs.candidate_payload_path is '只含 uncovered slices 的 candidates JSON 路径。';
comment on column retrieval_v2.claim_extraction_jobs.run_root is 'worker 输出 mini clean run 的根目录。';
comment on column retrieval_v2.claim_extraction_jobs.cache_root is 'filesystem claim cache 根目录；为空时 worker 可只写 PG 或使用默认值。';
comment on column retrieval_v2.claim_extraction_jobs.uncovered_slice_count is '任务中待抽取的 candidate slice 数。';
comment on column retrieval_v2.claim_extraction_jobs.job_payload is '任务完整 payload；保存 candidates path、cache path、source run 和调度策略。';
comment on column retrieval_v2.claim_extraction_jobs.attempt_count is '任务已尝试次数。';
comment on column retrieval_v2.claim_extraction_jobs.max_attempts is '任务最大尝试次数。';
comment on column retrieval_v2.claim_extraction_jobs.locked_by is '当前持有任务 lease 的 worker 标识。';
comment on column retrieval_v2.claim_extraction_jobs.locked_at is '当前任务锁获取时间。';
comment on column retrieval_v2.claim_extraction_jobs.lease_until is '当前任务锁过期时间。';
comment on column retrieval_v2.claim_extraction_jobs.last_error is '最近一次失败摘要；成功时为空。';
comment on column retrieval_v2.claim_extraction_jobs.created_at is '任务创建时间。';
comment on column retrieval_v2.claim_extraction_jobs.updated_at is '任务最近更新时间。';

comment on column retrieval_v2.claim_extraction_job_runs.id is '本表内部主键。';
comment on column retrieval_v2.claim_extraction_job_runs.run_code is 'claim 抽取运行稳定代码。';
comment on column retrieval_v2.claim_extraction_job_runs.job_id is '关联 claim_extraction_jobs.id。';
comment on column retrieval_v2.claim_extraction_job_runs.worker_id is '执行本次运行的 worker 标识。';
comment on column retrieval_v2.claim_extraction_job_runs.started_at is '本次运行开始时间。';
comment on column retrieval_v2.claim_extraction_job_runs.ended_at is '本次运行结束时间；运行中为空。';
comment on column retrieval_v2.claim_extraction_job_runs.status is '本次运行状态。';
comment on column retrieval_v2.claim_extraction_job_runs.input_fingerprint is '本次运行输入摘要 hash。';
comment on column retrieval_v2.claim_extraction_job_runs.output_fingerprint is '本次运行输出摘要 hash。';
comment on column retrieval_v2.claim_extraction_job_runs.run_root is '本次运行产物根目录。';
comment on column retrieval_v2.claim_extraction_job_runs.claim_count is '本次运行抽取并写入产物的 claim 数。';
comment on column retrieval_v2.claim_extraction_job_runs.usage_payload is '模型 usage 汇总；无模型调用时为空对象。';
comment on column retrieval_v2.claim_extraction_job_runs.error_type is '失败类型；成功时为空。';
comment on column retrieval_v2.claim_extraction_job_runs.error_msg is '失败信息摘要；成功时为空。';
comment on column retrieval_v2.claim_extraction_job_runs.run_payload is '本次运行结构化审计元数据。';
