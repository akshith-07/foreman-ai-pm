#!/usr/bin/env python3
"""Foreman board CLI: multi-project.

Each project lives in projects/<key>.json and has a short KEY (like Jira),
so task ids look like INV-4 or WEB-2. Commands that take a task id work out
the project from the id. Other commands use --project/-p KEY, or the active
project (set with `use`).

Agents call this instead of hand-editing files, so every board stays valid
and every change leaves an audit trail.

Projects:
  board.py projects                       list projects with health
  board.py new-project --name "Acme Mobile App" --key ACME --release v1.0 --due 2026-12-01 [--team aisha,ben] [--description "..."] --by foreman-pm
  board.py use ACME                       set the active project
  board.py portfolio                      all projects + cross-project workload

Tasks (-p KEY optional when the id says it, e.g. INV-4):
  board.py show [-p KEY]
  board.py add -p KEY --title "..." --epic Auth --priority high --due 2026-11-13 [--owner aisha] --by foreman-pm
  board.py assign INV-4 ben --reason "React + login flows" --by foreman-assigner
  board.py approve INV-4 INV-5 --by <human>        (or: approve -p KEY --all-proposed)
  board.py cancel INV-8 --by <human>               (proposed tasks only)
  board.py status INV-4 in_progress|done|todo --by <who>
  board.py block INV-4 "callback URL not configured" --by <who>
  board.py unblock INV-4 --by <who>
  board.py note INV-4 "text" --by <who>

Reports:
  board.py load                           open tasks per person, across projects
  board.py report [-p KEY]                project status report with health
  board.py standup [-p KEY]               daily standup data (last 24h)
  board.py weekly [-p KEY]                weekly report data (last 7 days)
  board.py save-report daily|weekly [-p KEY] --summary "..." --by foreman-reporter
  board.py save-report portfolio --summary "..." --by foreman-reporter

Maintenance:
  board.py validate                       check every project
  board.py reset                          restore the demo seed, clear reports
"""
import argparse
import datetime as dt
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "projects"
SEED = ROOT / "seed" / "projects"
ACTIVE = PROJECTS / ".active"
REPORTS = ROOT / "reports"

STATUSES = ["proposed", "todo", "in_progress", "blocked", "done"]
OPEN = {"todo", "in_progress", "blocked"}
PRIORITIES = ["high", "medium", "low"]
TEAM = ["aisha", "ben", "chen", "diego"]
OVERLOAD = 4  # open tasks across all projects before someone counts as overloaded
KEY_RE = re.compile(r"^[A-Z][A-Z0-9]{1,5}$")


# ---------- time helpers ----------
def now() -> dt.datetime:
    return dt.datetime.now().replace(second=0, microsecond=0)


def today() -> str:
    return dt.date.today().isoformat()


def stamp() -> str:
    return now().strftime("%Y-%m-%d %H:%M")


def parse_at(s: str) -> dt.datetime:
    try:
        return dt.datetime.strptime(s, "%Y-%m-%d %H:%M")
    except ValueError:
        return dt.datetime.strptime(s[:10], "%Y-%m-%d")


# ---------- storage ----------
def ensure() -> None:
    PROJECTS.mkdir(exist_ok=True)
    if not any(PROJECTS.glob("*.json")):
        seed()


def seed() -> None:
    PROJECTS.mkdir(exist_ok=True)
    for f in PROJECTS.glob("*.json"):
        f.unlink()
    for f in SEED.glob("*.json"):
        shutil.copy(f, PROJECTS / f.name)
    keys_ = keys()
    ACTIVE.write_text((keys_[0] if keys_ else "") + "\n")


def path_for(key: str) -> Path:
    return PROJECTS / f"{key.lower()}.json"


def keys() -> list:
    out = []
    for f in sorted(PROJECTS.glob("*.json")):
        try:
            out.append(json.loads(f.read_text())["key"])
        except Exception:
            continue
    return out


def load(key: str) -> dict:
    p = path_for(key)
    if not p.exists():
        sys.exit(f"No project {key}. Run `board.py projects` to list projects.")
    return json.loads(p.read_text())


def load_all() -> list:
    ensure()
    return [load(k) for k in keys()]


def save(board: dict) -> None:
    errors = check(board)
    if errors:
        sys.exit("Refusing to save invalid board:\n  " + "\n  ".join(errors))
    p = path_for(board["key"])
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(board, indent=2) + "\n")
    tmp.replace(p)  # atomic, so the dashboard never reads half a file


def active_key() -> str:
    ensure()
    ks = keys()
    try:
        k = ACTIVE.read_text().strip().upper()
        if k in ks:
            return k
    except OSError:
        pass
    return ks[0]


def resolve(a, ids=()) -> dict:
    """Pick the project: explicit -p, else the task id prefix, else active."""
    ensure()
    if getattr(a, "project", None):
        return load(a.project.upper())
    for i in ids:
        prefix = i.upper().rsplit("-", 1)[0]
        if prefix in keys():
            return load(prefix)
    return load(active_key())


def check(board: dict) -> list:
    errors, seen = [], set()
    key = board.get("key", "?")
    for t in board.get("tasks", []):
        tid = t.get("id", "?")
        if not tid.startswith(key + "-"):
            errors.append(f"{tid}: id must start with {key}-")
        if tid in seen:
            errors.append(f"{tid}: duplicate id")
        seen.add(tid)
        if t.get("status") not in STATUSES:
            errors.append(f"{tid}: bad status {t.get('status')!r}")
        if t.get("priority") not in PRIORITIES:
            errors.append(f"{tid}: bad priority {t.get('priority')!r}")
        if t.get("owner") not in TEAM + [None]:
            errors.append(f"{tid}: unknown owner {t.get('owner')!r}")
        if t.get("status") == "blocked" and not t.get("blocker"):
            errors.append(f"{tid}: blocked but no blocker reason")
        if t.get("status") != "proposed" and not t.get("owner"):
            errors.append(f"{tid}: approved tasks need an owner")
    return errors


def find(board: dict, tid: str) -> dict:
    tid = tid.upper()
    for t in board["tasks"]:
        if t["id"] == tid:
            return t
    sys.exit(f"No task {tid} in {board['key']}. Run `board.py show -p {board['key']}`.")


def log(task: dict, by: str, text: str) -> None:
    task.setdefault("updates", []).append({"at": stamp(), "by": by, "text": text})


# ---------- derived views (shared with the dashboard) ----------
def loads(board) -> dict:
    counts = {m: 0 for m in TEAM}
    for t in board["tasks"]:
        if t["status"] in OPEN and t["owner"] in counts:
            counts[t["owner"]] += 1
    return counts


def people(boards) -> dict:
    """Open tasks per person across all projects, with a per-project breakdown."""
    out = {m: {"total": 0, "by": {}} for m in TEAM}
    for b in boards:
        for m, n in loads(b).items():
            if n:
                out[m]["by"][b["key"]] = n
                out[m]["total"] += n
    for m in out:
        out[m]["overloaded"] = out[m]["total"] >= OVERLOAD
    return out


def overdue(board) -> list:
    return [t for t in board["tasks"] if t["status"] in OPEN and t["due"] < today()]


def health(board) -> dict:
    """Release health: one rule used by the CLI, the agents and the dashboard."""
    tasks = [t for t in board["tasks"] if t["status"] != "proposed"]
    done = sum(t["status"] == "done" for t in tasks)
    blocked = [t for t in tasks if t["status"] == "blocked"]
    late = overdue(board)
    days_left = (dt.date.fromisoformat(board["release"]["due"]) - dt.date.today()).days
    reasons = []
    if days_left < 0 and done < len(tasks):
        verdict = "Off track"
        reasons.append("release date has passed with work still open")
    elif any(t["priority"] == "high" for t in late) or len(blocked) >= 3:
        verdict = "Off track"
    elif blocked or late:
        verdict = "At risk"
    else:
        verdict = "On track"
    reasons += [f"{t['id']} blocked: {t['blocker']}" for t in blocked]
    reasons += [f"{t['id']} overdue (due {t['due']})" for t in late]
    return {
        "verdict": verdict, "reasons": reasons, "done": done, "total": len(tasks),
        "days_left": days_left, "blocked": len(blocked), "overdue": len(late),
        "proposed": sum(t["status"] == "proposed" for t in board["tasks"]),
    }


def summary(board) -> dict:
    counts = {s: 0 for s in STATUSES}
    for t in board["tasks"]:
        counts[t["status"]] += 1
    return {
        "key": board["key"], "name": board["name"], "description": board.get("description", ""),
        "release": board["release"], "team": board.get("team", TEAM),
        "created": board.get("created"), "health": health(board), "counts": counts,
    }


def activity(boards, since: dt.datetime | None = None) -> list:
    items = []
    for b in boards:
        for t in b["tasks"]:
            for i, u in enumerate(t.get("updates", [])):
                at = parse_at(u["at"])
                if since is None or at >= since:
                    items.append({**u, "project": b["key"], "task": t["id"], "title": t["title"], "_k": (at, i)})
        for i, u in enumerate(b.get("log", [])):  # project-level events (e.g. created)
            at = parse_at(u["at"])
            if since is None or at >= since:
                items.append({**u, "project": b["key"], "task": b["key"], "title": b["name"], "_k": (at, i)})
    items.sort(key=lambda x: x["_k"], reverse=True)
    for x in items:
        x.pop("_k")
    return items


def latest_report(key: str | None = None) -> dict | None:
    if not REPORTS.exists():
        return None
    files = list(REPORTS.glob("*.md"))
    if key:
        files = [f for f in files if f"-{key.lower()}-" in f.name]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    return {"name": files[0].name, "text": files[0].read_text()}


# ---------- formatting ----------
def owner_str(o):
    return ("@" + o) if o else "unassigned"


def line(t: dict) -> str:
    s = f"- **{t['id']}** {t['title']} — {owner_str(t['owner'])} · {t['priority']} · due {t['due']}"
    if t.get("blocker"):
        s += f"\n  - BLOCKED: {t['blocker']}"
    return s


def title(board) -> str:
    return f"{board['name']} ({board['key']}) {board['release']['name']}"


def report_text(board) -> str:
    tasks, rel, h = board["tasks"], board["release"], health(board)
    team = board.get("team", TEAM)
    out = [f"## Status report — {title(board)} (due {rel['due']}, {h['days_left']} days left), as of {stamp()}\n",
           f"**Health: {h['verdict']}**  ·  Progress: {h['done']}/{h['total']} approved tasks done\n"]
    blocked = [t for t in tasks if t["status"] == "blocked"]
    out.append(f"**Blockers ({len(blocked)}):**")
    out.append("\n".join(f"- {t['id']} {t['title']} (@{t['owner']}): {t['blocker']}" for t in blocked) or "- none")
    late = overdue(board)
    out.append(f"\n**Overdue ({len(late)}):**")
    out.append("\n".join(f"- {t['id']} {t['title']} (@{t['owner']}, due {t['due']})" for t in late) or "- none")
    out.append("\n**Who is working on what:**")
    for m in team:
        mine = [t for t in tasks if t["owner"] == m and t["status"] in OPEN]
        out.append(f"- @{m}: " + ("; ".join(f"{t['id']} {t['title']} [{t['status']}]" for t in mine) or "nothing open"))
    proposed = [t for t in tasks if t["status"] == "proposed"]
    if proposed:
        out.append("\n**Awaiting approval:** " + ", ".join(f"{t['id']} ({owner_str(t['owner'])})" for t in proposed))
    return "\n".join(out)


def portfolio_text(boards) -> str:
    ppl = people(boards)
    out = [f"## Portfolio — {len(boards)} projects, as of {stamp()}\n"]
    for b in boards:
        h = health(b)
        out.append(f"- **{b['key']}** {b['name']} — {b['release']['name']} due {b['release']['due']} "
                   f"({h['days_left']}d) · **{h['verdict']}** · {h['done']}/{h['total']} done"
                   + (f" · {h['blocked']} blocked" if h["blocked"] else "")
                   + (f" · {h['overdue']} overdue" if h["overdue"] else "")
                   + (f" · {h['proposed']} awaiting approval" if h["proposed"] else ""))
        for r in h["reasons"][:2]:
            out.append(f"  - {r}")
    out.append("\n**Workload across projects (open tasks):**")
    for m, p in ppl.items():
        split = ", ".join(f"{k} {n}" for k, n in p["by"].items()) or "none"
        out.append(f"- @{m}: {p['total']} ({split})" + ("  ⚠ overloaded" if p["overloaded"] else ""))
    risky = [b for b in boards if health(b)["verdict"] != "On track"]
    out.append("\n**Needs attention:** " + (", ".join(f"{b['key']} ({health(b)['verdict']})" for b in risky) or "nothing, all projects on track"))
    return "\n".join(out)


def standup_text(board) -> str:
    since = now() - dt.timedelta(hours=24)
    acts = activity([board], since)
    out = [f"## Daily standup — {title(board)}, {today()}\n",
           f"**Health: {health(board)['verdict']}**\n"]
    for m in board.get("team", TEAM):
        mine = [t for t in board["tasks"] if t["owner"] == m]
        ids = {t["id"] for t in mine}
        done = sorted({a["task"] for a in acts if a["text"] == "Status -> done." and a["task"] in ids})
        doing = [t["id"] for t in mine if t["status"] in ("in_progress", "todo")]
        stuck = [f"{t['id']} ({t['blocker']})" for t in mine if t["status"] == "blocked"]
        out.append(f"**@{m}**")
        out.append(f"- Done (24h): {', '.join(done) or '—'}")
        out.append(f"- Working on: {', '.join(doing) or '—'}")
        out.append(f"- Blocked: {'; '.join(stuck) or '—'}")
    return "\n".join(out)


def weekly_text(board) -> str:
    since = now() - dt.timedelta(days=7)
    acts = [a for a in activity([board], since) if a["task"] != board["key"]]
    h = health(board)
    done = sorted({a["task"] for a in acts if a["text"] == "Status -> done."})
    added = sorted({a["task"] for a in acts if a["text"].startswith("Proposed")})
    raised = sorted({a["task"] for a in acts if a["text"].startswith("Blocked:")})
    out = [f"## Weekly report — {title(board)}, week ending {today()}\n",
           f"**Health: {h['verdict']}**  ·  {h['done']}/{h['total']} done  ·  {h['days_left']} days to release\n",
           f"- Completed this week ({len(done)}): {', '.join(done) or '—'}",
           f"- New tasks this week ({len(added)}): {', '.join(added) or '—'}",
           f"- Blockers raised ({len(raised)}): {', '.join(raised) or '—'}",
           f"- Board changes this week: {len(acts)}",
           "\n**Per person (open / done this week):**"]
    for m in board.get("team", TEAM):
        d = sum(1 for tid in done if find(board, tid)["owner"] == m)
        out.append(f"- @{m}: {loads(board)[m]} open / {d} done")
    if h["reasons"]:
        out.append("\n**Risks:**\n" + "\n".join(f"- {r}" for r in h["reasons"]))
    return "\n".join(out)


# ---------- project commands ----------
def cmd_projects(_a):
    act = active_key()
    for b in load_all():
        h = health(b)
        mark = " (active)" if b["key"] == act else ""
        print(f"- {b['key']}{mark}: {b['name']} — {b['release']['name']} due {b['release']['due']} · "
              f"{h['verdict']} · {h['done']}/{h['total']} done · {len(b['tasks'])} tasks")


def cmd_new_project(a):
    ensure()
    key = a.key.upper()
    if not KEY_RE.match(key):
        sys.exit("Key must be 2-6 letters/digits, starting with a letter (e.g. ACME).")
    if key in keys():
        sys.exit(f"Project {key} already exists.")
    dt.date.fromisoformat(a.due)  # validates the date
    team = [m.strip().lower() for m in a.team.split(",")] if a.team else list(TEAM)
    bad = [m for m in team if m not in TEAM]
    if bad:
        sys.exit(f"Unknown team members: {', '.join(bad)}. Known: {', '.join(TEAM)}.")
    board = {
        "key": key, "name": a.name, "description": a.description or "",
        "release": {"name": a.release, "due": a.due}, "team": team,
        "created": stamp(), "next_id": 1, "tasks": [],
        "log": [{"at": stamp(), "by": a.by, "text": f"Project created: {a.name}, {a.release} due {a.due}."}],
    }
    save(board)
    ACTIVE.write_text(key + "\n")
    print(f"Created project {key}: {a.name} ({a.release} due {a.due}), team: {', '.join(team)}. Now active.")


def cmd_use(a):
    ensure()
    key = a.key.upper()
    if key not in keys():
        sys.exit(f"No project {key}. Known: {', '.join(keys())}.")
    ACTIVE.write_text(key + "\n")
    print(f"Active project: {key}")


def cmd_portfolio(_a):
    print(portfolio_text(load_all()))


# ---------- task commands ----------
def cmd_show(a):
    board = resolve(a)
    rel = board["release"]
    print(f"## {title(board)} board — due {rel['due']}\n")
    for st in STATUSES:
        tasks = [t for t in board["tasks"] if t["status"] == st]
        print(f"### {st.replace('_', ' ').title()} ({len(tasks)})")
        print("\n".join(line(t) for t in tasks) if tasks else "- (none)")
        print()


def cmd_add(a):
    board = resolve(a)
    if a.owner and a.owner not in board.get("team", TEAM):
        sys.exit(f"@{a.owner} is not on the {board['key']} team ({', '.join(board.get('team', TEAM))}).")
    tid = f"{board['key']}-{board['next_id']}"
    board["next_id"] += 1
    task = {
        "id": tid, "title": a.title, "epic": a.epic, "owner": a.owner,
        "status": "proposed", "priority": a.priority, "due": a.due,
        "blocker": None, "updates": [],
    }
    log(task, a.by, "Proposed. Waiting for human approval.")
    board["tasks"].append(task)
    save(board)
    print(f"Added {tid} (proposed) to {board['key']}: {a.title} -> {owner_str(a.owner)}")


def cmd_approve(a):
    board = resolve(a, a.ids)
    targets = [t for t in board["tasks"] if t["status"] == "proposed"] if a.all_proposed \
        else [find(board, i) for i in a.ids]
    if not targets:
        sys.exit(f"Nothing to approve in {board['key']}.")
    for t in targets:
        if t["status"] != "proposed":
            sys.exit(f"{t['id']} is {t['status']}, not proposed.")
        if not t["owner"]:
            sys.exit(f"{t['id']} has no owner yet. Assign it before approving.")
    for t in targets:
        t["status"] = "todo"
        log(t, a.by, "Approved by human.")
    save(board)
    print("Approved: " + ", ".join(t["id"] for t in targets))


def cmd_cancel(a):
    board = resolve(a, [a.id])
    t = find(board, a.id)
    if t["status"] != "proposed":
        sys.exit(f"{t['id']} is {t['status']}. Only proposed tasks can be cancelled.")
    board["tasks"].remove(t)
    save(board)
    print(f"Cancelled proposed task {t['id']} ({t['title']}) by {a.by}")


def cmd_assign(a):
    board = resolve(a, [a.id])
    t = find(board, a.id)
    if a.owner not in board.get("team", TEAM):
        sys.exit(f"@{a.owner} is not on the {board['key']} team ({', '.join(board.get('team', TEAM))}).")
    if t["owner"] == a.owner:
        print(f"{t['id']} is already owned by @{a.owner}. Nothing changed.")
        return
    old, t["owner"] = t["owner"], a.owner
    why = f" Reason: {a.reason}" if a.reason else ""
    log(t, a.by, (f"Assigned to @{a.owner}." if not old else f"Reassigned @{old} -> @{a.owner}.") + why)
    save(board)
    print(f"{t['id']} now owned by @{a.owner}")


def cmd_status(a):
    board = resolve(a, [a.id])
    t = find(board, a.id)
    if t["status"] == "proposed":
        sys.exit(f"{t['id']} is still proposed. A human must approve it first.")
    t["status"] = a.status
    if a.status != "blocked":
        t["blocker"] = None
    log(t, a.by, f"Status -> {a.status}.")
    save(board)
    print(f"{t['id']} -> {a.status}")


def cmd_block(a):
    board = resolve(a, [a.id])
    t = find(board, a.id)
    if t["status"] == "proposed":
        sys.exit(f"{t['id']} is still proposed. A human must approve it first.")
    t["status"], t["blocker"] = "blocked", a.reason
    log(t, a.by, f"Blocked: {a.reason}")
    save(board)
    print(f"{t['id']} BLOCKED: {a.reason}")


def cmd_unblock(a):
    board = resolve(a, [a.id])
    t = find(board, a.id)
    t["status"], t["blocker"] = "in_progress", None
    log(t, a.by, "Unblocked.")
    save(board)
    print(f"{t['id']} unblocked -> in_progress")


def cmd_note(a):
    board = resolve(a, [a.id])
    t = find(board, a.id)
    log(t, a.by, a.text)
    save(board)
    print(f"Noted on {t['id']}")


# ---------- report commands ----------
def cmd_load(_a):
    for m, p in people(load_all()).items():
        split = ", ".join(f"{k} {n}" for k, n in p["by"].items()) or "none"
        print(f"@{m}: {p['total']} open ({split})" + ("  ⚠ overloaded" if p["overloaded"] else ""))


def cmd_report(a):
    print(report_text(resolve(a)))


def cmd_standup(a):
    print(standup_text(resolve(a)))


def cmd_weekly(a):
    print(weekly_text(resolve(a)))


def cmd_save_report(a):
    REPORTS.mkdir(exist_ok=True)
    if a.kind == "portfolio":
        body, path = portfolio_text(load_all()), REPORTS / f"{today()}-portfolio.md"
    else:
        board = resolve(a)
        body = standup_text(board) if a.kind == "daily" else weekly_text(board)
        path = REPORTS / f"{today()}-{board['key'].lower()}-{a.kind}.md"
    path.write_text(f"{body}\n\n### Summary (by {a.by})\n{a.summary.strip()}\n")
    print(f"Saved {path.relative_to(ROOT)}")


def cmd_validate(_a):
    errors = [e for b in load_all() for e in check(b)]
    print(f"All {len(keys())} projects OK" if not errors else "\n".join(errors))
    sys.exit(1 if errors else 0)


def cmd_reset(_a):
    seed()
    if REPORTS.exists():
        for f in REPORTS.glob("*.md"):
            f.unlink()
    print(f"Reset to demo seed: {', '.join(keys())} (reports cleared)")


def main():
    p = argparse.ArgumentParser(description="Foreman board (multi-project)")
    sub = p.add_subparsers(dest="cmd", required=True)

    def sp(name, by=True, project=True):
        s = sub.add_parser(name)
        if by:
            s.add_argument("--by", default="agent", help="who made the change")
        if project:
            s.add_argument("-p", "--project", help="project KEY (default: from task id, else active)")
        return s

    sp("projects", by=False, project=False)
    s = sp("new-project", project=False)
    s.add_argument("--name", required=True)
    s.add_argument("--key", required=True, help="2-6 chars, e.g. ACME")
    s.add_argument("--release", required=True, help="e.g. v1.0")
    s.add_argument("--due", required=True, help="YYYY-MM-DD")
    s.add_argument("--team", default="", help="comma list, default everyone")
    s.add_argument("--description", default="")
    s = sp("use", by=False, project=False)
    s.add_argument("key")
    sp("portfolio", by=False, project=False)

    sp("show", by=False)
    s = sp("add")
    s.add_argument("--title", required=True)
    s.add_argument("--epic", required=True)
    s.add_argument("--owner", choices=TEAM, default=None, help="leave out to let the assigner pick")
    s.add_argument("--priority", default="medium", choices=PRIORITIES)
    s.add_argument("--due", required=True, help="YYYY-MM-DD")
    s = sp("approve")
    s.add_argument("ids", nargs="*")
    s.add_argument("--all-proposed", action="store_true")
    s = sp("cancel")
    s.add_argument("id")
    s = sp("assign")
    s.add_argument("id")
    s.add_argument("owner", choices=TEAM)
    s.add_argument("--reason", default="", help="why this person")
    s = sp("status")
    s.add_argument("id")
    s.add_argument("status", choices=[x for x in STATUSES if x not in ("blocked", "proposed")])
    s = sp("block")
    s.add_argument("id")
    s.add_argument("reason")
    s = sp("unblock")
    s.add_argument("id")
    s = sp("note")
    s.add_argument("id")
    s.add_argument("text")

    sp("load", by=False, project=False)
    for name in ("report", "standup", "weekly"):
        sp(name, by=False)
    s = sp("save-report")
    s.add_argument("kind", choices=["daily", "weekly", "portfolio"])
    s.add_argument("--summary", required=True, help="2-4 sentence narrative from the reporter")
    sp("validate", by=False, project=False)
    sp("reset", by=False, project=False)

    a = p.parse_args()
    globals()[f"cmd_{a.cmd.replace('-', '_')}"](a)


if __name__ == "__main__":
    main()
