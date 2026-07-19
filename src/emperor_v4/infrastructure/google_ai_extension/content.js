(() => {
  "use strict";

  if (window.top !== window || window.__EMPEROR_V4_GOOGLE_AI_BRIDGE__) return;
  const current = new URL(window.location.href);
  if (current.searchParams.get("gai_bridge") !== "1") return;
  window.__EMPEROR_V4_GOOGLE_AI_BRIDGE__ = true;

  const API = "http://127.0.0.1:8765";
  const WORKER_KEY = "emperor_v4_google_ai_worker_id";
  const ATTEMPT_START_KEY = "emperor_v4_google_ai_attempt_start";
  const bridgeSession = current.searchParams.get("gai_session") || "";
  if (!bridgeSession) return;
  const workerId = sessionStorage.getItem(WORKER_KEY) || crypto.randomUUID();
  sessionStorage.setItem(WORKER_KEY, workerId);

  let busy = false;
  let heartbeat = null;
  const POLL_INTERVAL_MS = 10_000;

  const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

  async function post(path, payload) {
    const response = await fetch(`${API}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...payload, bridge_session: bridgeSession }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || `${path}: HTTP ${response.status}`);
    return body;
  }

  function taskUrl(task) {
    const url = new URL("https://www.google.com/search");
    url.searchParams.set("udm", "50");
    url.searchParams.set("gai_bridge", "1");
    url.searchParams.set("gai_session", bridgeSession);
    url.searchParams.set("gai_task", task.task_code);
    url.searchParams.set("q", task.query);
    return url.toString();
  }

  function answerRoot(task) {
    const candidates = [...document.querySelectorAll(".CKgc1d, .Zkbeff, .pCTyYe")]
      .filter((node) => {
        const text = normalizeMarkdownAnswer((node.innerText || "").trim());
        return (
          text.startsWith("DISCOVERY_SUMMARY") &&
          /\nLEAD\s+L1(?:\n|$)/.test(text) &&
          /\nOMISSIONS(?:\n|$)/.test(text) &&
          text.includes("\nsearched_categories:") &&
          text.includes("\nuncovered_categories:") &&
          text.includes("\nstop_reason:") &&
          text.includes("\nomitted_leads:") &&
          text.includes("\nomission_reason:") &&
          !text.includes("您说：") &&
          !text.includes("searched_categories: <") &&
          !text.includes("LEAD <L1...>") &&
          !text.includes("lead_type: <") &&
          !text.includes(task.query)
        );
      });
    if (candidates.length) {
      return candidates.sort((left, right) => (left.innerText || "").length - (right.innerText || "").length)[0];
    }
    const compactCandidates = [...document.querySelectorAll(".CKgc1d, .Zkbeff, .pCTyYe")]
      .filter((node) => {
        const text = (node.innerText || "").trim();
        return (
          /(?:^|\n)LEAD\s+L1\s*[:：]/.test(text) &&
          !text.includes("您说：") &&
          !text.includes("LEAD <L1...") &&
          !text.includes(task.query)
        );
      })
      .sort((left, right) => (left.innerText || "").length - (right.innerText || "").length);
    return compactCandidates[0] || null;
  }

  function pageText() {
    return ((document.querySelector("main") || document.body).innerText || "")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  function answerText(task) {
    const root = answerRoot(task);
    if (!root) return "";
    const text = normalizeMarkdownAnswer(root.innerText || "");
    const structured = text.match(/[\s\S]*\nomission_reason:[^\n]*(?:\n|$)/);
    return (structured ? structured[0] : normalizeCompactAnswer(task, text)).trim();
  }

  function normalizeMarkdownAnswer(text) {
    const fieldNames = new Set([
      "searched_categories", "uncovered_categories", "stop_reason", "lead_type", "lead",
      "period_or_ruler_context", "subject_action", "responsibility", "observable_result",
      "project_relevance", "source_hints", "source_type", "source_work", "volume_or_section",
      "locator_anchor", "locator_confidence", "locator_uncertainty", "source_url",
      "uncertainty", "omitted_leads", "omission_reason",
    ]);
    const rows = [];
    let collectingLeadValues = false;
    for (const rawLine of String(text).replace(/^\s*yaml\s*\n/i, "").split(/\r?\n/)) {
      const heading = rawLine.match(/^\s*#{1,6}\s*(DISCOVERY_SUMMARY|LEAD\s+L\d+|OMISSIONS)\s*$/i);
      if (heading) {
        rows.push(heading[1].replace(/\s+/g, " "));
        collectingLeadValues = false;
        continue;
      }
      const line = rawLine.replace(/^\s*[*-]\s*/, "").trimEnd();
      const field = line.match(/^([a-z_]+):\s*(.*)$/i);
      if (field && fieldNames.has(field[1])) {
        const [, name, value] = field;
        if (name === "lead" && !value.trim()) {
          collectingLeadValues = true;
          continue;
        }
        rows.push(`${name}: ${value}`.trimEnd());
        collectingLeadValues = false;
        continue;
      }
      if (collectingLeadValues && line.trim()) {
        rows.push(`lead: ${line.trim()}`);
        continue;
      }
      rows.push(rawLine.trimEnd());
    }
    return normalizeSourceUrlFields(rows.join("\n").replace(/\n{3,}/g, "\n\n").trim());
  }

  function normalizeSourceUrlFields(text) {
    return text.replace(/^(\s*source_url:\s*)(\S+)\s*$/gm, (line, prefix, value) => {
      if (value === "未核") return line;
      try {
        const url = new URL(value);
        if (
          !/^https?:$/.test(url.protocol) ||
          (!url.pathname.replace(/\/+$/, "") && !url.search && !url.hash)
        ) {
          return `${prefix}未核`;
        }
      } catch {
        return `${prefix}未核`;
      }
      return line;
    });
  }

  function normalizeCompactAnswer(task, text) {
    if (text.startsWith("DISCOVERY_SUMMARY")) return text;
    if (task.purpose_code !== "authority_evaluation_discovery") return text;
    const leadPattern = /(?:^|\n)LEAD\s+L(\d+)\s*[:：]\s*([\s\S]*?)(?=(?:\nLEAD\s+L\d+\s*[:：])|(?:\n(?:遗漏线索|遗漏)\s*(?:为|[:：]))|$)/g;
    const leads = [...text.matchAll(leadPattern)];
    if (!leads.length) return text;
    const summary = text.slice(0, leads[0].index).replace(/\s+/g, " ").trim();
    const omission = text.match(/(?:遗漏线索|遗漏)\s*(?:为|[:：])\s*([^\n]+)/)?.[1]?.trim() || "模型未按字段返回";
    const rows = [
      "DISCOVERY_SUMMARY",
      "searched_categories: 模型未按字段返回",
      `uncovered_categories: ${omission}`,
      "stop_reason: time_or_search_limit",
    ];
    for (const match of leads) {
      const lead = match[2].replace(/\s+/g, " ").trim();
      rows.push(
        `LEAD L${match[1]}`,
        "lead_type: authority_evaluation",
        `lead: ${lead}`,
        "period_or_ruler_context: 未结构化回答待回源",
        "subject_action: 不适用",
        "responsibility: not_applicable",
        "observable_result: 评价线索已定位，待回源",
        "project_relevance: 人才等级复核",
        "uncertainty: 模型未按字段返回，书名卷次与外链待回源核验"
      );
    }
    rows.push(
      "OMISSIONS",
      `omitted_leads: ${omission}`,
      "omission_reason: 模型未按字段返回",
      `model_summary: ${summary || "无"}`
    );
    return rows.join("\n");
  }

  function isBlocked(text) {
    return [
      "检测到异常流量",
      "unusual traffic",
      "captcha",
      "稍后重试",
    ].some((marker) => text.toLowerCase().includes(marker.toLowerCase()));
  }

  function isGenerating() {
    const labels = [...document.querySelectorAll("button")]
      .filter((node) => node.getClientRects().length > 0 && node.getAttribute("aria-hidden") !== "true")
      .map((node) => `${node.getAttribute("aria-label") || ""} ${node.innerText || ""}`);
    return labels.some((value) => /停止|stop generating|停止生成/i.test(value));
  }

  function answerQuality(task, text) {
    const quality = task.quality_requirements;
    const acceptableMentions = quality.acceptable_subject_mentions || [task.subject_name];
    return {
      subjectPassed:
        !quality.require_subject_mention ||
        acceptableMentions.some((value) => text.includes(value)),
      lengthPassed: text.length >= quality.min_answer_characters,
      structurePassed:
        text.startsWith("DISCOVERY_SUMMARY") &&
        /\nOMISSIONS(?:\n|$)/.test(text) &&
        text.includes("\nsearched_categories:") &&
        text.includes("\nuncovered_categories:") &&
        text.includes("\nstop_reason:") &&
        text.includes("\nomitted_leads:") &&
        text.includes("\nomission_reason:"),
      promptFree: !text.includes("您说：") && !text.includes(task.query),
      linksPassed: sourceLinks(task).length >= quality.min_source_links,
    };
  }

  function isGoogleHostname(hostname) {
    return /(^|\.)google\.[a-z.]+$/i.test(hostname) || /(^|\.)googleusercontent\.com$/i.test(hostname);
  }

  function sourceLinks(task) {
    const root = answerRoot(task);
    if (!root) return [];
    const links = [];
    const seen = new Set();
    const omissionNodes = [...root.querySelectorAll("*")]
      .filter((node) => (node.innerText || "").includes("omission_reason:"))
      .sort((left, right) => (left.innerText || "").length - (right.innerText || "").length);
    const answerEnd = omissionNodes[0] || null;
    const add = (candidate, title) => {
      let url;
      try {
        url = new URL(candidate, window.location.href);
      } catch {
        return;
      }
      if (!/^https?:$/.test(url.protocol)) return;
      if (isGoogleHostname(url.hostname)) {
        const target = url.searchParams.get("q") || url.searchParams.get("url");
        if (!target || !/^https?:\/\//.test(target)) return;
        url = new URL(target);
      }
      if (isGoogleHostname(url.hostname)) return;
      const href = url.toString();
      if (seen.has(href)) return;
      seen.add(href);
      links.push({ title: title.trim(), url: href });
    };
    for (const anchor of root.querySelectorAll("a[href]")) {
      if (
        answerEnd &&
        !(anchor.compareDocumentPosition(answerEnd) & Node.DOCUMENT_POSITION_FOLLOWING) &&
        !answerEnd.contains(anchor)
      ) {
        continue;
      }
      add(anchor.href, anchor.innerText || anchor.title || "");
    }
    for (const match of answerText(task).matchAll(/https?:\/\/[^\s<>"”）)]+/g)) {
      add(match[0], "inline_source");
    }
    for (const match of answerText(task).matchAll(
      /(?:^|\n)source_url:\s*((?:[a-z0-9-]+\.)+[a-z]{2,}(?:\/[^\s<>"”）)]*)?)/gi
    )) {
      add(`https://${match[1]}`, "normalized_source_url");
    }
    return links.slice(0, 50);
  }

  async function waitForAnswer(task) {
    const deadline = Date.now() + task.response_timeout_seconds * 1_000;
    // A response can arrive shortly after the requested generation SLA. Keep
    // observing this exact conversation instead of opening a retry conversation.
    const captureGraceDeadline = deadline + 30_000;
    while (Date.now() < captureGraceDeadline) {
      const page = pageText();
      if (isBlocked(page)) throw new Error(`BLOCKED:${page.slice(0, 240)}`);
      const text = answerText(task);
      const quality = answerQuality(task, text);
      if (
        quality.subjectPassed &&
        quality.lengthPassed &&
        quality.structurePassed &&
        quality.promptFree &&
        quality.linksPassed &&
        !isGenerating()
      ) {
        return text;
      }
      await sleep(POLL_INTERVAL_MS);
    }
    const finalText = answerText(task);
    const finalQuality = answerQuality(task, finalText);
    if (
      finalQuality.subjectPassed &&
      finalQuality.lengthPassed &&
      finalQuality.structurePassed &&
      finalQuality.promptFree &&
      finalQuality.linksPassed
    ) {
      return finalText;
    }
    throw new Error(
      `TIMEOUT:${JSON.stringify(finalQuality)}:${finalText.slice(0, 240) || pageText().slice(0, 240)}`
    );
  }

  async function runTask(task) {
    const expected = taskUrl(task);
    if (new URL(window.location.href).searchParams.get("gai_task") !== task.task_code) {
      sessionStorage.setItem(
        ATTEMPT_START_KEY,
        JSON.stringify({
          task_code: task.task_code,
          started_at: new Date().toISOString(),
          started_ms: Date.now(),
        })
      );
      window.location.replace(expected);
      return;
    }
    heartbeat = setInterval(() => {
      post("/heartbeat", { worker_id: workerId, lease_token: task.lease_token }).catch(() => {});
    }, 20_000);
    let storedAttemptStart = null;
    try {
      storedAttemptStart = JSON.parse(sessionStorage.getItem(ATTEMPT_START_KEY) || "null");
    } catch {
      sessionStorage.removeItem(ATTEMPT_START_KEY);
    }
    const matchingAttemptStart =
      storedAttemptStart?.task_code === task.task_code ? storedAttemptStart : null;
    const attemptStartedAt = matchingAttemptStart?.started_at || new Date().toISOString();
    const attemptStartedMs = Number(matchingAttemptStart?.started_ms) || Date.now();
    let outcomeRecorded = false;
    try {
      const answer = await waitForAnswer(task);
      const answerReadyAt = new Date();
      await post("/complete", {
        worker_id: workerId,
        lease_token: task.lease_token,
        result: {
          schema_version: task.output_schema,
          task_code: task.task_code,
          input_fingerprint: task.input_fingerprint,
          answer_text: answer,
          source_links: sourceLinks(task),
          page_title: document.title,
          page_url: window.location.href,
          captured_at: new Date().toISOString(),
          attempt_started_at: attemptStartedAt,
          answer_ready_at: answerReadyAt.toISOString(),
          discovery_duration_seconds: (Date.now() - attemptStartedMs) / 1_000,
        },
      });
      outcomeRecorded = true;
    } catch (error) {
      const message = String(error?.message || error);
      let reason = "transient_page_error";
      if (message.startsWith("BLOCKED:")) {
        reason = /流量|unusual|captcha/i.test(message) ? "captcha" : "transient_page_error";
      } else if (message.startsWith("TIMEOUT:")) {
        reason = "transient_page_error";
      } else if (message.startsWith("Google AI ")) {
        reason = "invalid_contract";
      }
      if (!outcomeRecorded) {
        const failureAnswer = answerText(task);
        await post("/fail", {
          worker_id: workerId,
          lease_token: task.lease_token,
          reason,
          detail: message.slice(0, 500),
          page_url: window.location.href,
          diagnostic_result: {
            schema_version: task.output_schema,
            task_code: task.task_code,
            input_fingerprint: task.input_fingerprint,
            answer_text: failureAnswer,
            source_links: sourceLinks(task),
            page_title: document.title,
            page_url: window.location.href,
            captured_at: new Date().toISOString(),
            attempt_started_at: attemptStartedAt,
            answer_ready_at: new Date().toISOString(),
            discovery_duration_seconds: (Date.now() - attemptStartedMs) / 1_000,
          },
        }).catch(() => {});
      }
    } finally {
      sessionStorage.removeItem(ATTEMPT_START_KEY);
      clearInterval(heartbeat);
      heartbeat = null;
    }
  }

  async function poll() {
    if (busy) return;
    busy = true;
    try {
      const response = await post("/lease", { worker_id: workerId });
      if (response.task) await runTask(response.task);
    } catch {
      // 本地服务未启动时保持安静；下次轮询自动恢复。
    } finally {
      busy = false;
    }
  }

  setInterval(poll, 1_500);
  poll();
})();
