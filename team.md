# Team and assignment rules (fictional demo team)

The people themselves (name, email, role, skills, availability) live in
`people.json`. See them with `python3 scripts/board.py team`, or
`team -p KEY` for one project. New people are added with `board.py add-person`.
People work across several projects; each project lists its own team, and
only team members can own its tasks. `board.py load` counts open tasks
(todo + in_progress + blocked) across **all** projects and flags anyone with
4 or more as overloaded.

Demo team: **Akshith** (engineering manager), **Aisha** (backend), **Felix**
(frontend), **Chen** (QA) and **Diego** (full-stack/DevOps, mornings only this
week).

## Assignment rules

1. Match the task's main skill to the person's skills first.
2. Break ties by lowest total load across projects. Avoid anyone overloaded.
3. Respect availability: don't give Diego anything due the same afternoon.
4. Config / environment / callback-URL / secrets work goes to Diego.
5. Every feature gets a testing task owned by Chen.
