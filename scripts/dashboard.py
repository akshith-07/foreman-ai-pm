#!/usr/bin/env python3
"""Foreman live dashboard (read-only).

  python3 scripts/dashboard.py            -> http://127.0.0.1:8787
  python3 scripts/dashboard.py --port 9000

It only reads tasks.json and reports/. All changes still happen in the
Switch room, where the agents run scripts/board.py. Standard library only.
"""
import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import board as B  # noqa: E402


def state() -> dict:
    data = B.load()
    return {
        "project": data["project"],
        "release": data["release"],
        "tasks": data["tasks"],
        "team": B.TEAM,
        "load": B.loads(data),
        "health": B.health(data),
        "activity": B.activity(data)[:40],
        "report": B.latest_report(),
        "generated": B.stamp(),
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/api/state"):
            try:
                self._send(200, json.dumps(state()).encode(), "application/json")
            except Exception as e:  # board mid-write or invalid: tell the page, don't crash
                self._send(503, json.dumps({"error": str(e)}).encode(), "application/json")
        elif self.path in ("/", "/index.html"):
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        else:
            self._send(404, b"not found", "text/plain")

    def log_message(self, *_):
        pass


PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Foreman Dashboard</title>
<style>
:root{--bg:#f6f7f9;--panel:#fff;--line:#e3e6eb;--text:#1b1f24;--muted:#65707d;--chip:#eef1f5;
--ok:#1f8a4c;--warn:#b26b00;--bad:#c8323b;--accent:#5b4bdb;--flash:#fff4c2}
@media (prefers-color-scheme:dark){:root{--bg:#0f1114;--panel:#171a1f;--line:#262b33;--text:#e7eaee;
--muted:#8d97a3;--chip:#20252d;--ok:#3ccf7d;--warn:#f0a63a;--bad:#ff5d66;--accent:#9d8cff;--flash:#3a3317}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);
font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif}
header{display:flex;flex-wrap:wrap;gap:16px;align-items:center;justify-content:space-between;
padding:18px 24px;border-bottom:1px solid var(--line);background:var(--panel)}
h1{font-size:20px;margin:0}.sub{color:var(--muted);font-size:13px}
.badge{padding:6px 12px;border-radius:999px;font-weight:700;font-size:13px;color:#fff}
.b-ok{background:var(--ok)}.b-warn{background:var(--warn)}.b-bad{background:var(--bad)}
.prog{width:220px}.bar{height:8px;border-radius:9px;background:var(--chip);overflow:hidden;margin-top:6px}
.bar>i{display:block;height:100%;background:var(--accent);transition:width .6s}
main{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:16px;padding:16px 24px}
@media (max-width:1100px){main{grid-template-columns:1fr}}
.board{display:grid;grid-template-columns:repeat(5,minmax(150px,1fr));gap:10px;overflow-x:auto}
.col{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px;min-height:260px}
.col h3{margin:0 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);
display:flex;justify-content:space-between}
.card{border:1px solid var(--line);border-radius:8px;padding:8px 9px;margin-bottom:8px;background:var(--bg);
transition:background 1.2s}
.card.flash{background:var(--flash)}
.card .id{font-weight:700;font-size:12px;color:var(--accent)}.card .t{margin:2px 0 6px}
.meta{display:flex;flex-wrap:wrap;gap:4px}.chip{background:var(--chip);border-radius:5px;padding:1px 6px;
font-size:11.5px;color:var(--muted)}.chip.high{color:var(--bad)}.chip.late{background:var(--bad);color:#fff}
.blk{margin-top:6px;font-size:12px;color:var(--bad)}
.col.blocked{border-color:color-mix(in srgb,var(--bad) 45%,var(--line))}
aside{display:flex;flex-direction:column;gap:16px;min-width:0}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.panel h2{font-size:13px;margin:0 0 10px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
.who{display:grid;grid-template-columns:60px 1fr 22px;gap:8px;align-items:center;margin:6px 0}
.who .bar{margin:0}.feed{max-height:330px;overflow:auto}
.ev{padding:6px 0;border-bottom:1px solid var(--line);font-size:12.5px}.ev:last-child{border:0}
.ev .by{font-weight:600}.ev .when{color:var(--muted);font-size:11.5px}
.agent{color:var(--accent)}.empty{color:var(--muted);font-size:13px}
.report{white-space:pre-wrap;font:12.5px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;max-height:260px;overflow:auto}
.live{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--muted)}
.dot{width:8px;height:8px;border-radius:50%;background:var(--ok)}.dot.off{background:var(--bad)}
</style></head><body>
<header>
  <div><h1 id="title">Foreman</h1><div class="sub" id="rel"></div></div>
  <div class="prog"><div class="sub" id="progtxt"></div><div class="bar"><i id="progbar" style="width:0"></i></div></div>
  <div style="display:flex;gap:14px;align-items:center">
    <span class="live"><span class="dot" id="dot"></span><span id="upd">connecting…</span></span>
    <span class="badge" id="health">…</span></div>
</header>
<main>
  <section class="board" id="board"></section>
  <aside>
    <div class="panel"><h2>Blockers &amp; risks</h2><div id="risks"></div></div>
    <div class="panel"><h2>Workload (open tasks)</h2><div id="load"></div></div>
    <div class="panel"><h2>Live activity</h2><div class="feed" id="feed"></div></div>
    <div class="panel"><h2 id="rtitle">Latest report</h2><div class="report" id="report"></div></div>
  </aside>
</main>
<script>
const COLS=[["proposed","Proposed"],["todo","To do"],["in_progress","In progress"],["blocked","Blocked"],["done","Done"]];
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let prev={};
function card(t,today){
  const late=t.status!=="done"&&t.status!=="proposed"&&t.due<today;
  return `<div class="card" data-id="${esc(t.id)}"><div class="id">${esc(t.id)} · ${esc(t.epic)}</div>
  <div class="t">${esc(t.title)}</div><div class="meta">
  <span class="chip">${t.owner?"@"+esc(t.owner):"unassigned"}</span>
  <span class="chip ${t.priority==="high"?"high":""}">${esc(t.priority)}</span>
  <span class="chip ${late?"late":""}">due ${esc(t.due.slice(5))}</span></div>
  ${t.blocker?`<div class="blk">⛔ ${esc(t.blocker)}</div>`:""}</div>`;
}
function render(s){
  const today=s.generated.slice(0,10), h=s.health;
  document.getElementById("title").textContent=`Foreman · ${s.project}`;
  document.getElementById("rel").textContent=`Release ${s.release.name} · due ${s.release.due} · ${h.days_left} days left`;
  document.getElementById("progtxt").textContent=`${h.done}/${h.total} approved tasks done`;
  document.getElementById("progbar").style.width=(h.total?100*h.done/h.total:0)+"%";
  const hb=document.getElementById("health");hb.textContent=h.verdict;
  hb.className="badge "+(h.verdict==="On track"?"b-ok":h.verdict==="At risk"?"b-warn":"b-bad");
  document.getElementById("board").innerHTML=COLS.map(([k,n])=>{
    const ts=s.tasks.filter(t=>t.status===k);
    return `<div class="col ${k}"><h3><span>${n}</span><span>${ts.length}</span></h3>${ts.map(t=>card(t,today)).join("")||'<div class="empty">—</div>'}</div>`;
  }).join("");
  const now={};s.tasks.forEach(t=>{now[t.id]=JSON.stringify(t);
    if(prev[t.id]!==undefined&&prev[t.id]!==now[t.id]||Object.keys(prev).length&&prev[t.id]===undefined){
      const el=document.querySelector(`.card[data-id="${CSS.escape(t.id)}"]`);
      if(el){el.classList.add("flash");setTimeout(()=>el.classList.remove("flash"),1600);}}});
  prev=now;
  document.getElementById("risks").innerHTML=h.reasons.length?h.reasons.map(r=>`<div class="ev">${esc(r)}</div>`).join(""):'<div class="empty">No blockers or overdue work 🎉</div>';
  const max=Math.max(3,...Object.values(s.load));
  document.getElementById("load").innerHTML=s.team.map(m=>`<div class="who"><span>@${esc(m)}</span>
    <div class="bar"><i style="width:${100*s.load[m]/max}%"></i></div><b>${s.load[m]}</b></div>`).join("");
  document.getElementById("feed").innerHTML=s.activity.map(a=>`<div class="ev">
    <span class="by ${a.by.startsWith("foreman")?"agent":""}">${esc(a.by)}</span> · <b>${esc(a.task)}</b> ${esc(a.text)}
    <div class="when">${esc(a.at)} · ${esc(a.title)}</div></div>`).join("")||'<div class="empty">No activity yet</div>';
  document.getElementById("rtitle").textContent=s.report?`Latest report · ${s.report.name}`:"Latest report";
  document.getElementById("report").textContent=s.report?s.report.text:"No report yet. Ask @foreman-reporter in the room.";
}
async function tick(){
  try{const r=await fetch("/api/state",{cache:"no-store"});if(!r.ok)throw 0;render(await r.json());
    document.getElementById("dot").className="dot";document.getElementById("upd").textContent="live";}
  catch(e){document.getElementById("dot").className="dot off";document.getElementById("upd").textContent="reconnecting…";}
}
tick();setInterval(tick,2000);
</script></body></html>"""


def main():
    p = argparse.ArgumentParser(description="Foreman live dashboard (read-only)")
    p.add_argument("--port", type=int, default=8787)
    a = p.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"Foreman dashboard: http://127.0.0.1:{a.port}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
