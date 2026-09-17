"use strict";

(() => {
  const screen = document.getElementById("screen");
  if (!screen) return;

  const cache = new Map();
  let scheduled = false;

  function currentRecord() {
    if (typeof byId === "undefined") return null;
    const match = location.hash.match(/^#net\/([^/?#]+)\/second(?:\/|$)/);
    if (!match) return null;
    try { return byId.get(decodeURIComponent(match[1])) || null; } catch { return null; }
  }

  function methodItem(record) {
    return (record?.net?.component_details?.method || []).find(item => item.label === "A制度建设") || null;
  }

  function sourcePath(ref) {
    return decodeURIComponent(String(ref || "").split("#", 1)[0]).replace(/:\d+(?:-\d+)?$/, "");
  }

  function dirname(path) {
    const at = path.lastIndexOf("/");
    return at < 0 ? "" : path.slice(0, at);
  }

  function rows(payload) {
    if (Array.isArray(payload?.records)) return payload.records;
    if (Array.isArray(payload?.collections?.records?.records)) return payload.collections.records.records;
    return [];
  }

  async function repoJson(path) {
    const response = await fetch(`../${path}?raw=1`, {cache:"no-cache"});
    if (!response.ok) throw new Error(`HTTP ${response.status}: ${path}`);
    return response.json();
  }

  async function formalA(record, item) {
    const path = sourcePath(item?.source);
    if (!path) return null;
    const key = `${record.ruler_id}\u0000${path}`;
    if (cache.has(key)) return cache.get(key);
    const pending = (async () => {
      const payload = await repoJson(path);
      let records = rows(payload);
      if (!records.length && Array.isArray(payload?.routes)) {
        const route = payload.routes.find(entry => entry?.polity === record.polity);
        if (!route?.path) return null;
        records = rows(await repoJson(`${dirname(path)}/${route.path}`));
      }
      return records.find(row => row?.ruler_id === record.ruler_id) || null;
    })().catch(error => {
      console.error("Failed to load formal A public projection", error);
      return null;
    });
    cache.set(key, pending);
    return pending;
  }

  function make(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function fmtWeight(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return "—";
    const text = Number.isInteger(number) ? String(number) : number.toFixed(1).replace(/\.0$/, "");
    return number > 0 ? `+${text}` : text;
  }

  function groupKey(direction) {
    if (direction === "正向") return "positive";
    if (direction === "负向") return "negative";
    return "mixed";
  }

  function groups(nodes) {
    const result = {positive:[], negative:[], mixed:[]};
    for (const node of nodes || []) result[groupKey(node?.public_direction)].push(node);
    return result;
  }

  function tagRow(tags) {
    const row = make("div", "second-item-a-tags");
    for (const tag of tags || []) row.append(make("span", "second-item-a-tag", tag));
    return row;
  }

  function textBox(title, text, className) {
    if (!String(text || "").trim()) return null;
    const box = make("div", className);
    box.append(make("strong", "", title), make("p", "", text));
    return box;
  }

  function card(node) {
    const li = make("li", "second-item-a-card");
    if (node?.institution_node_id) li.dataset.institutionNodeId = node.institution_node_id;

    const head = make("div", "second-item-a-head");
    head.append(make("strong", "", node?.public_label || "制度节点"));
    head.append(tagRow(node?.public_tags || []));
    head.append(make("span", "second-item-a-direction", node?.public_direction || ""));
    head.append(make("span", "second-item-a-impact", `本项计入：${fmtWeight(node?.signed_weight)}`));
    li.append(head);

    if (node?.public_adjudication_basis) {
      li.append(make("p", "second-item-a-basis", node.public_adjudication_basis));
    }
    const scope = textBox("具体范围", node?.public_scope, "second-item-a-scope");
    if (scope) li.append(scope);
    const boundary = textBox("边界", node?.public_boundary, "second-item-a-boundary");
    if (boundary) li.append(boundary);
    if (node?.public_reception) {
      li.append(make("small", "second-item-a-reception", node.public_reception));
    }
    return li;
  }

  function section(title, nodes) {
    const wrapper = make("section", "second-item-a-group");
    wrapper.append(make("h4", "", title));
    if (!nodes.length) {
      wrapper.append(make("p", "second-item-a-empty", "当前正式结算没有该类制度节点。"));
      return wrapper;
    }
    const list = make("ul", "second-item-a-list");
    list.replaceChildren(...nodes.map(card));
    wrapper.append(list);
    return wrapper;
  }

  function ensureStyles() {
    if (document.getElementById("second-item-a-public-style")) return;
    const style = document.createElement("style");
    style.id = "second-item-a-public-style";
    style.textContent = `
      .second-item-a-reading{margin:4px 0 8px}
      .second-item-a-intro{margin:4px 0 14px;line-height:1.75}
      .second-item-a-summary{margin:10px 0 16px;padding:11px 13px;border-left:3px solid var(--gold);background:#f1eee6;font-size:12px;line-height:1.75}
      .second-item-a-group{margin:14px 0 18px}
      .second-item-a-group>h4{margin:0 0 8px;font-size:15px}
      .second-item-a-list{list-style:none;margin:0;padding:0;display:grid;gap:8px}
      .second-item-a-card{margin:0;padding:10px 12px;border:1px solid var(--line);border-radius:5px;background:#fff}
      .second-item-a-head{display:flex;align-items:center;gap:7px;flex-wrap:wrap}
      .second-item-a-head>strong{font-size:14px}
      .second-item-a-tags{display:flex;gap:5px;flex-wrap:wrap;align-items:center}
      .second-item-a-tag{display:inline-block;padding:1px 6px;border:1px solid var(--line);border-radius:999px;font-size:10px;line-height:1.6;color:var(--green);font-weight:700;background:#f4f5ef}
      .second-item-a-direction{font-size:10px;color:var(--muted);font-weight:700}
      .second-item-a-impact{display:inline-block;margin-left:auto;padding:1px 7px;border-radius:999px;background:#ecefe6;color:var(--ink);font-size:10px;font-weight:700;white-space:nowrap}
      .second-item-a-basis{margin:6px 0 0;font-size:12px;line-height:1.72}
      .second-item-a-scope,.second-item-a-boundary{margin-top:7px;padding:7px 9px;background:rgba(0,0,0,.025);font-size:11px;line-height:1.65}
      .second-item-a-scope strong,.second-item-a-boundary strong{font-size:11px;color:var(--muted)}
      .second-item-a-scope p,.second-item-a-boundary p{margin:2px 0 0}
      .second-item-a-reception{display:block;margin-top:7px;font-size:11px;line-height:1.65;color:var(--green);font-weight:600}
      .second-item-a-empty{margin:4px 0;color:var(--muted);font-size:12px}
    `;
    document.head.append(style);
  }

  function legacyOwnershipKey(record, formal) {
    return `${record.ruler_id}|${formal.direction_index}|${(formal.M_positive_profile || []).length}|${(formal.M_negative_profile || []).length}|${(formal.M_mixed_profile || []).length}|${(formal.important_institutions || []).length}`;
  }

  function existingHow(body) {
    return Array.from(body.querySelectorAll(":scope > details")).find(node =>
      node.querySelector(":scope > summary")?.textContent.trim() === "这个分数怎么算？"
    ) || null;
  }

  async function patch() {
    ensureStyles();
    const record = currentRecord();
    if (!record) return;
    const item = methodItem(record);
    const detail = Array.from(document.querySelectorAll(".net-metric-detail[data-second-source-label]"))
      .find(node => node.dataset.secondSourceLabel === "A制度建设");
    const body = detail?.querySelector(":scope > .net-metric-body");
    if (!item || !body) return;

    const formal = await formalA(record, item);
    if (!formal || !body.isConnected || currentRecord()?.ruler_id !== record.ruler_id) return;

    const ownershipKey = legacyOwnershipKey(record, formal);
    body.dataset.secondInstitutionKey = ownershipKey;

    const publicNodes = formal.public_institution_nodes;
    const summary = String(formal.public_adjudication_summary || "").trim();
    if (!Array.isArray(publicNodes) || !summary) {
      if (body.dataset.aPublic === "missing") return;
      body.innerHTML = "";
      body.append(make("p", "notice", "制度建设的正式公开节点尚未同步，请先刷新正式 A 公开投影。"));
      body.dataset.aPublic = "missing";
      return;
    }

    const publicKey = `${formal.public_projection_schema_version || ""}|${record.ruler_id}|${publicNodes.length}|${summary}`;
    if (body.dataset.aPublicKey === publicKey && body.querySelector(":scope > .second-item-a-reading")) return;

    const how = existingHow(body);
    how?.remove();

    body.innerHTML = "";
    const reading = make("div", "second-item-a-reading");
    reading.append(make("div", "label", "制度建设清单"));
    reading.append(make("p", "second-item-a-intro", "按正式逐节点裁决阅读。每项制度直接显示方向、制度类型、本项计入权重、具体范围、边界和后世接收。"));
    reading.append(make("div", "second-item-a-summary", summary));

    const grouped = groups(publicNodes);
    reading.append(section("正向制度建设", grouped.positive));
    reading.append(section("负向制度设计与制度性损害", grouped.negative));
    reading.append(section("正负并存的制度", grouped.mixed));
    body.append(reading);

    const gradeDetails = make("details", "");
    gradeDetails.append(make("summary", "", "为什么最终是这个等级？"));
    gradeDetails.append(make("p", "prose", summary));
    body.append(gradeDetails);
    if (how) body.append(how);

    body.dataset.aPublic = "done";
    body.dataset.aPublicKey = publicKey;
    body.dataset.secondInstitutionKey = ownershipKey;
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      void patch();
    });
  }

  new MutationObserver(schedule).observe(screen, {childList:true, subtree:true, characterData:true});
  window.addEventListener("hashchange", schedule);
  schedule();
})();
