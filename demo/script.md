# Demo script: target 2–3 minutes

**Before recording:**
- Run `python3 scripts/board.py reset`.
- Make sure both agents show as available in `project-room`.
- Use one human Mattermost account. When you speak as a teammate, start the
  message with their name (for example "Aisha here:"), so the agents record
  the right person. If teammates are with you, use their real accounts.

Rehearse all 4 scenes twice before recording.

---

## Scene 0: Hook (10 s, voice over the Mattermost window)
> "Small teams don't have a project manager, so developers end up chasing
> each other for updates. Foreman puts an AI PM and an AI tracker in your team
> chat, connected through Switch, and the humans stay in control."

## Scene 1: New work comes in (45 s)
**You type:**
```
@foreman-pm We need Google OAuth login by Friday (2026-11-13).
```
**Expected:** the PM proposes 3–4 tasks, for example backend OAuth → Aisha,
frontend login button → Ben, callback URL and secrets config → Diego, and
OAuth testing → Chen. Each comes with a reason and the approve prompt.

**You type:**
```
@foreman-pm approve
```
**Expected:** the tasks move to `todo`, followed by "Board updated: ...".

## Scene 2: Progress and a blocker, agent to agent (45 s)
**You type:**
```
@foreman-tracker Aisha here: backend OAuth is done.
```
**Expected:** the backend task moves to `done`.

**You type:**
```
@foreman-tracker Ben here: frontend login is blocked, the Google callback URL isn't configured yet.
```
**Expected:** the Tracker marks the task blocked, then hands it off with
"@foreman-pm blocker on T-x ...". The PM then proposes an unblock (Diego,
callback config).

This scene shows the agents talking to each other through Switch, so point
it out in the voice-over.

## Scene 3: The manager question (40 s), the hero moment
**You type:**
```
@foreman-pm What is everyone working on, and what is blocking our release?
```
**Expected:** the PM replies with progress x/y, the blocker with its owner
and next step, the overdue list, one line per person, and an
**On track / At risk** verdict.

Optionally, type `@foreman-pm show the board` to finish on the Kanban view.

## Scene 4: Close (10 s)
> "Every change went through a human approval, the board is a plain JSON file
> in the repo, and it all runs on Switch with Codex, or any agent you choose.
> That's Foreman."

---

## If something goes wrong while recording
- **An agent doesn't answer:** check that Switch Console is open and the
  agent session is running, then send the message again.
- **The board looks wrong:** run `python3 scripts/board.py reset` and start
  again from Scene 1.
- **You hit usage limits:** wait for the window to reset, or cut Scene 2's
  second message.
