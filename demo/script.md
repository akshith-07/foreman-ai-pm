# Demo script: target 3–3.5 minutes

**Before recording:**
- Run `python3 scripts/board.py reset`. This restores INV and WEB and clears
  reports.
- Start `python3 scripts/dashboard.py` and open http://127.0.0.1:8787. It
  starts on **All projects**.
- Optional, for real emails: start the Foreman Mailpit and `cp .env.example .env`
  (see the README). The Notifications panel then shows **SENT**.
- Arrange the screen: **Mattermost on the left, the dashboard on the
  right.** Every chat message should visibly change the dashboard.
- Make sure all four agents show as available in `project-room`.
- Use one human Mattermost account. When you speak as a teammate, start the
  message with their name (for example "Aisha here:"), so the agents record
  the right person.

Rehearse every scene twice before recording.

---

## Scene 0: Hook (10 s)
> "Small teams juggle several projects and no project manager, so
> developers end up chasing each other for updates. Foreman puts four AI
> agents in your team chat, connected through Switch, to run every project,
> and the humans stay in control."

## Scene 1: Create a project and build its team from chat (35 s)
**You type:**
```
@foreman-pm Start a new project: Acme Mobile App, release v1.0 due 2026-12-01, team Aisha, Ben and Chen.
```
**Expected:** the PM creates **ACME**, and a new **ACME** tab and card
appear on the dashboard.

**You type:**
```
@foreman-pm Priya just joined as a frontend engineer (React Native), priya@invoicely.example. Add her to ACME.
```
**Expected:**
- The PM registers Priya and adds her to the ACME team.
- She appears in the dashboard's workload panel.
- A "You've joined Acme Mobile App" email appears under **Notifications**.

## Scene 2: New work, PM to Assigner handoff (50 s)
Click the **INV** tab on the dashboard.

**You type:**
```
@foreman-pm INV needs Google OAuth login by Friday (2026-11-13).
```
**Expected:**
- The PM adds 3–4 unassigned INV tasks (INV-4 onward), then posts
  "@foreman-assigner please propose owners…".
- The Assigner replies with owners and reasons, mentioning load across
  projects (for example "Ben already has work in WEB").
- The cards appear under **Proposed**, then get owners.

**You type:**
```
@foreman-pm approve
```
**Expected:**
- The cards slide to **To do**.
- Each owner gets a "You've been assigned…" email (pop-ups plus the
  Notifications panel).

## Scene 3: Progress and a blocker, Tracker to PM handoff (40 s)
**You type:**
```
@foreman-tracker Aisha here: backend OAuth is done.
```
```
@foreman-tracker Ben here: frontend login is blocked, the Google callback URL isn't configured yet.
```
**Expected:**
- The cards move to **Done** and **Blocked**, and INV turns **At risk**.
- **Maya, the manager, is emailed** that the backend task was completed.
  Optional: flash the Mailpit inbox at http://127.0.0.1:8026.
- The Tracker hands off with "@foreman-pm blocker on INV-x…".
- The PM points to the existing config task and @mentions Diego.

## Scene 4: The manager question, across projects (35 s), the hero moment
Click **All projects** on the dashboard.

**You type:**
```
@foreman-pm How are all our projects doing, and is anyone overloaded?
```
**Expected:**
- one line per project (INV at risk, WEB and ACME status);
- workload across projects, flagging Ben if he's overloaded;
- which project needs attention first.

## Scene 5: Portfolio report, PM to Reporter handoff (25 s)
**You type:**
```
@foreman-pm send the portfolio report to the team.
```
**Expected:**
- The PM hands off with "@foreman-reporter please write the portfolio
  report."
- The Reporter posts a summary with a rebalancing suggestion and saves
  `reports/<date>-portfolio.md`.
- The report appears in the dashboard's **Latest report** panel.

## Scene 6: Close (10 s)
> "Several projects, four agents, one room, and every decision approved by
> a human. Every change is logged, the boards are plain files in the repo,
> and it all runs on Switch with Codex, or any agent you choose. That's
> Foreman."

---

## If something goes wrong while recording
- **An agent doesn't answer:** check that Switch Console is open and the
  agent is green, then send the message again.
- **The Assigner doesn't reply:** type `@foreman-pm assign them yourself`.
- **An agent asks "which project?":** answer with the key, for example "INV".
- **The boards look wrong:** run `python3 scripts/board.py reset` and start
  again from Scene 1.
