"use strict";

(() => {
  const app = document.getElementById("archive-app");
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const cache = new Map();
  let battleIndex = null;
  let commanderIndex = null;
  let battleById = new Map();
  let commanderByProfile = new Map();
  let commanderByActor = new Map();
  let commanderByName = new Map();

  const resultMeaning = {
    C: "局部战术或低权重辅助结果",
    B: "重要清障、防御或单项目标，但未形成主要战略终局",
    A: "主要区域、门户、主力集团或重大阶段结果",
    "S-": "强区域终局、核心根据地或长期独立战略方向成立",
    S: "决定性击败第一梯队竞争极、国家级终局或同量级结果",
    "S+": "统一终局、多个第一梯队竞争极终局或外部霸权终局等最高量级结果",
  };
  const difficultyMeaning = {
    D0: "未形成有效军事对抗，或主要接收已崩解残余",
    D1: "本方综合优势足以稳定覆盖常规风险",
    D2: "存在一项重大难点，但总体态势仍覆盖主要风险",
    D3: "两项以上重大约束相互强化，需要高质量一线统帅才能稳定完成",
    D4: "极端劣势、孤军、断粮、被围、战线濒临崩溃或连续败退后的临阵逆转",
  };
  const militaryGrade = {
    historic: "历史级",
    top: "顶级",
    elite: "精英级",
    important: "重要级",
    capable: "有力级",
    usable: "可用级",
    ordinary: "普通级",
  };
  const roleName = {
    commander_in_chief: "最高统帅",
    principal_commander: "主力指挥",
    participant: "参战者",
    not_in_command_chain: "不在指挥链",
  };
  const capabilityName = {
    integrated_command: "统合指挥",
    independent_direction: "独立方向指挥",
    operational_design: "作战设计／高层统筹",
    tactical_execution: "战术执行",
    authorization_only: "仅授权",
    nominal_only: "仅名义责任",
  };

  async function json(path) {
    if (cache.has(path)) return cache.get(path);
    const pending = fetch(path, {cache: "force-cache"}).then(response => {
      if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
      return response.json();
    });
    cache.set(path, pending);
    return pending;
  }

  async function ensureIndexes() {
    if (battleIndex && commanderIndex) return;
    [battleIndex, commanderIndex] = await Promise.all([
      json("data/military/battles-index.json"),
      json("data/military/commanders-index.json"),
    ]);
    battleById = new Map(battleIndex.records.map(row => [row.id, row]));
    commanderByProfile = new Map(commanderIndex.records.map(row => [row.profile_ref, row]));
    commanderByActor = new Map();
    commanderByName = new Map();
    for (const row of commanderIndex.records) {
      for (const ref of row.actor_refs || []) commanderByActor.set(ref, row);
      const names = [row.name, ...(row.aliases || [])].filter(Boolean);
      for (const name of names) if (!commanderByName.has(name)) commanderByName.set(name, row);
    }
  }

  function repoHref(ref) {
    const value = String(ref || "").trim();
    if (!value) return "";
    if (/^(docs|config|reader|src)\//.test(value)) return `../${encodeURI(value)}`;
    return "";
  }

  function sourceList(refs) {
    const values = [...new Set((refs || []).filter(Boolean))];
    if (!values.length) return '<p class="muted">当前登记没有附加可直接跳转的来源定位。</p>';
    return `<div class="sources">${values.map(ref => {
      const href = repoHref(ref);
      return href ? `<a href="${href}">${esc(ref)}</a>` : `<code>${esc(ref)}</code>`;
    }).join("")}</div>`;
  }

  function archiveHead(title, eyebrow, subtitle = "") {
    return `<a class="back" href="military.html">← 返回战役与武将档案</a><div class="eyebrow">${esc(eyebrow)}</div><h1>${esc(title)}</h1>${subtitle ? `<p class="muted">${esc(subtitle)}</p>` : ""}`;
  }

  function gradeChips(result, difficulty) {
    const resultChip = result ? `<span class="chip result" title="${esc(resultMeaning[result] || "战略结果档")}">结果 ${esc(result)}</span>` : "";
    const difficultyChip = difficulty ? `<span class="chip diff" title="${esc(difficultyMeaning[difficulty] || "作战难度档")}">难度 ${esc(difficulty)}</span>` : "";
    return `<div class="chips">${resultChip}${difficultyChip}</div>`;
  }

  function normalized(value) {
    return String(value ?? "").toLocaleLowerCase("zh-CN").replace(/\s+/g, "");
  }

  function searchBattles(term) {
    const q = normalized(term);
    if (!q) return [];
    return battleIndex.records.filter(row => normalized([row.name, row.dynasty, row.period, ...(row.members || [])].join(" ")).includes(q)).slice(0, 60);
  }

  function searchCommanders(term) {
    const q = normalized(term);
    if (!q) return [];
    return commanderIndex.records.filter(row => normalized([row.name, row.dynasty, ...(row.aliases || [])].join(" ")).includes(q)).slice(0, 60);
  }

  function battleCard(row) {
    return `<a class="card" href="#battle=${encodeURIComponent(row.id)}"><strong>${esc(row.name)}</strong><small>${esc([row.dynasty, row.period].filter(Boolean).join(" · "))}</small>${gradeChips(row.result_grade, row.difficulty_grade)}${row.members?.length ? `<small>责任人物：${esc(row.members.slice(0,5).join("、"))}${row.members.length > 5 ? "…" : ""}</small>` : ""}</a>`;
  }

  function commanderCard(row) {
    const grade = row.grade ? `${militaryGrade[row.grade] || row.grade}（${row.grade}）` : "未定总档";
    return `<a class="card" href="#commander=${encodeURIComponent(row.profile_ref)}"><strong>${esc(row.name)}</strong><small>${esc(row.dynasty || "时代未标")}</small><div class="chips"><span class="chip">${esc(grade)}</span></div></a>`;
  }

  function searchView(term = "") {
    const battles = term ? searchBattles(term) : [];
    const commanders = term ? searchCommanders(term) : [];
    app.innerHTML = `<div class="eyebrow">公共军事成果 · 只读档案</div><h1>战役与武将档案</h1><p class="notice">这里直接读取公共战役登记和武将人才登记。<strong>战役结果档、作战难度档、武将全生涯总档、第一项C统帅档是四个不同概念</strong>，不会互相机械换算。</p><div class="panel"><form id="archive-search" class="toolbar"><input id="archive-q" value="${esc(term)}" placeholder="搜索战役、人物、朝代，例如：鄱阳湖、李世民、明"><button>搜索</button></form></div>${term ? `<section><h2>战役档案 <small>${battles.length}${battles.length === 60 ? "+" : ""}</small></h2><div class="cards">${battles.length ? battles.map(battleCard).join("") : '<div class="empty">没有找到匹配战役。</div>'}</div></section><section><h2>武将档案 <small>${commanders.length}${commanders.length === 60 ? "+" : ""}</small></h2><div class="cards">${commanders.length ? commanders.map(commanderCard).join("") : '<div class="empty">没有找到匹配人物。</div>'}</div></section>` : `<div class="stats"><div class="stat"><b>${battleIndex.record_count}</b><div>公共战役／战役群登记</div></div><div class="stat"><b>${commanderIndex.profile_count}</b><div>军事人才档案</div></div></div><section class="panel"><h2>S− / D3 到底是什么？</h2><p><strong>左边是战略结果档</strong>：回答“这场战役最终兑现了多大的战略结果”；<strong>右边是作战难度档</strong>：回答“在战前条件下，这个军事问题本身有多难”。两者彼此独立。</p><div class="grade-grid">${Object.entries(resultMeaning).map(([k,v]) => `<div><strong>${esc(k)}</strong><br><small>${esc(v)}</small></div>`).join("")}</div><div class="grade-grid" style="margin-top:10px">${Object.entries(difficultyMeaning).map(([k,v]) => `<div><strong>${esc(k)}</strong><br><small>${esc(v)}</small></div>`).join("")}</div></section>`}<p class="footer">档案不重新裁决任何战役或人物，只把正式登记中的结构化字段翻译为阅读页面。</p>`;
    document.getElementById("archive-search")?.addEventListener("submit", event => {
      event.preventDefault();
      const q = document.getElementById("archive-q")?.value.trim() || "";
      location.hash = q ? `#search=${encodeURIComponent(q)}` : "";
    });
  }

  async function battleRecord(row) {
    const payload = await json(`../${row.source}`);
    return (payload.records || []).find(record => record.war_event_id === row.id) || null;
  }

  async function commanderRecord(row) {
    const payload = await json(`../${row.source}`);
    return (payload.profiles || []).find(profile => profile.profile_ref === row.profile_ref) || null;
  }

  function memberCommander(member) {
    return commanderByActor.get(member.actor_ref) || commanderByName.get(member.actor_name) || null;
  }

  function memberBlock(member) {
    const idx = member.person_command_index || {};
    const result = (member.person_command_result || [])[0] || {};
    const commander = memberCommander(member);
    const profileLink = commander ? `<a href="#commander=${encodeURIComponent(commander.profile_ref)}">打开武将档案 →</a>` : "";
    const personGrade = result.result_tier || idx.projected_result_tier;
    const personDifficulty = result.combat_difficulty || idx.projected_combat_difficulty;
    return `<div class="member"><div class="member-head"><strong>${esc(member.actor_name || "未具名")}</strong><span>${esc(roleName[member.role_code] || member.role_code || "角色未标")}</span></div>${gradeChips(personGrade, personDifficulty)}${idx.capability_mode ? `<small>能力责任：${esc(capabilityName[idx.capability_mode] || idx.capability_mode)}</small>` : ""}${idx.basis || member.contribution_scope ? `<p class="prose">${esc(idx.basis || member.contribution_scope)}</p>` : ""}${profileLink ? `<p class="sources">${profileLink}</p>` : ""}</div>`;
  }

  async function renderBattle(id) {
    const row = battleById.get(id);
    if (!row) { app.innerHTML = '<div class="empty">没有找到这个战役档案。<br><a href="military.html">返回搜索</a></div>'; return; }
    app.innerHTML = '<div class="empty">正在读取正式战役登记…</div>';
    const record = await battleRecord(row);
    if (!record) { app.innerHTML = '<div class="empty">战役索引与正式分片失步。</div>'; return; }
    const period = row.period || "年代未标";
    const process = record.battle_process || record.canonical_label || "";
    const observable = record.observable_result || "";
    const tierBasis = record.tier_basis || "";
    const diffBasis = record.combat_difficulty_basis || "";
    const cost = record.cost_or_burden || record.cost_summary || "当前登记未形成可单独展示的成本摘要。";
    const members = (record.members || []).filter(member => member.actor_kind === "person");
    app.innerHTML = `${archiveHead(record.canonical_label || id, `${record.dynasty || ""} · 战役档案`, period)}${gradeChips(record.campaign_tier, record.combat_difficulty)}<section class="panel"><h2>战役过程与结果</h2>${process ? `<div class="label">过程摘要</div><p class="prose">${esc(typeof process === "string" ? process : JSON.stringify(process))}</p>` : ""}${observable ? `<div class="label">可观察结果</div><p class="prose">${esc(observable)}</p>` : ""}</section><section class="panel"><h2>为什么是 ${esc(record.campaign_tier || "未定结果档")} / ${esc(record.combat_difficulty || "未定难度档")}？</h2><div class="label">战略结果档</div><p><strong>${esc(record.campaign_tier || "—")}</strong>：${esc(resultMeaning[record.campaign_tier] || "按正式战役登记裁定。")}</p>${tierBasis ? `<p class="prose">${esc(tierBasis)}</p>` : ""}<div class="label">作战难度档</div><p><strong>${esc(record.combat_difficulty || "—")}</strong>：${esc(difficultyMeaning[record.combat_difficulty] || "按正式战役登记裁定。")}</p>${diffBasis ? `<p class="prose">${esc(diffBasis)}</p>` : ""}<p class="notice">结果档衡量“做成了多大的事”，难度档衡量“这件事原本有多难”。高结果不自动等于高难度，反之亦然。</p></section><section class="panel"><h2>军事成本</h2><p class="prose">${esc(typeof cost === "string" ? cost : JSON.stringify(cost))}</p>${record.uncertainties?.length ? `<details><summary>成本与材料限制</summary><ul>${record.uncertainties.map(v => `<li>${esc(v)}</li>`).join("")}</ul></details>` : ""}<p class="muted">这里只展示该战役登记已有的成本事实；不能用单场战役成本反推第一项或第三项的总体军事成本档。</p></section><section class="panel"><h2>责任人物</h2>${members.length ? members.map(memberBlock).join("") : '<p class="muted">当前登记没有闭合到具名人物责任。</p>'}</section><section class="panel"><h2>正式来源</h2>${sourceList(record.source_refs || record.source_lineage?.source_revision_refs)}</section>`;
  }

  function achievementBlock(item) {
    const ref = item.campaign_ref || item.capability_episode_ref;
    const battleId = battleIndex.result_ref_to_battle?.[ref];
    const link = battleId ? `<a href="#battle=${encodeURIComponent(battleId)}">打开对应战役档案 →</a>` : "";
    return `<div class="achievement"><strong>${esc(item.canonical_label || ref || "军事能力记录")}</strong>${gradeChips(item.campaign_tier || item.parent_campaign_tier, item.combat_difficulty || item.parent_combat_difficulty)}${item.capability_mode ? `<small>责任模式：${esc(capabilityName[item.capability_mode] || item.capability_mode)}</small>` : ""}${item.basis ? `<p class="prose">${esc(item.basis)}</p>` : ""}${link ? `<p class="sources">${link}</p>` : ""}</div>`;
  }

  async function renderCommander(profileRef) {
    const row = commanderByProfile.get(profileRef);
    if (!row) { app.innerHTML = '<div class="empty">没有找到这个武将档案。<br><a href="military.html">返回搜索</a></div>'; return; }
    app.innerHTML = '<div class="empty">正在读取正式武将登记…</div>';
    const profile = await commanderRecord(row);
    if (!profile) { app.innerHTML = '<div class="empty">武将索引与正式分片失步。</div>'; return; }
    const grade = profile.military_grade ? `${militaryGrade[profile.military_grade] || profile.military_grade}（${profile.military_grade}）` : "未定总档";
    const achievements = profile.consumed_achievements || [];
    const domainGrades = profile.domain_grades || {};
    app.innerHTML = `${archiveHead(profile.person || row.name, `${profile.dynasty || row.dynasty || ""} · 武将档案`, "全生涯军事人才聚合档案") }<section class="panel"><h2>${esc(grade)}</h2><p>这是公共军事人才登记的<strong>全生涯聚合档</strong>，综合峰值、独立复验、稳定性和重大反证；它不是某一场战役的结果档，也不能机械换算为皇帝第一项C档。</p><div class="chips"><span class="chip">证据状态 ${esc(profile.grade_status || "未标")}</span><span class="chip">稳定性 ${esc(profile.stability_status || "未标")}</span>${profile.capability_episode_count != null ? `<span class="chip">能力记录 ${esc(profile.capability_episode_count)}</span>` : ""}</div></section>${Object.keys(domainGrades).length ? `<section class="panel"><h2>领域档</h2><div class="grade-grid">${Object.entries(domainGrades).map(([key,value]) => `<div><strong>${esc(key)}</strong><br><small>${esc(value?.grade || "—")} · ${esc(value?.grade_status || "")}</small></div>`).join("")}</div></section>` : ""}<section class="panel"><h2>代表性军事能力记录</h2>${achievements.length ? achievements.map(achievementBlock).join("") : '<p class="muted">当前登记没有可展示的已消费军事能力记录。</p>'}</section>${profile.major_adverse_episode_refs?.length ? `<section class="panel"><h2>重大反向记录</h2><ul>${profile.major_adverse_episode_refs.map(ref => `<li>${esc(ref)}</li>`).join("")}</ul></section>` : ""}<section class="panel"><h2>档案说明</h2><p class="notice">武将总档回答“全生涯军事能力证据整体达到什么层级”；单场战役的S/A/B与D0—D4回答“结果多大、问题多难”；第一项C只消费指定创业／统一窗口内、且能归责给君主本人的军事能力。三套尺度不能互换。</p></section>`;
  }

  async function route() {
    try {
      await ensureIndexes();
      const hash = location.hash.slice(1);
      if (hash.startsWith("battle=")) return renderBattle(decodeURIComponent(hash.slice(7)));
      if (hash.startsWith("commander=")) return renderCommander(decodeURIComponent(hash.slice(10)));
      if (hash.startsWith("search=")) return searchView(decodeURIComponent(hash.slice(7)));
      return searchView("");
    } catch (error) {
      console.error(error);
      app.innerHTML = `<div class="empty">战役档案加载失败：${esc(error.message || error)}<br><a href="index.html">返回人物总览</a></div>`;
    }
  }

  window.addEventListener("hashchange", route);
  route();
})();
