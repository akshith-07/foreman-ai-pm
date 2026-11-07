#!/usr/bin/env python3
"""Foreman task board CLI.

The agents call this instead of hand-editing files, so the board stays
valid JSON and every change leaves an audit trail in `updates`.

Usage (run from the repo root):
  python3 scripts/board.py show
  python3 scripts/board.py add --title "..." --epic Auth --priority high --due 2026-11-13 [--owner aisha] --by foreman-pm
  python3 scripts/board.py assign T-4 ben --reason "React + login flows" --by foreman-assigner
  python3 scripts/board.py approve T-4 T-5 --by <human>        (or: approve --all-proposed)
  python3 scripts/board.py cancel T-8 --by <human>             (proposed tasks only)
  python3 scripts/board.py status T-4 in_progress|done|todo --by <who>
  python3 scripts/board.py block T-4 "callback URL not configured" --by <who>
  python3 scripts/board.py unblock T-4 --by <who>
  python3 scripts/board.py note T-4 "text" --by <who>
  python3 scripts/board.py load          open tasks per person
  python3 scripts/board.py report        status report with release health
  python3 scripts/board.py standup       daily standup data (last 24h)
  python3 scripts/board.py weekly        weekly report data (last 7 days)
  python3 scripts/board.py save-report daily|weekly --summary "..." --by foreman-reporter
  python3 scripts/board.py validate
  python3 scripts/board.py reset
"""
import argparse
import datetime as dt
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOARD = ROOT / "tasks.json"
SEED = ROOT / "seed" / "tasks.seed.json"
REPORTS = ROOT / "reports"

STATUSES = ["proposed", "todo", "in_progress", "blocked", "done"]
OPEN = {"todo", "in_progress", "blocked"}
PRIORITIES = ["high", "medium", "low"]
TEAM = ["aisha", "ben", "chen", "diego"]


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
def load() -> dict:
    if not BOARD.exists():
        shutil.copy(SEED, BOARD)
    return json.loads(BOARD.read_text())


def save(board: dict) -> None:
    errors = check(board)
    if errors:
        sys.exit("Refusing to save invalid board:\n  " + "\n  ".join(errors))
    tmp = BOARD.with_suffix(".tmp")
    tmp.write_text(json.dumps(board, indent=2) + "\n")
    tmp.replace(BOARD)  # atomic, so the dashboard never reads half a file


def check(board: dict) -> list:
    errors, seen = [], set()
    for t in board.get("tasks", []):
        tid = t.get("id", "?")
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
    sys.exit(f"No task {tid}. Run `board.py show` to list tasks.")


def log(task: dict, by: str, text: str) -> None:
    task.setdefault("updates", []).append({"at": stamp(), "by": by, "text": text})


# ---------- derived views (shared with the dashboard) ----------
def loads(board) -> dict:
    counts = {m: 0 for m in TEAM}
    for t in board["tasks"]:
        if t["status"] in OPEN and t["owner"] in counts:
            counts[t["owner"]] += 1
    return counts


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
    }


def activity(board, since: dt.datetime | None = None) -> list:
    items = []
    for t in board["tasks"]:
        for i, u in enumerate(t.get("updates", [])):
            at = parse_at(u["at"])
            if since is None or at >= since:
                items.append({**u, "task": t["id"], "title": t["title"], "_k": (at, i)})
    items.sort(key=lambda x: x["_k"], reverse=True)
    for x in items:
        x.pop("_k")
    return items


def latest_report() -> dict | None:
    if not REPORTS.exists():
        return None
    files = sorted(REPORTS.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    return {"name": files[0].name, "text": files[0].read_text()}


# ---------- formatting ----------
def line(t: dict) -> str:
    s = f"- **{t['id']}** {t['title']} — {('@' + t['owner']) if t['owner'] else 'unassigned'} · {t['priority']} · due {t['due']}"
    if t.get("blocker"):
        s += f"\n  - BLOCKED: {t['blocker']}"
    return s


def report_text(board) -> str:
    tasks, rel, h = board["tasks"], board["release"], health(board)
    out = [f"## Status report — {board['project']} {rel['name']} (due {rel['due']}, {h['days_left']} days left), as of {stamp()}\n",
           f"**Health: {h['verdict']}**  ·  Progress: {h['done']}/{h['total']} approved tasks done\n"]
    blocked = [t for t in tasks if t["status"] == "blocked"]
    out.append(f"**Blockers ({len(blocked)}):**")
    out.append("\n".join(f"- {t['id']} {t['title']} (@{t['owner']}): {t['blocker']}" for t in blocked) or "- none")
    late = overdue(board)
    out.append(f"\n**Overdue ({len(late)}):**")
    out.append("\n".join(f"- {t['id']} {t['title']} (@{t['owner']}, due {t['due']})" for t in late) or "- none")
    out.append("\n**Who is working on what:**")
    for m in TEAM:
        mine = [t for t in tasks if t["owner"] == m and t["status"] in OPEN]
        out.append(f"- @{m}: " + ("; ".join(f"{t['id']} {t['title']} [{t['status']}]" for t in mine) or "nothing open"))
    proposed = [t for t in tasks if t["status"] == "proposed"]
    if proposed:
        out.append("\n**Awaiting approval:** " + ", ".join(f"{t['id']} ({'@' + t['owner'] if t['owner'] else 'unassigned'})" for t in proposed))
    return "\n".join(out)


def standup_text(board) -> str:
    since = now() - dt.timedelta(hours=24)
    acts = activity(board, since)
    out = [f"## Daily standup — {board['project']} {board['release']['name']}, {today()}\n",
           f"**Health: {health(board)['verdict']}**\n"]
    for m in TEAM:
        done = sorted({a["task"] for a in acts if a["text"] == "Status -> done." and
                       find(board, a["task"])["owner"] == m})
        mine = [t for t in board["tasks"] if t["owner"] == m]
        doing = [t["id"] for t in mine if t["status"] in ("in_progress", "todo")]
        stuck = [f"{t['id']} ({t['blocker']})" for t in mine if t["status"] == "blocked"]
        out.append(f"**@{m}**")
        out.append(f"- Done (24h): {', '.join(done) or '—'}")
        out.append(f"- Working on: {', '.join(doing) or '—'}")
        out.append(f"- Blocked: {'; '.join(stuck) or '—'}")
    return "\n".join(out)


def weekly_text(board) -> str:
    since = now() - dt.timedelta(days=7)
    acts = activity(board, since)
    h = health(board)
    done = sorted({a["task"] for a in acts if a["text"] == "Status -> done."})
    added = sorted({a["task"] for a in acts if a["text"].startswith("Proposed")})
    raised = sorted({a["task"] for a in acts if a["text"].startswith("Blocked:")})
    out = [f"## Weekly report — {board['project']} {board['release']['name']}, week ending {today()}\n",
           f"**Health: {h['verdict']}**  ·  {h['done']}/{h['total']} done  ·  {h['days_left']} days to release\n",
           f"- Completed this week ({len(done)}): {', '.join(done) or '—'}",
           f"- New tasks this week ({len(added)}): {', '.join(added) or '—'}",
           f"- Blockers raised ({len(raised)}): {', '.join(raised) or '—'}",
           f"- Board changes this week: {len(acts)}",
           "\n**Per person (open / done this week):**"]
    for m in TEAM:
        d = sum(1 for tid in done if find(board, tid)["owner"] == m)
        out.append(f"- @{m}: {loads(board)[m]} open / {d} done")
    if h["reasons"]:
        out.append("\n**Risks:**\n" + "\n".join(f"- {r}" for r in h["reasons"]))
    return "\n".join(out)


# ---------- commands ----------
def cmd_show(board, _):
    rel = board["release"]
    print(f"## {board['project']} board — release {rel['name']} due {rel['due']}\n")
    for st in STATUSES:
        tasks = [t for t in board["tasks"] if t["status"] == st]
        print(f"### {st.replace('_', ' ').title()} ({len(tasks)})")
        print("\n".join(line(t) for t in tasks) if tasks else "- (none)")
        print()


def cmd_add(board, a):
    tid = f"T-{board['next_id']}"
    board["next_id"] += 1
    task = {
        "id": tid, "title": a.title, "epic": a.epic, "owner": a.owner,
        "status": "proposed", "priority": a.priority, "due": a.due,
        "blocker": None, "updates": [],
    }
    log(task, a.by, "Proposed. Waiting for human approval.")
    board["tasks"].append(task)
    save(board)
    print(f"Added {tid} (proposed): {a.title} -> {('@' + a.owner) if a.owner else 'unassigned'}")


def cmd_approve(board, a):
    targets = [t for t in board["tasks"] if t["status"] == "proposed"] if a.all_proposed \
        else [find(board, i) for i in a.ids]
    if not targets:
        sys.exit("Nothing to approve.")
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


def cmd_cancel(board, a):
    t = find(board, a.id)
    if t["status"] != "proposed":
        sys.exit(f"{t['id']} is {t['status']}. Only proposed tasks can be cancelled.")
    board["tasks"].remove(t)
    save(board)
    print(f"Cancelled proposed task {t['id']} ({t['title']}) by {a.by}")


def cmd_assign(board, a):
    t = find(board, a.id)
    if t["owner"] == a.owner:
        print(f"{t['id']} is already owned by @{a.owner}. Nothing changed.")
        return
    old, t["owner"] = t["owner"], a.owner
    why = f" Reason: {a.reason}" if a.reason else ""
    log(t, a.by, (f"Assigned to @{a.owner}." if not old else f"Reassigned @{old} -> @{a.owner}.") + why)
    save(board)
    print(f"{t['id']} now owned by @{a.owner}")


def cmd_status(board, a):
    t = find(board, a.id)
    if t["status"] == "proposed" and a.status != "proposed":
        sys.exit(f"{t['id']} is still proposed. A human must approve it first.")
    t["status"] = a.status
    if a.status != "blocked":
        t["blocker"] = None
    log(t, a.by, f"Status -> {a.status}.")
    save(board)
    print(f"{t['id']} -> {a.status}")


def cmd_block(board, a):
    t = find(board, a.id)
    if t["status"] == "proposed":
        sys.exit(f"{t['id']} is still proposed. A human must approve it first.")
    t["status"], t["blocker"] = "blocked", a.reason
    log(t, a.by, f"Blocked: {a.reason}")
    save(board)
    print(f"{t['id']} BLOCKED: {a.reason}")


def cmd_unblock(board, a):
    t = find(board, a.id)
    t["status"], t["blocker"] = "in_progress", None
    log(t, a.by, "Unblocked.")
    save(board)
    print(f"{t['id']} unblocked -> in_progress")


def cmd_note(board, a):
    t = find(board, a.id)
    log(t, a.by, a.text)
    save(board)
    print(f"Noted on {t['id']}")


def cmd_load(board, _):
    for m, n in loads(board).items():
        print(f"@{m}: {n} open")


def cmd_report(board, _):
    print(report_text(board))


def cmd_standup(board, _):
    print(standup_text(board))


def cmd_weekly(board, _):
    print(weekly_text(board))


def cmd_save_report(board, a):
    REPORTS.mkdir(exist_ok=True)
    body = standup_text(board) if a.kind == "daily" else weekly_text(board)
    path = REPORTS / f"{today()}-{a.kind}.md"
    text = f"{body}\n\n### Summary (by {a.by})\n{a.summary.strip()}\n"
    path.write_text(text)
    print(f"Saved {path.relative_to(ROOT)}")


def cmd_validate(board, _):
    errors = check(board)
    print("Board OK" if not errors else "\n".join(errors))
    sys.exit(1 if errors else 0)


def cmd_reset(_board, _):
    shutil.copy(SEED, BOARD)
    if REPORTS.exists():
        for f in REPORTS.glob("*.md"):
            f.unlink()
    print("Board reset to seed/tasks.seed.json (reports cleared)")


def main():
    p = argparse.ArgumentParser(description="Foreman task board")
    sub = p.add_subparsers(dest="cmd", required=True)

    def by(sp):
        sp.add_argument("--by", default="agent", help="who made the change")
        return sp

    sub.add_parser("show")
    s = by(sub.add_parser("add"))
    s.add_argument("--title", required=True)
    s.add_argument("--epic", required=True)
    s.add_argument("--owner", choices=TEAM, default=None, help="leave out to let the assigner pick")
    s.add_argument("--priority", default="medium", choices=PRIORITIES)
    s.add_argument("--due", required=True, help="YYYY-MM-DD")
    s = by(sub.add_parser("approve"))
    s.add_argument("ids", nargs="*")
    s.add_argument("--all-proposed", action="store_true")
    s = by(sub.add_parser("cancel"))
    s.add_argument("id")
    s = by(sub.add_parser("assign"))
    s.add_argument("id")
    s.add_argument("owner", choices=TEAM)
    s.add_argument("--reason", default="", help="why this person")
    s = by(sub.add_parser("status"))
    s.add_argument("id")
    s.add_argument("status", choices=[x for x in STATUSES if x not in ("blocked", "proposed")])
    s = by(sub.add_parser("block"))
    s.add_argument("id")
    s.add_argument("reason")
    s = by(sub.add_parser("unblock"))
    s.add_argument("id")
    s = by(sub.add_parser("note"))
    s.add_argument("id")
    s.add_argument("text")
    for name in ("load", "report", "standup", "weekly", "validate", "reset"):
        sub.add_parser(name)
    s = by(sub.add_parser("save-report"))
    s.add_argument("kind", choices=["daily", "weekly"])
    s.add_argument("--summary", required=True, help="2-4 sentence narrative from the reporter")

    a = p.parse_args()
    board = None if a.cmd == "reset" else load()
    globals()[f"cmd_{a.cmd.replace('-', '_')}"](board, a)


if __name__ == "__main__":
    main()
