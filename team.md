# Team (fictional demo team)

The agents read this file to decide who should own a task. People work across
several projects; each project's board lists which of them are on its team.
For current workload, run `python3 scripts/board.py load`, which counts open
tasks (todo + in_progress + blocked) across **all** projects and flags anyone
with 4 or more as overloaded.

| Handle | Name  | Role                 | Skills                                         | Availability            |
|--------|-------|----------------------|------------------------------------------------|-------------------------|
| aisha  | Aisha | Backend engineer     | Node.js, auth, OAuth/OIDC, Postgres, APIs      | Full time               |
| ben    | Ben   | Frontend engineer    | React, TypeScript, UI, login flows, perf (web) | Full time               |
| chen   | Chen  | QA engineer          | Test plans, Playwright, regression, security   | Full time               |
| diego  | Diego | Full-stack / DevOps  | CI/CD, cloud config, env vars, PDFs, caching   | Mornings only this week |

## Assignment rules

1. Match the task's main skill to the person's skills first.
2. Break ties by lowest total load across projects. Avoid anyone overloaded.
3. Respect availability: don't give Diego anything due the same afternoon.
4. Config / environment / callback-URL / secrets work goes to Diego.
5. Every feature gets a testing task owned by Chen.
