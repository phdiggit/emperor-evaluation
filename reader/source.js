"use strict";

async function showSource() {
  const query = new URLSearchParams(location.search);
  const ref = query.get("ref") || "";
  const revision = query.get("revision") || "";
  const separator = ref.indexOf("#");
  const path = ref.slice(0, separator);
  const pointer = ref.slice(separator + 1);
  const segments = path.split("/");
  if (!["docs", "config", "archive"].includes(segments[0]) ||
      segments.some(part => !part || part === "." || part === ".." || part.includes("\\")) ||
      !path.endsWith(".json") || separator < 0 || !pointer.startsWith("/") || !/^[a-f0-9]{40,64}$/.test(revision)) {
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
  for (const part of pointer.slice(1).split("/")) {
    const key = part.replace(/~1/g, "/").replace(/~0/g, "~");
    if (!node || typeof node !== "object" || !Object.hasOwn(node, key) ||
        (Array.isArray(node) && !/^(0|[1-9]\d*)$/.test(key))) {
      throw new Error("这个定位在正式文件中不存在。");
    }
    node = node[key];
  }
  document.getElementById("status").textContent = `${path} · ${pointer} · ${revision.slice(0, 10)}`;
  const record = document.getElementById("record");
  record.textContent = JSON.stringify(node, null, 2);
  record.hidden = false;
}

showSource().catch(error => {
  document.getElementById("status").textContent = error.message || "读取正式资料失败。";
});
