"use strict";

(() => {
  const screenEl = document.getElementById("screen");
  if (!screenEl) return;

  const PUBLIC_GRADE = {G0:"E",G1:"D",G2:"C",G3:"B",G4:"A",G5:"S"};
  const STATE_GRADE = {1:"E",2:"D",3:"C",4:"B",5:"A",6:"S"};
  const HANDOFF_GRADE = {0:"E",1:"D",2:"C",3:"B",4:"A",5:"S"};
  const FINANCE_ORDINAL_GRADE = {"一":"E","二":"D","三":"C","四":"B","五":"A","六":"S","1":"E","2":"D","3":"C","4":"B","5":"A","6":"S"};
  const LOSS_TEXT = {
    0:"未见独立有效低谷",
    1:"已证独立损害，按证据范围作有限修正",
    2:"出现明显低谷",
    3:"出现严重低谷",
  };
  const METHOD_MAX = {"A制度建设":100,"B1官僚治理":100,"B2反馈与约束":80};
  const FINANCE_MAX = {"C1民生":80,"C2经济财政":35,"C3社会安全":60};
  const HANDOFF_LABELS = {
    "D1继任行政连续性":"行政承接",
    "D3政权交接稳定":"终局继承",
  };
  const SECOND_GROUPS = ["method", "finance", "handoff"];
  const SECOND_CALC_VISIBLE = {
    method:new Set(["治理手段"]),
    finance:new Set(["治理结果"]),
    handoff:new Set(["交接得分"]),
  };
  const SECOND_CALC_LABELS = {
    "AB计分块":"制度建设与官僚治理合成",
    "B2折算":"反馈与约束折算",
    "治理手段":"制度与行政合计",
    "治理结果":"民生与社会合计",
    "低侧封顶":"交接短板上限",
    "交接得分":"政权交接得分",
    "第二项合计":"治国成效合计",
  };
  const PUBLIC_ITEM_LABELS = {
    "A制度建设":"制度建设",
    "B1官僚治理":"官僚治理",
    "B2反馈与约束":"反馈与约束",
    "C1民生":"民生",
    "C2经济财政":"经济财政",
    "C3社会安全":"社会安全",
    "C4恢复与成本":"恢复与额外代价",
    "D1继任行政连续性":"行政连续性",
    "D3政权交接稳定":"交接稳定",
  };
  const PUBLIC_ROLE_LABELS = {
    MAJOR_RESTRUCTURE:"重构",
    MAJOR_RECONSTRUCTION:"重建",
    FOUNDATIONAL_CREATION:"创设",
    CANONICALIZATION:"定型",
    MAJOR_CIVILIZATIONAL_CORRECTION:"重大纠偏",
    STRUCTURAL_NON_DURABLE:"核心结构",
    DURABILITY_EVIDENCE_PENDING:"耐久性待核",
  };

  function finite(value) {
    if (value == null || value === "") return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }

  function fmt(value, digits = 1) {
    const n = finite(value);
    return n == null ? "—" : n.toFixed(digits);
  }

  function personRecord() {
    if (typeof byId === "undefined") return null;
    const match = location.hash.match(/^#person\/([^/?#]+)/);
    if (!match) return null;
    try { return byId.get(decodeURIComponent(match[1])) || null; } catch { return null; }
  }

  function netRecord() {
    if (typeof byId === "undefined") return null;
    const match = location.hash.match(/^#net\/([^/?#]+)/);
    if (!match) return null;
    try { return byId.get(decodeURIComponent(match[1])) || null; } catch { return null; }
  }

  function compareRecords() {
    if (typeof byId === "undefined" || !location.hash.startsWith("#compare/")) return [];
    return location.hash.slice(9).split("/").filter(Boolean).slice(0, 2).map(id => {
      try { return byId.get(decodeURIComponent(id)) || null; } catch { return null; }
    }).filter(Boolean);
  }

  function itemMap(record, key) {
    return new Map((record?.net?.component_details?.[key] || []).map(item => [item.label, item]));
  }

  function secondItems(record) {
    const result = new Map();
    for (const key of SECOND_GROUPS) {
      for (const item of record?.net?.component_details?.[key] || []) result.set(item.label, item);
    }
    return result;
  }

  function secondTotals(record) {
    const method = itemMap(record, "method");
    const finance = itemMap(record, "finance");
    const handoff = itemMap(record, "handoff");
    return {
      method: finite(method.get("治理手段")?.value),
      finance: finite(finance.get("治理结果")?.value),
      handoff: finite(handoff.get("交接得分")?.value),
      total: finite(record?.net?.second_item_score ?? handoff.get("第二项合计")?.value),
    };
  }

  function positionSuffix(text) {
    const lower = String(text || "").toLowerCase();
    if (/lower|low/.test(lower)) return "-";
    if (/upper|high/.test(lower)) return "+";
    return "";
  }

  function publicMethodGrade(item) {
    const text = String(item?.grade || "");
    const band = text.match(/\bG([0-5])\b/i);
    if (!band) return "";
    return `${PUBLIC_GRADE[`G${band[1]}`] || ""}${positionSuffix(text)}`;
  }

  function stateGradeMeta(item) {
    const match = String(item?.grade || "").match(/\bC[123]-(\d)\s*\/\s*L([0-3])\b/i);
    if (!match) return null;
    const band = Number(match[1]);
    const loss = Number(match[2]);
    return {grade:STATE_GRADE[band] || "",lossText:item.public_loss_label || LOSS_TEXT[loss] || ""};
  }

  function publicHandoffGrade(item) {
    const level = Number(item?.value);
    return Number.isInteger(level) ? HANDOFF_GRADE[level] || "" : "";
  }

  function boundaryExcerpt(item) {
    const text = String(item?.reader_boundary || "").trim();
    if (!text) return "";
    return "适用范围与限制见展开说明";
  }

  function ensureStyles() {
    if (document.getElementById("second-item-public-polish-style")) return;
    const style = document.createElement("style");
    style.id = "second-item-public-polish-style";
    style.textContent = `
      .second-item-public-grade-ready > .second-item-scale-note{display:block;margin-top:4px;font-size:11px;line-height:1.55;color:var(--green);font-weight:600}
      .net-metric-detail>summary b.second-item-public-value{font:20px Georgia,serif;color:var(--green)}
      .component>b.second-item-public-value{font-size:13px;color:var(--green)}
      .second-item-public-copy{font-size:13px;line-height:1.7}
      small.second-item-public-copy{font-size:11px;color:var(--muted);line-height:1.55}
      .net-major-card .big.second-item-public-score{font:30px Georgia,serif;color:var(--green)}
      .second-item-total-grid b.second-item-public-score{font:21px Georgia,serif;color:var(--green)}
      .second-item-public-reading{margin:2px 0 4px}
      .second-item-public-reading .label{margin-top:8px}
      .second-item-public-reading ul{margin:8px 0 12px;padding-left:20px}
      .second-item-public-reading li{margin:5px 0;line-height:1.8}
      .second-item-public-reading .prose{margin:8px 0 12px}
      .adjudication-material-group{margin:14px 0 18px}
      .adjudication-material-group>h4{margin:0 0 8px;font-size:15px}
      .adjudication-material-list{list-style:none!important;margin:0!important;padding:0!important;display:grid;gap:8px}
      .adjudication-material-card{margin:0;padding:11px 12px;border:1px solid var(--line);border-radius:5px;background:#fff}
      .adjudication-material-card.is-supplement{background:#f7f5ef}
      .adjudication-material-head{display:flex;align-items:flex-start;justify-content:space-between;gap:8px;flex-wrap:wrap}
      .adjudication-material-head>strong{font-size:14px;line-height:1.55}
      .adjudication-material-meta{display:flex;align-items:center;justify-content:flex-end;gap:5px;flex-wrap:wrap}
      .adjudication-material-chip{display:inline-block;padding:1px 6px;border:1px solid var(--line);border-radius:999px;font-size:10px;line-height:1.6;color:var(--muted);font-weight:700;background:#f4f5ef}
      .adjudication-material-chip.direction{color:var(--green)}
      .adjudication-material-chip.strength{color:var(--red);border-color:color-mix(in srgb,var(--red) 28%,var(--line))}
      .adjudication-material-chip.contribution{color:var(--ink);background:#ecefe6}
      .adjudication-material-basis{margin:7px 0 0!important;font-size:12px!important;line-height:1.78!important;white-space:pre-line}
      .adjudication-material-scope{margin-top:7px;padding:7px 9px;background:rgba(0,0,0,.025);font-size:11px;line-height:1.65}
      .adjudication-material-scope strong{color:var(--muted)}
      .adjudication-material-scope p{margin:2px 0 0}
      .adjudication-material-boundary{margin-top:7px!important;padding:6px 0 0!important}
      .adjudication-material-boundary>summary{color:var(--muted);font-size:11px!important}
      .adjudication-material-boundary>p{margin:5px 0 0;font-size:11px;line-height:1.7}
      .adjudication-material-footer{display:block;margin-top:7px;color:var(--green);font-size:11px;line-height:1.65;font-weight:600}
      .adjudication-material-empty{margin:4px 0;color:var(--muted);font-size:12px}
      .adjudication-material-card,.adjudication-material-head>strong,.adjudication-material-basis,.adjudication-material-scope,.adjudication-material-boundary>p{overflow-wrap:anywhere}
      @media(max-width:700px){
        .adjudication-material-card{padding:10px}
        .adjudication-material-head{display:block}
        .adjudication-material-meta{justify-content:flex-start;margin-top:6px}
        .adjudication-material-chip{white-space:normal;overflow-wrap:anywhere}
      }
    `;
    document.head.append(style);
  }

  // The public layer owns these text nodes. The structural renderer respects
  // the data-public-* markers instead of restoring its intermediate copy.
  // Write real text: CSS generated content is not a replacement for readable DOM.
  function setPublicText(node, text, key, className) {
    if (!node || !text) return;
    node.classList.add(className);
    if (node.dataset[key] !== text) node.dataset[key] = text;
    if (node.textContent !== text) node.textContent = text;
  }

  function writePublicCopy(node, text) {
    setPublicText(node, text, "publicCopy", "second-item-public-copy");
  }

  function writePublicScore(node, text) {
    setPublicText(node, text, "publicScore", "second-item-public-score");
  }

  function setPublicGrade(span, valueNode, grade, noteParts) {
    if (!span || !grade) return;
    const note = noteParts.filter(Boolean).join("｜");
    span.classList.add("second-item-public-grade-ready");
    if (span.dataset.publicGradeNote !== note) span.dataset.publicGradeNote = note;
    let noteNode = span.querySelector(":scope > .second-item-scale-note");
    if (!noteNode) {
      noteNode = document.createElement("small");
      noteNode.className = "second-item-scale-note";
      span.append(noteNode);
    }
    if (noteNode.textContent !== note) noteNode.textContent = note;
    setPublicText(valueNode, grade, "publicValue", "second-item-public-value");
  }

  function patchMethodGrades(root, record) {
    if (!root || !record?.net) return;
    const items = itemMap(record, "method");
    if (!items.size) return;
    for (const detail of root.querySelectorAll(".net-metric-detail[data-second-source-label]")) {
      const sourceLabel = detail.dataset.secondSourceLabel || "";
      const item = items.get(sourceLabel);
      const grade = publicMethodGrade(item);
      if (!item || !grade || !METHOD_MAX[sourceLabel]) continue;
      const summary = detail.querySelector(":scope > summary");
      setPublicGrade(summary?.querySelector(":scope > span"), summary?.querySelector(":scope > b"), grade,
        sourceLabel === "A制度建设" ? [boundaryExcerpt(item)] : [`原始表现指数 ${Number(item.value).toFixed(1)} / ${METHOD_MAX[sourceLabel]}（用于本组折算，不单列得分）`, boundaryExcerpt(item)]);
    }
    for (const span of root.querySelectorAll(".component > span[data-second-source-label]")) {
      const sourceLabel = span.dataset.secondSourceLabel || "";
      const item = items.get(sourceLabel);
      const grade = publicMethodGrade(item);
      if (!item || !grade || !METHOD_MAX[sourceLabel]) continue;
      setPublicGrade(span, span.parentElement?.querySelector(":scope > b"), grade,
        sourceLabel === "A制度建设" ? [boundaryExcerpt(item)] : [`原始表现指数 ${Number(item.value).toFixed(1)} / ${METHOD_MAX[sourceLabel]}（用于本组折算，不单列得分）`, boundaryExcerpt(item)]);
    }
  }

  function patchFinanceGrades(root, record) {
    if (!root || !record?.net) return;
    const items = itemMap(record, "finance");
    if (!items.size) return;
    for (const detail of root.querySelectorAll(".net-metric-detail[data-second-source-label]")) {
      const sourceLabel = detail.dataset.secondSourceLabel || "";
      const item = items.get(sourceLabel);
      const meta = stateGradeMeta(item);
      if (!item || !meta?.grade || !FINANCE_MAX[sourceLabel]) continue;
      const summary = detail.querySelector(":scope > summary");
      setPublicGrade(summary?.querySelector(":scope > span"), summary?.querySelector(":scope > b"), meta.grade,
        ["主要状态", meta.lossText, boundaryExcerpt(item)]);
    }
    for (const span of root.querySelectorAll(".component > span[data-second-source-label]")) {
      const sourceLabel = span.dataset.secondSourceLabel || "";
      const item = items.get(sourceLabel);
      const meta = stateGradeMeta(item);
      if (!item || !meta?.grade || !FINANCE_MAX[sourceLabel]) continue;
      setPublicGrade(span, span.parentElement?.querySelector(":scope > b"), meta.grade,
        ["主要状态", meta.lossText, boundaryExcerpt(item)]);
    }
  }

  function patchHandoffGrades(root, record) {
    if (!root || !record?.net) return;
    const items = itemMap(record, "handoff");
    if (!items.size) return;
    for (const detail of root.querySelectorAll(".net-metric-detail[data-second-source-label]")) {
      const sourceLabel = detail.dataset.secondSourceLabel || "";
      const item = items.get(sourceLabel);
      const grade = publicHandoffGrade(item);
      if (!item || !grade || !HANDOFF_LABELS[sourceLabel]) continue;
      const summary = detail.querySelector(":scope > summary");
      setPublicGrade(summary?.querySelector(":scope > span"), summary?.querySelector(":scope > b"), grade,
        [HANDOFF_LABELS[sourceLabel], boundaryExcerpt(item)]);
    }
    for (const span of root.querySelectorAll(".component > span[data-second-source-label]")) {
      const sourceLabel = span.dataset.secondSourceLabel || "";
      const item = items.get(sourceLabel);
      const grade = publicHandoffGrade(item);
      if (!item || !grade || !HANDOFF_LABELS[sourceLabel]) continue;
      setPublicGrade(span, span.parentElement?.querySelector(":scope > b"), grade,
        [HANDOFF_LABELS[sourceLabel], boundaryExcerpt(item)]);
    }
  }

  function patchGradeGroups(root, record) {
    patchMethodGrades(root, record);
    patchFinanceGrades(root, record);
    patchHandoffGrades(root, record);
  }

  function publicEnumText(value) {
    let text = String(value ?? "").trim();
    for (const [from, to] of Object.entries(PUBLIC_ITEM_LABELS)) text = text.replaceAll(from, to);
    for (const [from, to] of Object.entries(PUBLIC_ROLE_LABELS)) text = text.replace(new RegExp("\\b" + from + "\\b", "g"), to);
    text = text
      .replace(/(?:现有材料|现材料|现有证据)?\s*未(?:独立)?闭合\s*R4/gi, "现有证据尚未证明跨朝代长期接收")
      .replace(/(?:现有材料|现材料|现有证据)?\s*未(?:独立)?闭合\s*R3/gi, "现有证据尚未证明被多个后继统治阶段持续采用")
      .replace(/闭合\s*R4/gi, "已证明跨朝代长期接收")
      .replace(/闭合\s*R3/gi, "已证明被多个后继统治阶段持续采用")
      .replace(/R3\s*\/\s*R4/gi, "长期接收")
      .replace(/R3\s*门(?:槛)?/gi, "长期接收门槛")
      .replace(/\bR4\b/gi, "跨朝代长期接收")
      .replace(/\bR3\b/gi, "被多个后继统治阶段持续采用")
      .replace(/\bR[12]\b/gi, "后世接收范围有限")
      .replace(/\bR0\b/gi, "本人任内运行证据")
      .replace(/\bG([0-5])\s*[-/]\s*([A-Za-z-]+)\b/gi, (_, band, position) => `${PUBLIC_GRADE[`G${band}`] || ""}${positionSuffix(position)}`)
      .replace(/\bG([0-5])(?=档)/g, (_, band) => PUBLIC_GRADE[`G${band}`] || band)
      .replace(/\bG([0-5])\b/g, (_, band) => `${PUBLIC_GRADE[`G${band}`] || band}档`)
      .replace(/\bC[123]-([1-6])\s*\/\s*L([0-3])\b/g, (_, band, loss) => `${STATE_GRADE[Number(band)] || band}档；${LOSS_TEXT[Number(loss)] || ""}`)
      .replace(/\bC[123]-([1-6])\b/g, (_, band) => `${STATE_GRADE[Number(band)] || band}档`)
      .replace(/\bD3-([0-5])\b/g, (_, level) => `${HANDOFF_GRADE[Number(level)] || level}档`)
      .replace(/\bD1\b/g, "行政连续性")
      .replace(/\bD3\b/g, "交接稳定")
      .replace(/\bH([0-5])\b/g, (_, level) => `${HANDOFF_GRADE[Number(level)] || level}档`)
      .replace(/\bL([0-3])\b/g, (_, level) => LOSS_TEXT[Number(level)] || "");
    return text.trim();
  }

  function publicTechnicalText(value) {
    return publicEnumText(value)
      .replace(/正式方向指数/g, "原始表现指数")
      .replace(/方向指数/g, "原始表现指数");
  }

  function publicFinanceText(value) { return String(value ?? ""); }

  function publicHandoffText(value) {
    return publicText(value)
      .replace(/实际率百官/g, "实际率领百官")
      .replace(/故仅能支持，不能把主政权降服等同全国行政完整收束。?/g, "这只能证明部分行政承接，不能把主政权降服等同于全国行政完整收束。")
      .replace(/。、/g, "。")
      .replace(/；、/g, "；")
      .replace(/。；/g, "；")
      .replace(/；；+/g, "；");
  }

  function publicCalculationText(value) {
    let text = publicTechnicalText(value);
    for (const [from, to] of Object.entries(SECOND_CALC_LABELS)) text = text.replaceAll(from, to);
    return text;
  }

  // Only contract-defined enum labels are translated. Sentences, negation,
  // responsibility and boundaries are otherwise preserved verbatim.
  function publicText(value) {
    return publicEnumText(value)
      .replace(/机械等价/g, "直接等同")
      .replace(/当前固定窗口/g, "当前评价窗口")
      .replace(/正式窗口/g, "评价窗口")
      .replace(/按合同/g, "按评价规则")
      .replace(/终态/g, "任期结束状态")
      .replace(/低谷标签/g, "低谷判断")
      .replace(/抬档/g, "提高等级")
      .replace(/压档/g, "压低等级")
      .replace(/扣档/g, "降低等级")
      .replace(/升档/g, "上调等级")
      .replace(/降档/g, "下调等级")
      .replace(/现有直接史料能够确认事实链已确认/g, "现有直接史料能够确认")
      .replace(/逐字引文证明链条成立/g, "现有直接史料能够确认")
      .replace(/链条成立/g, "事实链已确认")
      .replace(/固定史源/g, "固定史料")
      .replace(/运行结果是/g, "实际运行情况：")
      .replace(/未计入长期接收加权/g, "未因后世长期沿用获得额外提高")
      .replace(/不自动取得长期接收权重/g, "不因后世长期沿用自动提高判断")
      .replace(/长期接收加权/g, "后世长期沿用加成")
      .replace(/低态/g, "低位状态")
      .replace(/有源([SABCDE][+−-]?)档或([SABCDE][+−-]?)档端点/g, "有证据支持的$1档或$2档判断")
      .replace(/条件槛/g, "条件")
      .replace(/(?:综合)?净值为-1/g, "综合判断仍偏负")
      .replace(/负账/g, "负向影响")
      .replace(/倒算/g, "追溯计入")
      .replace(/追溯计入计入/g, "追溯计入")
      .replace(/持续采用持续采用/g, "持续采用")
      .replace(/故较低档→较高档/g, "因此整体判断上调")
      .replace(/压低较高档\s*档内位置/g, "压低当前等级的档内位置")
      .replace(/整体判断为较高档（中下位）/g, "整体判断位于当前公开等级的中下段")
      .replace(/经两层独立固定史源和五长期接收条件复裁计入制度建设/g, "经独立史源与长期接收条件复核后计入制度建设")
      .replace(/按当前固定窗口和设立、运行与后续变化去重裁决/g, "按当前评价窗口，将同一机制的设立、运行与后续变化合并判断")
      .replace(/本层只修正机制颗粒度，不新增史实/g, "此处只说明机制范围，不新增历史事实")
      .replace(/父链/g, "证据链")
      .replace(/复裁/g, "复核")
      .replace(/重裁/g, "重新核对")
      .replace(/未通过实际恢复准入/g, "尚未达到实际恢复的计入条件")
      .replace(/不准入当前判断/g, "不纳入当前判断")
      .replace(/责任准入/g, "本人责任条件")
      .replace(/由([^，。；]+)准入/g, "由$1支持计入")
      .replace(/准入/g, "计入条件")
      .replace(/按合同前者越窗/g, "按评价窗口，前者不计入本期")
      .replace(/越窗/g, "超出评价窗口")
      .replace(/公共法律底账/g, "公共法律正式记录")
      .replace(/联合底账/g, "联合正式记录")
      .replace(/底账/g, "正式记录")
      .replace(/前中期主态/g, "前中期主要阶段状态")
      .replace(/主要阶段压制异议的主态/g, "主要阶段压制异议的状态")
      .replace(/主态/g, "主要阶段状态")
      .replace(/不能倒灌抹去/g, "不能追溯用来抹去")
      .replace(/不把([^，。；]+?)倒灌为/g, "不把$1追溯作为")
      .replace(/不得把([^，。；]+?)倒灌为/g, "不得把$1追溯作为")
      .replace(/不能把([^，。；]+?)倒灌为/g, "不能把$1追溯作为")
      .replace(/不得倒灌为/g, "不得追溯作为")
      .replace(/不能倒灌为/g, "不能追溯作为")
      .replace(/不倒灌为/g, "不追溯作为")
      .replace(/不得倒灌(?=[^，。；])/g, "不得追溯计入")
      .replace(/不能倒灌(?=[^，。；])/g, "不能追溯计入")
      .replace(/不倒灌(?=[^，。；])/g, "不追溯计入")
      .replace(/不得倒灌/g, "不得追溯计入本人")
      .replace(/不能倒灌/g, "不能追溯计入本人")
      .replace(/不倒灌/g, "不追溯计入本人")
      .replace(/倒灌/g, "追溯计入")
      .replace(/不得把([^，。；]+?)回填/g, "不得把$1追溯计入本人")
      .replace(/不能把([^，。；]+?)回填/g, "不能把$1追溯计入本人")
      .replace(/不把([^，。；]+?)回填/g, "不把$1追溯计入本人")
      .replace(/不得回填(?=[^，。；])/g, "不得追溯计入")
      .replace(/不能回填(?=[^，。；])/g, "不能追溯计入")
      .replace(/不回填(?=[^，。；])/g, "不追溯计入")
      .replace(/不得回填/g, "不得追溯计入本人")
      .replace(/不能回填/g, "不能追溯计入本人")
      .replace(/不回填/g, "不追溯计入本人")
      .replace(/回填/g, "追溯计入")
      .replace(/第三项军事成本军事成本/g, "军事与边疆项的军事成本")
      .replace(/第三项军事成本/g, "军事与边疆项的军事成本")
      .replace(/军事与边疆项的军事成本第五级(高位|中位|低位)?/g, (_, position) => `严重军事成本${position ? "（"+position+"）" : ""}`)
      .replace(/。；/g, "；")
      .replace(/；；+/g, "；");
  }

  function dedupeBoundaryText(value) {
    const text = String(value ?? "")
      .replace(/\s+/g, " ")
      .replace(/。；/g, "；")
      .replace(/；；+/g, "；")
      .trim();
    if (!text) return "";
    const seen = new Set();
    const clauses = [];
    for (const raw of text.split("；")) {
      const clause = raw.trim();
      if (!clause) continue;
      const key = clause.replace(/[。；]+$/g, "").trim();
      if (!key || seen.has(key)) continue;
      seen.add(key);
      clauses.push(clause);
    }
    return clauses.join("；");
  }

  function publicBoundaryText(value) {
    return dedupeBoundaryText(publicText(value));
  }

  function publicFinanceBoundaryText(value) {
    return String(value ?? "");
  }

  function secondMethodExpandedHow(label) {
    const record = netRecord() || personRecord();
    const method = itemMap(record, "method");
    if (!method.size) return "";
    if (label === "A制度建设" || label === "B1官僚治理") {
      const a = finite(method.get("A制度建设")?.value);
      const b1 = finite(method.get("B1官僚治理")?.value);
      const ab = finite(method.get("AB计分块")?.value);
      if (a == null || b1 == null || ab == null) return "";
      const high = Math.max(a, b1);
      const low = Math.min(a, b1);
      return `制度建设与官僚治理不各自直接加分，而是组成同一主块：0.8 × [较高表现指数 ${fmt(high)} + 0.5 × 较低表现指数 ${fmt(low)}] = ${fmt(ab)} 分。`;
    }
    if (label === "B2反馈与约束") {
      const b2 = finite(method.get("B2反馈与约束")?.value);
      const converted = finite(method.get("B2折算")?.value);
      if (b2 == null || converted == null) return "";
      return `反馈与约束单独占45分：45 / 80 × 当前表现指数 ${fmt(b2)} = ${fmt(converted)} 分。`;
    }
    return "";
  }

  function secondHandoffExpandedHow() {
    const record = netRecord() || personRecord();
    const handoff = itemMap(record, "handoff");
    const total = handoff.get("交接得分");
    if (!total) return "";
    const how = publicTechnicalText(total.reader_how || "");
    return how ? `${how} 其中0—5只作为 E—S 档在合成公式中的权重，公开裁决仍使用 E—S，并不是另一套数字档位。` : "";
  }

  function secondScoreHowDetails(item, label) {
    const details = document.createElement("details");
    details.className = "second-item-score-how";
    details.append(makeTextBlock("summary", "", "这个分怎么算？"));
    const rows = [];
    const add = (name, value) => { if (value) rows.push([name, value]); };

    if (item.reader_public_c) {
      details.append(makeTextBlock("p", "prose", item.reader_public_c.public_calculation));
      return details;
    }

    if (METHOD_MAX[label]) {
      const grade = publicMethodGrade(item);
      add("当前裁决", [grade ? `${grade}档` : "", `原始表现指数 ${fmt(item.value)} / ${METHOD_MAX[label]}`].filter(Boolean).join(" · "));
      const formal = label === "B1官僚治理" ? String(item.reader_how || "") : publicTechnicalText(item.reader_how || "该原始表现指数进入制度与行政合成，不作为本项直接得分。");
      const expanded = secondMethodExpandedHow(label);
      add("换算规则", [formal, expanded].filter(Boolean).join(" "));
      add("当前结果", "用于制度与行政折算，不单列得分");
    } else if (FINANCE_MAX[label] || label === "C4恢复与成本") {
      throw new Error("第二项C缺少上游正式计算说明，请重建阅读数据");
    } else if (HANDOFF_LABELS[label]) {
      const grade = publicHandoffGrade(item);
      add("当前裁决", grade ? `${grade}档` : "");
      const formal = publicTechnicalText(item.reader_how || "");
      const expanded = secondHandoffExpandedHow();
      add("换算规则", [formal, expanded].filter(Boolean).join(" "));
      add("当前结果", grade ? `${grade}档` : "");
    } else {
      add("换算规则", publicTechnicalText(item.reader_how || ""));
      add("当前结果", item.value == null ? "—" : `${fmt(item.value)}${item.unit ? " " + item.unit : ""}`);
    }

    if (!rows.length) return null;
    for (const [name,value] of rows) {
      details.append(makeTextBlock("p", "prose", name + "：" + value));
    }
    return details;
  }

  globalThis.SecondItemScoreHowDetails = secondScoreHowDetails;

  function materialChip(text, className = "") {
    const value = publicText(text);
    if (!value) return null;
    const chip = document.createElement("span");
    chip.className = `adjudication-material-chip ${className}`.trim();
    chip.textContent = value;
    return chip;
  }

  function materialCard(data = {}) {
    const format = data.verbatim ? value => String(value ?? "") : publicText;
    const card = document.createElement("li");
    card.className = "adjudication-material-card" + (data.supplement ? " is-supplement" : "");
    for (const [key, value] of Object.entries(data.dataset || {})) if (value != null && value !== "") card.dataset[key] = String(value);

    const head = document.createElement("div");
    head.className = "adjudication-material-head";
    const title = document.createElement("strong");
    title.textContent = format(data.title || "裁决材料");
    head.append(title);

    const meta = document.createElement("div");
    meta.className = "adjudication-material-meta";
    for (const [value, className] of [
      [data.direction, "direction"],
      [data.strength, "strength"],
      ...(Array.isArray(data.tags) ? data.tags.map(tag => [tag, "tag"]) : []),
      [data.contribution, "contribution"],
    ]) {
      const chip = materialChip(value, className);
      if (chip) meta.append(chip);
    }
    if (meta.childNodes.length) head.append(meta);
    card.append(head);

    const body = format(data.body);
    if (body) card.append(makeTextBlock("p", "adjudication-material-basis", body));

    const scope = format(data.scope);
    const boundary = data.verbatim ? format(data.boundary) : publicBoundaryText(data.boundary);
    if (scope || boundary) {
      const details = document.createElement("details");
      details.className = "adjudication-material-boundary";
      details.append(makeTextBlock("summary", "", "范围与边界"));
      if (scope) {
        const box = makeTextBlock("div", "adjudication-material-scope", "");
        box.append(makeTextBlock("strong", "", "具体范围"), makeTextBlock("p", "", scope));
        details.append(box);
      }
      if (boundary) {
        const box = makeTextBlock("div", "adjudication-material-scope", "");
        box.append(makeTextBlock("strong", "", "判断边界"), makeTextBlock("p", "", boundary));
        details.append(box);
      }
      card.append(details);
    }

    const footer = publicText(data.footer);
    if (footer) card.append(makeTextBlock("small", "adjudication-material-footer", footer));
    return card;
  }

  function materialGroup(title, cards) {
    if (!cards.length) return document.createDocumentFragment();
    const section = document.createElement("section");
    section.className = "adjudication-material-group";
    section.append(makeTextBlock("h4", "", publicText(title)));
    const list = document.createElement("ul");
    list.className = "adjudication-material-list";
    list.replaceChildren(...cards);
    section.append(list);
    return section;
  }

  function renderB2MaterialGroups(evidence) {
    const groups = {positive:[], negative:[], mixed:[]};
    for (const entry of evidence || []) {
      const direction = String(entry?.public_direction || "");
      const key = direction.startsWith("正向") ? "positive" : direction.startsWith("负向") ? "negative" : "mixed";
      groups[key].push(materialCard({
        title: entry?.public_label || entry?.public_role,
        direction,
        tags: entry?.public_tags || [],
        body: entry?.public_basis,
        boundary: entry?.public_boundary,
        verbatim: true,
        dataset: {publicEvidenceId: entry?.id || ""},
      }));
      const card = groups[key][groups[key].length - 1];
      const sources = document.createElement("details");
      sources.className = "b2-material-sources";
      sources.append(makeTextBlock("summary", "", "本条史料与归责依据"));
      for (const ref of entry.source_refs || []) {
        const source = makeTextBlock("div", "b2-source", "");
        source.append(makeTextBlock("p", "", [ref.source_title, ref.source_locator].filter(Boolean).join(" · ")));
        if (ref.exact_quote) source.append(makeTextBlock("blockquote", "prose", ref.exact_quote));
        const links = document.createElement("p");
        links.className = "sources";
        if (typeof link === "function") links.innerHTML = link(ref.path, "查看所引材料登记 ↗") + (ref.source_url ? " " + link(ref.source_url, "查看史源 ↗") : "");
        source.append(links);
        sources.append(source);
      }
      card.append(sources);
    }
    const wrapper = document.createElement("div");
    wrapper.className = "adjudication-material-groups b2-material-groups";
    wrapper.append(
      materialGroup("正向反馈与约束", groups.positive),
      materialGroup("负向反馈失灵", groups.negative),
      materialGroup("正负并存或阶段变化", groups.mixed)
    );
    return wrapper;
  }

  function b2Reading(item) {
    const reading = document.createElement("div");
    reading.className = "second-item-public-reading b2-public-reading";
    reading.append(makeTextBlock("div", "label", "为什么是这个等级"));
    reading.append(makeTextBlock("p", "prose b2-adjudication-summary", String(item.public_adjudication_summary || item.reader_summary || "")));
    reading.append(makeTextBlock("p", "subline", "看具体意见如何进入、本人如何处置及结果是否改变。主动改意、接受信息与受到外部程序约束分别理解；背景材料不当作独立功过。"));
    reading.append(renderB2MaterialGroups(item.reader_public_evidence_items || item.public_evidence_items || []));
    return reading;
  }
  globalThis.SecondItemB2Reading = Object.freeze({
    render: b2Reading,
    html: item => b2Reading(item).outerHTML,
  });

  function financeRoleKey(role) {
    const value = String(role || "").trim();
    if (value === "主要状态") return "state";
    if (value === "低谷") return "loss";
    if (value === "边界") return "boundary";
    if (value === "恢复" || value === "责任范围") return "recovery";
    if (value === "状态恶化" || value === "额外代价") return "cost";
    return "other";
  }

  function renderFinanceMaterialGroups(label, evidence) {
    const groups = {state:[], loss:[], recovery:[], cost:[], boundary:[], other:[]};
    for (const entry of evidence || []) {
      const role = String(entry?.public_role || "").trim();
      const key = financeRoleKey(role);
      groups[key].push(materialCard({
        title: publicFinanceText(entry?.public_label || role || "正式裁决材料"),
        tags: role ? [role] : [],
        body: publicFinanceText(entry?.public_basis),
        boundary: publicFinanceText(entry?.public_boundary),
        dataset: {publicEvidenceId: entry?.id || ""},
      }));
    }
    const wrapper = document.createElement("div");
    wrapper.className = "adjudication-material-groups finance-material-groups";
    if (label === "C4恢复与成本") {
      wrapper.append(
        materialGroup("恢复与归责", groups.recovery),
        materialGroup("恶化与额外代价", groups.cost),
        materialGroup("重复计算与评价边界", groups.boundary),
      );
    } else {
      wrapper.append(
        materialGroup("主要状态", groups.state),
        materialGroup("低谷与损失", groups.loss),
        materialGroup("评价边界", groups.boundary),
      );
    }
    if (groups.other.length) wrapper.append(materialGroup("其他正式材料", groups.other));
    return wrapper;
  }


  function renderHandoffMaterialGroups(label, evidence) {
    const groups = {preparation:[], result:[], continuity:[], other:[]};
    for (const entry of evidence || []) {
      const role = String(entry?.public_role || "").trim();
      const key = role === "事前安排" ? "preparation"
        : (role === "交接结果" || role === "终局事实") ? "result"
        : (role === "前任行政资产承接" || role === "行政承接与限制") ? "continuity"
        : "other";
      const card = materialCard({
        verbatim: true,
        title: entry.public_label,
        tags: role ? [role] : [],
        body: entry.public_basis,
        boundary: entry.public_boundary,
        dataset: {publicEvidenceId: entry?.id || ""},
      });
      const sources = document.createElement("details");
      sources.className = "handoff-public-sources";
      sources.append(makeTextBlock("summary", "", "本条史料与评价依据"));
      for (const ref of entry.source_refs) {
        const source = document.createElement("section");
        source.append(makeTextBlock("p", "meta", `${ref.source_kind} · ${ref.source_title} · ${ref.source_locator}`));
        if (ref.support_role) source.append(makeTextBlock("p", "meta", ref.support_role));
        source.append(makeTextBlock("blockquote", "prose", ref.public_excerpt));
        const links = document.createElement("p");
        links.className = "sources";
        if (typeof link === "function") links.innerHTML = link(ref.path, "查看所引记录 ↗");
        if (ref.source_url?.startsWith("https://")) {
          const anchor = document.createElement("a");
          anchor.href = ref.source_url; anchor.textContent = "查看史源 ↗";
          anchor.target = "_blank"; anchor.rel = "noopener";
          links.append(document.createTextNode(" · "), anchor);
        }
        source.append(links); sources.append(source);
      }
      card.append(sources);
      const modes = {DIRECT:"史料直接记载", INFERRED:"受约束推断", ASSESSMENT:"正式评价判断", BACKGROUND:"背景核对"};
      card.prepend(makeTextBlock("p", "meta", modes[entry.evidence_mode]));
      groups[key].push(card);
    }
    const wrapper = document.createElement("div");
    wrapper.className = "adjudication-material-groups handoff-material-groups";
    if (label === "D1继任行政连续性") {
      wrapper.append(materialGroup("行政承接、断裂与限制", groups.continuity));
    } else {
      wrapper.append(
        materialGroup("事前安排", groups.preparation),
        materialGroup("实际交接与终局事实", groups.result),
      );
    }
    if (groups.other.length) wrapper.append(materialGroup("其他正式材料", groups.other));
    return wrapper;
  }


  globalThis.SecondItemMaterialCards = Object.freeze({
    card: materialCard,
    group: materialGroup,
    publicEnumText,
    boundaryText: publicBoundaryText,
  });

  function handoffReading(item) {
    const authored = item.reader_public_d;
    if (!authored) throw new Error("缺少政权交接正式公开正文");
    const reading = document.createElement("div");
    reading.className = "handoff-authored-reading";
    reading.dataset.formalPublicSource = "";
    for (const paragraph of authored.public_story.split(/\n\n+/)) reading.append(makeTextBlock("p", "prose", paragraph));
    reading.append(makeDetails("为什么这样评", authored.public_adjudication_summary));
    reading.append(makeTextBlock("p", "prose", `观察范围：${authored.public_window}`));
    reading.append(makeTextBlock("p", "prose", `本人责任：${authored.public_responsibility}`));
    reading.append(renderHandoffMaterialGroups(item.label, authored.public_evidence_items));
    reading.append(makeDetails("范围与边界", authored.public_boundary));
    return reading;
  }

  globalThis.SecondItemDReading = Object.freeze({html: item => handoffReading(item).outerHTML});

  function publicFacts(item) {
    if (item?.reader_public_d) return [item.reader_public_d.public_story];
    const evidence = Array.isArray(item?.reader_public_evidence_items) ? item.reader_public_evidence_items : [];
    if (evidence.length) {
      return evidence.map(entry => {
        if (!entry || typeof entry !== "object") return "";
        const label = String(entry.public_label || "").trim();
        const direction = String(entry.public_direction || "").trim();
        const basis = publicText(entry.public_basis || "");
        const boundary = publicText(entry.public_boundary || "");
        return [
          [label, direction].filter(Boolean).join(" · "),
          basis,
          boundary ? `边界：${boundary}` : "",
        ].filter(Boolean).join("；");
      }).map(publicText).filter(Boolean);
    }
    const highlights = (Array.isArray(item?.reader_highlights) ? item.reader_highlights : [])
      .map(publicText).filter(Boolean);
    if (highlights.length) return highlights;
    const summary = publicText(item?.reader_summary || "");
    return summary ? [summary] : [];
  }

  function makeTextBlock(tagName, className, text) {
    const node = document.createElement(tagName);
    if (className) node.className = className;
    node.textContent = text;
    return node;
  }

  function makeDetails(title, text, className = "") {
    if (!text) return null;
    const details = document.createElement("details");
    if (className) details.className = className;
    const summary = document.createElement("summary");
    summary.textContent = title;
    details.append(summary, makeTextBlock("p", "prose", text));
    return details;
  }

  function publicEvidenceList(evidence) {
    const list = makeTextBlock("ul", "second-item-public-evidence", "");
    for (const entry of evidence) {
      const card = makeTextBlock("li", "second-item-public-evidence-card", "");
      const title = [publicText(entry.public_label || entry.public_role), publicText(entry.public_direction)].filter(Boolean).join(" · ");
      if (title) card.append(makeTextBlock("strong", "", title));
      card.append(makeTextBlock("p", "prose", publicText(entry.public_basis)));
      const boundary = makeDetails("适用范围与限制", publicText(entry.public_boundary));
      if (boundary) card.append(boundary);
      list.append(card);
    }
    return list;
  }

  function patchMetricBodies(record) {
    if (!record?.net || !location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/)) return;
    const items = secondItems(record);
    const root = document.getElementById("net-major-body");
    if (!root) return;
    for (const detail of root.querySelectorAll(".net-metric-detail[data-second-source-label]")) {
      const label = detail.dataset.secondSourceLabel || "";
      // Dedicated A/B1 renderers own these bodies. Do not overwrite them when
      // their asynchronous formal data load triggers the shared observer.
      if (label === "A制度建设" || label === "B1官僚治理") continue;
      const item = items.get(label);
      if (item?.reader_public_c) continue;
      if (!item || item.reader_kind !== "judgment") continue;
      const body = detail.querySelector(":scope > .net-metric-body");
      if (!body) continue;
      const key = [item.reader_summary || "", JSON.stringify(item.reader_public_d || null), JSON.stringify(item.reader_public_evidence_items || []), ...(item.reader_highlights || []), item.reader_boundary || "", item.reader_how || "", item.reader_full_basis || ""].join("|");
      if (body.dataset.secondPublicBodyKey === key && body.querySelector(":scope > .second-item-public-reading")) continue;
      const audit = body.querySelector(":scope > .net-audit-sources");
      if (audit) audit.remove();
      let formal = body.querySelector(":scope > .net-formal-basis-raw");
      if (formal) formal.remove();
      const raw = String(item.reader_full_basis || "").trim();
      if (!formal && raw && raw !== String(item.reader_summary || "").trim()) {
        formal = makeDetails("正式裁决原文（未改写）", raw, "net-formal-basis-raw");
      }
      body.innerHTML = "";
      const reading = document.createElement("div");
      reading.className = "second-item-public-reading";
      reading.append(makeTextBlock("div", "label", "为什么这样判断"));
      const evidence = item.reader_public_evidence_items;
      const facts = publicFacts(item);
      if (label === "B2反馈与约束" && Array.isArray(evidence) && evidence.length) {
        reading.replaceChildren(...b2Reading(item).childNodes);
        reading.classList.add("b2-public-reading");
      } else if (["C1民生","C2经济财政","C3社会安全","C4恢复与成本"].includes(label) && Array.isArray(evidence) && evidence.length) {
        reading.append(renderFinanceMaterialGroups(label, evidence));
      } else if (["D1继任行政连续性","D3政权交接稳定"].includes(label) && Array.isArray(evidence) && evidence.length) {
        reading.replaceChildren(handoffReading(item));
        reading.dataset.formalPublicSource = "";
      } else if (Array.isArray(evidence) && evidence.length) {
        reading.append(publicEvidenceList(evidence));
      } else if (facts.length > 1) {
        const list = document.createElement("ul");
        for (const fact of facts) list.append(makeTextBlock("li", "", fact));
        reading.append(list);
      } else if (facts.length === 1) {
        reading.append(makeTextBlock("p", "prose", facts[0]));
      } else {
        reading.append(makeTextBlock("p", "prose", "当前尚未提供公开说明，请查看正式记录。"));
      }
      body.append(reading);
      const financeItem = ["C1民生","C2经济财政","C3社会安全","C4恢复与成本"].includes(label);
      const boundaryDetails = item.reader_public_d
        ? null
        : makeDetails("范围与边界", financeItem ? publicFinanceBoundaryText(item.reader_boundary || "") : publicBoundaryText(item.reader_boundary || ""));
      if (boundaryDetails) body.append(boundaryDetails);
      const howDetails = secondScoreHowDetails(item, label);
      if (howDetails) body.append(howDetails);
      if (formal) body.append(formal);
      if (audit) body.append(audit);
      body.dataset.secondPublicBodyKey = key;
    }
  }

  function patchCalculationRows(root, record) {
    if (!root || !record?.net) return;
    for (const key of SECOND_GROUPS) {
      const panel = root.querySelector(`#net-group-${key}`);
      const details = panel?.querySelector(":scope > .net-calculations");
      if (!details) continue;
      const rows = Array.from(details.querySelectorAll(":scope > .component"));
      const visible = SECOND_CALC_VISIBLE[key];
      const calculations = (record.net.component_details?.[key] || [])
        .filter(item => item.reader_kind === "calculation" && item.value != null && (!visible || visible.has(item.label)));
      const summary = details.querySelector(":scope > summary");
      if (summary) summary.textContent = "本组小计怎么形成？";
      rows.forEach((row, index) => {
        const item = calculations[index];
        if (!item) return;
        const strong = row.querySelector("strong");
        const small = row.querySelector("small");
        if (strong) strong.textContent = SECOND_CALC_LABELS[item.label] || publicText(item.public_component_label || item.label);
        if (small) small.textContent = publicCalculationText(item.reader_how || "");
      });
    }
  }

  function patchGroupIntros(record) {
    if (!record?.net || !location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/)) return;
    const values = secondTotals(record);
    writePublicCopy(document.querySelector('[data-second-intro="method"]'),
      `这一组看国家机器如何建立规则、配置官僚并形成反馈约束。当前合计 ${fmt(values.method)} 分；公开层先看等级和历史依据，具体表现指数与折算放在展开内容里。`);
    writePublicCopy(document.querySelector('[data-second-intro="finance"]'),
      `这一组看统治时期普通家庭、经济财政和社会安全的主要状态，再结合任内低谷、恢复与额外代价形成结果判断。当前合计 ${fmt(values.finance)} 分。`);
    writePublicCopy(document.querySelector('[data-second-intro="handoff"]'),
      "统治如何收尾，会直接影响国家机器和继承秩序能否平稳延续。行政连续性看旧国家机器有多少被接住，交接稳定看继承过程是否顺利；两项均以 S—E 六档显示。");
  }

  function patchScorePresentation(record) {
    if (!record?.net) return;
    const totals = secondTotals(record);
    if (location.hash.match(/^#net\/[^/?#]+\/(?:all)?$/)) {
      const card = Array.from(document.querySelectorAll(".net-major-card")).find(node => /\/second(?:\/|$)/.test(node.getAttribute("href") || ""));
      if (card) {
        if (totals.total != null) writePublicScore(card.querySelector(".big"), `${fmt(totals.total)} 分`);
      }
    }
    if (location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/)) {
      const intro = document.querySelector(".net-detail-page > .panel");
      const scoreLine = intro?.querySelector(":scope > p.subline");
      if (totals.total != null) writePublicCopy(scoreLine, `治国成效：${fmt(totals.total)} 分。先看结论，再展开到各项依据。`);
    }
    if (location.hash.startsWith("#person/")) {
      const panel = document.getElementById("person-outcome");
      for (const row of panel?.querySelectorAll(":scope > .component") || []) {
        const span = row.querySelector("span");
        if (!span || !span.textContent.trim().startsWith("治国成效")) continue;
        if (totals.total != null) writePublicScore(row.querySelector("b"), `${fmt(totals.total)} 分`);
      }
    }
  }

  function patchCompareScores(records) {
    if (records.length < 2 || !location.hash.startsWith("#compare/")) return;
    const row = Array.from(screenEl.querySelectorAll(".comparison tbody tr")).find(item => item.cells?.[0]?.textContent.trim() === "治国成效");
    if (!row) return;
    records.forEach((record, index) => {
      const score = finite(record?.net?.second_item_score);
      const cell = row.cells?.[index + 1];
      if (!cell || score == null) return;
      writePublicScore(cell.querySelector("b"), `${fmt(score)} 分`);
    });
  }

  function replaceText(node, replacements) {
    if (!node) return;
    let next = node.textContent;
    for (const [from, to] of replacements) next = next.replaceAll(from, to);
    if (next !== node.textContent) node.textContent = next;
  }

  function patchPersonOutcomeLink() {
    const record = personRecord();
    const panel = document.getElementById("person-outcome");
    if (!record || !panel) return;
    const row = Array.from(panel.querySelectorAll(":scope > .component")).find(component => {
      const label = component.querySelector("span")?.textContent.trim() || "";
      return label.startsWith("治国成效") || label.startsWith("治国净收益");
    });
    if (!row || row.querySelector(":scope > .net-overview-jump")) return;
    const anchor = document.createElement("a");
    anchor.className = "net-overview-jump";
    anchor.href = `#net/${encodeURIComponent(record.ruler_id)}/second`;
    anchor.setAttribute("aria-label", `查看${record.ruler_name}的治国成效计分逻辑`);
    while (row.firstChild) anchor.append(row.firstChild);
    row.append(anchor);
  }

  function patchShellLanguage() {
    const head = document.querySelector(".net-detail-head");
    replaceText(head?.querySelector(".eyebrow"), [["净收益计分", "统治绩效"]]);
    replaceText(head?.querySelector("h1"), [["净收益计分总览", "统治绩效构成"], ["治国净收益", "治国成效"]]);
    replaceText(head?.querySelector(".muted"), [["总榜净收益", "统治绩效总分"]]);
    const nav = document.querySelector(".net-major-nav");
    if (nav) nav.setAttribute("aria-label", "统治绩效详情");
    const secondNav = Array.from(nav?.querySelectorAll("a") || []).find(a => /\/second(?:\/|$)/.test(a.getAttribute("href") || ""));
    if (secondNav && secondNav.textContent !== "治国成效") secondNav.textContent = "治国成效";
    for (const cardTitle of document.querySelectorAll(".net-major-card h2")) {
      replaceText(cardTitle, [["治国净收益", "治国成效"], ["净收益计分总览", "统治绩效构成"]]);
    }
    const reading = document.querySelector("#person-evidence .net-reading[data-net-compact='done']");
    if (reading) {
      const section = reading.closest("section.panel");
      const heading = section?.querySelector(":scope > h2, :scope > h3");
      if (heading?.textContent.trim() === "净收益构成") heading.textContent = "统治绩效构成";
      for (const link of reading.querySelectorAll("a")) replaceText(link, [["净收益计分页", "统治绩效详情"], ["净收益计分", "统治绩效"]]);
      for (const intro of reading.querySelectorAll("p.reading-intro")) replaceText(intro, [["独立净收益计分页", "独立统治绩效详情页"]]);
    }
    for (const message of screenEl.querySelectorAll(".empty p, .empty[role='status']")) {
      replaceText(message, [
        ["净收益计分详情加载失败", "统治绩效详情加载失败"],
        ["净收益详情地址无效", "统治绩效详情地址无效"],
        ["净收益正式结算", "统治绩效正式结算"],
        ["净收益计分逻辑", "统治绩效详情"],
      ]);
    }
  }

  function patchPublicGrades() {
    const net = netRecord();
    if (net && location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/)) {
      const root = document.getElementById("net-major-body");
      patchGradeGroups(root, net);
      patchMetricBodies(net);
      patchCalculationRows(root, net);
      patchGroupIntros(net);
    }
    const person = personRecord();
    if (person) patchGradeGroups(screenEl, person);
    const records = compareRecords();
    if (records.length) {
      const rows = Array.from(screenEl.querySelectorAll(".comparison tbody tr"));
      const structureRow = rows.find(row => ["分项构成", "构成与依据"].includes(row.cells?.[0]?.textContent.trim()));
      if (structureRow) records.forEach((record, index) => patchGradeGroups(structureRow.cells[index + 1], record));
      patchCompareScores(records);
    }
  }

  function patch() {
    ensureStyles();
    patchPersonOutcomeLink();
    patchShellLanguage();
    patchPublicGrades();
    const net = netRecord();
    if (net) patchScorePresentation(net);
    const person = personRecord();
    if (person) patchScorePresentation(person);
  }

  globalThis.SecondItemPublicAlias = Object.freeze({patch});
})();
