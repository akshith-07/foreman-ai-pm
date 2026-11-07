# Team — Invoicely (fictional demo team)

The PM agent reads this file to decide who should own a task.
`Load` = number of open tasks (todo + in_progress + blocked) the person owns today; the PM recalculates it from `tasks.json` and treats this table's value only as a fallback.

| Handle | Name  | Role                 | Skills                                         | Availability            |
|--------|-------|----------------------|------------------------------------------------|-------------------------|
| aisha  | Aisha | Backend engineer     | Node.js, auth, OAuth/OIDC, Postgres, APIs      | Full time               |
| ben    | Ben   | Frontend engineer    | React, TypeScript, UI, login flows, perf (web) | Full time               |
| chen   | Chen  | QA engineer          | Test plans, Playwright, regression, security   | Full time               |
| diego  | Diego | Full-stack / DevOps  | CI/CD, cloud config, env vars, PDFs, caching   | Mornings only this week |

## Assignment rules

1. Match the task's main skill to the person's skills first.
2. Break ties by lowest current load.
3. Respect availability: don't give Diego anything due the same afternoon.
4. Config / environment / callback-URL / secrets work goes to Diego.
5. Every feature gets a testing task owned by Chen.
