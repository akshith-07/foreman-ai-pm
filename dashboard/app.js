/* Foreman live dashboard (read-only, multi-project). Polls /api/state every 2 s. */
(() => {
  "use strict";

  const POLL_MS = 2000;
  const ACTIVE_MS = 3 * 60 * 1000; // an agent "glows" for 3 min after acting

  const COLUMNS = [
    { key: "proposed", name: "Proposed" },
    { key: "todo", name: "To do" },
    { key: "in_progress", name: "In progress" },
    { key: "blocked", name: "Blocked" },
    { key: "done", name: "Done" },
  ];

  const PEOPLE = {
    aisha: { name: "Aisha", role: "Backend", color: "#14b8a6" },
    ben: { name: "Ben", role: "Frontend", color: "#3b82f6" },
    chen: { name: "Chen", role: "QA", color: "#ec4899" },
    diego: { name: "Diego", role: "DevOps", color: "#f97316" },
  };

  const AGENTS = {
    "foreman-pm": { short: "PM", role: "Plans & decides", color: "#7c6cff" },
    "foreman-assigner": { short: "AS", role: "Picks owners", color: "#06b6d4" },
    "foreman-tracker": { short: "TR", role: "Tracks progress", color: "#f59e0b" },
    "foreman-reporter": { short: "RP", role: "Writes reports", color: "#22c55e" },
  };

  const PROJECT_COLORS = ["#7c6cff", "#0ea5e9", "#f97316", "#ec4899", "#22c55e", "#eab308", "#14b8a6", "#ef4444"];
  const VERDICT_RANK = { "On track": 0, "At risk": 1, "Off track": 2 };

  const $ = (id) => document.getElementById(id);
  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // View state
  let selected = currentHash();
  let first = true;          // first render after load or after switching view
  let firstEver = true;      // first render since page load (for toasts)
  let lastBoardSig = "";
  let lastPortfolioSig = "";
  let lastReportSig = "";
  let lastTabsSig = "";
  let prevTasks = new Map();
  let prevProjects = new Map();
  let knownProjects = new Set();
  let seenEvents = new Set();
  const colorOf = {};

  function currentHash() {
    const h = decodeURIComponent(location.hash.replace(/^#/, "")).toUpperCase();
    return h && h !== "ALL" ? h : "ALL";
  }

  /* ---------- helpers ---------- */
  function parseAt(at) {
    const [d, t = "00:00"] = String(at).split(" ");
    const [y, m, day] = d.split("-").map(Number);
    const [hh, mm] = t.split(":").map(Number);
    return new Date(y, m - 1, day, hh, mm);
  }

  function ago(at) {
    if (!String(at).includes(" ")) return at;
    const s = Math.max(0, (Date.now() - parseAt(at).getTime()) / 1000);
    if (s < 45) return "just now";
    if (s < 3600) return `${Math.round(s / 60)}m ago`;
    if (s < 86400) return `${Math.round(s / 3600)}h ago`;
    return `${Math.round(s / 86400)}d ago`;
  }

  function avatar(who, cls = "") {
    if (AGENTS[who]) {
      const a = AGENTS[who];
      return `<span class="av agent ${cls}" style="--c:${a.color}" title="${esc(who)}">${a.short}</span>`;
    }
    if (PEOPLE[who]) {
      const p = PEOPLE[who];
      return `<span class="av ${cls}" style="--c:${p.color}" title="${esc(p.name)}">${p.name[0]}</span>`;
    }
    if (!who) return `<span class="av none ${cls}" title="Unassigned">?</span>`;
    return `<span class="av ${cls}" style="--c:#64748b" title="${esc(who)}">${esc(who[0].toUpperCase())}</span>`;
  }

  function displayName(who) {
    if (PEOPLE[who]) return PEOPLE[who].name;
    if (AGENTS[who]) return "@" + who.replace("foreman-", "");
    if (who === "user") return "You";
    return who;
  }

  function describe(text) {
    const t = String(text);
    let m;
    if ((m = t.match(/^Status -> (\w+)\.$/))) return `moved to <b>${esc(COLUMNS.find((c) => c.key === m[1])?.name || m[1])}</b>`;
    if ((m = t.match(/^Blocked: (.*)$/))) return `marked <b>blocked</b>: ${esc(m[1])}`;
    if (t === "Unblocked.") return "unblocked it";
    if (t.startsWith("Approved")) return "<b>approved</b> it";
    if (t.startsWith("Proposed")) return "proposed it";
    if ((m = t.match(/^Project created: (.*?), (.*)\.$/))) return `created project <b>${esc(m[1])}</b> · ${esc(m[2])}`;
    if ((m = t.match(/^Assigned to @(\w+)\.(?: Reason: (.*))?$/))) return `assigned it to <b>${esc(displayName(m[1]))}</b>${m[2] ? ` · ${esc(m[2])}` : ""}`;
    if ((m = t.match(/^Reassigned @(\w+) -> @(\w+)\.(?: Reason: (.*))?$/))) return `reassigned it to <b>${esc(displayName(m[2]))}</b>${m[3] ? ` · ${esc(m[3])}` : ""}`;
    return esc(t);
  }

  const evKey = (e) => `${e.at}|${e.by}|${e.task}|${e.text}`;

  function assignColors(projects) {
    projects.forEach((p, i) => { if (!colorOf[p.key]) colorOf[p.key] = PROJECT_COLORS[Object.keys(colorOf).length % PROJECT_COLORS.length]; });
  }

  function setKpi(id, val, cls) {
    const el = $(id);
    el.textContent = val;
    el.closest(".kpi").classList.remove("alert", "attn");
    if (cls) el.closest(".kpi").classList.add(cls);
  }

  function setRing(pct) {
    $("ring").style.strokeDashoffset = String(113.1 * (1 - pct));
  }

  function setHealth(v) {
    $("health").dataset.v = v;
    $("health-txt").textContent = v;
  }

  function setBanner(verdict, reasons) {
    const banner = $("risk-banner");
    if (reasons.length) {
      banner.hidden = false;
      banner.innerHTML = `<b>${esc(verdict)}</b><ul>${reasons.slice(0, 3).map((r) => `<li>${r}</li>`).join("")}</ul>`;
    } else banner.hidden = true;
  }

  /* ---------- tabs ---------- */
  function renderTabs(s) {
    const sig = JSON.stringify([selected, s.projects.map((p) => [p.key, p.name, p.health.verdict])]);
    if (sig === lastTabsSig) return;
    lastTabsSig = sig;
    const worst = s.projects.reduce((w, p) => (VERDICT_RANK[p.health.verdict] > VERDICT_RANK[w] ? p.health.verdict : w), "On track");
    const tabs = [`<button class="tab ${selected === "ALL" ? "on" : ""}" data-key="ALL" type="button">
        <span class="hdot" data-v="${esc(worst)}"></span>All projects <span class="col-count">${s.projects.length}</span></button>`];
    for (const p of s.projects) {
      const isNew = !firstEver && !knownProjects.has(p.key);
      tabs.push(`<button class="tab ${selected === p.key ? "on" : ""} ${isNew ? "enter" : ""}" data-key="${esc(p.key)}" type="button" style="--pc:${colorOf[p.key]}">
        <span class="hdot" data-v="${esc(p.health.verdict)}"></span><span class="key">${esc(p.key)}</span>${esc(p.name)}</button>`);
    }
    $("tabs").innerHTML = tabs.join("");
  }

  $("tabs").addEventListener("click", (e) => {
    const b = e.target.closest(".tab");
    if (!b) return;
    location.hash = b.dataset.key === "ALL" ? "" : b.dataset.key;
  });
  $("portfolio").addEventListener("click", (e) => {
    const c = e.target.closest(".proj");
    if (c) location.hash = c.dataset.key;
  });
  window.addEventListener("hashchange", () => {
    selected = currentHash();
    first = true;
    lastBoardSig = lastPortfolioSig = lastReportSig = lastTabsSig = "";
    prevTasks = new Map();
    tick();
  });

  /* ---------- portfolio view ---------- */
  function renderPortfolioHeader(s) {
    const ps = s.projects;
    const sum = (f) => ps.reduce((n, p) => n + f(p), 0);
    const done = sum((p) => p.health.done), total = sum((p) => p.health.total);
    const risky = ps.filter((p) => p.health.verdict !== "On track");
    const worst = ps.reduce((w, p) => (VERDICT_RANK[p.health.verdict] > VERDICT_RANK[w] ? p.health.verdict : w), "On track");
    const over = Object.entries(s.people).filter(([, p]) => p.overloaded);

    $("project").textContent = "Portfolio";
    $("release").textContent = `${ps.length} project${ps.length === 1 ? "" : "s"} · ${s.team.length} people`;
    document.title = `${worst} · Foreman · Portfolio`;
    $("k-progress").textContent = `${done}/${total}`;
    $("k-progress-lbl").textContent = "Tasks done";
    setRing(total ? done / total : 0);
    setKpi("k-blocked", sum((p) => p.health.blocked), sum((p) => p.health.blocked) ? "alert" : "");
    setKpi("k-overdue", sum((p) => p.health.overdue), sum((p) => p.health.overdue) ? "alert" : "");
    setKpi("k-approval", sum((p) => p.health.proposed), sum((p) => p.health.proposed) ? "attn" : "");
    setKpi("k-days", risky.length, risky.length ? "attn" : "");
    $("k-days-lbl").textContent = "Projects at risk";
    setHealth(worst);

    const reasons = [];
    for (const p of risky) for (const r of p.health.reasons.slice(0, 2)) reasons.push(`<span class="ptag" style="--pc:${colorOf[p.key]}">${esc(p.key)}</span>${esc(r)}`);
    for (const [m, p] of over) reasons.push(`${esc(displayName(m))} is overloaded: ${p.total} open tasks across ${Object.keys(p.by).length} projects`);
    setBanner(worst === "On track" && over.length ? "Heads up" : worst, reasons);
  }

  function projectCard(p) {
    const h = p.health, c = p.counts, total = Object.values(c).reduce((a, b) => a + b, 0) || 1;
    const seg = (k) => `<i style="width:${(100 * c[k]) / total}%;background:var(--s-${k})"></i>`;
    const cnt = (k, n) => (c[k] ? `<span class="cnt"><i style="background:var(--s-${k})"></i>${c[k]} ${n}</span>` : "");
    const risk = h.reasons[0];
    return `
      <button class="proj" type="button" data-key="${esc(p.key)}" style="--pc:${colorOf[p.key]}">
        <div class="proj-top"><span class="proj-key">${esc(p.key)}</span><span class="pill" data-v="${esc(h.verdict)}"><span class="hdot" data-v="${esc(h.verdict)}"></span>${esc(h.verdict)}</span></div>
        <div class="proj-name">${esc(p.name)}</div>
        <div class="proj-desc">${esc(p.description)}</div>
        <div class="proj-rel"><span><b>${esc(p.release.name)}</b> · due ${esc(p.release.due)}</span><span>${h.days_left}d left</span></div>
        <div class="pbar">${seg("done")}${seg("in_progress")}${seg("todo")}${seg("blocked")}${seg("proposed")}</div>
        <div class="proj-counts">${cnt("done", "done")}${cnt("in_progress", "in progress")}${cnt("todo", "to do")}${cnt("blocked", "blocked")}${cnt("proposed", "proposed")}${total === 1 && !Object.values(c).some(Boolean) ? '<span class="cnt">No tasks yet</span>' : ""}</div>
        <div class="proj-team">${(p.team || []).map((m) => avatar(m)).join("")}</div>
        <div class="proj-risk ${risk ? "bad" : ""}">${risk ? `⛔ ${esc(risk)}` : `${h.done}/${h.total} approved tasks done`}</div>
      </button>`;
  }

  function renderPortfolio(s) {
    const sig = JSON.stringify(s.projects);
    if (sig === lastPortfolioSig) return;
    lastPortfolioSig = sig;
    const next = new Map(s.projects.map((p) => [p.key, JSON.stringify(p)]));
    $("portfolio").innerHTML = s.projects.map(projectCard).join("") ||
      `<div class="col-empty">No projects yet. Ask <code>@foreman-pm</code> to start one.</div>`;
    document.querySelectorAll(".proj").forEach((el) => {
      const k = el.dataset.key;
      if (!first && !prevProjects.has(k)) el.classList.add("enter", "flash");
      else if (!first && prevProjects.get(k) !== next.get(k)) el.classList.add("flash");
      if (el.classList.contains("flash")) setTimeout(() => el.classList.remove("flash"), 1800);
    });
    prevProjects = next;
  }

  /* ---------- project view ---------- */
  function renderProjectHeader(s) {
    const p = s.project, h = p.health;
    $("project").textContent = `${p.name}`;
    $("release").textContent = `${p.key} · ${p.release.name} · due ${p.release.due}${p.description ? " · " + p.description : ""}`;
    document.title = `${h.verdict} · Foreman · ${p.name}`;
    $("k-progress").textContent = `${h.done}/${h.total}`;
    $("k-progress-lbl").textContent = "Tasks done";
    setRing(h.total ? h.done / h.total : 0);
    setKpi("k-blocked", h.blocked, h.blocked ? "alert" : "");
    setKpi("k-overdue", h.overdue, h.overdue ? "alert" : "");
    setKpi("k-approval", h.proposed, h.proposed ? "attn" : "");
    setKpi("k-days", h.days_left, h.days_left <= 2 ? "attn" : "");
    $("k-days-lbl").textContent = "Days to release";
    setHealth(h.verdict);
    setBanner(h.verdict, h.reasons.map(esc));
  }

  function cardHTML(t, today) {
    const late = !["done", "proposed"].includes(t.status) && t.due < today;
    const days = (parseAt(t.due) - parseAt(today)) / 86400000;
    const soon = !late && t.status !== "done" && days <= 1;
    const last = (t.updates || [])[t.updates.length - 1];
    return `
      <article class="card" data-id="${esc(t.id)}" style="--stripe:var(--s-${t.status})">
        <div class="card-top">
          <span class="card-id">${esc(t.id)}</span>
          <span class="epic" title="${esc(t.epic)}">${esc(t.epic)}</span>
        </div>
        <div class="card-title">${esc(t.title)}</div>
        <div class="card-meta">
          <div class="meta-left">
            ${avatar(t.owner)}
            <span class="prio ${esc(t.priority)}"><i></i>${esc(t.priority)}</span>
          </div>
          <span class="due ${late ? "late" : soon ? "soon" : ""}">${late ? "Overdue · " : ""}${esc(t.due.slice(5).replace("-", "/"))}</span>
        </div>
        ${t.blocker ? `<div class="blocker">⛔ ${esc(t.blocker)}</div>` : ""}
        ${last ? `<div class="last"><b>${esc(displayName(last.by))}</b> · ${ago(last.at)}</div>` : ""}
      </article>`;
  }

  function renderBoard(s) {
    const tasks = s.project.tasks;
    const sig = JSON.stringify(tasks);
    if (sig === lastBoardSig) {
      document.querySelectorAll(".card").forEach((el) => {
        const t = tasks.find((x) => x.id === el.dataset.id);
        const last = t && t.updates[t.updates.length - 1];
        const box = el.querySelector(".last");
        if (box && last) box.innerHTML = `<b>${esc(displayName(last.by))}</b> · ${ago(last.at)}`;
      });
      return;
    }
    lastBoardSig = sig;

    const before = new Map();
    document.querySelectorAll(".card").forEach((el) => before.set(el.dataset.id, el.getBoundingClientRect()));

    const today = s.generated.slice(0, 10);
    $("board").innerHTML = COLUMNS.map(({ key, name }) => {
      const ts = tasks.filter((t) => t.status === key);
      return `
        <div class="col ${key}">
          <div class="col-head">
            <div class="col-title"><span class="col-dot" style="background:var(--s-${key})"></span>${name}</div>
            <span class="col-count">${ts.length}</span>
          </div>
          <div class="col-body">
            ${ts.map((t) => cardHTML(t, today)).join("") || `<div class="col-empty">${key === "proposed" ? "Nothing waiting for approval" : "No tasks"}</div>`}
          </div>
        </div>`;
    }).join("");

    const next = new Map(tasks.map((t) => [t.id, JSON.stringify(t)]));
    document.querySelectorAll(".card").forEach((el) => {
      const id = el.dataset.id;
      const old = before.get(id);
      if (!first && !prevTasks.has(id)) {
        el.classList.add("enter", "flash");
      } else if (old) {
        const now = el.getBoundingClientRect();
        const dx = old.left - now.left, dy = old.top - now.top;
        if (Math.abs(dx) > 1 || Math.abs(dy) > 1) {
          el.animate([{ transform: `translate(${dx}px, ${dy}px)`, zIndex: 5 }, { transform: "none", zIndex: 5 }],
            { duration: 650, easing: "cubic-bezier(.2,.8,.2,1)" });
        }
        if (!first && prevTasks.get(id) !== next.get(id)) el.classList.add("flash");
      }
      if (el.classList.contains("flash")) setTimeout(() => el.classList.remove("flash"), 1800);
    });
    prevTasks = next;
  }

  /* ---------- rail ---------- */
  function renderAgents(s) {
    const lastBy = {};
    for (const e of s.activity) if (AGENTS[e.by] && !lastBy[e.by]) lastBy[e.by] = e;
    $("agents").innerHTML = Object.entries(AGENTS).map(([name, a]) => {
      const e = lastBy[name];
      const active = e && String(e.at).includes(" ") && Date.now() - parseAt(e.at).getTime() < ACTIVE_MS;
      return `
        <div class="agent-card ${active ? "active" : ""}" style="--c:${a.color}" title="${esc(name)}">
          ${avatar(name, "lg")}
          <div style="min-width:0">
            <div class="agent-name">@${esc(name.replace("foreman-", ""))}</div>
            <div class="agent-role">${e ? `${esc(e.task)} · ${ago(e.at)}` : esc(a.role)}</div>
          </div>
        </div>`;
    }).join("");
  }

  function renderTeam(s) {
    if (selected === "ALL") {
      $("team-note").textContent = "open tasks, all projects";
      const max = Math.max(4, ...Object.values(s.people).map((p) => p.total));
      $("team").innerHTML = s.team.map((m) => {
        const p = s.people[m], who = PEOPLE[m] || { name: m, role: "" };
        const segs = Object.entries(p.by).map(([k, n]) => `<i style="width:${(100 * n) / max}%;background:${colorOf[k] || "var(--accent)"}" title="${esc(k)}: ${n}"></i>`).join("");
        return `
          <div class="member">
            ${avatar(m, "lg")}
            <div>
              <div class="member-name"><span style="color:var(--text);font-weight:600;font-size:13px">${esc(who.name)}${p.overloaded ? '<span class="over">Overloaded</span>' : ""}</span><span>${Object.keys(p.by).join(" · ") || who.role}</span></div>
              <div class="stack">${segs}</div>
            </div>
            <div class="member-count">${p.total}</div>
          </div>`;
      }).join("") +
        `<div class="legend">${s.projects.map((p) => `<span style="--c:${colorOf[p.key]}">${esc(p.key)}</span>`).join("")}</div>`;
      return;
    }
    const p = s.project;
    $("team-note").textContent = `open tasks in ${p.key}`;
    const counts = {};
    for (const m of p.team) counts[m] = { todo: 0, in_progress: 0, blocked: 0 };
    for (const t of p.tasks) if (counts[t.owner] && counts[t.owner][t.status] !== undefined) counts[t.owner][t.status]++;
    const max = Math.max(3, ...p.team.map((m) => p.load[m] || 0));
    $("team").innerHTML = p.team.map((m) => {
      const c = counts[m], who = PEOPLE[m] || { name: m, role: "" }, all = s.people[m];
      const seg = (k) => `<i style="width:${(100 * c[k]) / max}%;background:var(--s-${k})" title="${c[k]} ${k.replace("_", " ")}"></i>`;
      return `
        <div class="member">
          ${avatar(m, "lg")}
          <div>
            <div class="member-name"><span style="color:var(--text);font-weight:600;font-size:13px">${esc(who.name)}${all && all.overloaded ? '<span class="over">Overloaded</span>' : ""}</span><span>${all ? `${all.total} across all` : esc(who.role)}</span></div>
            <div class="stack">${seg("in_progress")}${seg("todo")}${seg("blocked")}</div>
          </div>
          <div class="member-count">${p.load[m] || 0}</div>
        </div>`;
    }).join("") +
      `<div class="legend"><span style="--c:var(--s-in_progress)">In progress</span><span style="--c:var(--s-todo)">To do</span><span style="--c:var(--s-blocked)">Blocked</span></div>`;
  }

  function renderFeed(s) {
    $("act-count").textContent = s.activity.length ? `${s.activity.length} recent` : "";
    if (!s.activity.length) {
      $("feed").innerHTML = `<li class="empty">No activity yet. Talk to the agents in #project-room.</li>`;
      return;
    }
    $("feed").innerHTML = s.activity.map((e) => {
      const isNew = !firstEver && !seenEvents.has(evKey(e));
      return `
        <li class="ev ${isNew ? "new" : ""}">
          ${avatar(e.by)}
          <div>
            <div class="ev-text"><b>${esc(displayName(e.by))}</b> ${describe(e.text)} <span class="tid" style="color:${colorOf[e.project] || "var(--accent)"}">${esc(e.task)}</span></div>
            <div class="ev-time">${ago(e.at)} · ${esc(e.title)}</div>
          </div>
        </li>`;
    }).join("");
  }

  function renderReport(s) {
    const sig = s.report ? s.report.name + s.report.text.length : "none";
    if (sig === lastReportSig) return;
    lastReportSig = sig;
    if (!s.report) {
      $("report-name").textContent = "";
      $("report").innerHTML = `<div class="empty">No report yet. Ask <code>@foreman-pm send today's standup</code> in the room.</div>`;
      return;
    }
    $("report-name").textContent = s.report.name;
    $("report").innerHTML = markdown(s.report.text);
  }

  function markdown(src) {
    const inline = (t) => esc(t).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/`([^`]+)`/g, "<code>$1</code>");
    const out = [];
    let list = false;
    for (const raw of src.split("\n")) {
      const line = raw.trimEnd();
      const li = line.match(/^\s*[-*] (.*)$/);
      if (!li && list) { out.push("</ul>"); list = false; }
      if (/^#{1,2} /.test(line)) out.push(`<h3>${inline(line.replace(/^#+ /, ""))}</h3>`);
      else if (/^#{3,} /.test(line)) out.push(`<h4>${inline(line.replace(/^#+ /, ""))}</h4>`);
      else if (li) { if (!list) { out.push("<ul>"); list = true; } out.push(`<li>${inline(li[1])}</li>`); }
      else if (line) out.push(`<p>${inline(line)}</p>`);
    }
    if (list) out.push("</ul>");
    return out.join("");
  }

  /* ---------- toasts ---------- */
  function toast(e) {
    const box = $("toasts");
    while (box.children.length >= 3) box.firstChild.remove();
    const el = document.createElement("div");
    el.className = "toast";
    el.innerHTML = `${avatar(e.by)}<div><b>${esc(displayName(e.by))}</b> ${describe(e.text)} <span class="tid" style="color:${colorOf[e.project] || "var(--accent)"};font-weight:600">${esc(e.task)}</span></div>`;
    box.appendChild(el);
    setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 400); }, 4500);
  }

  /* ---------- loop ---------- */
  function render(s) {
    assignColors(s.projects);
    // If the hash names a project that doesn't exist (yet), show the portfolio.
    if (selected !== "ALL" && s.selected === "ALL") selected = "ALL";
    renderTabs(s);

    const isAll = selected === "ALL";
    $("portfolio").hidden = !isAll;
    $("board").hidden = isAll;
    if (isAll) { renderPortfolioHeader(s); renderPortfolio(s); }
    else { renderProjectHeader(s); renderBoard(s); }

    renderAgents(s);
    renderTeam(s);
    renderFeed(s);
    renderReport(s);

    const fresh = s.activity.filter((e) => !seenEvents.has(evKey(e)));
    if (!firstEver) fresh.slice(0, 3).reverse().forEach(toast);
    fresh.forEach((e) => seenEvents.add(evKey(e)));
    s.projects.forEach((p) => knownProjects.add(p.key));
    first = false;
    firstEver = false;
  }

  let inflight = false;
  async function tick() {
    if (inflight) return;
    inflight = true;
    try {
      const r = await fetch(`/api/state?project=${encodeURIComponent(selected)}`, { cache: "no-store" });
      if (!r.ok) throw new Error(String(r.status));
      render(await r.json());
      $("live").classList.remove("off");
      $("live-txt").textContent = "Live";
    } catch {
      $("live").classList.add("off");
      $("live-txt").textContent = "Reconnecting";
    } finally {
      inflight = false;
    }
  }

  /* ---------- theme toggle ---------- */
  function applyTheme(t) {
    if (t) document.documentElement.dataset.theme = t;
    else delete document.documentElement.dataset.theme;
  }
  try { applyTheme(localStorage.getItem("foreman-theme")); } catch {}
  $("theme").addEventListener("click", () => {
    const cur = document.documentElement.dataset.theme ||
      (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = cur === "dark" ? "light" : "dark";
    applyTheme(next);
    try { localStorage.setItem("foreman-theme", next); } catch {}
  });

  tick();
  setInterval(tick, POLL_MS);
})();
