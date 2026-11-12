"use strict";

(() => {
  function isMachineSource(ref) {
    try {
      const path = decodeURIComponent(new URL(ref, "https://reader.invalid/").pathname);
      return /\.(?:jsonl?|ndjson)(?:$|[:/])/i.test(path);
    } catch {
      return /\.(?:jsonl?|ndjson)(?:$|[?#:/])/i.test(String(ref));
    }
  }

  function externalSource(ref) {
    try {
      const url = new URL(ref);
      if (!["http:", "https:"].includes(url.protocol) || isMachineSource(ref)) return "";
      if (/(?:^|\.)(?:github\.com|githubusercontent\.com|github\.io)$/.test(url.hostname)) return "";
      return ref;
    } catch {
      return "";
    }
  }

  function citationTitle(ref, label) {
    const title = metadataLabel(label).replace(/\s*[↗→]$/, "");
    if (title.startsWith("《")) return title;
    const work = projectSourceTitle(ref);
    return work.startsWith("《") ? work : "";
  }

  function metadataLabel(value) {
    const text = String(value ?? "").trim()
      .replace(/^(?:固定修订|修订号)\s*\d+[，、]\s*/, "")
      .replace(/\b[PL]\d{4}(?:[—–-][PL]\d{4})?(?:[、，,]\s*)?/g, "")
      .trim();
    if (isMachineSource(text) || /^(?:docs|config|archive)\//.test(text) ||
        /^(?:volume-\d+|[LP]\d{3,}|(?:SRC|WAR|RULER|MIL|[CM]\dP)-[\w-]+)(?:$|[.:#\s])/i.test(text) ||
        /^(?:[A-Z][A-Z0-9]+[_-])+[A-Z0-9-]+$/.test(text) ||
        /^[a-z][a-z_0-9]*(?:\s*\/\s*(?:[a-z][a-z_0-9]*|\d+))*$/.test(text)) return "";
    return text;
  }

  function projectSourceTitle(ref) {
    const path = String(ref ?? "").split("#", 1)[0];
    const volume = /^docs\/史料通读产物\/.+\/([^/]+)\/volume-0*(\d+)/.exec(path);
    if (volume) return "《" + volume[1] + "》卷" + volume[2];
    const title = path.split("/").pop().replace(/^\d+-|\.(?:jsonl?|md)$|(?:非战役)?通读总结/g, "");
    return /[\u3400-\u9fff]/.test(title) ? metadataLabel(title) : "";
  }

  function personRoute(ref) {
    const match = /^docs\/评分结算\/(.+?)\.json#ruler_id=([^#&/]+)$/.exec(ref);
    if (!match) return null;
    const [, path, id] = match;
    const person = encodeURIComponent(id);
    if (path.startsWith("人物画像/")) {
      const axis = /^人物画像\/([CM]\d)\//.exec(path)?.[1];
      return {id, route:`#person/${person}/profile${axis ? "/" + axis : ""}`};
    }
    if (path.startsWith("历史影响/")) return {id, route:`#person/${person}/impact`};
    const major = /^净收益\/第([一二三四])项/.exec(path)?.[1];
    if (!major) return null;
    const section = {一:"first", 二:"second", 三:"third", 四:"fourth"}[major];
    const focus = section === "third" ? {
      军事体系有效性:"system", 军事成本收益比:"cost",
    }[path.split("/")[2]] : "";
    return {id, route:`#net/${person}/${section}${focus ? `/${focus}` : ""}`};
  }

  globalThis.ReaderSourceLinks = Object.freeze({isMachineSource, externalSource, citationTitle, metadataLabel, projectSourceTitle, personRoute});
})();
