# We put an AI project manager in our team chat, built on Switch

*By Akshith and Felix · Flip the Switch Hackathon, Track 01: Best Business Workflow*

Small teams rarely have a project manager. Someone still has to break down
work, decide who owns what, chase updates, notice blockers and write the
status report, so it ends up being a developer, in between writing code.

For the Flip the Switch hackathon we built **Foreman**: four AI agents that
live in our team chat and do that coordination with us, through
[Switch](https://docs.switchagents.ai). In one day it went from an idea to a
working multi-project setup, with a live dashboard and real email
notifications.

This post covers how it works, how we set up Switch, and the problems we hit
along the way. If you're trying Switch for the first time, the last section
might save you an hour.

**Repo:** https://github.com/akshith-07/foreman-ai-pm · **Demo:** *(video link)*

---

## The idea: one room, four specialists, humans in charge

We started with a bigger plan (four agents plus a full project-management
web app) and cut it down hard. The rule we settled on: **every change
happens in the chat room, and a human approves every assignment.**

| Agent | What it does |
|---|---|
| `@foreman-pm` | Creates projects, breaks requests into tasks, applies human decisions, answers "what's blocking the release?" |
| `@foreman-assigner` | Picks an owner for each task from skills and workload across all projects |
| `@foreman-tracker` | Records progress and blockers, and escalates blockers to the PM |
| `@foreman-reporter` | Writes standups, weekly and portfolio reports |

A typical exchange in the room goes like this:

1. **Akshith:** `@foreman-pm Invoicely needs Google OAuth login by Friday.`
2. The PM creates four tasks and hands off: `@foreman-assigner please propose owners for INV-4…INV-7.`
3. The Assigner replies with an owner and a reason for each task ("Felix,
   React and login flows, 3 open tasks across projects").
4. **Akshith:** `@foreman-pm approve`. Each owner gets an email.
5. **Felix,** from his own laptop: `@foreman-tracker I'm blocked, the Google callback URL isn't configured.`
6. The Tracker marks it blocked and hands it to the PM, which finds the
   existing config task (owned by Diego) instead of creating a duplicate.
7. **Akshith:** `@foreman-pm How are all our projects doing, and is anyone overloaded?`

The handoffs between agents are the part that needs Switch. Without it,
this would be four chatbots in four terminals that can't see each other or
the team.

## How Switch fits in

Here's what we actually used:

- **Switch Console** → **Get started → On this computer**. This runs a
  local Switch server plus a **bundled Mattermost**, so we didn't need a
  Slack workspace.
- **Four agents**, all on **Codex** (the ChatGPT-signed-in CLI), each
  registered under **Your Agents → Add agent** with its **Directory** set to
  our repo.
- **One room** (`foreman-demo`) containing the four agents and the humans,
  plus room instructions that every agent reads when it joins.
- **Who can talk to your agent → Anyone**, so Felix, whose chat account
  isn't linked to a Switch user, could instruct the agents.

Three Switch features shaped the design:

1. **Agents only respond when @mentioned.** That's a built-in way to prevent
   loops. We added one rule on top: *only @mention another agent when you're
   handing it work, never to say thanks.*
2. **Each agent has a fixed working directory.** We keep all the behavior in
   the repo. In Switch, each agent's instructions are just two lines: *"read
   `AGENTS.md` and `agents/pm.md` and follow them."* That meant we changed
   the prompts many times during the day without retyping anything into
   Switch.
3. **Codex reads `AGENTS.md` automatically.** That's where our shared rules
   live: the roster, who hands off to whom, and the hard limits.

## The agents don't edit files; they call a tool

The most important design decision: **agents never hand-edit the board.**
Each project is a JSON file (`projects/inv.json`), and the only way to
change one is `scripts/board.py`, a small CLI that uses only the Python
standard library:

```bash
python3 scripts/board.py add -p INV --title "Google OAuth backend" --epic Auth --priority high --due 2026-11-13 --by foreman-pm
python3 scripts/board.py assign INV-4 aisha --reason "OAuth skills, lowest load" --by foreman-assigner
python3 scripts/board.py approve INV-4 --by akshith
python3 scripts/board.py block INV-5 "callback URL missing" --by felix
python3 scripts/board.py portfolio
```

The CLI enforces rules the prompt only asks for:

- Tasks start as `proposed`, and can't be started until a human approves them.
- A task can't be approved without an owner.
- Only members of a project's team can own its tasks.
- Nobody can be removed from a team while they still own open work.
- Every change records who made it and when.

The prompt says "only humans approve", and the code makes sure of it. On
the first test run, the PM created a duplicate task. We fixed it twice: a
"check before you add" rule in `AGENTS.md`, and a `cancel` command for
proposed tasks.

## Emails the model can't invent

We wanted owners emailed when their task is approved, and the manager when
work is done. The key choice: **emails are triggered by board events in
code, never written by the model.**

| Event | Who's emailed |
|---|---|
| A human approves a task | the owner |
| A task is marked done | the manager (owner in cc) |
| The last task in a project is done (the project becomes **Completed**) | the manager and the whole team |
| Someone joins a project | the new member |

By default every email is saved as a `.eml` file in `outbox/`. With a
`.env` file, it's sent over SMTP. For the demo we used a local
[Mailpit](https://mailpit.axllent.org) inbox, so the emails are real but
nothing leaves the laptop.

## The dashboard

`scripts/dashboard.py` serves a small HTML, CSS and JS page (no framework,
no build step) that polls the boards every two seconds. It has:

- an **All projects** view with a health card per project and workload
  across projects;
- a per-project **Kanban board**, where cards slide to their new column when
  an agent moves them;
- an **Agents panel** that lights up whichever agent just acted;
- a **Notifications** panel showing each email and whether it was sent.

The dashboard is read-only. If you want to change something, you say it in
the room.

## What broke, and how we fixed it

This is the part we'd have wanted to read before starting.

**1. "The local command/tool host is unavailable."**
Our first agent reply couldn't run any shell command. Codex runs commands
through a helper binary, `codex-code-mode-host`. Ours had been moved to the
Trash by accident, and once restored, macOS Gatekeeper blocked it ("Apple
could not verify…").
**Fix:** System Settings → Privacy & Security → **Open Anyway**. Then
**fully quit and reopen Switch Console.** Switch keeps long-running Codex
processes, and those stay broken until they restart. Testing with
`codex exec` in a terminal is a quick way to tell a Codex problem from a
Switch problem.

**2. "I only take instructions from my owner."**
Felix's first message was refused. A new agent defaults to **Me and my
agents**, and Felix's Mattermost account wasn't linked to a Switch user.
**Fix:** set **Who can talk to your agent** to **Anyone** on each agent.
According to the docs, that includes chat users without a linked account.

**3. Emails failed with "Operation not permitted."**
The agents run in Codex's sandbox, which has no network access, even to
`127.0.0.1`. That's a good default, so we kept it.
**Fix:** the agents only *queue* emails, and the dashboard server (outside
the sandbox) runs a small **mail relay** that sends queued emails every
three seconds. Safety stayed intact and the emails still go out.

**4. Teammate on another laptop.**
The bundled Mattermost only listens on `localhost`.
**Fix:** [Tailscale](https://tailscale.com) and one command,
`tailscale serve --bg <mattermost-port>`. Felix got a private HTTPS address
that only our Tailscale network can reach. (Use `serve`, not `funnel`, which
makes it public.)

## What we learned

- **The model is the easy part.** Most of the work was in tool boundaries,
  approvals, state and the audit trail.
- **Enforce rules in code, not only in prompts.**
- **Keep prompts in the repo** and point the agents at them. It made fast
  changes painless.
- **Most agent failures were environmental:** a quarantined binary, a
  sandbox without network, a stale session. Reproduce the problem outside
  the platform first.
- **Start with the smallest working version, then grow it.** We went from 2
  agents to 4, and from one project to many, only after each step worked
  end to end.

## Try it

Everything is in the repo, including a 20-minute setup guide and a full
test plan: https://github.com/akshith-07/foreman-ai-pm

Thanks to Switch, WeMakeDevs and DevTools Academy for the hackathon. This
was a fun way to learn how much coordination agents can take on when they
share a room with the team.
