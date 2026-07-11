create schema if not exists retrieval_v3;

-- retrieval_v3 object source cache worker 原则：
-- 1. 本迁移只建立抓包侧对象源缓存队列，不写对象池，不导入 claim，不接消费端，不触发评分。
-- 2. worker 只执行离线 seed -> object source cache build-shards -> review-audit，占位留给后续阶段编排。
-- 3. 取值有限的字段使用 PostgreSQL enum type，不用 text + check 承载状态机。

do $$
begin
    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v3'
           and t.typname = 'rv3_object_source_cache_job_status'
    ) then
        execute 'create type retrieval_v3.rv3_object_source_cache_job_status as enum (''ready'', ''running'', ''succeeded'', ''failed'', ''retry_wait'', ''cancelled'')';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v3'
           and t.typname = 'rv3_object_source_cache_run_status'
    ) then
        execute 'create type retrieval_v3.rv3_object_source_cache_run_status as enum (''running'', ''succeeded'', ''failed'', ''cancelled'')';
    end if;
end;
$$;

comment on type retrieval_v3.rv3_object_source_cache_job_status is '对象源缓存队列任务状态；ready 可领取，retry_wait 可重试，succeeded 表示缓存产物已完成。';
comment on type retrieval_v3.rv3_object_source_cache_run_status is '对象源缓存任务单次运行状态。';

create table if not exists retrieval_v3.object_source_cache_jobs (
    id bigint generated always as identity primary key,
    job_code text not null,
    idem_key text not null,
    status retrieval_v3.rv3_object_source_cache_job_status not null default 'ready',
    priority integer not null default 100,
    emperor_name text not null default '',
    capture_profile text not null default '',
    seed_jsonl_path text not null default '',
    output_root text not null default '',
    page_cache_root text not null default '',
    seed_count integer not null default 0,
    job_payload jsonb not null default '{}'::jsonb,
    attempt_count integer not null default 0,
    max_attempts integer not null default 3,
    locked_by text,
    locked_at timestamptz,
    lease_until timestamptz,
    last_error text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv3_object_source_cache_jobs_code_uk unique (job_code),
    constraint rv3_object_source_cache_jobs_idem_uk unique (idem_key),
    constraint rv3_object_source_cache_jobs_code_not_blank check (btrim(job_code) <> ''),
    constraint rv3_object_source_cache_jobs_idem_not_blank check (btrim(idem_key) <> ''),
    constraint rv3_object_source_cache_jobs_priority_positive check (priority > 0),
    constraint rv3_object_source_cache_jobs_attempts_ck check (attempt_count >= 0 and max_attempts > 0),
    constraint rv3_object_source_cache_jobs_seed_count_ck check (seed_count >= 0),
    constraint rv3_object_source_cache_jobs_payload_ck check (jsonb_typeof(job_payload) = 'object')
);

create table if not exists retrieval_v3.object_source_cache_job_runs (
    id bigint generated always as identity primary key,
    run_code text not null,
    job_id bigint not null references retrieval_v3.object_source_cache_jobs(id) on delete cascade,
    worker_id text not null default '',
    started_at timestamptz not null default now(),
    ended_at timestamptz,
    status retrieval_v3.rv3_object_source_cache_run_status not null default 'running',
    input_fingerprint text not null default '',
    output_fingerprint text not null default '',
    output_root text not null default '',
    person_count integer not null default 0,
    source_document_count integer not null default 0,
    mention_slice_count integer not null default 0,
    fetch_error_count integer not null default 0,
    review_queue_count integer not null default 0,
    run_payload jsonb not null default '{}'::jsonb,
    error_type text not null default '',
    error_msg text not null default '',
    constraint rv3_object_source_cache_job_runs_code_uk unique (run_code),
    constraint rv3_object_source_cache_job_runs_code_not_blank check (btrim(run_code) <> ''),
    constraint rv3_object_source_cache_job_runs_counts_ck check (
        person_count >= 0
        and source_document_count >= 0
        and mention_slice_count >= 0
        and fetch_error_count >= 0
        and review_queue_count >= 0
    ),
    constraint rv3_object_source_cache_job_runs_payload_ck check (jsonb_typeof(run_payload) = 'object')
);

create index if not exists rv3_object_source_cache_jobs_ready_idx
on retrieval_v3.object_source_cache_jobs(priority, created_at)
where status in ('ready', 'retry_wait');

create index if not exists rv3_object_source_cache_jobs_target_idx
on retrieval_v3.object_source_cache_jobs(emperor_name, capture_profile, status);

create index if not exists rv3_object_source_cache_job_runs_job_idx
on retrieval_v3.object_source_cache_job_runs(job_id, started_at desc);

comment on table retrieval_v3.object_source_cache_jobs is '抓包侧对象源缓存队列表：保存 seed JSONL 到离线对象源缓存的异步构建任务。';
comment on table retrieval_v3.object_source_cache_job_runs is '对象源缓存任务运行记录表：记录每次 worker attempt 的输入、输出计数和错误。';

comment on column retrieval_v3.object_source_cache_jobs.id is '本表内部主键。';
comment on column retrieval_v3.object_source_cache_jobs.job_code is '对象源缓存任务稳定代码。';
comment on column retrieval_v3.object_source_cache_jobs.idem_key is '对象源缓存任务幂等键；同一 seed、输出目录和关键参数不得重复创建任务。';
comment on column retrieval_v3.object_source_cache_jobs.status is '对象源缓存任务状态。';
comment on column retrieval_v3.object_source_cache_jobs.priority is '任务优先级；数字越小越优先。';
comment on column retrieval_v3.object_source_cache_jobs.emperor_name is '目标皇帝名称；全量对象预热或未知目标时留空。';
comment on column retrieval_v3.object_source_cache_jobs.capture_profile is '任务所属抓包 profile，例如 personnel_political_wide。';
comment on column retrieval_v3.object_source_cache_jobs.seed_jsonl_path is '输入对象 seed JSONL 路径。';
comment on column retrieval_v3.object_source_cache_jobs.output_root is '对象源缓存产物根目录。';
comment on column retrieval_v3.object_source_cache_jobs.page_cache_root is 'Wikisource 页面原文缓存根目录。';
comment on column retrieval_v3.object_source_cache_jobs.seed_count is '输入 seed 行数。';
comment on column retrieval_v3.object_source_cache_jobs.job_payload is '任务完整 payload；保存 build-shards 参数、seed 摘要和调度策略。';
comment on column retrieval_v3.object_source_cache_jobs.attempt_count is '任务已尝试次数。';
comment on column retrieval_v3.object_source_cache_jobs.max_attempts is '任务最大尝试次数。';
comment on column retrieval_v3.object_source_cache_jobs.locked_by is '当前持有任务 lease 的 worker 标识。';
comment on column retrieval_v3.object_source_cache_jobs.locked_at is '当前任务锁获取时间。';
comment on column retrieval_v3.object_source_cache_jobs.lease_until is '当前任务锁过期时间。';
comment on column retrieval_v3.object_source_cache_jobs.last_error is '最近一次失败摘要；成功时为空。';
comment on column retrieval_v3.object_source_cache_jobs.created_at is '任务创建时间。';
comment on column retrieval_v3.object_source_cache_jobs.updated_at is '任务最近更新时间。';

comment on column retrieval_v3.object_source_cache_job_runs.id is '本表内部主键。';
comment on column retrieval_v3.object_source_cache_job_runs.run_code is '对象源缓存运行稳定代码。';
comment on column retrieval_v3.object_source_cache_job_runs.job_id is '关联 object_source_cache_jobs.id。';
comment on column retrieval_v3.object_source_cache_job_runs.worker_id is '执行本次运行的 worker 标识。';
comment on column retrieval_v3.object_source_cache_job_runs.started_at is '本次运行开始时间。';
comment on column retrieval_v3.object_source_cache_job_runs.ended_at is '本次运行结束时间；运行中为空。';
comment on column retrieval_v3.object_source_cache_job_runs.status is '本次运行状态。';
comment on column retrieval_v3.object_source_cache_job_runs.input_fingerprint is '本次运行输入摘要 hash。';
comment on column retrieval_v3.object_source_cache_job_runs.output_fingerprint is '本次运行输出摘要 hash。';
comment on column retrieval_v3.object_source_cache_job_runs.output_root is '本次运行对象源缓存产物根目录。';
comment on column retrieval_v3.object_source_cache_job_runs.person_count is '本次运行覆盖的人物数。';
comment on column retrieval_v3.object_source_cache_job_runs.source_document_count is '本次运行生成的 source document 数。';
comment on column retrieval_v3.object_source_cache_job_runs.mention_slice_count is '本次运行生成的人物 mention slice 数。';
comment on column retrieval_v3.object_source_cache_job_runs.fetch_error_count is '本次运行记录的抓取错误数。';
comment on column retrieval_v3.object_source_cache_job_runs.review_queue_count is '本次运行留下的 agent review 占位队列数。';
comment on column retrieval_v3.object_source_cache_job_runs.run_payload is '本次运行结构化审计元数据。';
comment on column retrieval_v3.object_source_cache_job_runs.error_type is '失败类型；成功时为空。';
comment on column retrieval_v3.object_source_cache_job_runs.error_msg is '失败信息摘要；成功时为空。';
