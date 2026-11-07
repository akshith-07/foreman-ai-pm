#!/usr/bin/env python3
"""Foreman task board CLI.

The agents call this instead of hand-editing tasks.json, so the board stays
valid JSON and every change leaves an audit trail in `updates`.

Usage (run from the repo root):
  python3 scripts/board.py show
  python3 scripts/board.py add --title "..." --epic Auth --owner aisha --priority high --due 2026-11-13 --by foreman-pm
  python3 scripts/board.py approve T-4 T-5 --by <human>      (or: approve --all-proposed)
  python3 scripts/board.py cancel T-8 --by <human>             (proposed tasks only)
  python3 scripts/board.py assign T-4 ben --by foreman-pm
  python3 scripts/board.py status T-4 in_progress|done|todo --by <who>
  python3 scripts/board.py block T-4 "callback URL not configured" --by foreman-tracker
  python3 scripts/board.py unblock T-4 --by foreman-tracker
  python3 scripts/board.py note T-4 "text" --by <who>
  python3 scripts/board.py load
  python3 scripts/board.py report
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

STATUSES = ["proposed", "todo", "in_progress", "blocked", "done"]
OPEN = {"todo", "in_progress", "blocked"}
PRIORITIES = ["high", "medium", "low"]
TEAM = ["aisha", "ben", "chen", "diego"]


def today() -> str:
    return dt.date.today().isoformat()


def load() -> dict:
    if not BOARD.exists():
        shutil.copy(SEED, BOARD)
    return json.loads(BOARD.read_text())


def save(board: dict) -> None:
    errors = check(board)
    if errors:
        sys.exit("Refusing to save invalid board:\n  " + "\n  ".join(errors))
    BOARD.write_text(json.dumps(board, indent=2) + "\n")


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
    return errors


def find(board: dict, tid: str) -> dict:
    tid = tid.upper()
    for t in board["tasks"]:
        if t["id"] == tid:
            return t
    sys.exit(f"No task {tid}. Run `board.py show` to list tasks.")


def log(task: dict, by: str, text: str) -> None:
    task.setdefault("updates", []).append({"at": today(), "by": by, "text": text})


def line(t: dict) -> str:
    s = f"- **{t['id']}** {t['title']} — @{t['owner'] or 'unassigned'} · {t['priority']} · due {t['due']}"
    if t.get("blocker"):
        s += f"\n  - BLOCKED: {t['blocker']}"
    return s


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
    print(f"Added {tid} (proposed): {a.title} -> @{a.owner}")


def cmd_approve(board, a):
    targets = [t for t in board["tasks"] if t["status"] == "proposed"] if a.all_proposed \
        else [find(board, i) for i in a.ids]
    if not targets:
        sys.exit("Nothing to approve.")
    for t in targets:
        if t["status"] != "proposed":
            sys.exit(f"{t['id']} is {t['status']}, not proposed.")
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
    old, t["owner"] = t["owner"], a.owner
    log(t, a.by, f"Reassigned @{old} -> @{a.owner}.")
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


def loads(board) -> dict:
    counts = {m: 0 for m in TEAM}
    for t in board["tasks"]:
        if t["status"] in OPEN and t["owner"] in counts:
            counts[t["owner"]] += 1
    return counts


def cmd_load(board, _):
    for m, n in loads(board).items():
        print(f"@{m}: {n} open")


def cmd_report(board, _):
    tasks, now = board["tasks"], today()
    rel = board["release"]
    release = [t for t in tasks if t["status"] != "proposed"]
    done = sum(t["status"] == "done" for t in release)
    print(f"## Status report — {board['project']} {rel['name']} (due {rel['due']}), as of {now}\n")
    print(f"**Progress:** {done}/{len(release)} approved tasks done\n")
    blocked = [t for t in tasks if t["status"] == "blocked"]
    print(f"**Blockers ({len(blocked)}):**")
    print("\n".join(f"- {t['id']} {t['title']} (@{t['owner']}): {t['blocker']}" for t in blocked) or "- none")
    overdue = [t for t in tasks if t["status"] in OPEN and t["due"] < now]
    print(f"\n**Overdue ({len(overdue)}):**")
    print("\n".join(f"- {t['id']} {t['title']} (@{t['owner']}, due {t['due']})" for t in overdue) or "- none")
    print("\n**Who is working on what:**")
    for m in TEAM:
        mine = [t for t in tasks if t["owner"] == m and t["status"] in OPEN]
        print(f"- @{m}: " + ("; ".join(f"{t['id']} {t['title']} [{t['status']}]" for t in mine) or "nothing open"))
    proposed = [t for t in tasks if t["status"] == "proposed"]
    if proposed:
        print(f"\n**Awaiting approval:** " + ", ".join(t["id"] for t in proposed))


def cmd_validate(board, _):
    errors = check(board)
    print("Board OK" if not errors else "\n".join(errors))
    sys.exit(1 if errors else 0)


def cmd_reset(_board, _):
    shutil.copy(SEED, BOARD)
    print("Board reset to seed/tasks.seed.json")


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
    s.add_argument("--owner", required=True, choices=TEAM)
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
    s = by(sub.add_parser("status"))
    s.add_argument("id")
    s.add_argument("status", choices=[x for x in STATUSES if x != "blocked"])
    s = by(sub.add_parser("block"))
    s.add_argument("id")
    s.add_argument("reason")
    s = by(sub.add_parser("unblock"))
    s.add_argument("id")
    s = by(sub.add_parser("note"))
    s.add_argument("id")
    s.add_argument("text")
    sub.add_parser("load")
    sub.add_parser("report")
    sub.add_parser("validate")
    sub.add_parser("reset")

    a = p.parse_args()
    board = None if a.cmd == "reset" else load()
    globals()[f"cmd_{a.cmd}"](board, a)


if __name__ == "__main__":
    main()
