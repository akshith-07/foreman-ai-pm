# Demo script: target 3 minutes

**Before recording:**
- Run `python3 scripts/board.py reset`. This also clears old reports.
- Start `python3 scripts/dashboard.py` and open http://127.0.0.1:8787.
- Arrange the screen: **Mattermost on the left, the dashboard on the
  right.** Every chat message should visibly change the board.
- Make sure all four agents show as available in `project-room`.
- Use one human Mattermost account. When you speak as a teammate, start the
  message with their name (for example "Aisha here:"), so the agents record
  the right person.

Rehearse all scenes twice before recording.

---

## Scene 0: Hook (10 s)
> "Small teams don't have a project manager, so developers end up chasing
> each other for updates. Foreman puts four AI agents in your team chat,
> connected through Switch, and the humans stay in control."

## Scene 1: New work, PM to Assigner handoff (50 s)
**You type:**
```
@foreman-pm We need Google OAuth login by Friday (2026-11-13).
```
**Expected:**
- The PM adds 3–4 unassigned tasks (T-4 onward), then posts
  "@foreman-assigner please propose owners…".
- The Assigner replies with a table of owners and reasons.
- On the dashboard, the cards appear under **Proposed**, then get owners.

**You type:**
```
@foreman-pm approve
```
**Expected:** the cards move to **To do**, and the activity feed shows
"Approved by human."

## Scene 2: Progress and a blocker, Tracker to PM handoff (45 s)
**You type:**
```
@foreman-tracker Aisha here: backend OAuth is done.
```
```
@foreman-tracker Ben here: frontend login is blocked, the Google callback URL isn't configured yet.
```
**Expected:**
- The cards move to **Done** and **Blocked**.
- The health badge turns **At risk**.
- The Tracker hands off with "@foreman-pm blocker on T-x…", and the PM
  points to the existing config task and @mentions Diego.

## Scene 3: The manager question (35 s), the hero moment
**You type:**
```
@foreman-pm What is everyone working on, and what is blocking our release?
```
**Expected:** the health verdict, progress, the blocker with its owner and
next step, and one line per person.

## Scene 4: Standup, PM to Reporter handoff (30 s)
**You type:**
```
@foreman-pm send today's standup to the team.
```
**Expected:**
- The PM hands off with "@foreman-reporter please write the daily report."
- The Reporter posts a summary and saves `reports/<date>-daily.md`.
- The report appears in the dashboard's **Latest report** panel.

## Scene 5: Close (10 s)
> "Four agents, one room, and every decision approved by a human. Every
> change is logged, the board is a plain file in the repo, and it all runs
> on Switch with Codex, or any agent you choose. That's Foreman."

---

## If something goes wrong while recording
- **An agent doesn't answer:** check that Switch Console is open and the
  agent is green, then send the message again.
- **The Assigner doesn't reply:** type `@foreman-pm assign them yourself`.
  The PM falls back to assigning the tasks.
- **The board looks wrong:** run `python3 scripts/board.py reset` and start
  again from Scene 1.
