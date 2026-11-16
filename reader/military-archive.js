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
  const searchStates = new Map();
  let lastSearch = "";
  let activeSearch = null;
  let renderSequence = 0;
  let activeEvidence = null;
  let activeBattleId = "";

  document.title = "帝王三镜 · 军事档案";
  const headerMeta = document.querySelector("header span");
  if (headerMeta) headerMeta.textContent = "战役档案 · 统帅档案";

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
  const gradeStatusName = {
    current_battle_registry_grade: "正式战役登记已闭合",
    evidence_lower_bound: "现有证据下限",
  };
  const stabilityStatusName = {
    major_failure_with_effective_recovery: "重大失败后完成有效重建，损失仍限制上沿",
    no_comparable_major_failure_established: "未发现足以压低总档的同量级重大失败",
    stability_limited_major_failure: "受一次重大失败限制",
    stability_limited_repeated_major_failures: "受多次重大失败限制",
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
  const publicMilitaryTerms = {
    external_state: "外部国家",
    subject_phase_views: "分主体阶段记录",
    strategic_gateway: "战略门户",
    local_point: "局部据点",
    very_low: "很低",
    campaign_group: "战役群",
    military_system_collapsed: "军事体系瓦解",
    decisive_creator: "起决定作用的主导者",
    co_decisive: "共同起决定作用",
    stage_executor: "执行本阶段任务",
    decisive_successor: "接手后完成关键成果",
    terminal_finisher: "完成战役收束",
    no_frontline_difficulty: "未取得可单列的前线难度",
    war_conduct_negative: "负面战争行为",
    command_adverse: "负向指挥结果",
    causal_fault: "可归责的过错",
    stability_limited_major_failure: "重大失败限制稳定性判断",
    stability_limited_repeated_major_failures: "反复重大失败限制稳定性判断",
    important_objective: "重要目标",
    major_stage_or_crisis: "重要阶段或危机逆转",
    single_integrated_command: "单一统帅统合指挥",
    large_region: "大区域",
    limited_attrition: "有限消耗",
    operational_cost: "作战代价",
    founding_startup_ledger: "建国起步阶段",
    local_rebellion: "地方叛乱",
    local_degradation: "局部作战能力受损",
    internal_commander: "内部军事指挥者",
    leadership_removed: "对手首领被清除",
    not_responsible: "不承担该项责任",
    not_responsible_in_this_parent: "不承担整场战役责任",
    command_failure: "指挥失利",
    person_result_required: "仍需单列本人指挥结果",
    operational_direction: "方面作战方向",
    full_campaign: "整场战役",
    fact_id: "史实登记",
    capability_episode_ref: "能力情境",
    usable_one_b_result_with_major_failure: "一项B级成果，同时保留重大失败",
    usable_one_b_result_with_adverse_contexts: "一项B级成果，同时保留不利情境",
    usable_one_b_result: "一项B级成果",
    important_one_a_d2_result: "一项A级、难度D2成果",
    important_two_a_results: "两项A级成果",
    elite_two_d3_major_results: "两项难度D3的重要成果",
    top_s_peak_with_independent_a: "S级峰值及独立A级复验",
    capable_operational_s_minus_result: "S−级作战成果",
    elite_blocked_by_failure_pressure: "重大失败限制精英级路径",
    top_blocked_by_failure_pressure: "重大失败限制顶级路径",
    top_s_minus_peak_with_independent_rechecks: "有独立复验的高阶战略成果",
    main_force_destroyed: "主力被摧毁",
    major_degradation: "主力受到严重削弱",
    CIC: "最高实际主帅",
    T_core: "核心统一完成时间",
    D_NOT_REQUIRED: "不适用难度分档",
    ATTACKER: "进攻方", DEFENDER: "防守方", THIRD_PARTY: "第三方",
    HIGH_RETURN: "高回报", LOW_RETURN: "低回报", MEDIUM_RETURN: "中等回报",
    NEGATIVE_RETURN: "负回报", NO_RETURN: "未形成回报",
    CONFIRMED: "已确认", GAIN: "取得控制", LOSS: "失去控制",
    PROPORTIONATE_RETURN: "回报与投入大致相称",
    HOLD:"保持控制", NONE:"无控制变化", WITHDRAWAL:"撤出", RECOVER:"恢复控制", RESTORE:"恢复控制",
    RAID:"袭扰", SIEGE:"围困", DEVASTATION:"破坏", SUPPRESS:"镇压", REALIGN:"归属转变", INCURSION:"入侵",
    GAIN_THEN_REVERSED:"取得后失去", INTERDICT:"阻断", HOLD_UNCONFIRMED:"保持情况未确认",
    LOSS_OF_SUPPLY:"失去补给", TEMPORARY_GAIN:"暂时取得", TEMPORARY_OCCUPATION:"暂时占据",
    TEMPORARY_LOSS:"暂时失去", TEMPORARY_BREAKTHROUGH:"暂时突破", DESTROY:"摧毁", ASSET_LOSS:"资产损失",
    ENDED:"已经结束", FAILED:"未能实现", HELD:"保持控制", HELD_AT_VOLUME_END:"本卷结束时保持",
    HELD_BY_DEFENDER:"防守方保持", HELD_BY_OPPONENT:"对方保持", HELD_BY_REBEL:"反叛方保持",
    HELD_ON_CONTRACTED_LINE:"收缩防线后保持", HELD_ON_REDUCED_LINE:"缩小范围后保持",
    HELD_OR_FAILED_GAIN:"守住原有控制或未能取得新控制", HELD_POLITICALLY:"政治上保持控制",
    HELD_UNTIL_NEXT_PHASE:"保持至下一阶段", HELD_UNTIL_SETTLEMENT:"保持至和解",
    LOST_AS_FORCE:"作为军事力量瓦解", LOST_AS_OFFENSIVE:"攻势终止", LOST_AS_REBELLION:"反叛被平定",
    LOST_AS_THREAT:"威胁解除", LOST_AT_FIELD:"在战场失去", LOST_AT_PHASE_END:"阶段结束时失去",
    LOST_AT_VOLUME_END:"本卷结束时失去", LOST_BY_ALLY:"盟方失去",
    NOT_REASSESSED:"未另行重评", NO_CONTROL:"没有控制", NO_CONTROL_GAIN:"没有新增控制", NO_STABLE_GAIN:"未形成稳定取得",
    RECOVERED_AFTER_WITHDRAWAL:"撤退后恢复", RECOVERED_LATER:"随后恢复", RECOVERED_SAME_DAY:"当天恢复",
    RECOVERY_REQUIRED:"尚待恢复", REVERSED:"已经逆转", REVERSED_LATER:"后来逆转", REVERSED_OR_UNRESOLVED:"逆转或尚未明确",
    REVERSED_WITHIN_VOLUME:"本卷内逆转", WITHDRAWN:"已经撤出", WITHDRAWN_AFTER_SEVEN_MONTHS:"七个月后撤出",
    POSTWAR_SETTLEMENT:"战后处置",
    HELD_AT_PHASE_END: "阶段结束时保持", LOST: "已经失去",
    NOT_APPLICABLE: "不适用", UNKNOWN: "未明确", UNRESOLVED: "尚未解决",
    shared: "共同责任", secondary: "次要责任",
    low: "低", medium: "中", high: "高",
    elite: "精英级",
    primary: "主要责任",
    failure: "失败记录",
    HYBRID: "本人直接承担关键统帅责任，同时由其他将领分担执行",
    DIRECT: "本人直接承担主要统帅责任",
    DELEGATED: "主要由受命将领执行",
    SHARED: "多人共同承担",
    POSITIVE: "正向",
    NEGATIVE: "负向",
    MIXED: "正负并存",
    FULL_COMMAND: "完整指挥责任",
    PARTIAL_COMMAND: "部分指挥责任",
    STRATEGIC_DIRECTION: "战略方向责任",
    OPERATIONAL_COMMAND: "战役／战区指挥责任",
    TACTICAL_COMMAND: "战术执行责任",
    AUTHORIZATION_ONLY: "仅授权责任",
    NOMINAL_ONLY: "仅名义责任",
  };
  const commanderRoutes = {
    historic_era_defining_peak: "时代罕见的终局峰值与独立复验",
    historic_extreme_problem_solver: "极难军事问题的多次独立解答",
    historic_sustained_grand_command: "持续的大统帅履历",
    top_national_strategic_peak: "国家级战略峰值及独立复验",
    top_hard_problem_solver: "高难军事问题的反复解答",
    top_sustained_first_line_command: "持续的一线统帅履历",
    elite_strategic_peak: "决定性的战略峰值",
    elite_hard_campaign_specialist: "独立高难战役成果",
    elite_reliable_major_command: "可靠的多次方面指挥",
    one_realized_command_result: "已有本人实现的军事贡献",
    no_consumable_positive_command_result: "现有记录未形成可采用的本人正向军事贡献",
    one_hard_a_or_two_independent_a: "高难A级成果或两项独立A级成果",
    one_a_or_two_independent_b: "一项A级成果或两项独立B级成果",
  };
  const narrativeTerms = {...militaryGrade, ...publicMilitaryTerms, ...commanderRoutes};
  const narrativeTermPattern = new RegExp(`\\b(?:${Object.keys(narrativeTerms).join("|")})\\b`, "g");
  const resultOrder = ["C", "B", "A", "S-", "S", "S+"];
  const difficultyOrder = ["D0", "D1", "D2", "D3", "D4"];
  function dynastyLabel(value) {
    const name = {ming:"明",qing:"清",yuan:"元",jin:"金",liao:"辽",north_song:"北宋",south_song:"南宋",xixia:"西夏",five_dynasties:"五代十国",qin_tang:"秦至唐"}[value];
    return name ? `${name}资料分区` : value || "";
  }
  const asList = value => Array.isArray(value) ? value.filter(item => item != null) : value && typeof value === "object" ? [value] : [];
  const directionName = value => ({negative:"负向／失败", defeat:"负向／失败", mixed:"正负并存", mixed_review:"正负并存", not_applicable:"不适用个人结果评价", positive:"正向", victory:"正向", neutral:"中性"}[value] || "方向未单列");
  const resultLabel = value => ["negative", "defeat"].includes(value) ? "损失量级" : ["mixed", "mixed_review"].includes(value) ? "得失量级" : "结果量级";
  function publicBattleTitle(value) {
    return publicMilitaryText(String(value || "").replace(/(?:战争|战役)?(?:父级|父群)$/, "战役"));
  }
  function resultExplanation(grade, direction) {
    if (["negative", "defeat"].includes(direction)) return "按本条记录的实际损失定档。";
    if (["mixed", "mixed_review"].includes(direction)) return "按本条记录的综合得失定档。";
    return resultMeaning[grade] || "";
  }
  function battleForRef(ref) {
    return battleById.get(ref) || battleById.get(battleIndex.result_ref_to_battle?.[ref]) || null;
  }

  function publicMilitaryText(value) {
    let output = String(value ?? "");
    const terms = {first_tier_pole:"第一梯队竞争力量",capital_or_state_survival:"首都或国家存续",core_heartland:"核心腹地",important_region:"重要区域",dominant_pole:"主导竞争极",regional_major:"区域主要对手",strong:"强盛",viable:"仍具作战能力",residual:"残余体系",defeat:"失败",victory:"胜利",failed:"未完成",complete:"完成",partial:"部分完成",mixed:"得失并存",objective_shortfall:"未完成目标",objective_shortfalls:"未完成目标",unknown:"未明确",unresolved:"尚未确认"};
    output = output.replace(/\b[a-z]+(?:_[a-z]+)*\b/g, word => terms[word] || word);
    output = output.replace(narrativeTermPattern, key => narrativeTerms[key]);
    return output
      .replace(/\bevent_start_year=(-?\d+)；event_end_year=(-?\d+)；calendar=CE(?:；source_window=([^；。]+))?；precision=year/g,
        (_, start, end, window) => (start === end ? start + "年" : start + "—" + end + "年") + (window ? "（史料覆盖" + window + "）" : ""))
      .replace(/\bstable_delivery=false\b/g, "本次成果不单列稳定性复验")
      .replace(/\bstable_delivery=true\b/g, "本次成果列入稳定性复验")
      .replace(/\bruler_binding\b/g, "君主归责记录")
      .replace(/\bmixed_review\b/g, "正负并存")
      .replace(/\battributable_failure\b/g, "可归责的军事失利")
      .replace(/\bperson_result\b/g, "本人指挥结果")
      .replace(/\bexternal_hegemony\b/g, "域外霸权级对手")
      .replace(/—?\border_only\b/g, "（仅能确认先后顺序）")
      .replace(/`?\b(?:SRC-[A-Z0-9-]+|[PL]\d{4})\b`?(?:[、，,\s]+`?\b(?:SRC-[A-Z0-9-]+|[PL]\d{4})\b`?)*/g, "所引段落")
      .replace(/[，；]?现有(S[+−-]?|[ABC])保持[。；]?/g, "。")
      .replace(/消费/g, "采用")
      .replace(/父群|父级/g, "整场战役")
      .replace(/闭合/g, "确认")
      .replace(/\bcommander_in_chief\b/gi, "最高统帅")
      .replace(/\bprincipal_commander\b/gi, "主力指挥")
      .replace(/\bparticipant\b/gi, "参战者")
      .replace(/\bnot_in_command_chain\b/gi, "不在指挥链")
      .replace(/\bintegrated_command\b/gi, "统合指挥")
      .replace(/\bindependent_direction\b/gi, "独立方向指挥")
      .replace(/\boperational_design\b/gi, "作战设计／高层统筹")
      .replace(/\btactical_execution\b/gi, "战术执行")
      .replace(/\bauthorization_only\b/gi, "仅授权")
      .replace(/\bnominal_only\b/gi, "仅名义责任")
      .replace(/\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b/g, "分类状态")
      .replace(/\s+/g, " ")
      .trim();
  }

  function militaryReadingParts(value) {
    const original = String(value ?? "").trim();
    const text = publicMilitaryText(original)
      .replace(/正负并存的正负并存/g, "正负并存")
      .replace(/整场战役整场战役/g, "整场战役")
      .replace(/实际正果[：:]/g, "取得的成果：")
      .replace(/实际不利及边界[：:]/g, "损失与限制：")
      .replace(/保留情况[：:]/g, "评价边界：");
    // Keep clauses intact. Only explicit accounting instructions move to the
    // boundary fold; no result, attribution or grade is inferred or discarded.
    const boundaryStart = /^(?:不复制|不继承|不采用|不重复计|不另计|不再另计|不称|评价边界[：:]|仅采用本条|仅采用本人的|按同一军令下.*登记)/;
    const clauses = text.match(/[^；。]+[；。]?/g) || [];
    const facts = [], boundaries = [];
    for (const clause of clauses) {
      const pieces = clause.split(/(?<=[，,])(?=不复制|不继承|不重复计|不另计|不再另计)/);
      for (const piece of pieces) {
        const cleaned = piece.trim();
        if (!cleaned) continue;
        (boundaryStart.test(cleaned) ? boundaries : facts).push(cleaned);
      }
    }
    return {original, text, facts, boundaries};
  }

  function militaryProse(value) {
    const reading = militaryReadingParts(value);
    if (!reading.original) return "";
    const paragraph = parts => parts.length ? `<p class="prose">${esc(parts.join(" ").replace(/[，,；;]$/, "。"))}</p>` : "";
    const boundaryText = reading.boundaries.map(text => text
      .replace(/不复制整场战役([SABCDE][+−-]?)/g, "不能把整场战役的$1档直接作为本人的评价")
      .replace(/仅采用本条已有本人角色与成果范围/g, "这里只评价已明确的本人作用与成果范围")
      .replace(/不继承整场战役、其他将领或其他周期/g, "不把整场战役、其他将领或其他时期的成果一并归于本人"));
    const boundaries = reading.boundaries.length
      ? `<details class="military-reading-boundary"><summary>评价范围与归责说明</summary>${paragraph(boundaryText)}</details>` : "";
    const original = reading.boundaries.length || reading.text !== reading.original
      ? `<details class="military-reading-original"><summary>查看原始表述</summary><p class="prose">${esc(reading.original)}</p></details>` : "";
    return paragraph(reading.facts) + boundaries + original;
  }

  function publicMilitaryTerm(value, mapping, fallback) {
    const raw = String(value ?? "").trim();
    if (!raw) return fallback;
    if (mapping[raw]) return mapping[raw];
    const translated = publicMilitaryText(raw);
    if (translated.includes("分类状态")) return fallback;
    if (translated !== raw) return translated;
    return /^[A-Za-z][A-Za-z0-9_]*$/.test(raw) ? fallback : raw;
  }

  function validatedRawUrl(path) {
    const local = String(path || "").replace(/^\.\.\//, "").split("#", 1)[0];
    const localHost = ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname);
    if (!localHost && typeof READER_SOURCE_REPOSITORY !== "undefined" && typeof READER_SOURCE_REVISION !== "undefined" &&
        READER_SOURCE_REPOSITORY && READER_SOURCE_REVISION) {
      const repo = READER_SOURCE_REPOSITORY.split("/").map(encodeURIComponent).join("/");
      const file = local.split("/").map(encodeURIComponent).join("/");
      return `https://raw.githubusercontent.com/${repo}/${encodeURIComponent(READER_SOURCE_REVISION)}/${file}`;
    }
    return `../${local}?raw=1`;
  }

  function expandBattleSourceReferences(record) {
    function phaseObjects(input) {
      const field = "phase_object_catalog", refKey = "phase_object_ref";
      const fields = new Set(["axis_source_refs", "P_inference", "border_control", "ruler_binding", "founding_startup_ledger", "cost_axes", "cost_axis_basis", "cost_evidence"]);
      const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
      const catalog = has(input, field) ? input[field] : {};
      if (!catalog || Array.isArray(catalog) || typeof catalog !== "object" ||
          (has(input, field) && !Object.keys(catalog).length)) throw new Error("战役阶段对象目录无效");
      const used = new Map(), signatures = new Set();
      function check(value) {
        if (Array.isArray(value)) value.forEach(check);
        else if (value && typeof value === "object") {
          if (has(value, field) || has(value, refKey)) throw new Error("战役阶段对象目录嵌套引用");
          Object.values(value).forEach(check);
        }
      }
      for (const [ref, entry] of Object.entries(catalog)) {
        if (!ref || !entry || Array.isArray(entry) || typeof entry !== "object" ||
            Object.keys(entry).length !== 2 || !has(entry, "field") || !has(entry, "value") ||
            !fields.has(entry.field) || !entry.value || Array.isArray(entry.value) || typeof entry.value !== "object")
          throw new Error("战役阶段对象目录条目无效");
        check(entry.value);
        const signature = JSON.stringify([entry.field, entry.value]);
        if (signatures.has(signature)) throw new Error("战役阶段对象目录重复");
        signatures.add(signature);
      }
      function expand(value) {
        if (Array.isArray(value)) return value.map(expand);
        if (!value || typeof value !== "object") return value;
        if (has(value, field) || has(value, refKey)) throw new Error("战役阶段对象引用位置非法");
        return Object.fromEntries(Object.entries(value).map(([key, child]) => {
          if (child && typeof child === "object" && has(child, refKey)) {
            const ref = child[refKey];
            if (Object.keys(child).length !== 1 || typeof ref !== "string" || !has(catalog, ref) || key !== catalog[ref].field)
              throw new Error("战役阶段对象引用悬空或跨字段");
            used.set(ref, (used.get(ref) || 0) + 1);
            return [key, JSON.parse(JSON.stringify(catalog[ref].value))];
          }
          return [key, expand(child)];
        }));
      }
      const result = expand(Object.fromEntries(Object.entries(input).filter(([k]) => k !== field)));
      if (used.size !== Object.keys(catalog).length || [...used.values()].some(n => n < 2))
        throw new Error("战役阶段对象目录存在未共用条目");
      return result;
    }
    record = phaseObjects(record);
    const field = "source_reference_catalog", refKey = "source_list_ref";
    const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
    const sourceKey = k => k.endsWith("source_refs") || ["source_anchor_refs", "source_revision_refs"].includes(k);
    const catalog = has(record, field) ? record[field] : {};
    if (!catalog || Array.isArray(catalog) || typeof catalog !== "object" ||
        (has(record, field) && !Object.keys(catalog).length)) throw new Error("战役来源目录无效");
    const used = new Map(), signatures = new Set();
    function check(value) {
      if (Array.isArray(value)) value.forEach(check);
      else if (value && typeof value === "object") {
        if (has(value, field) || has(value, refKey)) throw new Error("战役来源目录含占位符");
        Object.values(value).forEach(check);
      }
    }
    for (const [ref, value] of Object.entries(catalog)) {
      if (!ref || !Array.isArray(value)) throw new Error("战役来源目录条目无效");
      check(value);
      const signature = JSON.stringify(value);
      if (signatures.has(signature)) throw new Error("战役来源目录重复");
      signatures.add(signature);
    }
    function expand(value) {
      if (Array.isArray(value)) return value.map(expand);
      if (!value || typeof value !== "object") return value;
      if (has(value, field) || has(value, refKey)) throw new Error("战役来源引用位置非法");
      return Object.fromEntries(Object.entries(value).map(([key, child]) => {
        if (child && typeof child === "object" && has(child, refKey)) {
          const ref = child[refKey];
          if (!sourceKey(key) || Object.keys(child).length !== 1 || typeof ref !== "string" || !has(catalog, ref))
            throw new Error("战役来源引用悬空或格式错误");
          used.set(ref, (used.get(ref) || 0) + 1);
          return [key, JSON.parse(JSON.stringify(catalog[ref]))];
        }
        return [key, expand(child)];
      }));
    }
    const result = expand(Object.fromEntries(Object.entries(record).filter(([k]) => k !== field)));
    if (used.size !== Object.keys(catalog).length || [...used.values()].some(n => n < 2))
      throw new Error("战役来源目录存在未共用条目");
    return result;
  }

  function expandTalentEvidence(profile) {
    const field = "talent_evidence_catalog", refKey = "talent_evidence_ref";
    const fields = ["consumed_achievements", "capability_episode_anchors", "negative_or_mixed_command_records", "failure_accountability"];
    const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
    const catalog = has(profile, field) ? profile[field] : {};
    if (!catalog || Array.isArray(catalog) || typeof catalog !== "object" ||
        (has(profile, field) && !Object.keys(catalog).length)) throw new Error("人才证据目录无效");
    function check(value) {
      if (Array.isArray(value)) value.forEach(check);
      else if (value && typeof value === "object") {
        if (has(value, field) || has(value, refKey)) throw new Error("人才证据含嵌套目录或越界占位符");
        Object.values(value).forEach(check);
      }
    }
    const signatures = new Set(), used = new Map();
    for (const [ref, value] of Object.entries(catalog)) {
      if (!ref || !value || Array.isArray(value) || typeof value !== "object" || Object.keys(value).length < 2)
        throw new Error("人才证据目录条目无效");
      check(value);
      const signature = JSON.stringify(value);
      if (signatures.has(signature)) throw new Error("人才证据目录重复");
      signatures.add(signature);
    }
    const result = JSON.parse(JSON.stringify(Object.fromEntries(Object.entries(profile).filter(([key]) => key !== field))));
    for (const key of fields) {
      if (!Array.isArray(result[key])) continue;
      result[key] = result[key].map(value => {
        if (!value || typeof value !== "object" || !has(value, refKey)) return value;
        const ref = value[refKey], suffix = value.fields;
        if (Array.isArray(value) || Object.keys(value).length !== 2 || !has(value, "fields") || typeof ref !== "string" || !has(catalog, ref) ||
            !suffix || Array.isArray(suffix) || typeof suffix !== "object" || Object.keys(suffix).some(k => has(catalog[ref], k)))
          throw new Error("人才证据引用悬空、格式无效或覆盖共享字段");
        check(suffix);
        used.set(ref, (used.get(ref) || 0) + 1);
        return {...JSON.parse(JSON.stringify(catalog[ref])), ...suffix};
      });
    }
    check(result);
    if (used.size !== Object.keys(catalog).length || [...used.values()].some(n => n < 2))
      throw new Error("人才证据目录存在未共用条目");
    return result;
  }

  async function json(path) {
    if (cache.has(path)) return cache.get(path);
    const url = path.startsWith("../") ? validatedRawUrl(path) : path;
    const pending = fetch(url, {cache: "no-cache"}).then(response => {
      if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
      return response.json();
    }).then(payload => {
      if (payload.schema_version === "battle-registry-shard-v1")
        payload.records = payload.records.map(expandBattleSourceReferences);
      if (payload.schema_version === "military-talent-registry-shard-v1") {
        if (payload.evidence_storage != null && payload.evidence_storage !== "military-talent-evidence-prefixes-v1")
          throw new Error("人才证据存储版本无效");
        if (payload.evidence_storage == null && payload.profiles.some(p => Object.prototype.hasOwnProperty.call(p, "talent_evidence_catalog")))
          throw new Error("人才证据分片缺少存储声明");
        payload.profiles = payload.profiles.map(expandTalentEvidence);
      }
      return payload;
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

  function originalSourceUrl(ref) {
    const value = String(ref || "").trim();
    const url = ReaderSourceLinks.externalSource(value);
    if (url) return url;
    const source = value.match(/^([^/@]+\/[^@]+)@([^#]*)(?:#(.*))?$/);
    if (source) {
      const revision = /^\d+$/.test(source[2]) ? `?oldid=${source[2]}` : "";
      return `https://zh.wikisource.org/wiki/${encodeURI(source[1])}${revision}`;
    }
    return "";
  }

  function sourceList(refs) {
    const values = [...new Set((refs || []).filter(Boolean))];
    const entries = values.map(ref => {
      const cardIndex = activeEvidence?.source_cards?.findIndex(card => card.refs.includes(ref)) ?? -1;
      if (cardIndex >= 0) {
        const card = activeEvidence.source_cards[cardIndex];
        return `<p><a href="#battle=${encodeURIComponent(activeBattleId)}&source=${cardIndex}">${esc(card.source_volume || card.title)} · 查看摘句与定位 →</a></p>`;
      }
      const unit = String(ref).match(/^(SRC-.+)-P\d+$/)?.[1];
      const volume = unit && activeEvidence?.source_cards?.find(card => card.refs.some(anchor => String(anchor).startsWith(unit + "-P")));
      if (volume) {
        const url = originalSourceUrl(volume.source_url) || originalSourceUrl(`${volume.source_volume}@${volume.revision || ""}`);
        if (url) return `<p><a href="${esc(url)}" target="_blank" rel="noopener">《${esc(volume.source_volume)}》 · 阅读原卷 ↗</a></p>`;
      }
      const battle = battleForRef(ref);
      if (battle) {
        const phase = /-P\d+$/.test(ref) ? `&phase=${encodeURIComponent(ref)}` : "";
        return `<p><a href="#battle=${encodeURIComponent(battle.id)}${phase}">${esc(battle.name)}${phase ? " · 对应主体阶段" : ""} →</a></p>`;
      }
      const href = originalSourceUrl(ref);
      const source = String(ref).match(/^([^@]+)@([^#]*)(?:#(.*))?$/);
      const locator = !source && String(ref).match(/^([^/#]+\/卷[^#]+)#(.+)$/);
      const title = source || locator ? `《${(source || locator)[1].replace("/", " · ")}》`
        : href ? "所引史源" : ReaderSourceLinks.citationTitle(ref, "");
      const excerpt = source ? (source[3] || (/^\d+$/.test(source[2]) ? "" : source[2])) : locator ? publicMilitaryText(locator[2]) : "";
      if (!title) return "";
      return `<p>${href ? `<a href="${esc(href)}" target="_blank" rel="noopener">${esc(title)} · 阅读来源 ↗</a>` : esc(title)}${excerpt ? `<br><span>来源定位摘句：${esc(excerpt)}</span>` : ""}</p>`;
    });
    const sources = [...new Set(entries.filter(Boolean))];
    return sources.length ? `<div class="sources">${sources.join("")}</div>` : "";
  }

  function archiveHead(title, eyebrow, subtitle = "") {
    return `<a class="back" href="${esc(lastSearch || "military.html")}">${lastSearch ? "← 返回搜索结果" : "← 返回军事档案"}</a><div class="eyebrow">${esc(eyebrow)}</div><h1>${esc(title)}</h1>${subtitle ? `<p class="muted">${esc(publicMilitaryText(subtitle))}</p>` : ""}`;
  }

  function gradeChips(result, difficulty, resultLabel = "战果", difficultyLabel = "难度") {
    result = resultOrder.includes(result) ? result : null;
    difficulty = difficultyOrder.includes(difficulty) ? difficulty : null;
    const hint = resultLabel.includes("损失") ? "本方已记录的损失量级" : resultLabel.includes("得失") ? "本条记录的综合得失量级" : resultMeaning[result] || "战略结果档";
    const resultChip = result ? `<span class="chip result" title="${esc(hint)}">${esc(resultLabel)} ${esc(result)}</span>` : "";
    const difficultyChip = difficulty ? `<span class="chip diff" title="${esc(difficultyMeaning[difficulty] || "作战难度档")}">${esc(difficultyLabel)} ${esc(difficulty)}</span>` : "";
    return `<div class="chips">${resultChip}${difficultyChip}</div>`;
  }

  function normalized(value) {
    return String(value ?? "").toLocaleLowerCase("zh-CN").replace(/\s+/g, "");
  }

  function commanderNames(row) {
    return [row.name, ...(row.aliases || []), ...(globalThis.ReaderPersonSearch?.aliasesForCommander(row.name, row.dynasty) || [])];
  }

  function searchBattles(term, commander, selected = false) {
    const q = normalized(term);
    if (!q) return [];
    const matches = [];
    for (const row of battleIndex.records) {
      const linked = commander && row.commander_refs?.includes(commander.profile_ref);
      if (selected && !linked) continue;
      const title = normalized(row.name);
      const match = [
        [title === q, "标题匹配"],
        [title.startsWith(q), "标题匹配"],
        [title.includes(q), "标题匹配"],
        [row.aliases?.some(alias => normalized(alias).includes(q)), "别名匹配"],
        [linked, "关联人物"],
        [row.members?.some(name => normalized(name).includes(q)), "责任人物姓名匹配"],
        [[dynastyLabel(row.dynasty), row.period].some(value => normalized(value).includes(q)), "朝代或时间匹配"],
        [normalized(row.search_text).includes(q), "正文提及"],
      ];
      const rank = match.findIndex(([found]) => found);
      if (rank !== -1) matches.push({row, rank, reason: match[rank][1]});
    }
    return matches.sort((a, b) => a.rank - b.rank);
  }

  function searchCommanders(term) {
    const q = normalized(term);
    if (!q) return [];
    return commanderIndex.records.filter(row => [row.dynasty, ...commanderNames(row)].some(value => normalized(value).includes(q)));
  }

  function battleCard({row, reason}) {
    return `<a class="card" href="#battle=${encodeURIComponent(row.id)}"><strong>${esc(publicBattleTitle(row.name))}</strong><small>${esc([dynastyLabel(row.dynasty), publicMilitaryText(row.period)].filter(Boolean).join(" · "))}</small><small>${esc(reason)}</small>${`<span class="chip">${esc(recordStatus(row))}</span>`}${row.direction ? `<span class="chip">${esc(directionName(row.direction))}</span>` : ""}${gradeChips(row.result_grade, row.difficulty_grade, resultLabel(row.direction), "战役难度")}${row.members?.length ? `<small>主要责任人物：${esc(row.members.slice(0,5).join("、"))}${row.members.length > 5 ? "…" : ""}</small>` : ""}</a>`;
  }

  function commanderCard(row) {
    const grade = row.grade ? (militaryGrade[row.grade] || publicMilitaryText(row.grade)) : "未定总档";
    return `<a class="card" href="#commander=${encodeURIComponent(row.profile_ref)}"><strong>${esc(row.name)}</strong><small>${esc(row.dynasty || "时代未标")}</small><div class="chips"><span class="chip">${esc(grade)}</span></div></a>`;
  }

  function recordStatus(record) {
    const state = record.disposition || "";
    if (record.phase_count || asList(record.subject_phase_views).length) return "分主体／分阶段记录";
    const labels = {
      SCOPE_ROUTE_CORRECTION_REQUIRED: "统一成果范围之外的记录",
      REDIRECTED_NON_BATTLE_OUTCOME: "非战役成果记录",
      REDIRECT_NON_BATTLE_OUTCOME: "非战役成果记录",
      NON_BATTLE_UNIFICATION_CONTEXT: "统一背景资料",
      NEUTRAL_EVENT_ONLY: "事件资料，不单列战果",
      CONTEXT_ONLY: "背景资料", SOURCE_CLUSTER_ONLY: "来源汇集",
      EXCLUDED_BELOW_PUBLIC_THRESHOLD: "未达公共战果登记门槛",
      BELOW_PUBLIC_OUTCOME_THRESHOLD: "未达公共战果登记门槛",
      EXCLUDED_AGGREGATE_SECURITY_STATE: "综合安全态势，不单列战役",
      EXCLUDED_UNIFICATION: "本登记不单列统一战果",
      MERGED_CROSS_SOURCE_DUPLICATE: "跨来源合并记录", MERGED_INTO_PARENT: "已并入上级记录",
      REDIRECTED_MIXED_PARENT: "混合记录，分项另行登记", SPLIT_CAMPAIGN_PORTFOLIO: "战役组合，分项另行登记",
    };
    return labels[state] || (record.public_outcome_registered === false ? "保留资料，未作为公共战果登记" : "战役成果记录");
  }

  const fieldNames = {
    basis:"依据", source_refs:"来源", P:"人员损害", S:"本土受损", M:"动员投入", A:"军事资产", WC:"本阶段综合成本",
    P_observed:"已载人员损害", range:"推定区间", center:"区间中心", upper_bound_reason:"上限依据", confidence:"判断把握",
    BCP:"控制收益", BCN:"控制损失", control_objects:"控制对象", control_outcome:"控制结果", control_change_mode:"控制变化",
    continuity_status:"持续状态", control_effect_status:"证据状态", grade:"档位", note:"说明", summary:"摘要",
    actor_name:"责任人物", responsibility_status:"责任认定",
  };
  function readableFields(value) {
    if (value == null || value === "") return "";
    if (typeof value !== "object") {
      const text = publicMilitaryText(value);
      return ReaderSourceLinks.metadataLabel(text) ? `<p class="prose">${esc(text)}</p>` : "";
    }
    if (Array.isArray(value)) return value.map(readableFields).join("");
    return Object.entries(value).map(([key, item]) => {
      if (key.endsWith("refs")) {
        const sources = sourceList(asList(item));
        return sources ? `<details><summary>相关来源</summary>${sources}</details>` : "";
      }
      if (/(?:_id|_ref|_key)$/.test(key)) return "";
      const body = readableFields(item);
      const label = fieldNames[key] || ReaderSourceLinks.metadataLabel(publicMilitaryText(key));
      return body && label ? `<div><strong>${esc(label)}</strong>${body}</div>` : body;
    }).join("");
  }
  function factSection(title, value, open = false) {
    if (value == null || value === "" || (typeof value === "object" && !Object.keys(value).length)) return "";
    return `<details class="panel" ${open ? "open" : ""}><summary>${esc(title)}</summary>${readableFields(value)}</details>`;
  }
  function phaseBlock(phase, index, inferencePolicy) {
    const control = phase.border_control || {};
    return `<details class="panel" id="${esc(phase.phase_id || `phase-${index}`)}"><summary>${index + 1}. ${esc(publicMilitaryText(phase.evaluation_subject_phase || "阶段记录"))}</summary>
      <p>${esc(publicMilitaryTerm(phase.subject_role, publicMilitaryTerms, "具体角色见阶段标题与经过"))}</p>
      ${phase.carry_in ? `<div class="label">阶段起点</div>${readableFields(phase.carry_in)}` : ""}
      <div class="label">实际经过</div>${readableFields(phase.actual_process)}
      <div class="label">控制变化与阶段结束状态</div>${readableFields(control)}
      ${phase.carry_out ? `<div class="label">阶段后续</div>${readableFields(phase.carry_out)}` : ""}
      ${factSection("本阶段历史成本及依据", { ...phase.cost_axes, ...((phase.cost_evidence || phase.cost_axis_basis) ? {依据:phase.cost_evidence || phase.cost_axis_basis} : {}), ...(phase.wc_basis ? {综合成本依据:phase.wc_basis} : {})})}
      ${factSection("本阶段安全与物资回报", {安全结果:phase.strategic_security,安全依据:phase.strategic_security_detail,物资回报:phase.material_return,物资依据:phase.material_return_detail,阶段回报:phase.phase_return_class,裁定依据:phase.phase_return_basis})}
      ${personnelInferenceSection(phase.P_inference, inferencePolicy)}
      ${factSection("平民损害与战争行为", [phase.civilian_harm_caused,phase.war_conduct_note,phase.war_conduct_notes,phase.civilian_harm_exclusion,phase.civilian_noncombatant_note,phase.post_capture_execution_note,phase.post_capture_execution_excluded_from_P,phase.casualty_de_duplication].filter(Boolean))}
      <details><summary>本阶段来源</summary>${sourceList(phase.source_anchor_refs || [])}</details></details>`;
  }
  function phaseSections(phases) {
    if (!phases.length) return "";
    const hasCosts = phases.some(phase => Object.keys(phase.cost_axes || {}).length || phase.cost_evidence || phase.cost_axis_basis || phase.wc_basis);
    const scope = hasCosts ? '<p class="subline">各阶段的成本按实际承担主体列示，整场成本另读正式汇总。</p>' : "";
    const inferencePolicy = phases.some(phase => hasPersonnelInference(phase.P_inference)) ? personnelInferencePolicy() : null;
    const blocks = phases.map((phase, index) => phaseBlock(phase, index, inferencePolicy)).join("");
    return `<section class="military-phases"><h2>各阶段的经过与结果</h2>${scope}${blocks}${inferencePolicy ? personnelInferenceGuide(inferencePolicy) : ""}</section>`;
  }
  function hasPersonnelInference(inference) {
    return inference != null && (typeof inference !== "object" || Object.keys(inference).length > 0);
  }
  function personnelInferencePolicy() {
    const policy = battleIndex?.personnel_inference_reading;
    const keys = ["title", "observed_title", "observed_note", "missing_observed", "legacy_title", "legacy_note", "current_title", "current_note"];
    if (!policy || keys.some(key => typeof policy[key] !== "string" || !policy[key].trim()))
      throw new Error("人员损害推定缺少上游阅读边界");
    return policy;
  }
  function personnelInferenceGuide(policy) {
    return `<details class="panel"><summary>${esc(policy.title)}</summary>
      <h3>${esc(policy.observed_title)}</h3><p>${esc(policy.observed_note)}</p>
      <h3>${esc(policy.current_title)}</h3><p>${esc(policy.current_note)}</p>
      <h3>${esc(policy.legacy_title)}</h3><p>${esc(policy.legacy_note)}</p></details>`;
  }
  function personnelInferenceSection(inference, policy) {
    if (!hasPersonnelInference(inference)) return "";
    const object = inference && typeof inference === "object" && !Array.isArray(inference);
    const observed = object ? inference.P_observed : null;
    const legacy = object ? Object.fromEntries(Object.entries(inference).filter(([key]) => key !== "P_observed")) : inference;
    return `<details class="panel"><summary>本阶段人员损害记录</summary>
      <h3>${esc(policy.observed_title)}</h3>${readableFields(observed == null || observed === "" ? policy.missing_observed : observed)}
      <details><summary>${esc(policy.legacy_title)}</summary>${readableFields(legacy)}</details></details>`;
  }
  function failureSection(record) {
    const failures = asList(record.attributable_failures);
    if (!failures.length) return "";
    return `<section class="panel"><h2>独立败责记录</h2><p>以下责任按正式记录单独列示，与前述战果属于不同判断；同一失败不重复累计。</p>${failures.map(failure => `<article class="member"><h3>${esc(failure.actor_name || "未具名责任人")}</h3><span class="chip">${esc(publicMilitaryTerm(failure.responsibility, publicMilitaryTerms, "责任范围见依据"))}</span>${gradeChips(failure.failure_impact_tier,null,"损失量级")}${readableFields(failure.basis)}${sourceList(failure.source_refs || [])}</article>`).join("")}</section>`;
  }
  function limitsSection(record) {
    return factSection("登记中的未完成目标（主体与范围见原文）",record.objective_shortfalls,true) + factSection("适用边界与材料限制",[...asList(record.limitations),...asList(record.uncertainties)]);
  }

  function personalEvidenceSection() {
    const rows = activeEvidence?.personal_results || [];
    if (!rows.length) return "";
    return `<section class="panel"><h2>已有个人结果与责任</h2><p>以下内容来自正式统帅记录，分别保留人物级结果和任务难度；与主体阶段的成本、控制变化分开阅读。能否用于第一项，仍以该人物第一项的窗口和裁决为准。</p>${rows.map(row => `<article class="member"><h3>${esc(row.person)}</h3>${achievementBlock(row.record)}<p><a href="#commander=${encodeURIComponent(row.profile_ref)}">打开${esc(row.person)}统帅档案 →</a></p><details><summary>个人记录出处</summary>${sourceList([row.source])}</details></article>`).join("")}</section>`;
  }

  function sourceEvidenceSection() {
    const cards = activeEvidence?.source_cards || [];
    if (!cards.length) return "";
    return `<details class="panel"><summary>史料摘句</summary>${cards.map((card,index) => {
      const book = String(card.source_volume || "").replace("资治通鉴", "資治通鑑").replace("辽史", "遼史");
      const url = /^https?:\/\//.test(card.source_url || "") ? originalSourceUrl(card.source_url)
        : /^\d+$/.test(String(card.revision)) ? originalSourceUrl(`${book}@${card.revision}`) : "";
      const context = card.authored_citation?.context;
      return `<article class="member" id="source-card-${index}"><h3>${esc(card.title || book)}</h3>${book && book !== card.title ? `<p class="meta">${esc(book)}</p>` : ""}${context ? `<p class="prose">${esc(context)}</p>` : ""}${card.quotes.length ? card.quotes.map(quote => `<blockquote class="prose">${esc(quote)}</blockquote>`).join("") : '<p>此处尚未收录可直接阅读的原文摘句。</p>'}${url ? `<p><a href="${esc(url)}" target="_blank" rel="noopener">打开原典卷篇 ↗</a></p>` : ""}</article>`;
    }).join("")}</details>`;
  }

  function focusEvidence() {
    const params = new URLSearchParams(location.hash.slice(1));
    const target = params.has("source") ? `source-card-${params.get("source")}` : params.get("phase");
    if (!target) return;
    requestAnimationFrame(() => {
      const element = document.getElementById(target);
      for (let parent = element; parent; parent = parent.parentElement) {
        if (parent.tagName === "DETAILS") parent.open = true;
      }
      element?.scrollIntoView({block:"start"});
    });
  }

  function relatedEvidenceView(ruler) {
    searchView(ruler);
    lastSearch = `#evidence=${encodeURIComponent(ruler)}`;
    const anchors = (battleIndex.first_item_c_anchors || []).filter(row => row.ruler === ruler && row.status !== "resolved_unique");
    const phrases = [...new Set(anchors.filter(row => row.status !== "search_only_nonspecific").map(row => row.raw_anchor || row.anchor))];
    const profiles = searchCommanders(ruler);
    const intro = document.createElement("section");
    intro.className = "panel";
    intro.innerHTML = `<h2>${esc(ruler)} · 第一项引文查找</h2><p>以下是引文尚未定位到单一战役时可继续查阅的人物相关资料。第一项实际采用的记录见下方结算入口。</p>${phrases.length ? `<details open><summary>原引用中的查找线索</summary><ul>${phrases.map(phrase=>`<li>${esc(phrase)}</li>`).join("")}</ul></details>` : ""}${profiles.length ? `<p>${profiles.map(profile=>`<a href="#commander=${encodeURIComponent(profile.profile_ref)}">${esc(profile.name)} · 统帅证据记录 →</a>`).join("　")}</p>` : ""}<p><a href="first-item-c.html">查看奠基时期统帅表现 →</a></p>`;
    app.querySelector(".panel")?.before(intro);
  }

  function searchHref(term, profileRef = "") {
    return `#search=${encodeURIComponent(term)}${profileRef ? `&person=${encodeURIComponent(profileRef)}` : ""}`;
  }

  function battleGradeGuide() {
    const grid = meanings => `<div class="grade-grid">${Object.entries(meanings).map(([grade, text]) =>
      `<div><strong>${esc(grade)}</strong><br><small>${esc(text)}</small></div>`).join("")}</div>`;
    return `<details class="panel"><summary>战果和难度怎么看？</summary>
      <p>结果档依据本条记录直接形成的后果。负向档表示损失量级，混合档表示综合得失。个人档位按具名人物的任务及责任另列。按阶段登记的资料可分别查看各方经过与结果。</p>
      <h3>结果量级</h3>${grid(resultMeaning)}<h3>任务难度</h3>${grid(difficultyMeaning)}</details>`;
  }

  function searchView(term = "", profileRef = "") {
    const q = normalized(term);
    const foundCommanders = searchCommanders(term);
    const named = foundCommanders.filter(row => commanderNames(row).some(name => normalized(name).includes(q)));
    const exact = named.filter(row => {
      const name = normalized(row.name);
      return commanderNames(row).some(value => {
        const alias = normalized(value);
        return alias === q || alias === q + name;
      });
    });
    const choices = exact.length > 1 ? exact : /^[\p{Script=Han}][祖宗]$/u.test(q) && exact.length && named.length > 1 ? named : [];
    const selected = choices.find(row => row.profile_ref === profileRef);
    const key = searchHref(term, selected?.profile_ref);
    const saved = searchStates.get(key) || {counts:[30,30], scroll:0};
    searchStates.set(key, saved);
    activeSearch = key;
    lastSearch = term ? key : "";
    const battles = searchBattles(term, selected || (!choices.length ? exact[0] : null), !!selected);
    const commanders = selected ? [selected] : foundCommanders;
    const selection = selected
      ? `<div class="panel"><p>战役已按${esc(selected.name)}（${esc(selected.dynasty)}）筛选。</p><a href="${esc(searchHref(term))}">查看全部匹配</a></div>`
      : choices.length
        ? `<div class="panel"><p>这个关键词匹配到多位人物。请选择人物查看其关联战役。</p><ul>${choices.map(row => `<li><a href="${esc(searchHref(term, row.profile_ref))}">${esc(row.name)}（${esc(row.dynasty)}）</a></li>`).join("")}</ul></div>`
        : "";
    app.innerHTML = `<h1>军事档案</h1><p>按战役查经过、战果和责任，按人物查军事生涯。</p><div class="panel"><form id="archive-search" class="toolbar"><input id="archive-q" value="${esc(term)}" placeholder="搜索战役、人物、朝代，例如：鄱阳湖、李世民、明"><button>搜索</button></form></div>${selection}${term ? `<section><h2>战役档案 <small>${battles.length}</small></h2><div class="cards">${battles.length ? battles.slice(0,30).map(battleCard).join("") : '<div class="empty">没有找到匹配战役。</div>'}</div></section><section><h2>统帅档案 <small>${commanders.length}</small></h2><div class="cards">${commanders.length ? commanders.slice(0,30).map(commanderCard).join("") : '<div class="empty">没有找到匹配人物。</div>'}</div></section>` : `<div class="stats"><div class="stat"><b>${battleIndex.record_count}</b><div>战役档案</div></div><div class="stat"><b>${commanderIndex.profile_count}</b><div>统帅档案</div></div></div>`}${battleGradeGuide()}`;
    document.getElementById("archive-search")?.addEventListener("submit", event => {
      event.preventDefault();
      const q = document.getElementById("archive-q")?.value.trim() || "";
      location.hash = q ? searchHref(q) : "";
    });
    if (term) {
      for (const [index, rows, render, label] of [[0,battles,battleCard,"战役"],[1,commanders,commanderCard,"统帅"]]) {
        const section = app.querySelectorAll("section")[index];
        if (!section) continue;
        section.querySelector("h2 small").textContent = rows.length;
        const cards = section.querySelector(".cards");
        let shown = 0;
        let batch = saved.counts[index] || 30;
        const more = document.createElement("button");
        more.type = "button";
        const draw = () => {
          const next = rows.slice(shown, shown + batch);
          if (!shown) cards.innerHTML = "";
          cards.insertAdjacentHTML("beforeend", next.map(render).join(""));
          shown += next.length;
          saved.counts[index] = shown;
          batch = 30;
          more.textContent = `继续显示${label}（已显示 ${shown} / ${rows.length}）`;
          more.hidden = shown >= rows.length;
        };
        if (rows.length) { more.addEventListener("click", draw); section.append(more); draw(); }
      }
    }
    requestAnimationFrame(() => {
      if (activeSearch === key) window.scrollTo(0, saved.scroll);
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

  function containsMilitaryPassage(text, passage) {
    const sentences = value => String(value ?? "").split(/(?<=[。！？])|\n+/)
      .map(line => line.trim().replace(/\s+/g, " ")).filter(Boolean);
    const story = sentences(text);
    const pieces = sentences(passage);
    return pieces.length > 0 && story.some((_, i) =>
      pieces.every((sentence, offset) => story[i + offset] === sentence));
  }

  function memberBlock(member, shownActions = []) {
    const idx = member.person_command_index || {};
    const results = asList(member.person_command_result);
    const result = results[0] || {};
    const commander = memberCommander(member);
    const profileLink = commander ? `<a href="#commander=${encodeURIComponent(commander.profile_ref)}">打开统帅档案 →</a>` : "";
    const personGrade = result.result_tier || idx.projected_result_tier;
    const personDifficulty = result.combat_difficulty || idx.projected_combat_difficulty;
    const role = publicMilitaryTerm(member.role_code, roleName, "责任角色未细分");
    const capability = publicMilitaryTerm(idx.capability_mode, capabilityName, "承担方式未细分");
    const basis = result.basis || idx.basis || member.contribution_scope || "";
    const personProse = (text, shownText = text) => shownActions.some(action => containsMilitaryPassage(action, text))
      ? "" : militaryProse(shownText);
    const direction = result.result_direction || idx.result_direction || member.command_result_direction;
    const resultCards = results.length ? results.map(row => `<div><strong>${esc(publicBattleTitle(row.result_label && !/^(WAR-|PCR-|HAN-)/.test(row.result_label) ? row.result_label : "本人责任记录"))}</strong><span class="chip">${esc(directionName(row.result_direction || direction))}</span>${gradeChips(row.result_tier, row.combat_difficulty, `个人${resultLabel(row.result_direction || direction)}`, "个人任务难度")}${row.basis ? personProse(row.basis) : personProse(basis, publicMilitaryText(basis))}</div>`).join("") : `<span class="chip">${esc(directionName(direction))}</span>${gradeChips(personGrade, personDifficulty, `个人${resultLabel(direction)}`, "个人任务难度")}${personProse(basis)}`;
    return `<div class="member"><div class="member-head"><strong>${esc(member.actor_name || "未具名")}</strong><span>${esc(role)}</span></div>${idx.capability_mode ? `<p>本人承担：${esc(capability)}</p>` : ""}${resultCards}${profileLink ? `<p class="sources">${profileLink}</p>` : ""}</div>`;
  }

  function battleMembers(record, showEmpty = false, shownActions = []) {
    const members = asList(record.members);
    if (!showEmpty && !members.length) return "";
    const nameCounts = new Map();
    for (const member of members) {
      const name = member.actor_name;
      if (name) nameCounts.set(name, (nameCounts.get(name) || 0) + 1);
    }
    const passages = new Map();
    for (const action of shownActions) {
      if (nameCounts.get(action.person) !== 1 || !action.text) continue;
      const texts = passages.get(action.person) || [];
      texts.push(action.text);
      passages.set(action.person, texts);
    }
    const body = members.length
      ? '<p class="subline">个人档位按具名人物的实际任务和责任列示。</p>' + members.map(member => memberBlock(member, passages.get(member.actor_name))).join("")
      : '<p class="muted">本条暂未单列具名责任。</p>';
    return `<section class="panel"><h2>责任人物</h2>${body}</section>`;
  }

  function battleAssessment(record, row) {
    const result = record.campaign_tier;
    const difficulty = difficultyOrder.includes(record.combat_difficulty) ? record.combat_difficulty : "未单列";
    const resultNote = resultExplanation(result, record.result_direction);
    const difficultyNote = difficultyMeaning[record.combat_difficulty] || "";
    const observable = String(record.observable_result || "").trim();
    const process = String(record.battle_process || record.actual_process || row.reading_context?.process || "").trim();
    const resultText = publicMilitaryText(observable);
    const basis = publicMilitaryText(record.tier_basis || "").trim();
    const diffBasis = publicMilitaryText(record.combat_difficulty_basis || "").trim();
    const resultBasis = basis && ![resultNote, resultText, publicMilitaryText(process)].includes(basis)
      ? `<details><summary>结果档依据</summary><p class="prose">${esc(basis)}</p></details>` : "";
    const difficultyBasis = diffBasis && diffBasis !== difficultyNote
      ? `<details><summary>作战难度依据</summary><p class="prose">${esc(diffBasis)}</p></details>` : "";
    return `<section class="panel"><h2>结果与定档</h2><p>登记方向 ${esc(directionName(record.result_direction))}。各方结果和本人责任见具名记录。</p>
      ${observable && observable !== process ? `<p class="prose">${esc(resultText)}</p>` : ""}
      <div class="grade-grid"><div><strong>战役登记${esc(resultLabel(record.result_direction))} ${esc(result)}</strong>${resultNote ? `<br><small>${esc(resultNote)}</small>` : ""}</div><div><strong>整场战役难度 ${esc(difficulty)}</strong>${difficultyNote ? `<br><small>${esc(difficultyNote)}</small>` : ""}</div></div>
      ${resultBasis}${difficultyBasis}</section>`;
  }

  async function renderBattle(id, sequence) {
    const row = battleById.get(id);
    if (!row) { app.innerHTML = '<div class="empty">没有找到这个战役档案。<br><a href="military.html">返回搜索</a></div>'; return; }
    app.innerHTML = '<div class="empty">正在读取正式战役登记…</div>';
    const record = await battleRecord(row);
    if (sequence !== renderSequence) return;
    if (!record) { app.innerHTML = '<div class="empty">战役索引与正式分片失步。</div>'; return; }
    const evidence = row.evidence_source ? await json(row.evidence_source) : {};
    if (sequence !== renderSequence) return;
    activeEvidence = evidence[id] || null;
    activeBattleId = id;
    const phases = asList(record.subject_phase_views);
    if (!resultOrder.includes(record.campaign_tier)) {
      const status = recordStatus(record);
      const period = row.period && !row.period.includes("未知") ? row.period : "当前登记未注明具体年代";
      const merged = battleForRef(record.merged_into);
      app.innerHTML = `${archiveHead(publicBattleTitle(record.canonical_label || row.name), `${dynastyLabel(record.dynasty)} · 军事资料`, period)}
        <section class="panel"><h2>${esc(status)}</h2>${readableFields(record.observable_result || record.basis)}<p class="muted">整场结果档未单列。${phases.length ? `下列 ${phases.length} 条为主体阶段记录。` : ""}</p>${merged ? `<a href="#battle=${encodeURIComponent(merged.id)}">查看合并后的记录 · ${esc(merged.name)} →</a>` : ""}</section>
        ${personalEvidenceSection()}${phaseSections(phases)}
        ${!phases.length && (record.battle_process || record.actual_process || row.context) ? factSection("已记录的经过",record.battle_process || record.actual_process || row.context,true) : ""}
        ${battleMembers(record)}
        ${failureSection(record)}${limitsSection(record)}${sourceEvidenceSection()}
        <details class="panel"><summary>正式来源</summary>${sourceList([...(record.source_refs || []),...(row.source_files || []),row.source])}</details>`;
      window.scrollTo(0,0);
      focusEvidence();
      return;
    }
    const period = row.period && !row.period.includes("未知") ? row.period : row.reading_context?.period || "具体起止未单列，见史料定位";
    const cost = readableFields(record.cost_or_burden || record.cost_summary || "本条未单列成本摘要。");
    const narrative = battleNarrative(record, row);
    app.innerHTML = `${archiveHead(publicBattleTitle(record.canonical_label || id), `${dynastyLabel(record.dynasty)} · 战役档案`, period)}
        ${narrative.html}${battleAssessment(record, row)}
        ${personalEvidenceSection()}${phaseSections(phases)}${battleMembers(record, true, narrative.shownActions)}
        ${failureSection(record)}${limitsSection(record)}${sourceEvidenceSection()}
        <details class="panel"><summary>军事成本</summary>${cost}</details>
        <details class="panel"><summary>正式来源</summary>${sourceList([...(record.source_refs || []), ...(record.source_lineage?.source_revision_refs || []), ...(row.source_files || []), row.source])}</details>`;
    focusEvidence();
  }

  function battleNarrative(record, row) {
    const context = row.reading_context || {};
    const actions = context.actions || asList(record.members).map(member => ({person:member.actor_name, text:member.military_capability_contribution?.basis})).filter(action => action.text);
    const process = record.battle_process || record.actual_process || context.process;
    const body = process ? militaryProse(process)
      : actions.length ? actions.map(action => `<div class="military-action"><h3>${esc(action.person || "")}</h3>${militaryProse(action.text)}</div>`).join("")
      : '<p class="muted">连续经过与具名行动未单列。</p>';
    const html = `<section class="panel"><h2>${process ? "战役经过" : "行动与责任摘录"}</h2>${context.prewar || row.context ? `<div class="label">战前态势</div>${militaryProse(context.prewar || row.context)}` : ""}${context.objective ? `<div class="label">作战目标</div>${militaryProse(context.objective)}` : ""}${body}${context.sources?.length ? `<details><summary>经过与时间来源</summary>${sourceList(context.sources)}</details>` : ""}</section>`;
    return {html, shownActions: process ? [] : actions};
  }

  function achievementBlock(item) {
    const ref = item.campaign_ref || item.capability_episode_ref;
    const battleId = battleForRef(ref)?.id;
    const link = battleId && battleId !== activeBattleId ? `<a href="#battle=${encodeURIComponent(battleId)}">打开对应战役档案 →</a>` : "";
    const capability = publicMilitaryTerm(item.capability_mode, capabilityName, "承担方式未细分");
    const basis = publicMilitaryText(item.basis || "");
    const resultGrade = item.campaign_tier;
    const difficultyGrade = item.combat_difficulty;
    const linked = (!resultGrade && item.parent_campaign_tier) || (!difficultyGrade && item.parent_combat_difficulty);
    const parentContext = linked ? `<details><summary>关联整场战役（背景）</summary>${gradeChips(item.parent_campaign_tier, item.parent_combat_difficulty, "整场结果量级", "整场难度")}</details>` : "";
    const missing = `${!resultGrade ? '<small>个人结果档未单列。</small>' : ""}${!difficultyGrade ? '<small>个人任务难度未单列。</small>' : ""}`;
    return `<div class="achievement"><strong>${esc(publicBattleTitle(item.canonical_label || ref || "军事能力记录"))}</strong><span class="chip">${esc(directionName(item.result_direction))}</span>${gradeChips(resultGrade, difficultyGrade, `个人${resultLabel(item.result_direction)}`, "个人任务难度")}${missing}${item.capability_mode ? `<p class="muted">承担方式：${esc(capability)}</p>` : ""}${basis ? militaryProse(item.basis) : ""}${item.responsibility_basis ? `<details><summary>责任认定依据</summary>${militaryProse(item.responsibility_basis)}</details>` : ""}${parentContext}${link ? `<p class="sources">${link}</p>` : ""}${item.source_refs?.length ? `<details><summary>史料依据</summary>${sourceList(item.source_refs)}</details>` : ""}</div>`;
  }

  function highestGrade(items, order, fieldNames) {
    let winner = "";
    let best = -1;
    for (const item of items) {
      const value = fieldNames.map(name => item?.[name]).find(Boolean);
      const rank = order.indexOf(value);
      if (rank > best) {
        best = rank;
        winner = value || "";
      }
    }
    return winner;
  }

  function commanderReason(profile, achievements, adverse, row) {
    const blocked = {historic_blocked_by_failure_pressure:"历史级",top_blocked_by_failure_pressure:"顶级",elite_blocked_by_failure_pressure:"精英级"}[profile.rule_path];
    const route = blocked ? `重大失败限制了${blocked}路径。` : commanderRoutes[profile.rule_path];
    const episodes = asList(profile.capability_episode_anchors);
    const peak = highestGrade(achievements, resultOrder, ["campaign_tier"]);
    const peakItems = achievements.filter(item => item.campaign_tier === peak);
    const names = items => items.map(item => {
      const battle = battleForRef(item.campaign_ref) || battleForRef(item.capability_episode_ref);
      const label = esc(publicMilitaryText(item.canonical_label || battle?.name || "军事记录"));
      return battle ? `<a href="#battle=${encodeURIComponent(battle.id)}">${label}</a>` : label;
    }).join("；");
    const gate = profile.stability_gate || {};
    const gateEffect = gate.stability_cap_applied
      ? (blocked ? "" : "重大失败已限制最终总档。")
      : "本次复核未因重大失败下压总档。";
    return `<section class="panel"><h2>为什么是这个总档？</h2>${route ? `<p>${esc(route)}</p>` : '<p>当前总档的具体裁决见下方正式记录。</p>'}${peakItems.length ? `<div class="label">个人战果峰值及其战役</div><p>${names(peakItems)}</p>` : ""}${episodes.length ? `<details><summary>独立能力情境（${episodes.length}项）</summary><p>${names(episodes)}</p><p class="muted">按正式记录归并，同一连续战役中的多条个人成果不重复视为独立复验。</p></details>` : ""}${Number.isInteger(gate.major_positive_context_count) ? `<p>正式稳定性复核采用 ${gate.major_positive_context_count} 项重大正向情境、${gate.major_adverse_context_count ?? "未注明"} 项重大不利情境。${gateEffect}</p>` : ""}${adverse.length ? `<div class="label">纳入复核的不利记录</div><p>${names(adverse)}</p>` : ""}<details><summary>总档正式依据与规则</summary>${sourceList([row.source + (profile.profile_ref ? '#' + profile.profile_ref : ''), "docs/证据规则/公共成果登记与人物画像规则.md"])}${militaryProse(profile.grade_basis || "")}</details></section>`;
  }

  async function renderCommander(profileRef, sequence) {
    activeEvidence = null;
    activeBattleId = "";
    const row = commanderByProfile.get(profileRef);
    if (!row) { app.innerHTML = '<div class="empty">没有找到这个统帅档案。<br><a href="military.html">返回搜索</a></div>'; return; }
    app.innerHTML = '<div class="empty">正在读取正式统帅登记…</div>';
    const profile = await commanderRecord(row);
    if (sequence !== renderSequence) return;
    if (!profile) { app.innerHTML = '<div class="empty">统帅索引与正式分片失步。</div>'; return; }
    const grade = profile.military_grade ? (militaryGrade[profile.military_grade] || publicMilitaryText(profile.military_grade)) : "未定总档";
    const achievements = profile.consumed_achievements || [];
    const domainGrades = profile.domain_grades || {};
    const adverseByRef = new Map();
    for (const item of [...asList(profile.negative_or_mixed_command_records), ...asList(profile.failure_accountability)]) {
      adverseByRef.set(item.campaign_ref || item.capability_episode_ref || item.canonical_label, item);
    }
    const coveredAdverseRefs = new Set([...adverseByRef.values()].flatMap(item => [item.campaign_ref, item.capability_episode_ref, item.person_command_result_ref].filter(Boolean)));
    for (const ref of profile.major_adverse_episode_refs || []) {
      if (!coveredAdverseRefs.has(ref)) adverseByRef.set(ref, {campaign_ref:ref, canonical_label:battleForRef(ref)?.name || "未列事由的失利", result_direction:"negative", source_refs:[row.source]});
    }
    const adverseRecords = [...adverseByRef.values()];
    const peakPersonalResult = highestGrade(achievements, resultOrder, ["campaign_tier"]);
    const peakPersonalDifficulty = highestGrade(achievements, difficultyOrder, ["combat_difficulty"]);
    const peakResult = peakPersonalResult;
    const peakDifficulty = peakPersonalDifficulty;
    const peakResultLabel = "最高个人战果";
    const peakDifficultyLabel = "最高个人任务难度";
    const evidenceState = gradeStatusName[profile.grade_status] || publicMilitaryTerm(profile.grade_status, {}, "证据状态未细分");
    const stabilityState = stabilityStatusName[profile.stability_status] || publicMilitaryTerm(profile.stability_status, {}, "稳定性状态未细分");
    app.innerHTML = `${archiveHead(profile.person || row.name, `${profile.dynasty || row.dynasty || ""} · 统帅档案`, "全生涯军事表现") }<section class="panel"><div class="eyebrow">全生涯结论</div><h2>${esc(grade)}</h2><p><strong>${esc(peakResultLabel)}：${esc(peakResult || "未形成可展示档位")}</strong>${peakDifficulty ? ` · <strong>${esc(peakDifficultyLabel)}：${esc(peakDifficulty)}</strong>` : ""}${achievements.length ? ` · 正式能力记录 ${esc(achievements.length)} 条` : ""}</p><div class="chips"><span class="chip">证据：${esc(evidenceState)}</span><span class="chip">稳定性：${esc(stabilityState)}</span></div></section>${commanderReason(profile, achievements, adverseRecords, row)}${Object.keys(domainGrades).length ? `<section class="panel"><h2>主要能力领域</h2><div class="grade-grid">${Object.entries(domainGrades).map(([key,value]) => `<div><strong>${esc(publicMilitaryText(key))}</strong><br><small>${esc(militaryGrade[value?.grade] || publicMilitaryText(value?.grade || "—"))}</small></div>`).join("")}</div></section>` : ""}<details class="panel"><summary>代表战绩</summary>${achievements.length ? achievements.map(achievementBlock).join("") : '<p class="muted">当前登记没有可展示的正式军事能力记录。</p>'}</details>${adverseRecords.length ? `<details class="panel"><summary>重大失利</summary>${adverseRecords.map(achievementBlock).join("")}</details>` : ""}`;
  }

  async function route() {
    const sequence = ++renderSequence;
    if (activeSearch !== null) {
      const saved = searchStates.get(activeSearch);
      if (saved) saved.scroll = window.scrollY;
      activeSearch = null;
    }
    try {
      await ensureIndexes();
      if (sequence !== renderSequence) return;
      const hash = location.hash.slice(1);
      if (hash.startsWith("battle=")) return await renderBattle(new URLSearchParams(hash).get("battle"), sequence);
      if (hash.startsWith("commander=")) return await renderCommander(decodeURIComponent(hash.slice(10)), sequence);
      if (hash.startsWith("evidence=")) return relatedEvidenceView(decodeURIComponent(hash.slice(9)));
      if (hash.startsWith("search=")) {
        const params = new URLSearchParams(hash);
        return searchView(params.get("search") || "", params.get("person") || "");
      }
      return searchView("");
    } catch (error) {
      if (sequence !== renderSequence) return;
      console.error(error);
      app.innerHTML = `<div class="empty">军事档案加载失败，请刷新后重试。<br><a href="index.html">返回人物总览</a></div>`;
    }
  }

  window.addEventListener("hashchange", route);
  route();
})();
