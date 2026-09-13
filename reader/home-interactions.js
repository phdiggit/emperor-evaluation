"use strict";

(() => {
  const sectionByCell = {
    1: "person-outcome",
    2: "person-capability",
    3: "person-impact",
  };
  const interactiveSelector = "button,a,input,select,textarea,summary,label,[role=button]";

  function recordForRow(row) {
    const id = row.querySelector("[data-person]")?.dataset.person;
    return id ? byId.get(id) : null;
  }

  function scrollWhenReady(section, attempt = 0) {
    if (!section) return;
    requestAnimationFrame(() => {
      const target = document.getElementById(section);
      if (target) {
        target.scrollIntoView({behavior: "smooth", block: "start"});
        return;
      }
      if (attempt < 80) setTimeout(() => scrollWhenReady(section, attempt + 1), 50);
    });
  }

  function openPersonSection(id, section) {
    const hash = "#person/" + encodeURIComponent(id);
    if (!section) {
      go(hash);
      return;
    }
    if (location.hash === hash) {
      route();
      scrollWhenReady(section);
      return;
    }

    const afterRoute = () => {
      window.removeEventListener("hashchange", afterRoute);
      scrollWhenReady(section);
    };
    window.addEventListener("hashchange", afterRoute);
    location.hash = hash;
  }

  function applyPolityFilter(polity) {
    state.polity = polity;
    const select = document.getElementById("polity");
    if (select) select.value = polity;
    renderRows();
  }

  function applyImpactFilter(grade) {
    state.grade = grade;
    const select = document.getElementById("impact-filter");
    if (select) select.value = grade;
    renderRows();
  }

  function enhanceHomeRows() {
    const container = document.getElementById("rows");
    if (!container) return;

    for (const row of container.querySelectorAll("tbody tr")) {
      const record = recordForRow(row);
      if (!record) continue;

      row.classList.add("home-click-row");
      row.dataset.homePerson = record.ruler_id;
      const cells = row.cells || row.querySelectorAll("td");

      for (const [index, section] of Object.entries(sectionByCell)) {
        const cell = cells[Number(index)];
        if (!cell) continue;
        cell.classList.add("home-jump-cell");
        cell.dataset.homeSection = section;
        cell.tabIndex = 0;
        cell.setAttribute("role", "link");
        const label = section === "person-outcome" ? "净收益" : section === "person-capability" ? "人物画像" : "历史影响";
        cell.setAttribute("aria-label", `查看${record.ruler_name}的${label}`);
      }

      const identityCell = cells[0];
      identityCell?.classList.add("home-person-cell");
      const meta = identityCell?.querySelector("small");
      if (meta && !meta.querySelector("[data-home-polity]")) {
        meta.textContent = "";
        const polity = document.createElement("button");
        polity.type = "button";
        polity.className = "inline-table-filter";
        polity.dataset.homePolity = record.polity;
        polity.textContent = record.polity;
        polity.title = `只看${record.polity}`;
        meta.append(polity, document.createTextNode(` · ${record.actual_power_window}`));
      }

      const grade = cells[3]?.querySelector(".impact-grade");
      if (grade && !grade.hasAttribute("data-home-grade")) {
        grade.dataset.homeGrade = record.impact.public_grade;
        grade.setAttribute("role", "button");
        grade.tabIndex = 0;
        grade.title = `只看历史影响 ${record.impact.public_grade}`;
      }
    }
  }

  // #screen survives route changes, while #rows is destroyed and recreated whenever
  // the user leaves and returns to the overview. Observe the stable root so every
  // newly rendered overview table is enhanced again.
  new MutationObserver(enhanceHomeRows).observe(screen, {childList: true, subtree: true});
  enhanceHomeRows();

  screen.addEventListener("click", event => {
    const polity = event.target.closest("[data-home-polity]");
    if (polity) {
      event.preventDefault();
      applyPolityFilter(polity.dataset.homePolity);
      return;
    }

    const grade = event.target.closest("[data-home-grade]");
    if (grade) {
      event.preventDefault();
      applyImpactFilter(grade.dataset.homeGrade);
      return;
    }

    if (event.target.closest(interactiveSelector)) return;
    const row = event.target.closest("tr[data-home-person]");
    if (!row) return;
    const cell = event.target.closest("td");
    openPersonSection(row.dataset.homePerson, cell?.dataset.homeSection || "");
  });

  screen.addEventListener("keydown", event => {
    if (event.key !== "Enter" && event.key !== " ") return;

    const grade = event.target.closest("[data-home-grade]");
    if (grade) {
      event.preventDefault();
      applyImpactFilter(grade.dataset.homeGrade);
      return;
    }

    const cell = event.target.closest("td[data-home-section]");
    const row = cell?.closest("tr[data-home-person]");
    if (!cell || !row) return;
    event.preventDefault();
    openPersonSection(row.dataset.homePerson, cell.dataset.homeSection);
  });
})();
