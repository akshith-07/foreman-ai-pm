"""Foreman email notifications.

Every notification is written to outbox/ as a real .eml file and logged in
outbox/log.jsonl (the dashboard shows this log). Nothing is sent unless you
opt in by setting an SMTP server:

  FOREMAN_SMTP_HOST=127.0.0.1 FOREMAN_SMTP_PORT=1025      # e.g. a local Mailpit
  FOREMAN_SMTP_USER / FOREMAN_SMTP_PASSWORD               # optional, for real servers
  FOREMAN_SMTP_TLS=1                                      # optional STARTTLS
  FOREMAN_MAIL_FROM="Foreman <foreman@invoicely.example>" # optional

You can also put these in a `.env` file in the repo root (it's git-ignored).
Standard library only.
"""
import json
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTBOX = ROOT / "outbox"
LOG = OUTBOX / "log.jsonl"


def _env() -> dict:
    env = dict(os.environ)
    dotenv = ROOT / ".env"
    if dotenv.exists():
        for line in dotenv.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return env


def mode() -> str:
    return "smtp" if _env().get("FOREMAN_SMTP_HOST") else "outbox"


def send(to: list, subject: str, body: str, *, event: str, project: str, task: str | None, at: str, cc: list | None = None) -> dict:
    """Write the email to the outbox, send it if SMTP is configured, and log it."""
    env = _env()
    to = sorted({a for a in to if a})
    cc = sorted({a for a in (cc or []) if a and a not in to})
    if not to:
        return {"status": "skipped", "reason": "no recipients"}

    msg = EmailMessage()
    msg["From"] = env.get("FOREMAN_MAIL_FROM", "Foreman <foreman@invoicely.example>")
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="foreman.local")
    msg["X-Foreman-Event"] = event
    msg.set_content(body + "\n\n— Foreman, your AI project manager (sent from #project-room via Switch)\n")

    OUTBOX.mkdir(exist_ok=True)
    n = sum(1 for _ in OUTBOX.glob("*.eml")) + 1
    eml = OUTBOX / f"{at.replace(' ', 'T').replace(':', '')}-{n:03d}-{event}.eml"
    eml.write_bytes(bytes(msg))

    status, error = "queued", None
    if env.get("FOREMAN_SMTP_HOST"):
        try:
            _smtp_send(env, msg)
            status = "sent"
        except PermissionError:
            # Agents run in a sandbox without network access. That's intended:
            # the email stays queued and the dashboard's mail relay
            # (deliver_pending, outside the sandbox) sends it within seconds.
            status = "queued"
        except Exception as e:  # never break a board update because mail failed
            status, error = "failed", f"{type(e).__name__}: {e}"

    entry = {"at": at, "event": event, "project": project, "task": task, "to": to, "cc": cc,
             "subject": subject, "status": status, "file": eml.name}
    if error:
        entry["error"] = error
    with LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def _smtp_send(env: dict, msg) -> None:
    port = int(env.get("FOREMAN_SMTP_PORT", "25"))
    with smtplib.SMTP(env["FOREMAN_SMTP_HOST"], port, timeout=8) as s:
        if env.get("FOREMAN_SMTP_TLS") == "1":
            s.starttls(context=ssl.create_default_context())
        if env.get("FOREMAN_SMTP_USER"):
            s.login(env["FOREMAN_SMTP_USER"], env.get("FOREMAN_SMTP_PASSWORD", ""))
        s.send_message(msg)


def _rows() -> list:
    """Log entries with later status updates folded in (the log is append-only)."""
    if not LOG.exists():
        return []
    rows, by_file = [], {}
    for line in LOG.read_text().splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if "update" in d:  # {"update": <file>, "status": ..., "error": ...}
            r = by_file.get(d["update"])
            if r:
                r["status"] = d["status"]
                if d["status"] == "failed":
                    r["tries"] = r.get("tries", 0) + 1
                r.pop("error", None)
                if d.get("error"):
                    r["error"] = d["error"]
        else:
            rows.append(d)
            by_file[d["file"]] = d
    return rows


def deliver_pending(max_tries: int = 5) -> int:
    """Send queued (or failed) emails. Runs outside the agent sandbox, e.g. in the dashboard."""
    env = _env()
    if not env.get("FOREMAN_SMTP_HOST"):
        return 0
    from email import policy
    from email.parser import BytesParser
    sent = 0
    for r in _rows():
        if r["status"] not in ("queued", "failed") or r.get("tries", 0) >= max_tries:
            continue
        eml = OUTBOX / r["file"]
        if not eml.exists():
            continue
        try:
            msg = BytesParser(policy=policy.default).parsebytes(eml.read_bytes())
            _smtp_send(env, msg)
            update = {"update": r["file"], "status": "sent"}
            sent += 1
        except Exception as e:
            update = {"update": r["file"], "status": "failed", "error": f"{type(e).__name__}: {e}"}
        with LOG.open("a") as f:
            f.write(json.dumps(update) + "\n")
    return sent


def recent(limit: int = 30, project: str | None = None) -> list:
    rows = _rows()
    if project:
        rows = [r for r in rows if r.get("project") == project]
    return list(reversed(rows))[:limit]


def clear() -> None:
    if OUTBOX.exists():
        for f in OUTBOX.iterdir():
            if f.is_file():
                f.unlink()
