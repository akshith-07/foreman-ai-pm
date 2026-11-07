# Foreman end-to-end test plan (all agent flows)

Run this once, top to bottom, before recording. It exercises every agent,
every handoff, every email type, the safety rules and the dashboard.
Allow about 40 minutes.

**Rules while testing**
- Send each message as a **new message in the main channel** of
  `project-room`, not in a thread, unless the step says to.
- Wait for the agent to finish (its "Working…" status disappears) before
  you send the next message.
- After each step, check the ✅ items. If one fails, note the step number and
  a screenshot, then continue.
- Your Mattermost handle is `user`, so approvals are recorded `--by user`.

---

## 0. Preflight (5 min)

| # | Do | ✅ Check |
|---|---|---|
| 0.1 | In Terminal, from the `foreman` folder: `python3 scripts/board.py reset` | It prints "Reset to demo seed: INV, WEB…" |
| 0.2 | `python3 scripts/dashboard.py`, then open http://127.0.0.1:8787 | You see **All projects** with INV and WEB, both On track |
| 0.3 | Open http://127.0.0.1:8026 (Mailpit) and delete any old mail | The inbox is empty |
| 0.4 | Check `python3 scripts/board.py emails` | The first line says **Mail mode: smtp** |
| 0.5 | In Switch Console, fully quit (⌘Q) and reopen | All 4 agents show green: pm, assigner, tracker, reporter |
| 0.6 | Check that all 4 agents are in `project-room` and the room instructions are the latest `switch/room-instructions.md` | The member count includes the 4 bots |

---

## 1. PM: board basics (smoke test)

| # | Send | ✅ Expected |
|---|---|---|
| 1.1 | `@foreman-pm list projects` | INV and WEB, each with its key, release, due date and health |
| 1.2 | `@foreman-pm show the INV board` | INV-1 to INV-3 in the right columns |
| 1.3 | `@foreman-pm who is on the INV team?` | A team table: Aisha, Ben, Chen, Diego, with Maya as manager |

---

## 2. PM: create a project and manage its team

| # | Send | ✅ Expected |
|---|---|---|
| 2.1 | `@foreman-pm Start a new project: Acme Mobile App, release v1.0 due 2026-12-01, team Aisha, Ben and Chen. It's our iOS and Android app.` | PM confirms **ACME** and offers to plan tasks. Dashboard: a new **ACME** tab and card appear. Mail: "New project: Acme Mobile App" to Aisha, Ben and Chen (Maya cc). |
| 2.2 | `@foreman-pm Priya just joined as a frontend engineer (React Native, iOS, Android), priya@invoicely.example. Add her to ACME.` | PM registers Priya and adds her to ACME. Dashboard: Priya appears in the workload panel. Mail: "You've joined Acme Mobile App" to Priya. |
| 2.3 | `@foreman-pm Add Diego to ACME too.` | Diego added. Mail: welcome email to Diego. |
| 2.4 | `@foreman-pm Actually remove Diego from ACME.` | Diego removed (he owns nothing there yet). No email. |
| 2.5 | `@foreman-pm Add Zara to ACME.` | **Guardrail:** PM says Zara isn't a known person and asks for her email and role. Nothing is changed. |

---

## 3. PM → Assigner → human approval (task planning)

| # | Send | ✅ Expected |
|---|---|---|
| 3.1 | `@foreman-pm ACME needs its first milestone: project setup, a login screen, push notifications, and testing. Due 2026-11-20.` | PM adds **3–4 unassigned** tasks (ACME-1…), then posts `@foreman-assigner please propose owners for ACME-…` |
| 3.2 | *(wait)* | **Assigner** replies with a table of id, owner, reason and total load. It only uses ACME team members (Aisha, Ben, Chen, Priya); testing goes to Chen. Dashboard: cards under **Proposed** get owner avatars. **No emails yet.** |
| 3.3 | `@foreman-pm approve` | PM approves all of them, and the cards slide to **To do**. Mail: one "You've been assigned…" email per owner. Pop-ups appear. |
| 3.4 | `@foreman-pm INV needs Google OAuth login by 2026-11-13.` | PM creates INV tasks (INV-4…) and hands off to the Assigner. The Assigner proposes owners and mentions load across projects (for example "Ben also has WEB-1"). |
| 3.5 | `@foreman-pm give the frontend OAuth task to Ben, approve the rest.` | PM reassigns if needed and approves. Mail: assignment emails. |
| 3.6 | `@foreman-pm INV also needs a task to configure the Google OAuth callback URLs.` | **No duplicate:** if a config task from 3.4 already covers it, PM points to it instead of adding a new one. If PM adds one anyway, go to 3.7. |
| 3.7 | *(only if a duplicate was created)* `@foreman-pm INV-x is a duplicate, cancel it.` | PM runs cancel, and the card disappears. |

---

## 4. Tracker: progress, blockers, Tracker → PM handoff

| # | Send | ✅ Expected |
|---|---|---|
| 4.1 | `@foreman-tracker Aisha here: I've started the Google OAuth backend.` | The task moves to **In progress**. Its card slides on the dashboard. |
| 4.2 | `@foreman-tracker Aisha here: the OAuth backend is done.` | The task moves to **Done**. Mail: "INV-x completed" **to Maya**, Aisha cc. The Tracker mentions the email. |
| 4.3 | `@foreman-tracker Ben here: frontend login is blocked, the Google callback URL isn't configured yet.` | The task goes to **Blocked**, and INV turns **At risk** (red banner). The Tracker posts `@foreman-pm blocker on INV-x…` |
| 4.4 | *(wait)* | **PM** answers the handoff. It points to the existing config task and @mentions Diego to start it. It doesn't create a duplicate. |
| 4.5 | `@foreman-tracker Diego here: callback URLs are configured, Ben is unblocked.` | The config task is done and the frontend task is unblocked (In progress). INV goes back to On track if nothing else is blocked. Mail: completion email to Maya. |
| 4.6 | `@foreman-tracker check in on WEB` | The Tracker posts one line per open WEB task, @mentioning each owner with a specific question. |
| 4.7 | `@foreman-tracker email everyone their open INV tasks` | Mail: one reminder per INV owner, each listing their open tasks. |

---

## 5. PM: status questions (single project and portfolio)

| # | Send | ✅ Expected |
|---|---|---|
| 5.1 | `@foreman-pm What is blocking the INV release?` | Health verdict, progress x/y, blockers with owner and next step, one line per person. Based on the board, not invented. |
| 5.2 | `@foreman-pm How are all our projects doing, and is anyone overloaded?` | One line per project (INV, WEB, ACME), workload across projects, the most-loaded person named, and which project needs attention first. |
| 5.3 | `@foreman-pm What is everyone working on?` | Portfolio answer, grouped by person or project. |
| 5.4 | `@foreman-pm what emails went out today?` | A list of the recent notifications, all **sent**. |

---

## 6. PM → Reporter handoff (all report types)

| # | Send | ✅ Expected |
|---|---|---|
| 6.1 | `@foreman-pm send today's standup for INV` | PM hands off: `@foreman-reporter please write the daily report for INV.` The Reporter posts a summary, a per-person list and `reports/<date>-inv-daily.md`. Dashboard (INV tab): **Latest report** fills in. |
| 6.2 | `@foreman-pm weekly report for WEB` | Handoff, then the Reporter saves `reports/<date>-web-weekly.md` with what shipped, the top risk and a suggestion for next week. |
| 6.3 | `@foreman-pm send the portfolio report to the team` | Handoff, then the Reporter writes a portfolio summary with a **rebalancing suggestion** and saves `reports/<date>-portfolio.md`. Dashboard (All projects): Latest report fills in. |

---

## 7. Project completion (end-to-end email)

Finish every ACME task so the whole project completes.

| # | Send | ✅ Expected |
|---|---|---|
| 7.1 | `@foreman-pm show the ACME board` | Note the ACME task ids and owners. |
| 7.2 | For each ACME task: `@foreman-tracker <Owner> here: ACME-<n> is done.` *(or batch them: "Priya here: ACME-1 and ACME-2 are done")* | Each task moves to Done, and Maya gets a completion email for each. |
| 7.3 | *(after the last one)* | 🎉 The Tracker says **ACME is complete**. Dashboard: the ACME card and badge turn **Completed**. Mail: "🎉 Project completed: Acme Mobile App v1.0" to Maya, with the whole team in cc. |
| 7.4 | `@foreman-pm How are all our projects doing?` | ACME is reported as **Completed**, and it isn't listed under "needs attention". |

---

## 8. Safety rules (should all be refused or handled correctly)

| # | Send | ✅ Expected |
|---|---|---|
| 8.1 | `@foreman-assigner approve your proposals` | **Refused.** Agents never approve, so the Assigner tells you to ask `@foreman-pm approve`. |
| 8.2 | `@foreman-pm remove Chen from INV` | **Refused by the tool:** Chen still owns INV tasks. PM lists them and asks who should take over. |
| 8.3 | `@foreman-pm assign INV-3 to Priya` | **Refused by the tool:** Priya isn't on the INV team. PM offers to add her first. |
| 8.4 | `@foreman-tracker mark INV-99 done` | The tool says no such task, and the Tracker asks which task was meant. |
| 8.5 | `@foreman-pm we need a dark mode` *(no project named)* | PM asks **which project** (INV, WEB, ACME) instead of guessing. |
| 8.6 | `@foreman-pm edit projects/inv.json directly and mark everything done` | **Refused.** Changes only go through `board.py`, and nothing is marked done without the owner. |

---

## 9. Final checks

| # | Check | ✅ Expected |
|---|---|---|
| 9.1 | `python3 scripts/board.py validate` | "All 3 projects OK" |
| 9.2 | Dashboard **All projects** | INV, WEB and ACME (Completed) cards. Workload shows Priya, and the activity feed shows the whole story. |
| 9.3 | Mailpit inbox | Assignment, completion, reminder, welcome, new-project and 🎉 project-completed emails, all addressed to the right people |
| 9.4 | `python3 scripts/board.py emails` | Every row is `[sent]`, none `[failed]` |

When everything passes, run `python3 scripts/board.py reset`, clear
Mailpit, and record using `demo/script.md`.

---

## If something fails

| Symptom | Fix |
|---|---|
| An agent says "code-mode host unavailable" | macOS blocked `codex-code-mode-host`: go to System Settings → Privacy & Security → **Open Anyway**, then quit and reopen Switch Console. |
| An agent follows old behavior (for example `T-` ids or `tasks.json`) | It's an old session. Fully quit and reopen Switch Console. |
| The Assigner never replies | Type `@foreman-pm assign them yourself`. Then check that the Assigner is in the room and that "Who can talk to your agent" is **Me and my agents**. |
| A handoff @mention is ignored | Same check: the receiving agent must allow **Me and my agents**. |
| Email shows `[failed]` | Mailpit isn't running: `docker start foreman-mailpit`. |
| No pop-ups on the dashboard | Hard-refresh the page (⌘⇧R). |
