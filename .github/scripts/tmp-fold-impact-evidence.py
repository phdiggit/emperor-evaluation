from pathlib import Path

js_path = Path('reader/person-readability.js')
css_path = Path('reader/readability.css')
js = js_path.read_text(encoding='utf-8')
css = css_path.read_text(encoding='utf-8')

anchor = '  function foldNetLedger() {'
block = r'''  function foldHistoricalImpact() {
    const evidence = document.querySelector("#history-evidence");
    if (!evidence || evidence.dataset.impactFolded === "done") return;

    const foldSection = (section, label, badgeText = "") => {
      if (!section || section.tagName === "DETAILS") return section;
      const wrapper = document.createElement("details");
      wrapper.id = section.id;
      wrapper.className = `${section.className} impact-evidence-fold`.trim();
      const summary = document.createElement("summary");
      summary.innerHTML = `<span>${esc(label)}</span>${badgeText ? `<span class="badge">${esc(badgeText)}</span>` : ""}`;
      wrapper.append(summary);

      const heading = section.querySelector(":scope > h3, :scope > .impact-dimension-head");
      if (heading) heading.remove();
      wrapper.append(...Array.from(section.childNodes));
      section.replaceWith(wrapper);
      return wrapper;
    };

    const core = evidence.querySelector(":scope > .impact-core-chains");
    foldSection(core, "核心历史主链");

    for (const [id, label] of [
      ["history-dimension-scope", "影响范围"],
      ["history-dimension-depth_duration", "深度与持续"],
      ["history-dimension-personal_causality", "个人因果"],
      ["history-dimension-paradigm", "政治范式"],
      ["history-judgment-boundary", "判断边界"],
    ]) {
      const section = document.getElementById(id);
      const badge = section?.querySelector(":scope > .impact-dimension-head .badge")?.textContent.trim() || "";
      foldSection(section, label, badge);
    }

    evidence.dataset.impactFolded = "done";
  }

  function openHistoricalImpactTarget(event) {
    const link = event.target.closest('[data-section^="history-dimension-"], [data-section="history-judgment-boundary"]');
    if (!link) return;
    const target = document.getElementById(link.dataset.section);
    if (target?.tagName === "DETAILS") target.open = true;
  }

'''
if block.strip() not in js:
    if anchor not in js:
        raise SystemExit('foldNetLedger anchor not found')
    js = js.replace(anchor, block + anchor, 1)

old = '    enhanceImpact(record);\n    normalizeEvidenceCardHeadings();'
new = '    enhanceImpact(record);\n    foldHistoricalImpact();\n    normalizeEvidenceCardHeadings();'
if new not in js:
    if old not in js:
        raise SystemExit('enhance call anchor not found')
    js = js.replace(old, new, 1)

listener_anchor = '  new MutationObserver(enhance).observe(screen, {childList: true, subtree: true});'
listener = '  screen.addEventListener("click", openHistoricalImpactTarget, true);\n'
if listener not in js:
    if listener_anchor not in js:
        raise SystemExit('observer anchor not found')
    js = js.replace(listener_anchor, listener + listener_anchor, 1)

css_block = r'''

/* Keep all three evidence families collapsed by default. */
#history-evidence > .impact-evidence-fold {
  margin-top: 0;
  padding: 14px 0;
  border-top: 1px solid var(--line);
}

#history-evidence > .impact-evidence-fold > summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 16px;
  font-weight: 500;
}

#history-evidence > .impact-evidence-fold > summary .badge {
  margin-right: 18px;
  color: var(--red);
  font: 17px/1.35 Georgia, serif;
}

#history-evidence > .impact-evidence-fold[open] > summary {
  margin-bottom: 8px;
}

#history-evidence > .impact-evidence-fold > .subline:first-of-type {
  margin-top: 4px;
}
'''
marker = '/* Keep all three evidence families collapsed by default. */'
if marker not in css:
    css += css_block

js_path.write_text(js, encoding='utf-8', newline='\n')
css_path.write_text(css, encoding='utf-8', newline='\n')
