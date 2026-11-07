/* Foreman live dashboard (read-only). Polls /api/state every 2 s. */
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

  const $ = (id) => document.getElementById(id);
  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  let first = true;
  let lastTasksSig = "";
  let lastReportSig = "";
  let prevTasks = new Map();
  let seenEvents = new Set();
  let latest = null;

  /* ---------- helpers ---------- */
  function parseAt(at) {
    // "YYYY-MM-DD HH:MM" (local) or "YYYY-MM-DD"
    const [d, t = "00:00"] = String(at).split(" ");
    const [y, m, day] = d.split("-").map(Number);
    const [hh, mm] = t.split(":").map(Number);
    return new Date(y, m - 1, day, hh, mm);
  }

  function ago(at) {
    if (!String(at).includes(" ")) return at; // date-only seed entries
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

  // Turn raw audit text into a readable phrase.
  function describe(text) {
    const t = String(text);
    let m;
    if ((m = t.match(/^Status -> (\w+)\.$/))) return `moved to <b>${esc(COLUMNS.find((c) => c.key === m[1])?.name || m[1])}</b>`;
    if ((m = t.match(/^Blocked: (.*)$/))) return `marked <b>blocked</b>: ${esc(m[1])}`;
    if (t === "Unblocked.") return "unblocked it";
    if (t.startsWith("Approved")) return "<b>approved</b> it";
    if (t.startsWith("Proposed")) return "proposed it";
    if ((m = t.match(/^Assigned to @(\w+)\.(?: Reason: (.*))?$/))) return `assigned it to <b>${esc(displayName(m[1]))}</b>${m[2] ? ` · ${esc(m[2])}` : ""}`;
    if ((m = t.match(/^Reassigned @(\w+) -> @(\w+)\.(?: Reason: (.*))?$/))) return `reassigned it to <b>${esc(displayName(m[2]))}</b>${m[3] ? ` · ${esc(m[3])}` : ""}`;
    return esc(t);
  }

  const evKey = (e) => `${e.at}|${e.by}|${e.task}|${e.text}`;

  /* ---------- header ---------- */
  function renderHeader(s) {
    const h = s.health;
    const proposed = s.tasks.filter((t) => t.status === "proposed").length;
    $("project").textContent = s.project;
    $("release").textContent = `Release ${s.release.name} · due ${s.release.due}`;
    document.title = `${h.verdict} · Foreman · ${s.project}`;

    $("k-progress").textContent = `${h.done}/${h.total}`;
    const pct = h.total ? h.done / h.total : 0;
    $("ring").style.strokeDashoffset = String(113.1 * (1 - pct));
    setKpi("k-blocked", h.blocked, h.blocked ? "alert" : "");
    setKpi("k-overdue", h.overdue, h.overdue ? "alert" : "");
    setKpi("k-approval", proposed, proposed ? "attn" : "");
    setKpi("k-days", h.days_left, h.days_left <= 2 ? "attn" : "");

    const hb = $("health");
    hb.dataset.v = h.verdict;
    $("health-txt").textContent = h.verdict;

    const banner = $("risk-banner");
    if (h.reasons.length) {
      banner.hidden = false;
      banner.innerHTML = `<b>${esc(h.verdict)}</b><ul>${h.reasons.slice(0, 3).map((r) => `<li>${esc(r)}</li>`).join("")}</ul>`;
    } else {
      banner.hidden = true;
    }
  }

  function setKpi(id, val, cls) {
    const el = $(id);
    el.textContent = val;
    el.closest(".kpi").classList.remove("alert", "attn");
    if (cls) el.closest(".kpi").classList.add(cls);
  }

  /* ---------- board (with FLIP animation) ---------- */
  function cardHTML(t, today) {
    const late = !["done", "proposed"].includes(t.status) && t.due < today;
    const days = (parseAt(t.due) - parseAt(today)) / 86400000;
    const soon = !late && t.status !== "done" && days <= 1;
    const last = (t.updates || [])[t.updates.length - 1];
    const stripe = `var(--s-${t.status})`;
    return `
      <article class="card" data-id="${esc(t.id)}" style="--stripe:${stripe}">
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
    const sig = JSON.stringify(s.tasks);
    if (sig === lastTasksSig) {
      // Only refresh the relative times.
      document.querySelectorAll(".card").forEach((el) => {
        const t = s.tasks.find((x) => x.id === el.dataset.id);
        const last = t && t.updates[t.updates.length - 1];
        const box = el.querySelector(".last");
        if (box && last) box.innerHTML = `<b>${esc(displayName(last.by))}</b> · ${ago(last.at)}`;
      });
      return;
    }
    lastTasksSig = sig;

    // FLIP step 1: remember where every card is.
    const before = new Map();
    document.querySelectorAll(".card").forEach((el) => before.set(el.dataset.id, el.getBoundingClientRect()));

    const today = s.generated.slice(0, 10);
    $("board").innerHTML = COLUMNS.map(({ key, name }) => {
      const tasks = s.tasks.filter((t) => t.status === key);
      return `
        <div class="col ${key}">
          <div class="col-head">
            <div class="col-title"><span class="col-dot" style="background:var(--s-${key})"></span>${name}</div>
            <span class="col-count">${tasks.length}</span>
          </div>
          <div class="col-body">
            ${tasks.map((t) => cardHTML(t, today)).join("") || `<div class="col-empty">${key === "proposed" ? "Nothing waiting for approval" : "No tasks"}</div>`}
          </div>
        </div>`;
    }).join("");

    // FLIP step 2: animate from the old spot to the new one.
    const next = new Map(s.tasks.map((t) => [t.id, JSON.stringify(t)]));
    document.querySelectorAll(".card").forEach((el) => {
      const id = el.dataset.id;
      const old = before.get(id);
      if (!first && !prevTasks.has(id)) {
        el.classList.add("enter", "flash");
      } else if (old) {
        const now = el.getBoundingClientRect();
        const dx = old.left - now.left;
        const dy = old.top - now.top;
        if (Math.abs(dx) > 1 || Math.abs(dy) > 1) {
          el.animate(
            [{ transform: `translate(${dx}px, ${dy}px)`, zIndex: 5 }, { transform: "none", zIndex: 5 }],
            { duration: 650, easing: "cubic-bezier(.2,.8,.2,1)" }
          );
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
    const counts = {};
    for (const m of s.team) counts[m] = { todo: 0, in_progress: 0, blocked: 0 };
    for (const t of s.tasks) if (counts[t.owner] && counts[t.owner][t.status] !== undefined) counts[t.owner][t.status]++;
    const max = Math.max(3, ...s.team.map((m) => s.load[m] || 0));
    $("team").innerHTML =
      s.team.map((m) => {
        const c = counts[m];
        const p = PEOPLE[m] || { name: m, role: "" };
        const seg = (k) => `<i style="width:${(100 * c[k]) / max}%;background:var(--s-${k})" title="${c[k]} ${k.replace("_", " ")}"></i>`;
        return `
          <div class="member">
            ${avatar(m, "lg")}
            <div>
              <div class="member-name">${esc(p.name)} <span>${esc(p.role)}</span></div>
              <div class="stack">${seg("in_progress")}${seg("todo")}${seg("blocked")}</div>
            </div>
            <div class="member-count">${s.load[m] || 0}</div>
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
      const isNew = !first && !seenEvents.has(evKey(e));
      return `
        <li class="ev ${isNew ? "new" : ""}">
          ${avatar(e.by)}
          <div>
            <div class="ev-text"><b>${esc(displayName(e.by))}</b> ${describe(e.text)} <span class="tid">${esc(e.task)}</span></div>
            <div class="ev-time">${ago(e.at)} · ${esc(e.title)}</div>
          </div>
        </li>`;
    }).join("");
  }

  function renderReport(s) {
    const sig = s.report ? s.report.name + s.report.text.length : "";
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

  // Tiny, safe Markdown subset: headings, bullets, bold, paragraphs.
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
    el.innerHTML = `${avatar(e.by)}<div><b>${esc(displayName(e.by))}</b> ${describe(e.text)} <span class="tid" style="color:var(--accent);font-weight:600">${esc(e.task)}</span></div>`;
    box.appendChild(el);
    setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 400); }, 4500);
  }

  /* ---------- loop ---------- */
  function render(s) {
    latest = s;
    renderHeader(s);
    renderBoard(s);
    renderAgents(s);
    renderTeam(s);
    renderFeed(s);
    renderReport(s);

    const fresh = s.activity.filter((e) => !seenEvents.has(evKey(e)));
    if (!first) fresh.slice(0, 3).reverse().forEach(toast);
    fresh.forEach((e) => seenEvents.add(evKey(e)));
    first = false;
  }

  async function tick() {
    try {
      const r = await fetch("/api/state", { cache: "no-store" });
      if (!r.ok) throw new Error(String(r.status));
      render(await r.json());
      $("live").classList.remove("off");
      $("live-txt").textContent = "Live";
    } catch {
      $("live").classList.add("off");
      $("live-txt").textContent = "Reconnecting";
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
