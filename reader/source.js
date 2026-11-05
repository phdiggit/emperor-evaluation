"use strict";

function containsCampaignGroup(node, group) {
  return !!node && typeof node === "object" &&
    (node.campaign_group_ref === group ||
      Object.values(node).some(value => containsCampaignGroup(value, group)));
}

async function showSource() {
  const query = new URLSearchParams(location.search);
  const ref = query.get("ref") || "";
  const revision = query.get("revision") || "";
  const separator = ref.indexOf("#");
  const path = ref.slice(0, separator);
  const pointer = ref.slice(separator + 1);
  const groupPrefix = "campaign_group_ref=";
  const group = pointer.startsWith(groupPrefix) ? pointer.slice(groupPrefix.length) : "";
  const evidence = pointer.match(/^evidence_id=([^/]+)\/evidence_fields\/(.+)$/);
  const segments = path.split("/");
  if (!["docs", "config", "archive"].includes(segments[0]) ||
      segments.some(part => !part || part === "." || part === ".." || part.includes("\\")) ||
      !path.endsWith(".json") || separator < 0 || (!pointer.startsWith("/") && !group && !evidence) || !/^[a-f0-9]{40,64}$/.test(revision)) {
    throw new Error("资料地址无效。");
  }
  const metadata = await fetch("source-revision.json");
  if (!metadata.ok) throw new Error("发布来源未登记。");
  const identity = await metadata.json();
  if (!/^[^/\s]+\/[^/\s]+$/.test(identity.repository)) throw new Error("发布来源未登记。");
  const escaped = segments.map(encodeURIComponent).join("/");
  const repo = identity.repository.split("/").map(encodeURIComponent).join("/");
  const link = document.getElementById("source");
  link.href = `https://github.com/${repo}/blob/${revision}/${escaped}`;
  link.hidden = false;
  const response = await fetch(`https://raw.githubusercontent.com/${repo}/${revision}/${escaped}`);
  if (!response.ok) throw new Error("正式资料暂不可读取，可从完整文件查阅。");
  let node = await response.json();
  let label = pointer;
  if (group) {
    node = (node.records || []).filter(row => row.war_event_id && containsCampaignGroup(row, group));
    if (!node.length) throw new Error("这个战役组在正式文件中没有可定位的登记。");
    label = `${group} · ${node.length} 条战役登记`;
  } else if (evidence) {
    const [, id, field] = evidence;
    const records = (node.records || []).filter(row => row.evidence_id === id);
    const fields = records[0]?.evidence_fields;
    if (records.length !== 1 || !fields || !Object.hasOwn(fields, field)) {
      throw new Error("这个证据字段在正式文件中无法唯一定位。");
    }
    node = fields[field];
    label = `${id} · ${field}`;
  } else {
    for (const part of pointer.slice(1).split("/")) {
      const key = part.replace(/~1/g, "/").replace(/~0/g, "~");
      if (!node || typeof node !== "object" || !Object.hasOwn(node, key) ||
          (Array.isArray(node) && !/^(0|[1-9]\d*)$/.test(key))) {
        throw new Error("这个定位在正式文件中不存在。");
      }
      node = node[key];
    }
  }
  document.getElementById("status").textContent = `${path} · ${label} · ${revision.slice(0, 10)}`;
  const record = document.getElementById("record");
  record.textContent = JSON.stringify(node, null, 2);
  record.hidden = false;
}

showSource().catch(error => {
  document.getElementById("status").textContent = error.message || "读取正式资料失败。";
});
